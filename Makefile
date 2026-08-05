PYTHON ?= python3

.PHONY: test pipeline serve rollback

test:
	$(PYTHON) -m pytest -q

pipeline:
	$(PYTHON) -m src.pipeline --config configs/baseline.yaml

serve:
	$(PYTHON) -m uvicorn src.api:app --host 0.0.0.0 --port 8000

rollback:
	$(PYTHON) -c "from src.mlops import LocalRegistry; print(LocalRegistry('registry').rollback())"
