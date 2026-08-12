PYTHON ?= python3
MODEL_REGISTRY_URI ?= file://registry

# Convenience targets for local development. If you are using Docker Compose,
# you can skip Make and run the containers directly.
.PHONY: test pipeline serve ui rollback

test:
	$(PYTHON) -m pytest -q

pipeline:
	$(PYTHON) -m src.training.pipeline --config configs/baseline.yaml --registry "$(MODEL_REGISTRY_URI)"

serve:
	$(PYTHON) -m uvicorn src.serving.api:app --host 0.0.0.0 --port 8000

ui:
	cd ui && npm install && npm run dev

rollback:
	MODEL_REGISTRY_URI="$(MODEL_REGISTRY_URI)" $(PYTHON) -c "import os; from src.mlops import create_registry; print(create_registry(os.environ['MODEL_REGISTRY_URI']).rollback())"
