"""Composition root do RPGPRO.

Único ponto de composição e instanciação de :class:`Runtime` com registry congelado.
No R0, nenhum evento real é emitido e nenhum plugin de produção é registrado;
a suíte de contratos e os testes usam implementações fakes e injeção explícita.
"""

from __future__ import annotations

from contracts.config import CampaignConfig
from kernel.registry import Registry
from kernel.runtime import Runtime


def build_runtime(
    campaign_id: str,
    config: CampaignConfig | None = None,
    registry: Registry | None = None,
) -> Runtime:
    """Constrói e devolve um :class:`Runtime` imutável com registry congelado."""
    if not isinstance(campaign_id, str) or not campaign_id.strip():
        raise ValueError("campaign_id deve ser texto não vazio")

    resolved_config = config
    if resolved_config is None:
        resolved_config = CampaignConfig(campaign_id=campaign_id, system="default")

    resolved_registry = registry
    if resolved_registry is None:
        resolved_registry = Registry()

    if not resolved_registry.is_frozen:
        resolved_registry.freeze()

    return Runtime(
        campaign_id=campaign_id,
        config=resolved_config,
        registry=resolved_registry,
    )


__all__ = ["build_runtime"]
