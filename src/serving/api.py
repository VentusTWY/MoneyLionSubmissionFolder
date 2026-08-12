"""ASGI entry point configured through environment variables."""

import os

from src.serving.predictor import create_app

# Step 1: resolve the registry URI while preserving the legacy environment name.
registry_uri = os.environ.get(
    "MODEL_REGISTRY_URI",
    os.environ.get("MODEL_REGISTRY", "file://registry"),
)

# Step 2: resolve the maximum number of applications accepted per batch request.
batch_limit = int(os.environ.get("PREDICTION_BATCH_LIMIT", "100"))

# Step 3: construct the ASGI application once when the server process starts.
app = create_app(
    registry_uri,
    batch_limit,
)
