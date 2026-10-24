"""adapters/persistence/lock.py: Gerenciador de lock cooperativo por campanha."""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path

from kernel.errors import LockTimeoutError


class CampaignLock:
    """Gerenciador de contexto para lock cooperativo por campanha."""

    def __init__(self, campaign_dir: Path | str, timeout: float = 10.0) -> None:
        self.campaign_dir = Path(campaign_dir)
        self.timeout = max(0.1, float(timeout))
        self.lock_path = self.campaign_dir / ".campaign.lock"
        self._handle = None
        self._acquired = False

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.lock_path, "a+", encoding="utf-8")
        self._handle = handle
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write("0")
                handle.flush()
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._acquired = True
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise LockTimeoutError(
                            f"Não foi possível obter o lock da campanha '{self.campaign_dir}' em {self.timeout}s."
                        ) from exc
                    time.sleep(0.05)
        except Exception:
            self.release()
            raise

    def release(self) -> None:
        if self._handle is not None:
            if self._acquired:
                with contextlib.suppress(OSError):
                    self._handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
                self._acquired = False
            with contextlib.suppress(OSError):
                self._handle.close()
            self._handle = None

    def __enter__(self) -> CampaignLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


__all__ = ["CampaignLock"]
