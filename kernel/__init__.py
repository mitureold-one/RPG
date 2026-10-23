"""Kernel do RPGPRO: identidade, ordem, composição e projeção.

O kernel não conhece domínio, Markdown, caminhos de campanha nem regras de
jogo. Ele depende apenas de ``contracts`` e da biblioteca padrão.
"""

from kernel.errors import (
    ConfigurationError,
    ConflictError,
    DuplicateRegistrationError,
    LockTimeoutError,
    MissingRequirementError,
    NotFoundError,
    RegistryFrozenError,
    ReplayError,
    RpgError,
    SchemaError,
    SeqConflictError,
    UnknownPortError,
    ValidationError,
)
from kernel.ids import new_event_id

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
    "new_event_id",
]
