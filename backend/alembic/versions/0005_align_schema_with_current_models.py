"""align schema with current models

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-29

Completa estruturas que existiam no ORM/runtime, mas nao estavam na baseline
Alembic. Todas as operacoes estruturais verificam o estado atual para que a
migration funcione tanto em instalacoes novas quanto em bancos legados que ja
receberam parte dessas mudancas pelo antigo DDL de startup.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _columns(table_name: str) -> dict[str, dict]:
    return {column["name"]: column for column in _inspector().get_columns(table_name)}


def _indexes(table_name: str) -> dict[str, dict]:
    return {
        index["name"]: index
        for index in _inspector().get_indexes(table_name)
        if index.get("name")
    }


def _unique_names(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in _inspector().get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _unique_constraints(table_name: str) -> dict[str, dict]:
    return {
        constraint["name"]: constraint
        for constraint in _inspector().get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _quote(identifier: str) -> str:
    return op.get_bind().dialect.identifier_preparer.quote(identifier)


def _assert_unique_rows(table_name: str, columns: list[str], constraint_name: str) -> None:
    quoted_columns = [_quote(column) for column in columns]
    # PostgreSQL UNIQUE permite repeticao quando qualquer componente e NULL.
    not_null = " AND ".join(f"{column} IS NOT NULL" for column in quoted_columns)
    group_by = ", ".join(quoted_columns)
    duplicate = op.get_bind().execute(
        sa.text(
            f"""
            SELECT 1
            FROM {_quote(table_name)}
            WHERE {not_null}
            GROUP BY {group_by}
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            f"Nao foi possivel criar {constraint_name}: existem valores duplicados "
            f"em {table_name}({', '.join(columns)}). Nenhuma linha foi removida."
        )


def _assert_no_orphans(
    table_name: str,
    columns: list[str],
    referred_table: str,
    referred_columns: list[str],
    constraint_name: str,
) -> None:
    source_columns = [_quote(column) for column in columns]
    target_columns = [_quote(column) for column in referred_columns]
    join = " AND ".join(
        f"source.{source} = target.{target}"
        for source, target in zip(source_columns, target_columns)
    )
    populated = " AND ".join(f"source.{column} IS NOT NULL" for column in source_columns)
    missing_target = " AND ".join(f"target.{column} IS NULL" for column in target_columns)
    orphan = op.get_bind().execute(
        sa.text(
            f"""
            SELECT 1
            FROM {_quote(table_name)} AS source
            LEFT JOIN {_quote(referred_table)} AS target ON {join}
            WHERE {populated} AND {missing_target}
            LIMIT 1
            """
        )
    ).first()
    if orphan:
        raise RuntimeError(
            f"Nao foi possivel criar {constraint_name}: existem referencias orfas "
            f"em {table_name}({', '.join(columns)}). Nenhuma linha foi removida."
        )


def _create_index_if_missing(
    name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    current = _indexes(table_name).get(name)
    if current:
        if current.get("column_names") == columns and bool(current.get("unique")) is unique:
            return
        if current.get("duplicates_constraint") or name in _unique_names(table_name):
            raise RuntimeError(
                f"{name} e associado a uma constraint e nao pode ser normalizado "
                "automaticamente."
            )
        op.drop_index(name, table_name=table_name)
    op.create_index(name, table_name, columns, unique=unique)


def _create_unique_if_missing(name: str, table_name: str, columns: list[str]) -> None:
    current = _unique_constraints(table_name).get(name)
    if current:
        if current.get("column_names") == columns:
            return
        raise RuntimeError(
            f"{name} existe com colunas diferentes das esperadas; "
            "a migration nao remove constraints de dados automaticamente."
        )

    _assert_unique_rows(table_name, columns, name)
    existing_index = _indexes(table_name).get(name)
    if existing_index:
        if (
            not existing_index.get("unique")
            or existing_index.get("column_names") != columns
            or existing_index.get("duplicates_constraint")
            or existing_index.get("dialect_options", {}).get("postgresql_where")
        ):
            raise RuntimeError(
                f"{name} existe como indice incompativel; "
                "a migration nao o remove automaticamente."
            )
        # Converte o indice UNIQUE legado em constraint sem apagar/recriar o
        # indice e sem abrir uma janela sem garantia de unicidade.
        op.execute(
            sa.text(
                f"ALTER TABLE {_quote(table_name)} "
                f"ADD CONSTRAINT {_quote(name)} UNIQUE USING INDEX {_quote(name)}"
            )
        )
        return

    op.create_unique_constraint(name, table_name, columns)


def _drop_standalone_index_if_present(name: str, table_name: str) -> None:
    current = _indexes(table_name).get(name)
    if not current:
        return
    if current.get("duplicates_constraint") or name in _unique_names(table_name):
        raise RuntimeError(
            f"{name} pertence a uma constraint e nao sera removido como indice."
        )
    op.drop_index(name, table_name=table_name)


def _create_foreign_key_if_missing(
    name: str,
    table_name: str,
    columns: list[str],
    referred_table: str,
    referred_columns: list[str],
) -> None:
    for foreign_key in _inspector().get_foreign_keys(table_name):
        if foreign_key.get("constrained_columns") != columns:
            continue
        if (
            foreign_key.get("referred_table") == referred_table
            and foreign_key.get("referred_columns") == referred_columns
        ):
            return
        raise RuntimeError(
            f"{table_name}({', '.join(columns)}) ja possui uma foreign key "
            "para outro destino; nenhuma constraint foi removida."
        )

    _assert_no_orphans(
        table_name,
        columns,
        referred_table,
        referred_columns,
        name,
    )
    op.create_foreign_key(
        name,
        table_name,
        referred_table,
        columns,
        referred_columns,
    )


def _normalize_text_column(table_name: str, column_name: str) -> None:
    column = _columns(table_name)[column_name]
    if isinstance(column["type"], sa.Text):
        return
    op.alter_column(
        table_name,
        column_name,
        existing_type=column["type"],
        type_=sa.Text(),
        existing_nullable=column["nullable"],
        postgresql_using=f"{_quote(column_name)}::text",
    )


def _create_notificacoes() -> None:
    if not _inspector().has_table("notificacoes"):
        op.create_table(
            "notificacoes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("estabelecimento_id", sa.Integer(), nullable=False),
            sa.Column(
                "agendamento_id",
                sa.Integer(),
                sa.ForeignKey("agendamentos.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("tipo", sa.String(length=40), nullable=False),
            sa.Column("titulo", sa.String(length=255), nullable=False),
            sa.Column("corpo", sa.Text(), nullable=True),
            sa.Column("lida", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("criada_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("lida_em", sa.DateTime(), nullable=True),
        )

    _create_index_if_missing("ix_notificacoes_id", "notificacoes", ["id"])
    _create_index_if_missing(
        "ix_notificacoes_estabelecimento_id",
        "notificacoes",
        ["estabelecimento_id"],
    )
    _create_index_if_missing(
        "ix_notificacoes_agendamento_id",
        "notificacoes",
        ["agendamento_id"],
    )
    _create_index_if_missing(
        "ix_notificacoes_tenant_lida_criada",
        "notificacoes",
        ["estabelecimento_id", "lida", "criada_em"],
    )


def _migrate_payment_oauth_states() -> None:
    table_name = "payment_oauth_states"
    columns = _columns(table_name)

    if "user_sub" not in columns:
        op.add_column(table_name, sa.Column("user_sub", sa.String(length=255), nullable=True))
    if "state" not in columns:
        op.add_column(table_name, sa.Column("state", sa.String(length=255), nullable=True))
    if "consumed_at" not in columns:
        op.add_column(table_name, sa.Column("consumed_at", sa.DateTime(), nullable=True))

    columns = _columns(table_name)
    if "state_token" in columns:
        op.execute(
            "UPDATE payment_oauth_states "
            "SET state = COALESCE(state, state_token) "
            "WHERE state IS NULL"
        )
    else:
        op.execute(
            "UPDATE payment_oauth_states "
            "SET state = CONCAT('legacy-', id) "
            "WHERE state IS NULL"
        )
    if "used_at" in columns:
        op.execute(
            "UPDATE payment_oauth_states "
            "SET consumed_at = COALESCE(consumed_at, used_at) "
            "WHERE consumed_at IS NULL"
        )

    # Estados OAuth sao efemeros. Linhas sem tenant/estado nao podem ser
    # consumidas com seguranca e sao descartadas antes dos NOT NULL.
    op.execute(
        "DELETE FROM payment_oauth_states "
        "WHERE establishment_id IS NULL OR state IS NULL"
    )

    columns = _columns(table_name)
    if columns["state"]["nullable"]:
        op.alter_column(
            table_name,
            "state",
            existing_type=sa.String(length=255),
            nullable=False,
        )
    if columns["establishment_id"]["nullable"]:
        op.alter_column(
            table_name,
            "establishment_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    _create_index_if_missing(
        "ix_payment_oauth_states_establishment_id",
        table_name,
        ["establishment_id"],
    )
    _create_index_if_missing("ix_payment_oauth_states_state", table_name, ["state"])
    _create_unique_if_missing(
        "ux_payment_oauth_states_provider_state",
        table_name,
        ["provider", "state"],
    )

    columns = _columns(table_name)
    if "state_token" in columns:
        op.drop_column(table_name, "state_token")
    if "used_at" in columns:
        op.drop_column(table_name, "used_at")


def _migrate_reminder_jobs() -> None:
    table_name = "reminder_jobs"
    columns = _columns(table_name)
    additions = (
        ("canal", sa.Column("canal", sa.String(length=20), nullable=True)),
        ("destinatario", sa.Column("destinatario", sa.String(length=30), nullable=True)),
        ("mensagem", sa.Column("mensagem", sa.Text(), nullable=True)),
        ("enviado_em", sa.Column("enviado_em", sa.DateTime(), nullable=True)),
        ("status", sa.Column("status", sa.String(length=20), nullable=True)),
        ("tentativas", sa.Column("tentativas", sa.Integer(), nullable=True)),
        ("ultimo_erro", sa.Column("ultimo_erro", sa.String(length=255), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column(table_name, column)

    columns = _columns(table_name)
    enviado_expression = "COALESCE(r.enviado, false)" if "enviado" in columns else "false"
    op.execute(
        sa.text(
            f"""
            UPDATE reminder_jobs AS r
            SET estabelecimento_id = COALESCE(r.estabelecimento_id, a.estabelecimento_id),
                canal = COALESCE(r.canal, 'whatsapp'),
                destinatario = COALESCE(NULLIF(r.destinatario, ''), NULLIF(a.cliente_telefone, ''), 'indisponivel'),
                mensagem = COALESCE(NULLIF(r.mensagem, ''), 'Lembrete de agendamento'),
                enviado_em = CASE
                    WHEN {enviado_expression} THEN COALESCE(r.enviado_em, r.criado_em, NOW())
                    ELSE r.enviado_em
                END,
                status = COALESCE(r.status, CASE WHEN {enviado_expression} THEN 'enviado' ELSE 'pendente' END),
                tentativas = COALESCE(r.tentativas, CASE WHEN {enviado_expression} THEN 1 ELSE 0 END)
            FROM agendamentos AS a
            WHERE a.id = r.agendamento_id
            """
        )
    )
    op.execute(
        """
        UPDATE reminder_jobs
        SET canal = COALESCE(canal, 'whatsapp'),
            destinatario = COALESCE(NULLIF(destinatario, ''), 'indisponivel'),
            mensagem = COALESCE(NULLIF(mensagem, ''), 'Lembrete de agendamento'),
            status = COALESCE(status, 'pendente'),
            tentativas = COALESCE(tentativas, 0)
        """
    )
    # Jobs orfaos nao sao processaveis e impediriam o isolamento por tenant.
    op.execute("DELETE FROM reminder_jobs WHERE estabelecimento_id IS NULL")

    columns = _columns(table_name)
    for name, type_ in (
        ("estabelecimento_id", sa.Integer()),
        ("canal", sa.String(length=20)),
        ("destinatario", sa.String(length=30)),
        ("mensagem", sa.Text()),
        ("status", sa.String(length=20)),
        ("tentativas", sa.Integer()),
    ):
        if columns[name]["nullable"]:
            op.alter_column(table_name, name, existing_type=type_, nullable=False)

    tipo = columns["tipo"]["type"]
    if getattr(tipo, "length", None) != 20:
        op.alter_column(
            table_name,
            "tipo",
            existing_type=tipo,
            type_=sa.String(length=20),
            existing_nullable=False,
        )

    # Mantem um unico job por agendamento/tipo antes da constraint.
    op.execute(
        """
        DELETE FROM reminder_jobs AS duplicate
        USING reminder_jobs AS keeper
        WHERE duplicate.agendamento_id = keeper.agendamento_id
          AND duplicate.tipo = keeper.tipo
          AND duplicate.id > keeper.id
        """
    )
    _create_index_if_missing("ix_reminder_jobs_criado_em", table_name, ["criado_em"])
    _create_index_if_missing(
        "ix_reminder_jobs_status_enviar_em",
        table_name,
        ["status", "enviar_em"],
    )
    _create_unique_if_missing(
        "ux_reminder_jobs_agendamento_tipo",
        table_name,
        ["agendamento_id", "tipo"],
    )

    if "enviado" in _columns(table_name):
        op.drop_column(table_name, "enviado")


def _migrate_webhook_events() -> None:
    table_name = "webhook_events"
    columns = _columns(table_name)
    additions = (
        ("provider", sa.Column("provider", sa.String(length=50), nullable=True)),
        ("event_id", sa.Column("event_id", sa.String(length=255), nullable=True)),
        ("tenant_id", sa.Column("tenant_id", sa.Integer(), nullable=True)),
        ("criado_em", sa.Column("criado_em", sa.DateTime(), nullable=True)),
        ("legacy_payload", sa.Column("legacy_payload", sa.JSON(), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column(table_name, column)

    columns = _columns(table_name)
    tenant_source = "estabelecimento_id" if "estabelecimento_id" in columns else "tenant_id"
    created_source = "created_at" if "created_at" in columns else "criado_em"
    op.execute(
        f"""
        UPDATE webhook_events
        SET provider = COALESCE(provider, 'legacy'),
            event_id = COALESCE(event_id, CONCAT('legacy-', id)),
            tenant_id = COALESCE(tenant_id, {tenant_source}),
            criado_em = COALESCE(criado_em, {created_source}, NOW())
        """
    )

    columns = _columns(table_name)
    for name, type_ in (
        ("provider", sa.String(length=50)),
        ("event_id", sa.String(length=255)),
        ("criado_em", sa.DateTime()),
    ):
        if columns[name]["nullable"]:
            op.alter_column(table_name, name, existing_type=type_, nullable=False)

    columns = _columns(table_name)
    if any(
        legacy_column in columns
        for legacy_column in ("event_type", "payload", "processed", "created_at")
    ):
        event_type = "event_type" if "event_type" in columns else "NULL"
        payload = "payload" if "payload" in columns else "NULL"
        processed = "processed" if "processed" in columns else "NULL"
        created_at = "created_at" if "created_at" in columns else "NULL"
        op.execute(
            f"""
            UPDATE webhook_events
            SET legacy_payload = COALESCE(
                legacy_payload::jsonb,
                jsonb_strip_nulls(
                    jsonb_build_object(
                        'event_type', {event_type},
                        'payload', {payload},
                        'processed', {processed},
                        'created_at', {created_at}
                    )
                )
            )::json
            """
        )

    _create_index_if_missing("ix_webhook_events_provider", table_name, ["provider"])
    _create_index_if_missing("ix_webhook_events_event_id", table_name, ["event_id"])
    _create_index_if_missing("ix_webhook_events_tenant_id", table_name, ["tenant_id"])
    _create_index_if_missing("ix_webhook_events_criado_em", table_name, ["criado_em"])
    _create_unique_if_missing(
        "ux_webhook_events_provider_event_id",
        table_name,
        ["provider", "event_id"],
    )

    for legacy_column in (
        "estabelecimento_id",
        "event_type",
        "payload",
        "processed",
        "created_at",
    ):
        if legacy_column in _columns(table_name):
            op.drop_column(table_name, legacy_column)


def _normalize_legacy_metadata() -> None:
    """Converge objetos legados para a mesma metadata da baseline nova.

    Os DDLs antigos criaram parte das garantias como indices UNIQUE, enquanto
    os modelos atuais as representam como constraints mais indices comuns.
    Esta normalizacao nao remove linhas para forcar constraints: duplicidades
    ou referencias orfas interrompem a migration com uma mensagem explicita.
    """

    _normalize_text_column("admin_mfa_settings", "secret_encrypted")
    _normalize_text_column("admin_mfa_settings", "pending_secret_encrypted")

    _create_unique_if_missing(
        "ux_agendamentos_confirmation_token",
        "agendamentos",
        ["confirmation_token"],
    )
    _create_index_if_missing(
        "ix_agendamentos_confirmation_token",
        "agendamentos",
        ["confirmation_token"],
    )

    _create_index_if_missing("ix_clientes_email", "clientes", ["email"])
    _create_unique_if_missing(
        "ux_clientes_estabelecimento_telefone",
        "clientes",
        ["estabelecimento_id", "telefone"],
    )

    _create_index_if_missing("ix_conversas_tenant_id", "conversas", ["tenant_id"])
    _create_index_if_missing(
        "ix_conversas_tenant_ativa",
        "conversas",
        ["tenant_id", "ativa"],
    )
    _create_unique_if_missing(
        "ux_conversas_tenant_telefone",
        "conversas",
        ["tenant_id", "telefone"],
    )

    for constraint_name, index_name, column_name in (
        ("ux_estabelecimentos_slug", "ix_estabelecimentos_slug", "slug"),
        (
            "uq_estabelecimentos_mega_instance_key",
            "ix_estabelecimentos_mega_instance_key",
            "mega_instance_key",
        ),
        (
            "uq_estabelecimentos_whatsapp_number",
            "ix_estabelecimentos_whatsapp_number",
            "whatsapp_number",
        ),
    ):
        _create_unique_if_missing(
            constraint_name,
            "estabelecimentos",
            [column_name],
        )
        _create_index_if_missing(
            index_name,
            "estabelecimentos",
            [column_name],
        )

    _create_unique_if_missing(
        "pagamentos_agendamento_id_key",
        "pagamentos",
        ["agendamento_id"],
    )
    _create_unique_if_missing(
        "ux_pagamentos_external_reference",
        "pagamentos",
        ["external_reference"],
    )
    _create_unique_if_missing(
        "ux_pagamentos_idempotency_key",
        "pagamentos",
        ["idempotency_key"],
    )
    _create_index_if_missing(
        "ix_pagamentos_agendamento_id",
        "pagamentos",
        ["agendamento_id"],
    )
    _create_index_if_missing("ix_pagamentos_expires_at", "pagamentos", ["expires_at"])
    _drop_standalone_index_if_present(
        "ix_pagamentos_external_reference",
        "pagamentos",
    )
    _drop_standalone_index_if_present(
        "ix_pagamentos_idempotency_key",
        "pagamentos",
    )

    _create_index_if_missing("ix_profissionais_ativo", "profissionais", ["ativo"])

    _create_foreign_key_if_missing(
        "pagamentos_payment_integration_id_fkey",
        "pagamentos",
        ["payment_integration_id"],
        "payment_integrations",
        ["id"],
    )
    _create_foreign_key_if_missing(
        "payment_oauth_states_establishment_id_fkey",
        "payment_oauth_states",
        ["establishment_id"],
        "estabelecimentos",
        ["id"],
    )
    _create_foreign_key_if_missing(
        "reminder_jobs_estabelecimento_id_fkey",
        "reminder_jobs",
        ["estabelecimento_id"],
        "estabelecimentos",
        ["id"],
    )


def upgrade() -> None:
    _create_notificacoes()
    _migrate_payment_oauth_states()
    _migrate_reminder_jobs()
    _migrate_webhook_events()
    _create_index_if_missing(
        "ix_pagamentos_external_merchant_order_id",
        "pagamentos",
        ["external_merchant_order_id"],
    )
    _normalize_legacy_metadata()


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade nao suportado: esta revisao reconcilia schemas legados "
        "heterogeneos. Para reverter, restaure um backup validado."
    )
