"""Adaptadores de persistência em arquivo: escrita atômica e locks."""

from adapters.persistence.files import atomic_write_text, campaign_lock

__all__ = ["atomic_write_text", "campaign_lock"]
