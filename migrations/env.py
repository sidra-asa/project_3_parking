"""Flask-Migrate / Alembic migration environment."""
import logging.config
from flask import current_app
from alembic import context

config = context.config
logging.config.fileConfig(config.config_file_name)


def get_metadata():
    return current_app.extensions['migrate'].db.metadata


def run_migrations_offline():
    url = str(current_app.extensions['migrate'].db.engine.url).replace('%','%%')
    context.configure(url=url, target_metadata=get_metadata(),
                      literal_binds=True, dialect_opts={'paramstyle':'named'})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = current_app.extensions['migrate'].db.engine
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=get_metadata(),
                          compare_type=True, render_as_batch=False)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
