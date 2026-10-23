"""Fronteira transacional dos casos de uso que mutam o SSOT da campanha."""

import functools
import os
from pathlib import Path

from council.helpers import atomic_write_text, campaign_lock
from council import find_campaign


def _serialized_campaign_mutation(func):
    """Serializa comandos que fazem read-modify-write no SSOT da campanha."""

    @functools.wraps(func)
    def wrapper(campaign_id, *args, **kwargs):
        try:
            info = find_campaign(campaign_id)
        except (ValueError, FileNotFoundError) as exc:
            return {"error": str(exc)}
        if not info:
            return func(campaign_id, *args, **kwargs)
        timeout = float(os.environ.get("RPGPRO_LOCK_TIMEOUT", "10.0"))
        try:
            with campaign_lock(info["dir"], timeout=timeout):
                # Snapshot dos arquivos mutáveis: se uma exceção inesperada
                # ocorrer no meio de um commit multiarquivo, restaura o estado
                # anterior em vez de deixar ficha/npcs/diario divergentes.
                snapshots = {}
                for key in ("ficha", "diario", "npcs", "mundo"):
                    path = info.get(key)
                    if path and Path(path).exists():
                        snapshots[Path(path)] = Path(path).read_text(encoding="utf-8")
                try:
                    return func(campaign_id, *args, **kwargs)
                except BaseException:
                    for path, content in snapshots.items():
                        try:
                            atomic_write_text(path, content)
                        except OSError:
                            pass
                    raise
        except TimeoutError as exc:
            return {"error": str(exc)}

    return wrapper
