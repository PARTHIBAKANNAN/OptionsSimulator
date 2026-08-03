"""asyncpg pool against Supabase Postgres. statement_cache_size=0 is required because Supabase's
transaction-mode pooler (pgbouncer) breaks asyncpg's prepared statements otherwise — same
workaround TradeDashBoard uses."""
import asyncpg

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn, statement_cache_size=0, min_size=1, max_size=5,
        command_timeout=10,  # blanket ceiling — a stalled query/connection should error, never hang forever
        max_inactive_connection_lifetime=120,  # recycle idle connections before the pooler/network can
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() during app startup first")
    return _pool
