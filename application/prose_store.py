"""application/prose_store.py: Armazenamento e verificação de prosa literária imutável."""

from __future__ import annotations

import hashlib
from pathlib import Path


class ProseStore:
    """Repositório de artefatos de prosa imutáveis por turno."""

    def __init__(self, campaign_dir: Path | str) -> None:
        self.campaign_dir = Path(campaign_dir)
        self.artifacts_dir = self.campaign_dir / "artifacts" / "prose"

    def store_turn_prose(
        self,
        turn: int,
        content: str,
        scene_type: str = "action",
    ) -> tuple[str, str, int]:
        """Grava prosa em artifacts/prose/turn_{turn:06d}-{hash[:8]}.md de forma imutável."""
        content_bytes = content.strip().encode("utf-8")
        sha = hashlib.sha256(content_bytes).hexdigest()
        filename = f"turn_{turn:06d}-{sha[:8]}.md"
        rel_path = f"artifacts/prose/{filename}"
        target = self.campaign_dir / rel_path

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content_bytes)

        return rel_path, f"sha256:{sha}", len(content_bytes)

    def verify_prose(self, relative_path: str, expected_hash: str) -> bool:
        """Verifica se o artefato de prosa existe e se o hash confere."""
        target = self.campaign_dir / relative_path
        if not target.exists():
            return False
        content_bytes = target.read_bytes()
        sha = hashlib.sha256(content_bytes).hexdigest()
        clean_expected = expected_hash.removeprefix("sha256:")
        return sha == clean_expected


__all__ = ["ProseStore"]
