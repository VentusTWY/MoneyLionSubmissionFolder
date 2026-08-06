"""ASGI entry point configured through environment variables."""

import os

from src.serving import create_app

app = create_app(
    os.environ.get(
        "MODEL_REGISTRY_URI",
        os.environ.get("MODEL_REGISTRY", "file://registry"),
    ),
    int(os.environ.get("PREDICTION_BATCH_LIMIT", "100")),
)
