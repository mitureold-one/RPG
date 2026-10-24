from __future__ import annotations

import os
from pathlib import Path

from adapters.persistence.lock import campaign_lock


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text atomically via temp file + fsync + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp_path, "w", encoding=encoding, newline="\n") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)


__all__ = ["atomic_write_text", "campaign_lock"]
