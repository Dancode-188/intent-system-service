from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Security, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
import httpx
import logging
from datetime import timedelta

from .config import settings
from .middleware import setup_middleware
from .auth.security import create_access_token, verify_password, MOCK_USERS_DB
from .auth.dependencies import get_current_active_user
from .auth.models import Token, User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    app.state.http_client = httpx.AsyncClient()
    logger.info("API Gateway started successfully")
    
    yield
    
    # Shutdown
    await app.state.http_client.aclose()
    logger.info("API Gateway shut down successfully")

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    lifespan=lifespan
)

# Setup middleware
setup_middleware(app)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}

@app.post(f"{settings.API_V1_PREFIX}/auth/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Token:
    """OAuth2 compatible token login."""
    user_dict = MOCK_USERS_DB.get(form_data.username)
    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user_dict["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user_dict["username"],
            "scopes": form_data.scopes or []
        },
        expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token)

@app.get(f"{settings.API_V1_PREFIX}/users/me", response_model=User)
async def read_users_me(
    current_user: User = Security(get_current_active_user, scopes=["read"])
) -> User:
    """Get current user information."""
    return current_user

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )