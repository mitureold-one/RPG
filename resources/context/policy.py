"""Políticas de contexto por modo de operação e derivação de audiência epistêmica."""

from __future__ import annotations

from typing import NamedTuple

from contracts.context import HolderRef


class ModePolicy(NamedTuple):
    """Diretrizes de audiência, visualizador e propósito para um modo de execução."""

    mode: str
    viewer: HolderRef
    audience: HolderRef
    purpose: str
    allow_new_context: bool


def resolve_mode_policy(
    mode: str,
    protagonist_id: str = "protagonist",
    player_id: str = "player",
    audience_override: str = "",
) -> ModePolicy:
    """Resolve a política epistêmica estrita com base no modo e overrides explícitos."""
    m = mode.lower().strip() if mode else "gm"
    aud_over = audience_override.lower().strip() if audience_override else ""

    # Defaults por modo usando holders canônicos válidos
    if m == "gm":
        viewer = HolderRef("universe", "gm")
        audience = HolderRef("universe", "gm")
        purpose = "arbitration"
        allow_new = True
    elif m == "narrator":
        viewer = HolderRef("protagonist", protagonist_id)
        audience = HolderRef("protagonist", protagonist_id)
        purpose = "narration"
        allow_new = True
    elif m == "writer":
        viewer = HolderRef("protagonist", protagonist_id)
        audience = HolderRef("protagonist", protagonist_id)
        purpose = "prose"
        allow_new = True
    elif m == "architect":
        viewer = HolderRef("player", "architect")
        audience = HolderRef("player", "architect")
        purpose = "structure"
        allow_new = True
    elif m == "director":
        viewer = HolderRef("player", "director")
        audience = HolderRef("player", "director")
        purpose = "direction"
        allow_new = True
    elif m == "reviewer":
        viewer = HolderRef("player", "reviewer")
        audience = HolderRef("player", "reviewer")
        purpose = "audit"
        allow_new = False
    else:
        viewer = HolderRef("player", "gm")
        audience = HolderRef("player", "gm")
        purpose = "arbitration"
        allow_new = True

    # Override explícito de depuração (--audience)
    if aud_over:
        if aud_over in ("universe", "system", "gm"):
            audience = HolderRef("universe", "gm")
        elif aud_over in ("player", "human"):
            audience = HolderRef("player", player_id)
        elif aud_over in ("protagonist", "pc", "narrator", "writer"):
            audience = HolderRef("protagonist", protagonist_id)
        elif aud_over in ("faction", "subgroup", "npc"):
            audience = HolderRef(aud_over, player_id)
        else:
            audience = HolderRef("player", aud_over)

    return ModePolicy(
        mode=m,
        viewer=viewer,
        audience=audience,
        purpose=purpose,
        allow_new_context=allow_new,
    )


__all__ = ["ModePolicy", "resolve_mode_policy"]
