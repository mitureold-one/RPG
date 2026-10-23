"""Primitivas de persistência em arquivo: escrita atômica e lock cooperativo por campanha."""

import contextlib
import os
import shutil
import time
from pathlib import Path


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Grava um arquivo de forma atômica no mesmo diretório.

    A escrita ocorre em um temporário exclusivo; o arquivo final só é
    substituído por ``os.replace`` depois que todo o conteúdo foi gravado e
    sincronizado. Assim, uma falha no meio da operação não trunca o SSOT.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with open(tmp, "w", encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            try:
                shutil.copymode(target, tmp)
            except OSError:
                pass
        # No Windows, um leitor concorrente (por exemplo, o sync_daemon)
        # pode manter o arquivo aberto por alguns milissegundos.
        for attempt in range(5):
            try:
                os.replace(tmp, target)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


@contextlib.contextmanager
def campaign_lock(campaign_dir: Path, timeout: float = 10.0):
    """Serializa escritores de uma campanha usando um lock de arquivo.

    O lock é cooperativo: protege apenas processos que usam esta função.
    Em Windows usa ``msvcrt.locking``; em POSIX usa ``fcntl.flock``.
    """
    lock_path = Path(campaign_dir) / ".campaign.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+", encoding="utf-8")
    acquired = False
    try:
        # Windows não consegue travar um byte além do EOF; garante 1 byte.
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write("0")
            handle.flush()
        deadline = time.monotonic() + max(0.1, float(timeout))
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Não foi possível obter o lock da campanha '{campaign_dir}' em {timeout}s."
                    ) from exc
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()
