"""DataStore interfaces and implementations."""

from scout.pipeline.data_store.base import DataStore

__all__ = ["DataStore", "get_supabase_store"]


def get_supabase_store() -> "SupabaseDataStore":
    """Lazy import to create the canonical Supabase-backed store."""
    from scout.pipeline.data_store.supabase import SupabaseDataStore

    return SupabaseDataStore()
