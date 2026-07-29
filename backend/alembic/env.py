import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importa todos os models para que o autogenerate os detecte
import app.models.estabelecimento  # noqa: F401
import app.models.profissional      # noqa: F401
import app.models.cliente           # noqa: F401
import app.models.servico           # noqa: F401
import app.models.agendamento       # noqa: F401
import app.models.conversa          # noqa: F401
import app.models.token_blacklist   # noqa: F401
import app.models.reminder_job      # noqa: F401
import app.models.webhook_event     # noqa: F401
import app.models.pagamento         # noqa: F401
import app.models.payment_account   # noqa: F401
import app.models.payment_integration  # noqa: F401
import app.models.payment_oauth_state  # noqa: F401
import app.models.payment_webhook_event  # noqa: F401
import app.models.admin_audit_log   # noqa: F401
import app.models.admin_mfa         # noqa: F401

from app.database import Base

target_metadata = Base.metadata


def compare_server_default(
    context,
    inspected_column,
    metadata_column,
    inspected_default,
    metadata_default,
    rendered_metadata_default,
):
    """Compara defaults que fazem parte explicitamente do contrato ORM.

    A baseline mantém defaults adicionais no PostgreSQL como proteção para
    inserções operacionais/raw SQL, enquanto o ORM usa ``default=`` Python
    equivalente. Esses defaults extras não são drift. Quando o modelo declara
    ``server_default``, porém, o Alembic continua usando sua comparação normal.
    """
    if metadata_default is None:
        return False
    return None


def get_url() -> str:
    from app.config import DATABASE_URL
    return DATABASE_URL


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=compare_server_default,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=compare_server_default,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
