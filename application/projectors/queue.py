"""application/projectors/queue.py: projeção derivada da fila de simulação (queue.json).

A fila é sempre reconstruível do log de eventos ``world.*``; este projector apenas
materializa o índice agregado com hash canônico para inspeção e retomada.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from contracts.ports import EventStreamView, ProjectionSection
from contracts.serialization import canonical_json
from resources.world.queue import collect, from_document
from resources.world.workqueue import queue_document


class QueueProjector:
    """Projeta ``queue.json`` agregando agendamentos, adiamentos e falhas."""

    file = "queue.json"
    section = "body"
    order = 60

    def __init__(
        self,
        initial_text: str | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        self.initial_text = initial_text
        self.config = dict(config or {})

    def project(self, view: EventStreamView) -> ProjectionSection:
        base_last_seq = 0
        initial_index = None
        if self.initial_text:
            try:
                document = json.loads(self.initial_text)
                if isinstance(document, dict):
                    initial_index = from_document(document)
                    base_last_seq = int(document.get("last_seq", 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                initial_index = None

        domain_events = [event for event in view.events if not event.type.startswith("projection.")]
        index = collect(domain_events, initial_index)
        last_seq = max(base_last_seq, domain_events[-1].seq if domain_events else 0)
        document = queue_document(index, last_seq, self.config)
        digest = hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()
        document["hash"] = f"sha256:{digest}"
        content = canonical_json(document) + "\n"
        return ProjectionSection(file=self.file, section=self.section, content=content)


__all__ = ["QueueProjector"]
