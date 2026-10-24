"""Kernel do RPGPRO: identidade, ordem, composição e projeção.

O kernel não conhece domínio, Markdown, caminhos de campanha nem regras de
jogo. Ele depende apenas de ``contracts`` e da biblioteca padrão.
"""

from kernel.dag import DependencyGraph
from kernel.errors import (
    ConfigurationError,
    ConflictError,
    DependencyCycleError,
    DependencyDepthError,
    DependencyError,
    DuplicateRegistrationError,
    InvalidDraftError,
    LockTimeoutError,
    MissingRequirementError,
    NotFoundError,
    RegistryFrozenError,
    ReplayError,
    RpgError,
    SchemaError,
    SeqConflictError,
    UnknownEventTypeError,
    UnknownPortError,
    ValidationError,
)
from kernel.ids import new_event_id
from kernel.registry import PluginManifest, Registry
from kernel.runtime import Runtime
from kernel.schema import is_valid_schema, validate_schema

__all__ = [
    "ConfigurationError",
    "ConflictError",
    "DependencyCycleError",
    "DependencyDepthError",
    "DependencyError",
    "DependencyGraph",
    "DuplicateRegistrationError",
    "InvalidDraftError",
    "LockTimeoutError",
    "MissingRequirementError",
    "NotFoundError",
    "PluginManifest",
    "Registry",
    "RegistryFrozenError",
    "ReplayError",
    "RpgError",
    "Runtime",
    "SchemaError",
    "SeqConflictError",
    "UnknownEventTypeError",
    "UnknownPortError",
    "ValidationError",
    "is_valid_schema",
    "new_event_id",
    "validate_schema",
]
