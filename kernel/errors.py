"""Taxonomia de erros do kernel.

Todo erro operacional do motor herda de :class:`RpgError` e expõe um ``code``
estável. A CLI traduz o erro para ``{"error": str(exc)}`` sem alterar o
contrato externo existente.
"""

from __future__ import annotations

from typing import Any, Mapping


class RpgError(Exception):
    """Erro base do motor, com código estável e detalhes opcionais."""

    code = "RPG_ERROR"

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = dict(details or {})

    def __str__(self) -> str:
        return self.message


class ValidationError(RpgError):
    """Entrada ou estado viola uma pré-condição do motor."""

    code = "VALIDATION_ERROR"


class ConfigurationError(RpgError):
    """Configuração de campanha ou de plugin inválida."""

    code = "CONFIG_INVALID"


class NotFoundError(RpgError):
    """Campanha, recurso ou registro ausente."""

    code = "NOT_FOUND"


class ConflictError(RpgError):
    """Conflito de estado entre a proposta e o estado persistido."""

    code = "CONFLICT"


class SeqConflictError(ConflictError):
    """``expected_last_seq`` não corresponde à sequência atual da campanha."""

    code = "SEQ_CONFLICT"


class SchemaError(ValidationError):
    """Payload ou schema de evento inválido."""

    code = "SCHEMA_INVALID"


class DuplicateRegistrationError(ConfigurationError):
    """Registro duplicado para o mesmo ponto e nome."""

    code = "REGISTRY_DUPLICATE"


class UnknownPortError(ConfigurationError):
    """Ponto de extensão ou implementação solicitada não existe."""

    code = "PORT_NOT_FOUND"


class RegistryFrozenError(ConfigurationError):
    """Tentativa de registrar depois do congelamento do registry."""

    code = "REGISTRY_FROZEN"


class MissingRequirementError(ConfigurationError):
    """Manifesto declara uma dependência ausente na composição."""

    code = "PLUGIN_REQUIREMENT_MISSING"


class LockTimeoutError(RpgError):
    """Não foi possível adquirir o lock da campanha no prazo."""

    code = "LOCK_TIMEOUT"


class ReplayError(RpgError):
    """Falha ao reconstruir estado a partir do event log."""

    code = "REPLAY_FAILED"


__all__ = [
    "RpgError",
    "ValidationError",
    "ConfigurationError",
    "NotFoundError",
    "ConflictError",
    "SeqConflictError",
    "SchemaError",
    "DuplicateRegistrationError",
    "UnknownPortError",
    "RegistryFrozenError",
    "MissingRequirementError",
    "LockTimeoutError",
    "ReplayError",
]
