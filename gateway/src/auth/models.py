from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List

class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    
    model_config = ConfigDict(from_attributes=True)

class TokenData(BaseModel):
    """Token payload model."""
    sub: str  # subject (user id)
    scopes: List[str] = []
    exp: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class User(BaseModel):
    """User model."""
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    disabled: bool = False
    scopes: List[str] = []
    
    model_config = ConfigDict(from_attributes=True)

class UserInDB(User):
    """User model with hashed password."""
    hashed_password: str
    
    model_config = ConfigDict(from_attributes=True)