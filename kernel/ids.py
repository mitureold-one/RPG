"""Geração de identificadores estáveis do kernel.

O formato é ``evt_<ulid>``: 48 bits de tempo em milissegundos e 80 bits
aleatórios, codificados em Crockford Base32. A ordem lexicográfica acompanha a
ordem de criação, inclusive dentro do mesmo milissegundo (contador monotônico).
"""

from __future__ import annotations

import secrets
import threading
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LENGTH = 26
_RANDOM_BITS = 80
_RANDOM_MASK = (1 << _RANDOM_BITS) - 1

_lock = threading.Lock()
_last_ms = 0
_last_random = 0


def _encode(value: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def _next_ulid() -> str:
    global _last_ms, _last_random

    with _lock:
        now_ms = int(time.time() * 1000)
        if now_ms > _last_ms:
            _last_ms = now_ms
            _last_random = secrets.randbits(_RANDOM_BITS)
        else:
            _last_random += 1
            if _last_random > _RANDOM_MASK:
                _last_ms += 1
                _last_random = 0
        value = (_last_ms << _RANDOM_BITS) | _last_random
        return _encode(value, _ULID_LENGTH)


def new_event_id() -> str:
    """Devolve um identificador novo no formato ``evt_<ulid>``."""

    return f"evt_{_next_ulid()}"


def new_batch_id() -> str:
    """Devolve um identificador novo no formato ``bat_<ulid>``."""

    return f"bat_{_next_ulid()}"


def new_correction_id() -> str:
    """Devolve um identificador novo no formato ``cor_<ulid>``."""

    return f"cor_{_next_ulid()}"


def new_work_id() -> str:
    """Devolve um identificador novo no formato ``wrk_<ulid>``."""

    return f"wrk_{_next_ulid()}"


__all__ = ["new_batch_id", "new_correction_id", "new_event_id", "new_work_id"]
