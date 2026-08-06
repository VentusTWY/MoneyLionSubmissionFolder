PYTHON ?= python3
MODEL_REGISTRY_URI ?= file://registry

.PHONY: test pipeline serve rollback

test:
	$(PYTHON) -m pytest -q

pipeline:
	$(PYTHON) -m src.pipeline --config configs/baseline.yaml --registry "$(MODEL_REGISTRY_URI)"

serve:
	$(PYTHON) -m uvicorn src.api:app --host 0.0.0.0 --port 8000

rollback:
	MODEL_REGISTRY_URI="$(MODEL_REGISTRY_URI)" $(PYTHON) -c "import os; from src.mlops import create_registry; print(create_registry(os.environ['MODEL_REGISTRY_URI']).rollback())"
