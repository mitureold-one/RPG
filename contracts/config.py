"""Configuração de composição de uma campanha.

``CampaignConfig`` é o produto já interpretado e validado do parser de
``campaign/``. O kernel recebe esta configuração e não lê Markdown, caminhos ou
arquivos da campanha.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from contracts.serialization import normalize_json_object


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} deve ser texto não vazio")
    return value


@dataclass(frozen=True)
class CampaignConfig:
    """Configuração normalizada que o ``bootstrap.py`` entrega ao runtime."""

    campaign_id: str
    system: str
    plugins: Mapping[str, str] = field(default_factory=dict)
    calendar: Mapping[str, Any] = field(default_factory=dict)
    config_version: int = 1

    def __post_init__(self) -> None:
        _require_text(self.campaign_id, "campaign_id")
        _require_text(self.system, "system")
        if isinstance(self.config_version, bool) or not isinstance(self.config_version, int):
            raise ValueError("config_version deve ser inteiro")
        if self.config_version < 1:
            raise ValueError("config_version deve ser >= 1")

        if not isinstance(self.plugins, Mapping):
            raise ValueError("plugins deve ser um mapa")
        plugins: dict[str, str] = {}
        for point, name in self.plugins.items():
            _require_text(point, "plugins.ponto")
            _require_text(name, f"plugins.{point}")
            plugins[point] = name
        object.__setattr__(self, "plugins", plugins)

        object.__setattr__(self, "calendar", normalize_json_object(self.calendar, "calendar"))


__all__ = ["CampaignConfig"]
