"""Adaptadores de persistência em arquivo: escrita atômica e locks."""

from adapters.persistence.event_store import JsonlEventStore
from adapters.persistence.files import atomic_write_text, campaign_lock
from adapters.persistence.lock import CampaignLock
from adapters.persistence.skeleton_queue import SkeletonQueue

__all__ = ["CampaignLock", "JsonlEventStore", "SkeletonQueue", "atomic_write_text", "campaign_lock"]
