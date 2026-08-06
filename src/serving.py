"""Framework-independent prediction plus a thin FastAPI interface."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

import joblib
import pandas as pd
from pydantic import BaseModel, ConfigDict

from src.features import transform_features
from src.mlops import LocalRegistry, verify_bundle


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    applicationDate: str


class LoanRiskPredictor:
    def __init__(self, version_dir: str | Path):
        self.version_dir = Path(version_dir)
        self.manifest = verify_bundle(self.version_dir)
        self.model = joblib.load(self.version_dir / "model.joblib")
        self.schema = json.loads((self.version_dir / "feature_schema.json").read_text())
        self.contract = self.manifest["feature_contract"]
        self.version = self.manifest["version"]
        self.review_threshold = float(self.manifest.get("review_threshold", self.manifest["decision_threshold"]))
        self.reject_threshold = float(self.manifest.get("reject_threshold", self.review_threshold))

    @classmethod
    def from_registry(cls, registry_root: str | Path) -> "LoanRiskPredictor":
        return cls(LocalRegistry(registry_root).champion_dir())

    def predict(self, raw: dict) -> dict:
        if "applicationDate" not in raw:
            raise ValueError("Missing required field: applicationDate")
        row = dict(raw)
        row.setdefault("has_clarity_report", any(
            key.startswith(".underwritingdata") and value is not None
            for key, value in row.items()
        ))
        matrix = transform_features(pd.DataFrame([row]), self.contract, self.schema)
        probability = float(self.model.predict_proba(matrix)[:, 1][0])
        if probability < 0.40:
            band = "low"
        elif probability < 0.70:
            band = "medium"
        else:
            band = "high"
        if probability >= self.reject_threshold:
            decision = "reject"
        elif probability >= self.review_threshold:
            decision = "review"
        else:
            decision = "pass"
        return {
            "adverse_probability": probability,
            "risk_band": band,
            "decision": decision,
            "model_version": self.version,
            "feature_contract_version": self.contract["name"],
        }


class ServiceMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = self.failures = 0
        self.latency_seconds = 0.0
        self.bands = {"low": 0, "medium": 0, "high": 0}

    def observe(self, elapsed: float, result: dict | None):
        with self.lock:
            self.requests += 1
            self.latency_seconds += elapsed
            if result is None:
                self.failures += 1
            else:
                self.bands[result["risk_band"]] += 1

    def prometheus(self, version: str) -> str:
        lines = [
            f'ml_prediction_requests_total{{model_version="{version}"}} {self.requests}',
            f'ml_prediction_failures_total{{model_version="{version}"}} {self.failures}',
            f'ml_prediction_latency_seconds_sum{{model_version="{version}"}} {self.latency_seconds}',
        ]
        lines.extend(
            f'ml_prediction_score_band_total{{model_version="{version}",band="{band}"}} {count}'
            for band, count in self.bands.items()
        )
        return "\n".join(lines) + "\n"


def create_app(registry_root: str | Path = "registry", batch_limit: int = 100):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import PlainTextResponse
    except ImportError as exc:  # pragma: no cover - dependency error is actionable
        raise RuntimeError("Install FastAPI dependencies from requirements.txt") from exc

    app = FastAPI(title="Loan Risk API", version="1")
    ui_origins = [
        origin.strip()
        for origin in os.environ.get("UI_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ui_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    predictor = LoanRiskPredictor.from_registry(registry_root)
    metrics = ServiceMetrics()

    def execute(payload: dict):
        started = time.perf_counter()
        result = None
        try:
            result = predictor.predict(payload)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            metrics.observe(time.perf_counter() - started, result)

    @app.post("/v1/predict")
    async def predict(payload: PredictionRequest):
        result = execute(payload.model_dump())
        result["request_id"] = str(uuid.uuid4())
        return result

    @app.post("/v1/predict/batch")
    async def predict_batch(payloads: list[PredictionRequest]):
        if len(payloads) > batch_limit:
            raise HTTPException(status_code=413, detail=f"Batch limit is {batch_limit}")
        return [execute(payload.model_dump()) for payload in payloads]

    @app.get("/v1/model")
    def model_info():
        return {
            "model_version": predictor.version,
            "feature_contract_version": predictor.contract["name"],
            "decision_threshold": predictor.review_threshold,
            "review_threshold": predictor.review_threshold,
            "reject_threshold": predictor.reject_threshold,
        }

    @app.get("/health/live")
    def live():
        return {"status": "live"}

    @app.get("/health/ready")
    def ready():
        return {"status": "ready", "model_version": predictor.version}

    @app.get("/metrics", response_class=PlainTextResponse)
    def service_metrics():
        return metrics.prometheus(predictor.version)

    return app
