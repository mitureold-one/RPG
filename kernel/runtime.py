"""Runtime imutável de composição de campanha.

Recebe uma configuração já normalizada e um registry congelado, servindo
como ponto de acesso a serviços e adaptadores para o turno.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contracts.config import CampaignConfig
from kernel.errors import UnknownPortError
from kernel.registry import Registry


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} deve ser texto não vazio")
    return value.strip()


@dataclass(frozen=True)
class Runtime:
    """Instância imutável de execução de uma campanha."""

    campaign_id: str
    config: CampaignConfig
    registry: Registry

    def __post_init__(self) -> None:
        campaign_id = _require_non_empty_str(self.campaign_id, "campaign_id")
        if not isinstance(self.config, CampaignConfig):
            raise ValueError("config deve ser uma instância de CampaignConfig")
        if self.config.campaign_id != campaign_id:
            raise ValueError(
                f"campaign_id '{campaign_id}' difere do id na configuração '{self.config.campaign_id}'"
            )
        if not isinstance(self.registry, Registry):
            raise ValueError("registry deve ser uma instância de Registry")

        if not self.registry.is_frozen:
            self.registry.freeze()

        # Validação dos plugins configurados contra o registry
        for point, name in self.config.plugins.items():
            if not self.registry.has(point, name):
                raise UnknownPortError(
                    f"Plugin configurado '{point}:{name}' não está registrado no registry"
                )

    def service(self, point: str, name: str | None = None) -> Any:
        """Obtém o serviço associado a ``point``.

        Se ``name`` for omitido, resolve pelo plugin declarado em ``config.plugins``
        ou pela única implementação registrada para a porta.
        """
        if name is not None:
            return self.registry.get(point, name)

        if point in self.config.plugins:
            return self.registry.get(point, self.config.plugins[point])

        impls = self.registry.all(point)
        if len(impls) == 1:
            return impls[0]
        if not impls:
            raise UnknownPortError(f"Nenhum plugin registrado para o ponto '{point}'")

        names = self.registry.all_names(point)
        raise UnknownPortError(
            f"Ponto '{point}' possui múltiplas implementações registradas ({names}); especifique o nome"
        )

    def services(self, point: str) -> list[Any]:
        """Devolve todas as implementações registradas para ``point``."""
        return self.registry.all(point)

    def has_service(self, point: str, name: str) -> bool:
        """Informa se existe implementação para ``point`` e ``name``."""
        return self.registry.has(point, name)


__all__ = ["Runtime"]
