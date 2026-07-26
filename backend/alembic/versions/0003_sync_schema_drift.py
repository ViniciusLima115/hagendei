"""sync schema drift

Reconcilia o schema real de producao (criado antes da consolidacao em
Alembic, via DDL best-effort em app/database.py) com o estado atual dos
modelos ORM. agendamentos.barbearia_id e conversas.estabelecimento_id nao
sao renomeadas — ambas ja coexistem fisicamente ao lado da coluna nova
(estabelecimento_id/tenant_id, respectivamente) por causa de uma migracao
manual antiga que nunca limpou a coluna velha; confirmado por consulta
direta que barbearia_id esta 100% NULL (11/11 linhas) e conversas tem 0
linhas, entao o drop da coluna orfa e seguro. Colunas/tabelas removidas
foram confirmadas vazias em producao antes de escrever esta migration
(payment_admin_audit_logs, payment_accounts.*,
payment_oauth_states.code_verifier,
estabelecimentos.pagamento_adiantado_obrigatorio/advance_payment_*/
payment_default_provider). NULLs pre-existentes em agendamentos.updated_at
e servicos.updated_at sao preenchidos antes de aplicar NOT NULL.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Backfill de NULLs antes de qualquer NOT NULL (dados reais confirmados) ---
    # Nem agendamentos nem servicos tem uma coluna separada de "criado em" —
    # so existe updated_at. Para as poucas linhas legadas sem valor, usa NOW()
    # como melhor aproximacao disponivel (nao ha logica de negocio que dependa
    # do valor historico exato desses registros).
    op.execute("UPDATE agendamentos SET updated_at = NOW() WHERE updated_at IS NULL")
    op.execute("UPDATE servicos SET updated_at = NOW() WHERE updated_at IS NULL")

    # --- 2. Colunas duplicadas legadas (nao e renomeacao — as duas colunas ja
    # coexistem fisicamente, confirmado por consulta direta antes de escrever
    # esta migration) ---
    # agendamentos: barbearia_id e uma coluna morta, 100% NULL nas 11 linhas
    # atuais; estabelecimento_id (ja populada em todas) e a coluna real usada
    # pelo modelo. Drop da coluna morta cascade-remove seu indice associado
    # (ix_agendamentos_barbearia_id), por isso esse indice nao aparece na
    # secao 8 abaixo.
    op.drop_column("agendamentos", "barbearia_id")
    # conversas: mesma duplicidade, mas a tabela tem 0 linhas hoje — sem risco
    # de dado. O modelo usa tenant_id; estabelecimento_id e a coluna orfa
    # aqui. O drop cascade-remove os 3 indices que a referenciam
    # (ix_conversas_tenant_id, ix_conversas_tenant_ativa,
    # ux_conversas_tenant_telefone) — recriados na secao 8, apontando para
    # tenant_id.
    op.drop_column("conversas", "estabelecimento_id")

    # --- 3. Tabelas novas (confirmado ausentes em producao) ---
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_user_id", sa.String(120), nullable=False),
        sa.Column("establishment_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=True),
        sa.Column("ip_address", sa.String(80), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_admin_audit_logs_admin_user_id", "admin_audit_logs", ["admin_user_id"])
    op.create_index("ix_admin_audit_logs_establishment_id", "admin_audit_logs", ["establishment_id"])
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_entity", "admin_audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])

    op.create_table(
        "payment_integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("establishment_id", sa.Integer(), sa.ForeignKey("estabelecimentos.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="mercadopago"),
        sa.Column("environment", sa.String(20), nullable=False, server_default="production"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_validation"),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("credentials_fingerprint", sa.String(64), nullable=True),
        sa.Column("public_metadata_encrypted", sa.Text(), nullable=True),
        sa.Column("account_name", sa.String(120), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("checkout_hold_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("last_validated_at", sa.DateTime(), nullable=True),
        sa.Column("validation_status", sa.String(30), nullable=False, server_default="not_validated"),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.String(120), nullable=True),
        sa.Column("updated_by_admin_id", sa.String(120), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint(
            "establishment_id", "provider", "environment",
            name="ux_payment_integrations_establishment_provider_environment",
        ),
        sa.UniqueConstraint(
            "provider", "environment", "credentials_fingerprint",
            name="ux_payment_integrations_provider_environment_fingerprint",
        ),
    )
    op.create_index("ix_payment_integrations_establishment_id", "payment_integrations", ["establishment_id"])
    op.create_index("ix_payment_integrations_provider", "payment_integrations", ["provider"])
    op.create_index("ix_payment_integrations_environment", "payment_integrations", ["environment"])
    op.create_index("ix_payment_integrations_status", "payment_integrations", ["status"])
    op.create_index("ix_payment_integrations_validation_status", "payment_integrations", ["validation_status"])

    # --- 4. Colunas novas (aditivas) ---
    op.add_column("agendamentos", sa.Column("confirmation_token_expires_at", sa.DateTime(), nullable=True))
    op.add_column(
        "estabelecimentos",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pagamentos",
        sa.Column("payment_integration_id", sa.Integer(), sa.ForeignKey("payment_integrations.id"), nullable=True),
    )
    op.create_index("ix_pagamentos_payment_integration_id", "pagamentos", ["payment_integration_id"])

    # --- 5. Colunas/tabela removidas (confirmado 0 linhas com dado real em producao) ---
    op.drop_table("payment_admin_audit_logs")
    op.drop_column("estabelecimentos", "pagamento_adiantado_obrigatorio")
    op.drop_column("estabelecimentos", "advance_payment_type")
    op.drop_column("estabelecimentos", "advance_payment_amount")
    op.drop_column("estabelecimentos", "payment_default_provider")
    op.drop_column("payment_accounts", "provider_account_email")
    op.drop_column("payment_accounts", "provider_account_id")
    op.drop_column("payment_accounts", "expires_at")
    op.drop_column("payment_accounts", "connected_at")
    op.drop_column("payment_accounts", "disconnected_at")
    op.drop_column("payment_accounts", "public_key")
    op.drop_column("payment_oauth_states", "code_verifier")

    # --- 6. Ajustes de tipo (todos seguros: widening ou float->numeric com precisao adequada pra valores monetarios) ---
    op.alter_column("estabelecimentos", "mega_token", type_=sa.Text())
    op.alter_column(
        "agendamentos", "payment_amount_snapshot",
        type_=sa.Numeric(12, 2),
        postgresql_using="payment_amount_snapshot::numeric(12,2)",
    )
    op.alter_column(
        "pagamentos", "amount",
        type_=sa.Numeric(12, 2),
        postgresql_using="amount::numeric(12,2)",
    )
    op.alter_column(
        "pagamentos", "platform_fee_amount",
        type_=sa.Numeric(12, 2),
        postgresql_using="platform_fee_amount::numeric(12,2)",
    )
    op.alter_column(
        "servicos", "preco",
        type_=sa.Numeric(12, 2),
        postgresql_using="preco::numeric(12,2)",
    )
    op.alter_column(
        "servicos", "advance_payment_amount",
        type_=sa.Numeric(12, 2),
        postgresql_using="advance_payment_amount::numeric(12,2)",
    )

    # --- 7. NOT NULL (dados verificados sem NULL antes, ou preenchidos no passo 1) ---
    op.alter_column("agendamentos", "confirmation_token", nullable=False)
    op.alter_column("agendamentos", "updated_at", nullable=False)
    op.alter_column("servicos", "updated_at", nullable=False)

    # --- 8. Higiene de nomes de indice (cosmetico, sem impacto em dados) ---
    op.drop_index("ix_barbearias_id", table_name="estabelecimentos")
    op.drop_index("ix_barbearias_mega_instance_key", table_name="estabelecimentos")
    op.drop_index("ix_barbearias_slug", table_name="estabelecimentos")
    op.drop_index("ix_barbearias_whatsapp_number", table_name="estabelecimentos")
    op.drop_index("ux_barbearias_slug", table_name="estabelecimentos")
    op.create_index("ix_estabelecimentos_id", "estabelecimentos", ["id"])
    op.create_index("ix_estabelecimentos_mega_instance_key", "estabelecimentos", ["mega_instance_key"], unique=True)
    op.create_index("ix_estabelecimentos_slug", "estabelecimentos", ["slug"], unique=True)
    op.create_index("ix_estabelecimentos_whatsapp_number", "estabelecimentos", ["whatsapp_number"], unique=True)

    op.drop_index("ix_barbeiros_ativo", table_name="profissionais")
    op.drop_index("ix_barbeiros_barbershop_id", table_name="profissionais")
    op.drop_index("ix_barbeiros_id", table_name="profissionais")
    op.create_index("ix_profissionais_estabelecimento_id", "profissionais", ["estabelecimento_id"])
    op.create_index("ix_profissionais_id", "profissionais", ["id"])

    # ix_agendamentos_barbearia_id ja foi removido em cascata pelo drop_column
    # da secao 2 — nao chamar drop_index de novo aqui (daria "does not exist").
    op.drop_index("ux_agendamentos_confirmation_token", table_name="agendamentos")
    # unique=True e obrigatorio aqui: confirmation_token e Column(unique=True, index=True)
    # no modelo — perder a unicidade removeria a garantia que impede dois agendamentos
    # compartilharem o mesmo token de confirmacao.
    op.create_index("ix_agendamentos_confirmation_token", "agendamentos", ["confirmation_token"], unique=True)
    op.create_index("ix_agendamentos_estabelecimento_id", "agendamentos", ["estabelecimento_id"])
    op.create_index("ix_agendamentos_pagamento_adiantado_exigido", "agendamentos", ["pagamento_adiantado_exigido"])

    op.drop_index("ix_servicos_barbearia_id", table_name="servicos")
    op.create_index("ix_servicos_estabelecimento_id", "servicos", ["estabelecimento_id"])

    op.drop_index("ix_reminder_jobs_tenant_id", table_name="reminder_jobs")
    op.create_index("ix_reminder_jobs_estabelecimento_id", "reminder_jobs", ["estabelecimento_id"])

    op.drop_index("ix_clientes_email", table_name="clientes")
    op.drop_index("ux_clientes_barbearia_telefone", table_name="clientes")

    # conversas: recriar os 3 indices cascade-removidos junto com a coluna
    # estabelecimento_id na secao 2, agora apontando para tenant_id (nome que
    # o modelo Conversa usa). Nenhum tem unique=True exceto o de telefone,
    # que precisa ser UNIQUE CONSTRAINT (nao so indice) para bater com
    # UniqueConstraint("tenant_id", "telefone") no modelo.
    op.create_index("ix_conversas_tenant_id", "conversas", ["tenant_id"])
    op.create_index("ix_conversas_tenant_ativa", "conversas", ["tenant_id", "ativa"])
    op.create_unique_constraint("ux_conversas_tenant_telefone", "conversas", ["tenant_id", "telefone"])

    # NAO tocar em "ux_pagamentos_idempotency_key": idempotency_key e
    # Column(unique=True, index=True) no modelo — essa unicidade e a garantia
    # de idempotencia de checkout (H-05 na auditoria de seguranca). O nome
    # fisico difere do padrao ix_ que o SQLAlchemy geraria hoje, mas isso e
    # so cosmetico; nao vale o risco de recriar errado numa tabela de
    # pagamento. Deixar como esta.
    op.drop_index("ix_pagamentos_expires_at", table_name="pagamentos")

    # NAO chamar drop_index para "ux_payment_accounts_provider_account_id":
    # o DROP COLUMN provider_account_id acima ja remove esse indice
    # automaticamente (ele dependia so dessa coluna); chamar de novo aqui
    # daria erro de "index does not exist" e abortaria a migration inteira.


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade nao suportado para esta migration — envolve renomeacoes e "
        "remocao de colunas com dados reais de producao. Restaurar via backup "
        "se necessario reverter."
    )
