"""Framework-independent prediction plus a thin FastAPI interface."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from hmac import compare_digest
from pathlib import Path

import joblib
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from src.features import transform_features
from src.mlops import ModelRegistry, create_registry, verify_bundle


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    applicationDate: str


class ModelChangeRequest(BaseModel):
    """Accountability data required for a privileged model change."""

    actor: str = Field(min_length=2, max_length=120)
    reason: str = Field(min_length=5, max_length=500)


class LoanRiskPredictor:
    def __init__(self, version_dir: str | Path):
        # Step 1: resolve and verify the immutable champion bundle.
        self.version_dir = Path(version_dir)
        self.manifest = verify_bundle(self.version_dir)

        # Step 2: load the trained estimator and its saved feature schema.
        self.model = joblib.load(self.version_dir / "model.joblib")
        self.schema = json.loads((self.version_dir / "feature_schema.json").read_text())

        # Step 3: expose traceable model and contract versions for every response.
        self.contract = self.manifest["feature_contract"]
        self.version = self.manifest["version"]

        # Step 4: restore review and rejection thresholds with legacy fallbacks.
        self.review_threshold = float(self.manifest.get("review_threshold", self.manifest["decision_threshold"]))
        self.reject_threshold = float(self.manifest.get("reject_threshold", self.review_threshold))

    @classmethod
    def from_registry(
        cls, registry: ModelRegistry | str | Path
    ) -> "LoanRiskPredictor":
        # Step 1: resolve a configured URI/path into a registry implementation.
        if isinstance(registry, (str, Path)):
            registry = create_registry(registry)

        # Step 2: load only the registry's verified active champion.
        return cls(registry.champion_dir())

    def predict(self, raw: dict) -> dict:
        # Step 1: enforce the minimum request contract before transformation.
        if "applicationDate" not in raw:
            raise ValueError("Missing required field: applicationDate")

        # Step 2: copy the request and derive Clarity-report presence when omitted.
        row = dict(raw)
        row.setdefault("has_clarity_report", any(
            key.startswith(".underwritingdata") and value is not None
            for key, value in row.items()
        ))

        # Step 3: recreate the exact ordered training matrix under the saved schema.
        matrix = transform_features(pd.DataFrame([row]), self.contract, self.schema)

        # Step 4: calculate the adverse-outcome probability with the champion model.
        probability = float(self.model.predict_proba(matrix)[:, 1][0])

        # Step 5: map the score to a human-readable operational risk band.
        if probability < 0.40:
            band = "low"
        elif probability < 0.70:
            band = "medium"
        else:
            band = "high"

        # Step 6: apply review/reject thresholds and return a traceable decision.
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


def create_app(
    registry: ModelRegistry | str | Path = "file://registry",
    batch_limit: int = 100,
    admin_api_key: str | None = None,
):
    # Step 1: import optional web dependencies and produce an actionable failure.
    try:
        from fastapi import FastAPI, Header, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import PlainTextResponse
    except ImportError as exc:  # pragma: no cover - dependency error is actionable
        raise RuntimeError("Install FastAPI dependencies from requirements.txt") from exc

    # Step 2: create the versioned FastAPI application.
    app = FastAPI(title="Loan Risk API", version="1")

    # Step 3: resolve the allow-list of trusted UI origins.
    ui_origins = [
        origin.strip()
        for origin in os.environ.get("UI_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]

    # Step 4: add narrow CORS rules for the documented read and prediction methods.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ui_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Admin-API-Key"],
    )

    # Step 5: load the champion once at startup and initialise in-process metrics.
    resolved_registry = create_registry(registry) if isinstance(registry, (str, Path)) else registry
    predictor = LoanRiskPredictor.from_registry(resolved_registry)
    predictor_lock = threading.RLock()
    metrics = ServiceMetrics()
    configured_admin_key = admin_api_key if admin_api_key is not None else os.environ.get("ADMIN_API_KEY")

    # Step 6: centralise prediction timing, error translation, and observations.
    def execute(payload: dict):
        started = time.perf_counter()
        result = None
        try:
            with predictor_lock:
                result = predictor.predict(payload)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            metrics.observe(time.perf_counter() - started, result)

    # Step 7: register single and bounded-batch prediction endpoints.
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

    # Step 8: expose active model metadata for traceability.
    @app.get("/v1/model")
    def model_info():
        with predictor_lock:
            return {
                "model_version": predictor.version,
                "feature_contract_version": predictor.contract["name"],
                "decision_threshold": predictor.review_threshold,
                "review_threshold": predictor.review_threshold,
                "reject_threshold": predictor.reject_threshold,
            }

    # Admin endpoints must always be protected by a configured service secret.
    # The UI keeps this secret server-side and authorizes its users separately.
    def require_admin(x_admin_api_key: str | None = Header(default=None)) -> None:
        if not configured_admin_key:
            raise HTTPException(status_code=503, detail="Admin API is not configured")
        if not x_admin_api_key or not compare_digest(x_admin_api_key, configured_admin_key):
            raise HTTPException(status_code=403, detail="Invalid admin API key")

    def reload_champion() -> LoanRiskPredictor:
        return LoanRiskPredictor.from_registry(resolved_registry)

    @app.get("/v1/admin/models")
    def admin_models(x_admin_api_key: str | None = Header(default=None)):
        require_admin(x_admin_api_key)
        return {"models": resolved_registry.list_versions()}

    @app.post("/v1/admin/models/{version}/promote")
    def promote_model(version: str, change: ModelChangeRequest, x_admin_api_key: str | None = Header(default=None)):
        nonlocal predictor
        require_admin(x_admin_api_key)
        loaded: LoanRiskPredictor | None = None

        def smoke_test():
            nonlocal loaded
            loaded = reload_champion()

        try:
            with predictor_lock:
                pointer = resolved_registry.promote(
                    version,
                    smoke_test=smoke_test,
                    reason=change.reason,
                    actor=change.actor,
                )
                predictor = loaded or reload_champion()
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"champion": pointer}

    @app.post("/v1/admin/models/rollback")
    def rollback_model(change: ModelChangeRequest, x_admin_api_key: str | None = Header(default=None)):
        nonlocal predictor
        require_admin(x_admin_api_key)
        try:
            with predictor_lock:
                loaded: LoanRiskPredictor | None = None

                def smoke_test():
                    nonlocal loaded
                    loaded = reload_champion()

                pointer = resolved_registry.rollback(
                    smoke_test=smoke_test,
                    reason=change.reason,
                    actor=change.actor,
                )
                predictor = loaded or reload_champion()
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"champion": pointer}

    # Step 9: expose separate process liveness and model readiness checks.
    @app.get("/health/live")
    def live():
        return {"status": "live"}

    @app.get("/health/ready")
    def ready():
        with predictor_lock:
            return {"status": "ready", "model_version": predictor.version}

    # Step 10: expose Prometheus metrics and return the configured application.
    @app.get("/metrics", response_class=PlainTextResponse)
    def service_metrics():
        with predictor_lock:
            return metrics.prometheus(predictor.version)

    return app
