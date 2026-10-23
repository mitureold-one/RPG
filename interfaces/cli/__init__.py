"""CLI do RPGPRO: só traduz argumentos em casos de uso e formata a saída."""

from interfaces.cli.main import main
from interfaces.cli.parser import build_cli

__all__ = ["build_cli", "main"]
