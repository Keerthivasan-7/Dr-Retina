from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import settings

_pool = None


async def open_pool(expected_role="retina_api"):
    global _pool
    _pool = AsyncConnectionPool(
        settings().database_url.get_secret_value(),
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"row_factory": dict_row, "prepare_threshold": None},
    )
    await _pool.open()
    async with _pool.connection() as conn:
        row = await (
            await conn.execute(
                "select current_user as name, rolsuper, rolbypassrls from pg_roles where rolname=current_user"
            )
        ).fetchone()
        if not row or row["name"] != expected_role or row["rolsuper"] or row["rolbypassrls"]:
            raise RuntimeError("Use the dedicated non-superuser, non-BYPASSRLS database role")


async def close_pool():
    if _pool:
        await _pool.close()


@asynccontextmanager
async def transaction(user_id=None, session_id=None):
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with _pool.connection() as conn:
        async with conn.transaction():
            await conn.execute(
                "select set_config('app.user_id', %s, true), set_config('app.session_id', %s, true)",
                (str(user_id or ""), str(session_id or "")),
            )
            yield conn


async def one(conn, sql, params=()):
    return await (await conn.execute(sql, params)).fetchone()


async def all_rows(conn, sql, params=()):
    return await (await conn.execute(sql, params)).fetchall()
