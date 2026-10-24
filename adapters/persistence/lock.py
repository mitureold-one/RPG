from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from kernel.errors import LockTimeoutError

_LOCK_GUARD = threading.RLock()
_HELD_LOCKS: dict[Path, tuple[int, int, int]] = {}
# Maps resolved lock_path -> (thread_ident, reentrant_depth, fd)


class CampaignLock:
    """Single-writer lock per campaign using OS-level file locking and thread reentrancy."""

    def __init__(
        self,
        campaign_dir: Path | str,
        timeout_seconds: float = 5.0,
        poll_interval: float = 0.05,
        *,
        allow_reentrant: bool = True,
    ) -> None:
        self.campaign_dir = Path(campaign_dir)
        self.lock_path = self.campaign_dir / ".campaign.lock"
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval
        self.allow_reentrant = allow_reentrant
        self._fd: int | None = None
        self._resolved: Path | None = None
        self._owned: bool = False

    def acquire(self) -> None:
        self.campaign_dir.mkdir(parents=True, exist_ok=True)
        resolved = self.lock_path.resolve()
        ident = threading.get_ident()
        deadline = time.monotonic() + self.timeout_seconds

        while True:
            with _LOCK_GUARD:
                existing = _HELD_LOCKS.get(resolved)
                if existing is not None:
                    owner_ident, depth, fd = existing
                    if owner_ident == ident and self.allow_reentrant:
                        _HELD_LOCKS[resolved] = (ident, depth + 1, fd)
                        self._resolved = resolved
                        self._owned = True
                        return
                else:
                    fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
                    try:
                        self._try_lock(fd)
                        _HELD_LOCKS[resolved] = (ident, 1, fd)
                        self._fd = fd
                        self._resolved = resolved
                        self._owned = True
                        return
                    except OSError:
                        os.close(fd)

            if time.monotonic() >= deadline:
                raise LockTimeoutError(
                    f"Timed out waiting for campaign lock: {self.lock_path}",
                    details={"lock_path": str(self.lock_path), "timeout_seconds": self.timeout_seconds},
                )
            time.sleep(self.poll_interval)

    def release(self) -> None:
        if not self._owned or self._resolved is None:
            return
        resolved = self._resolved
        self._owned = False
        self._resolved = None
        with _LOCK_GUARD:
            existing = _HELD_LOCKS.get(resolved)
            if existing is None:
                return
            owner_ident, depth, fd = existing
            if depth > 1:
                _HELD_LOCKS[resolved] = (owner_ident, depth - 1, fd)
                return
            _HELD_LOCKS.pop(resolved, None)
            try:
                self._unlock(fd)
            except OSError:
                pass
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass
                self._fd = None

    def __enter__(self) -> CampaignLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    @staticmethod
    def _try_lock(fd: int) -> None:
        if sys.platform.startswith("win"):
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(fd: int) -> None:
        if sys.platform.startswith("win"):
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def campaign_lock(
    camp_dir: Path | str,
    timeout: float = 5.0,
    timeout_sec: float | None = None,
) -> Iterator[None]:
    actual_timeout = timeout_sec if timeout_sec is not None else timeout
    with CampaignLock(camp_dir, timeout_seconds=actual_timeout, allow_reentrant=False):
        yield


__all__ = ["CampaignLock", "campaign_lock"]
