"""Broker-facing integration for parking vehicle searches."""
from .search_registry import SearchRegistry, get_registry, integration_enabled

__all__ = ["SearchRegistry", "get_registry", "integration_enabled"]
