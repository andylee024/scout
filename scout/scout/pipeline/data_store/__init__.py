"""DataStore interfaces and implementations."""

from scout.pipeline.data_store.base import DataStore
from scout.pipeline.data_store.sqlite import SQLiteDataStore

__all__ = ["DataStore", "SQLiteDataStore"]


def get_supabase_store() -> "SupabaseDataStore":
    """Lazy import to avoid requiring supabase when not used."""
    from scout.pipeline.data_store.supabase import SupabaseDataStore

    return SupabaseDataStore()
