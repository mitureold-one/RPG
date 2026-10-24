"""adapters/persistence/skeleton_queue.py: Fila esqueleto de tarefas append-only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class SkeletonQueue:
    """Fila esqueleto baseada em arquivo append-only queue.jsonl."""

    def __init__(self, campaign_dir: Path | str) -> None:
        self.campaign_dir = Path(campaign_dir)
        self.queue_file = self.campaign_dir / "queue.jsonl"

    def _append(self, record: dict) -> dict:
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self.queue_file.open("a", encoding="utf-8") as f:
            f.write(line)
        return record

    def enqueue(self, task_id: str, task_type: str, payload: dict | None = None) -> dict:
        """Enfileira uma nova tarefa com status pending."""
        record = {
            "task_id": task_id,
            "type": task_type,
            "status": "pending",
            "payload": payload or {},
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._append(record)

    def complete(self, task_id: str, result: dict | None = None) -> dict:
        """Registra conclusão de uma tarefa com status done (append-only)."""
        record = {
            "task_id": task_id,
            "status": "done",
            "result": result or {},
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._append(record)

    def fail(self, task_id: str, error: str) -> dict:
        """Registra falha de uma tarefa com status failed (append-only)."""
        record = {
            "task_id": task_id,
            "status": "failed",
            "error": error,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._append(record)

    def _read_aggregated(self) -> dict[str, dict]:
        if not self.queue_file.exists():
            return {}
        tasks: dict[str, dict] = {}
        with self.queue_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                tid = data.get("task_id")
                if not tid:
                    continue
                if tid not in tasks:
                    tasks[tid] = data.copy()
                else:
                    tasks[tid].update(data)
        return tasks

    def list_pending(self) -> list[dict]:
        """Retorna tarefas que estão atualmente pendentes."""
        aggregated = self._read_aggregated()
        return [t for t in aggregated.values() if t.get("status") == "pending"]

    def get_task(self, task_id: str) -> dict | None:
        """Retorna o estado agregado atual de uma tarefa."""
        aggregated = self._read_aggregated()
        return aggregated.get(task_id)


__all__ = ["SkeletonQueue"]
