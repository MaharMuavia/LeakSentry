"""LeakSentry FastAPI backend.

Async app exposing audit, findings, reasoning-trace, and human-approval
endpoints; every agent step is logged to a JSONL trace file. Populated in
build step 6 (`backend/main.py`).
"""
