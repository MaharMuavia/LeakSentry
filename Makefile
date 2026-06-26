# LeakSentry — developer commands
# NOTE: targets are wired up incrementally as build steps land.

.PHONY: help install data eval test backend demo clean

help:
	@echo "LeakSentry make targets:"
	@echo "  install   Install Python dependencies"
	@echo "  data      Generate synthetic dataset + ground truth   (step 2)"
	@echo "  test      Run pytest suite                            (step 3+)"
	@echo "  eval      Run the precision/recall eval harness        (step 8)"
	@echo "  backend   Launch the FastAPI backend                   (step 6)"
	@echo "  demo      Seed data + launch backend + dashboard        (step 9)"
	@echo "  clean     Remove generated data, db, traces, caches"

install:
	pip install -r requirements.txt

data:
	python data/generate_dataset.py

test:
	pytest -q

eval:
	python eval/run_eval.py

backend:
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Full demo: seeds data then launches everything. Wired up in build step 9.
demo:
	@echo "TODO(step 9): seed data + docker-compose up (backend + dashboard)."

clean:
	rm -f data/*.csv leaksentry.db traces/*.jsonl
	rm -rf __pycache__ .pytest_cache .ruff_cache
