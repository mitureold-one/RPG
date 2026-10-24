"""application/projection_engine.py: Motor de projeção determinístico e escrita atômica."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Sequence

from adapters.persistence.files import atomic_write_text
from contracts.ports import EventStreamView, Projector


class ProjectionEngine:
    """Orquestra a execução dos projectors e a gravação atômica em disco."""

    def __init__(
        self,
        projectors: Sequence[Projector],
        campaign_dir: Path | str,
        projections_subdir: str = "projections",
    ) -> None:
        self.projectors = sorted(projectors, key=lambda p: p.order)
        self.campaign_dir = Path(campaign_dir)
        self.projections_dir = self.campaign_dir / projections_subdir

    def project(self, view: EventStreamView) -> dict[str, str]:
        """Aplica os projectors ordenados sobre a visão de eventos."""
        outputs: dict[str, list[str]] = {}
        for p in self.projectors:
            section = p.project(view)
            outputs.setdefault(section.file, []).append(section.content)

        return {
            filename: "\n\n".join(parts).strip() + "\n"
            for filename, parts in outputs.items()
        }

    def write_projections_atomic(self, projections: dict[str, str]) -> str:
        """Grava os arquivos de projeção atomicamente e devolve o hash consolidado."""
        self.projections_dir.mkdir(parents=True, exist_ok=True)
        buffer = bytearray()

        for filename, content in sorted(projections.items()):
            target_path = self.projections_dir / filename
            atomic_write_text(target_path, content, encoding="utf-8")
            buffer.extend(filename.encode("utf-8"))
            buffer.extend(b":")
            buffer.extend(content.encode("utf-8"))

        sha = hashlib.sha256(buffer).hexdigest()
        return f"sha256:{sha}"


__all__ = ["ProjectionEngine"]
