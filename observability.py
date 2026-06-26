"""Structured observability (Concept 4 / prototype-to-production).

Every agent step — which agent, which tool, inputs/outputs, latency, tokens — is
captured as a TraceStep, appended to a JSONL trace file, and attached to the
Finding so the UI can show a per-finding reasoning trace.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager

import config
from models import TraceStep


class Tracer:
    def __init__(self, run_id: str | None = None, trace_file: str | None = None):
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.trace_file = trace_file or config.TRACE_FILE
        os.makedirs(os.path.dirname(self.trace_file), exist_ok=True)
        self.steps: list[TraceStep] = []

    def _write(self, step: TraceStep) -> None:
        rec = {"run_id": self.run_id, "ts": time.time(), **step.model_dump()}
        with open(self.trace_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    def emit(self, step: TraceStep, sink: list[TraceStep] | None = None) -> TraceStep:
        self.steps.append(step)
        if sink is not None:
            sink.append(step)
        self._write(step)
        return step

    @contextmanager
    def timed(self, agent: str, action: str, *, tool: str | None = None,
              detail: str = "", sink: list[TraceStep] | None = None):
        step = TraceStep(agent=agent, action=action, tool=tool, detail=detail)
        t0 = time.perf_counter()
        try:
            yield step
        finally:
            step.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            self.emit(step, sink)
