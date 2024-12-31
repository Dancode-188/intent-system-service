-- Ensure the TimescaleDB extension exists
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

DO $$
BEGIN
    -- Create predictions table if it doesn't exist
    CREATE TABLE IF NOT EXISTS predictions (
        prediction_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        context_id TEXT NOT NULL,
        prediction_type TEXT NOT NULL,
        predictions JSONB NOT NULL,
        confidence FLOAT NOT NULL,
        metadata JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    
    -- Create prediction metrics table if it doesn't exist
    CREATE TABLE IF NOT EXISTS prediction_metrics (
        time TIMESTAMPTZ NOT NULL,
        prediction_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        metric_value FLOAT NOT NULL,
        tags JSONB,
        FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
    );

    -- Convert to hypertable if not already
    PERFORM create_hypertable('prediction_metrics', 'time', if_not_exists => TRUE);

EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Error creating tables: %', SQLERRM;
END $$;

-- Create indexes if they don't exist
DO $$
BEGIN
    CREATE INDEX IF NOT EXISTS idx_predictions_user_id ON predictions(user_id);
    CREATE INDEX IF NOT EXISTS idx_predictions_context_id ON predictions(context_id);
    CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_metrics_prediction_id ON prediction_metrics(prediction_id);
    CREATE INDEX IF NOT EXISTS idx_metrics_user_id ON prediction_metrics(user_id);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Error creating indexes: %', SQLERRM;
END $$;