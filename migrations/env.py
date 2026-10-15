import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import MetaData, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Importing the models registers their tables in ModelBase.metadata.
import deribit_price_tracker.prices.models  # noqa: F401
from deribit_price_tracker.config.base import Config
from deribit_price_tracker.db.base import ModelBase


def get_metadata() -> MetaData:
    return ModelBase.metadata


def get_database_url() -> str:
    # The URL comes from the app config (env / .env), not from alembic.ini,
    # so credentials are never stored in the repository.
    return Config.from_env().database_url


def run_migrations_offline() -> None:
    """Render migrations as SQL without connecting to the database."""
    context.configure(
        url=get_database_url(),
        target_metadata=get_metadata(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=get_metadata())
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(get_database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def main() -> None:
    if context.config.config_file_name is not None:
        fileConfig(context.config.config_file_name)
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())


main()
