"""
Adapters package - Unificado exclusivamente para o ecossistema Gupy
"""
from .base import BaseJobAdapter
from .gupy_adapter import GupyAdapter

__all__ = ["BaseJobAdapter", "GupyAdapter"]
