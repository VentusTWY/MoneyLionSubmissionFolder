"""Online model loading, prediction contracts, and API application."""

from src.serving.predictor import LoanRiskPredictor, create_app

__all__ = ["LoanRiskPredictor", "create_app"]
