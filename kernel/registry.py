"""Registro de extensões e manifestos de plugins do RPGPRO.

Permite registro explícito de implementações por ponto de extensão (port),
validação de dependências cruzadas (requires) e congelamento na inicialização.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from contracts.serialization import normalize_json_object
from kernel.errors import (
    ConfigurationError,
    DuplicateRegistrationError,
    MissingRequirementError,
    RegistryFrozenError,
    UnknownPortError,
)


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} deve ser texto não vazio")
    return value.strip()


@dataclass(frozen=True)
class PluginManifest:
    """Metadados e declaração de capacidades de um plugin."""

    name: str
    version: str
    api_version: int
    provides: tuple[str, ...]
    requires: tuple[str, ...] = ()
    deterministic: bool = True
    config_schema: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.name, "name")
        _require_non_empty_str(self.version, "version")

        if isinstance(self.api_version, bool) or not isinstance(self.api_version, int) or self.api_version < 1:
            raise ValueError("api_version deve ser inteiro >= 1")

        if not isinstance(self.provides, (list, tuple)) or not self.provides:
            raise ValueError("provides deve ser uma sequência não vazia de portas")
        provides = tuple(_require_non_empty_str(p, "provides") for p in self.provides)
        object.__setattr__(self, "provides", provides)

        if not isinstance(self.requires, (list, tuple)):
            raise ValueError("requires deve ser uma sequência de portas")
        requires = tuple(_require_non_empty_str(r, "requires") for r in self.requires)
        object.__setattr__(self, "requires", requires)

        if not isinstance(self.deterministic, bool):
            raise ValueError("deterministic deve ser booleano")

        object.__setattr__(
            self,
            "config_schema",
            normalize_json_object(self.config_schema, "config_schema"),
        )


class Registry:
    """Tabela de registro e composição de plugins e portas de extensão."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], tuple[Any, PluginManifest | None]] = {}
        self._frozen: bool = False

    @property
    def is_frozen(self) -> bool:
        """Indica se o registry foi congelado para novas mutações."""
        return self._frozen

    def register(
        self,
        point: str,
        name: str,
        impl: Any,
        manifest: PluginManifest | None = None,
    ) -> None:
        """Registra uma implementação para o ponto de extensão ``point`` com o nome ``name``."""
        if self._frozen:
            raise RegistryFrozenError("Registry está congelado; não é permitido registrar novas implementações")

        _require_non_empty_str(point, "point")
        _require_non_empty_str(name, "name")

        key = (point, name)
        if key in self._entries:
            raise DuplicateRegistrationError(f"Implementação já registrada para '{point}:{name}'")

        if manifest is not None:
            if not isinstance(manifest, PluginManifest):
                raise ValueError("manifest deve ser uma instância de PluginManifest")
            if manifest.name != name:
                raise ConfigurationError(
                    f"Nome no manifesto '{manifest.name}' difere do nome de registro '{name}'"
                )
            if point not in manifest.provides:
                raise ConfigurationError(
                    f"Manifesto de '{name}' não declara fornecer o ponto '{point}'"
                )

        self._entries[key] = (impl, manifest)

    def get(self, point: str, name: str) -> Any:
        """Recupera a implementação registrada para ``point`` e ``name``."""
        key = (point, name)
        if key not in self._entries:
            raise UnknownPortError(f"Serviço não encontrado para '{point}:{name}'")
        return self._entries[key][0]

    def get_manifest(self, point: str, name: str) -> PluginManifest | None:
        """Recupera o manifesto associado à implementação registrada."""
        key = (point, name)
        if key not in self._entries:
            raise UnknownPortError(f"Serviço não encontrado para '{point}:{name}'")
        return self._entries[key][1]

    def has(self, point: str, name: str) -> bool:
        """Informa se existe implementação registrada para ``point`` e ``name``."""
        return (point, name) in self._entries

    def all(self, point: str) -> list[Any]:
        """Devolve todas as implementações registradas para ``point``, em ordem de registro."""
        return [impl for (p, _), (impl, _) in self._entries.items() if p == point]

    def all_names(self, point: str) -> list[str]:
        """Devolve os nomes de todas as implementações registradas para ``point``."""
        return [n for (p, n) in self._entries.keys() if p == point]

    def points(self) -> set[str]:
        """Devolve o conjunto de todos os pontos de extensão com registros."""
        return {p for (p, _) in self._entries.keys()}

    def freeze(self) -> None:
        """Valida dependências declaradas e congela o registry para novas mutações."""
        if self._frozen:
            return

        for (point, name), (_, manifest) in self._entries.items():
            if manifest and manifest.requires:
                for req in manifest.requires:
                    if ":" in req:
                        req_point, req_name = req.split(":", 1)
                        if not self.has(req_point, req_name):
                            raise MissingRequirementError(
                                f"Manifesto '{manifest.name}' requer '{req}', que não está registrado"
                            )
                    else:
                        if not any(p == req for (p, _) in self._entries.keys()):
                            raise MissingRequirementError(
                                f"Manifesto '{manifest.name}' requer o ponto '{req}', que não possui implementações registradas"
                            )

        self._frozen = True


__all__ = ["PluginManifest", "Registry"]
