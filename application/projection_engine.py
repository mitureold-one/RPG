"""application/projection_engine.py: Motor de projeção determinístico e escrita atômica."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Sequence

from contracts.ports import EventStreamView, Projector


def _atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp_path, "w", encoding=encoding, newline="\n") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)


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
        """Grava os arquivos de projeção atomicamente em projections/ e na raiz da campanha."""
        self.projections_dir.mkdir(parents=True, exist_ok=True)
        self.campaign_dir.mkdir(parents=True, exist_ok=True)

        for existing in list(self.projections_dir.iterdir()):
            if existing.is_file() and existing.name not in projections:
                try:
                    existing.unlink()
                except OSError:
                    pass

        buffer = bytearray()
        for filename, content in sorted(projections.items()):
            proj_target = self.projections_dir / filename
            root_target = self.campaign_dir / filename
            _atomic_write(proj_target, content, encoding="utf-8")
            _atomic_write(root_target, content, encoding="utf-8")
            buffer.extend(filename.encode("utf-8"))
            buffer.extend(b":")
            buffer.extend(content.encode("utf-8"))

        sha = hashlib.sha256(buffer).hexdigest()
        return f"sha256:{sha}"


__all__ = ["ProjectionEngine"]
