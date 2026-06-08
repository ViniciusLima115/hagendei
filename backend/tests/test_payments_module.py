from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta

import pytest

from app.models.agendamento import Agendamento
from app.models.estabelecimento import Estabelecimento
from app.models.pagamento import Pagamento
from app.models.payment_account import PaymentAccount
from app.models.payment_admin_audit_log import PaymentAdminAuditLog
from app.models.payment_oauth_state import PaymentOAuthState
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.models.profissional import Profissional
from app.models.servico import Servico
from app.services.payments import payment_account_service, payment_service, webhook_service
from app.services.payments.constants import (
    PAYMENT_ACCOUNT_STATUS_CONNECTED,
    PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
    PAYMENT_ACCOUNT_STATUS_ERROR,
    PAYMENT_ACCOUNT_STATUS_EXPIRED,
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_PROVIDER_PICPAY,
)
from app.services.payments.crypto import decrypt_sensitive_value, encrypt_sensitive_value
from app.services.payments.providers.base import PaymentTokenRefreshError
from app.services.payments.provider_factory import get_payment_provider as factory_get_payment_provider


@pytest.fixture(autouse=True)
def payment_crypto_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENCRYPTION_KEY", "12345678901234567890123456789012")


class DummyProvider:
    def __init__(self):
        self.webhook_calls = 0
        self.exchange_calls = 0
        self.checkout_calls = 0
        self.refresh_calls = 0
        self.validation_calls = 0
        self.last_checkout: dict | None = None
        self.last_validated_access_token: str | None = None

    def build_connect_url(self, *, state: str, code_challenge: str | None = None) -> str:
        if code_challenge:
            return f"https://dummy.example/oauth?state={state}&code_challenge={code_challenge}"
        return f"https://dummy.example/oauth?state={state}"

    def exchange_oauth_code(self, *, code: str, code_verifier: str | None = None):
        self.exchange_calls += 1
        return {
            "access_token": "mp-access-token",
            "refresh_token": "mp-refresh-token",
            "public_key": "mp-public-key",
            "token_expires_at": datetime.utcnow() + timedelta(hours=1),
            "external_user_id": f"user-{code}",
            "external_account_email": "owner@example.com",
        }

    def refresh_access_token(self, *, refresh_token: str):
        self.refresh_calls += 1
        return {
            "access_token": "mp-access-token-refreshed",
            "refresh_token": "mp-refresh-token-refreshed",
            "public_key": "mp-public-key-refreshed",
            "token_expires_at": datetime.utcnow() + timedelta(hours=1),
        }

    def validate_access_token(self, *, access_token: str):
        self.validation_calls += 1
        self.last_validated_access_token = access_token
        return {
            "provider_account_id": None,
            "provider_account_email": "owner@example.com",
        }

    def create_checkout(
        self,
        *,
        access_token: str,
        external_reference: str,
        title: str,
        description: str,
        amount: float,
        payer_email: str | None,
        payer_name: str | None,
        payer_phone: str | None,
        metadata: dict,
        notification_url: str,
        back_urls: dict | None,
        expires_at: datetime | None,
    ):
        self.checkout_calls += 1
        self.last_checkout = {
            "access_token": access_token,
            "external_reference": external_reference,
            "metadata": metadata,
            "notification_url": notification_url,
            "back_urls": back_urls,
            "expires_at": expires_at,
        }
        return {
            "preference_id": f"pref-{external_reference}",
            "checkout_url": f"https://dummy.example/checkout/{external_reference}",
            "raw": {
                "external_reference": external_reference,
                "amount": amount,
                "notification_url": notification_url,
                "back_urls": back_urls,
            },
        }

    def get_payment(self, *, access_token: str, payment_id: str):
        self.webhook_calls += 1
        return {
            "id": payment_id,
            "status": "approved",
            "external_reference": "",
            "payment_method_id": "pix",
        }

    def refund_payment(self, *, access_token: str, payment_id: str):
        return {"id": payment_id, "status": "refunded"}



def _patch_providers(monkeypatch: pytest.MonkeyPatch, provider: DummyProvider):
    monkeypatch.setattr(payment_account_service, "get_payment_provider", lambda _provider: provider)
    monkeypatch.setattr(payment_service, "get_payment_provider", lambda _provider: provider)
    monkeypatch.setattr(webhook_service, "get_payment_provider", lambda _provider: provider)



def _seed_tenant_bundle(db_session, *, tenant_name: str, require_advance_payment: bool):
    tenant = Estabelecimento(nome=tenant_name, endereco="Rua A, 1", plano="premium")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    profissional = Profissional(nome=f"Prof {tenant_name}", estabelecimento_id=tenant.id)
    servico = Servico(
        nome=f"Servico {tenant_name}",
        duracao_minutos=40,
        preco=100.0,
        estabelecimento_id=tenant.id,
        pagamento_adiantado_obrigatorio=require_advance_payment,
        advance_payment_type="full" if require_advance_payment else None,
    )
    db_session.add_all([profissional, servico])
    db_session.commit()
    db_session.refresh(profissional)
    db_session.refresh(servico)

    return tenant, profissional, servico



def _create_active_payment_account(
    db_session,
    *,
    tenant_id: int,
    provider_account_id: str = "mp-user-1",
    access_token: str = "token-active",
    refresh_token: str = "token-refresh",
):
    account = PaymentAccount(
        establishment_id=tenant_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        provider_account_id=provider_account_id,
        provider_account_email="owner@example.com",
        access_token_encrypted=encrypt_sensitive_value(access_token) or "",
        refresh_token_encrypted=encrypt_sensitive_value(refresh_token),
        public_key="public-key",
        status=PAYMENT_ACCOUNT_STATUS_CONNECTED,
        checkout_hold_minutes=10,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def _create_active_picpay_account(
    db_session,
    *,
    tenant_id: int,
    provider_account_id: str = "picpay-user-1",
    access_token: str = "picpay-token-active",
    seller_token: str = "picpay-seller-token",
):
    account = PaymentAccount(
        establishment_id=tenant_id,
        provider=PAYMENT_PROVIDER_PICPAY,
        provider_account_id=provider_account_id,
        provider_account_email="picpay-owner@example.com",
        access_token_encrypted=encrypt_sensitive_value(access_token) or "",
        refresh_token_encrypted=encrypt_sensitive_value(seller_token),
        status=PAYMENT_ACCOUNT_STATUS_CONNECTED,
        checkout_hold_minutes=10,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


def _create_pending_payment_booking(
    db_session,
    *,
    tenant_id: int,
    profissional_id: int,
    servico_id: int,
    payment_account_id: int | None = None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    suffix: str = "pending",
):
    booking = Agendamento(
        cliente_id=1,
        profissional_id=profissional_id,
        servico_id=servico_id,
        estabelecimento_id=tenant_id,
        cliente_nome=f"Cliente {suffix}",
        cliente_telefone=f"1199999{suffix[-4:].zfill(4)}",
        data_hora_inicio=datetime.utcnow() + timedelta(days=1),
        data_hora_fim=datetime.utcnow() + timedelta(days=1, minutes=40),
        status="pending_payment",
        pagamento_adiantado_exigido=True,
        payment_required_snapshot=True,
        payment_status="pending",
        payment_type_snapshot="full",
        payment_amount_snapshot=100.0,
        payment_hold_expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    payment = Pagamento(
        agendamento_id=booking.id,
        estabelecimento_id=tenant_id,
        payment_account_id=payment_account_id,
        provider=provider,
        idempotency_key=f"idempotency-{suffix}-{booking.id}",
        external_reference=f"booking:{booking.id}:{suffix}",
        amount=100.0,
        status="pending",
        checkout_url=f"https://dummy.example/checkout/booking-{booking.id}-{suffix}",
        expires_at=booking.payment_hold_expires_at,
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)
    return booking, payment



def _tenant_headers(make_tenant_headers, tenant_id: int):
    return make_tenant_headers(tenant_id)


def _mp_signature(*, secret: str, data_id: str, request_id: str, timestamp: str = "1700000000") -> str:
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={timestamp},v1={digest}"


def _approved_provider_payment_payload(
    payment: Pagamento,
    *,
    provider_payment_id: str,
    provider_account_id: str,
    amount: float | None = None,
    metadata: dict | None = None,
    external_reference: str | None = None,
):
    return {
        "id": provider_payment_id,
        "status": "approved",
        "external_reference": external_reference if external_reference is not None else payment.external_reference,
        "transaction_amount": amount if amount is not None else payment.amount,
        "collector_id": provider_account_id,
        "payment_method_id": "pix",
        "metadata": metadata
        if metadata is not None
        else {
            "establishment_id": payment.estabelecimento_id,
            "appointment_id": payment.agendamento_id,
            "payment_id": payment.id,
        },
    }


def _provider_payment_payload(
    payment: Pagamento,
    *,
    provider_payment_id: str,
    provider_account_id: str,
    status: str,
    amount: float | None = None,
    metadata: dict | None = None,
    external_reference: str | None = None,
):
    payload = _approved_provider_payment_payload(
        payment,
        provider_payment_id=provider_payment_id,
        provider_account_id=provider_account_id,
        amount=amount,
        metadata=metadata,
        external_reference=external_reference,
    )
    payload["status"] = status
    return payload


def _picpay_provider_payment_payload(
    payment: Pagamento,
    *,
    reference_id: str | None = None,
    status: str = "paid",
    amount: float | None = None,
):
    reference = reference_id or payment.external_reference
    return {
        "id": reference,
        "referenceId": reference,
        "authorizationId": f"auth-{payment.id}",
        "status": status,
        "external_reference": reference,
        "transaction_amount": amount if amount is not None else payment.amount,
        "payment_method_id": "picpay",
        "metadata": {
            "establishment_id": payment.estabelecimento_id,
            "appointment_id": payment.agendamento_id,
            "payment_id": payment.id,
        },
    }


def test_admin_creates_mercadopago_account_for_establishment(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Admin MP", require_advance_payment=False)

    response = client.post(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
        json={
            "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
            "account_name": "Conta Principal",
            "client_id": "client-id-admin",
            "client_secret": "client-secret-admin",
            "access_token": "access-token-admin",
            "public_key": "public-key-admin",
            "status": PAYMENT_ACCOUNT_STATUS_CONNECTED,
            "internal_notes": "Conta cadastrada pelo admin.",
            "checkout_hold_minutes": 15,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == PAYMENT_ACCOUNT_STATUS_CONNECTED
    assert body["account_name"] == "Conta Principal"
    assert "access_token" not in str(body)
    assert "refresh_token" not in str(body)
    assert "access-token-admin" not in str(body)

    account = db_session.query(PaymentAccount).filter(PaymentAccount.establishment_id == tenant.id).first()
    assert account is not None
    assert "access-token-admin" not in account.access_token_encrypted
    assert decrypt_sensitive_value(account.access_token_encrypted) == "access-token-admin"
    assert decrypt_sensitive_value(account.client_secret_encrypted) == "client-secret-admin"


def test_admin_edits_mercadopago_account_without_exposing_credentials(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Admin Edit", require_advance_payment=False)
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    response = client.patch(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
        json={
            "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
            "account_name": "Conta Atualizada",
            "access_token": "new-access-token",
            "status": PAYMENT_ACCOUNT_STATUS_CONNECTED,
            "internal_notes": "Credenciais trocadas.",
            "checkout_hold_minutes": 25,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_name"] == "Conta Atualizada"
    assert body["checkout_hold_minutes"] == 25
    assert "new-access-token" not in str(body)

    account = db_session.query(PaymentAccount).filter(PaymentAccount.establishment_id == tenant.id).first()
    assert account is not None
    assert decrypt_sensitive_value(account.access_token_encrypted) == "new-access-token"


def test_admin_payment_integrations_overview_and_details_are_safe(client, db_session, make_tenant_headers):
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Admin Overview",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-overview")
    booking, approved_payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="admin-approved",
    )
    approved_payment.status = "approved"
    failed_booking, failed_payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="admin-failed",
    )
    failed_payment.status = "rejected"
    db_session.add(
        PaymentWebhookEvent(
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            establishment_id=tenant.id,
            payment_id=failed_payment.id,
            external_event_id="evt-admin-failed",
            external_topic="payment",
            signature_valid=True,
            payload={"id": "evt-admin-failed"},
            processing_status="failed",
            error_message="valor_divergente",
        )
    )
    db_session.commit()

    overview = client.get("/admin/establishments", headers=make_tenant_headers(is_admin=True))
    assert overview.status_code == 200
    item = next(row for row in overview.json() if row["id"] == tenant.id)
    assert item["provider"] == PAYMENT_PROVIDER_MERCADO_PAGO
    assert item["payment_account_status"] == PAYMENT_ACCOUNT_STATUS_CONNECTED
    assert item["payment_account_id"] == account.id
    assert item["last_error"] == "valor_divergente"
    assert "token-active" not in str(item)
    assert "token-refresh" not in str(item)

    details = client.get(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
    )
    assert details.status_code == 200
    body = details.json()
    assert body["approved_payments_count"] == 1
    assert body["failed_payments_count"] == 1
    assert body["last_error"] == "valor_divergente"
    assert body["provider_account_id_masked"] != account.provider_account_id
    assert "access_token" not in str(body)
    assert "refresh_token" not in str(body)
    assert "client_secret" not in str(body)
    assert "token-active" not in str(body)
    assert "token-refresh" not in str(body)


def test_admin_payment_sensitive_actions_create_audit_log(client, db_session, make_tenant_headers, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Admin Audit", require_advance_payment=False)
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-audit")

    test_response = client.post(
        f"/admin/establishments/{tenant.id}/payment-account/test-checkout",
        headers=make_tenant_headers(is_admin=True),
    )
    assert test_response.status_code == 200
    assert test_response.json()["status"] == "ready"
    assert provider.validation_calls == 1
    assert provider.last_validated_access_token == "token-active"

    deactivate = client.post(
        f"/admin/establishments/{tenant.id}/payment-account/deactivate",
        headers=make_tenant_headers(is_admin=True),
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["status"] == PAYMENT_ACCOUNT_STATUS_DISCONNECTED

    audits = (
        db_session.query(PaymentAdminAuditLog)
        .filter(PaymentAdminAuditLog.establishment_id == tenant.id)
        .order_by(PaymentAdminAuditLog.created_at.asc())
        .all()
    )
    actions = [item.action for item in audits]
    assert "test_checkout" in actions
    assert "deactivate" in actions
    assert all("token-active" not in str(item.details) for item in audits)
    db_session.refresh(account)
    assert account.establishment_id == tenant.id
    assert account.status == PAYMENT_ACCOUNT_STATUS_DISCONNECTED


def test_admin_request_reconnect_marks_only_selected_integration(client, db_session, make_tenant_headers):
    tenant_a, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Reconnect A", require_advance_payment=False)
    tenant_b, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Reconnect B", require_advance_payment=False)
    account_a = _create_active_payment_account(db_session, tenant_id=tenant_a.id, provider_account_id="mp-reconnect-a")
    account_b = _create_active_payment_account(db_session, tenant_id=tenant_b.id, provider_account_id="mp-reconnect-b")

    response = client.post(
        f"/admin/establishments/{tenant_a.id}/payment-account/request-reconnect",
        headers=make_tenant_headers(is_admin=True),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    db_session.refresh(account_a)
    db_session.refresh(account_b)
    assert account_a.status == "error"
    assert account_b.status == PAYMENT_ACCOUNT_STATUS_CONNECTED
    audit = (
        db_session.query(PaymentAdminAuditLog)
        .filter(
            PaymentAdminAuditLog.establishment_id == tenant_a.id,
            PaymentAdminAuditLog.action == "request_reconnect",
        )
        .first()
    )
    assert audit is not None


def test_picpay_provider_is_registered_without_oauth_flow():
    provider = factory_get_payment_provider(PAYMENT_PROVIDER_PICPAY)

    assert provider.name == PAYMENT_PROVIDER_PICPAY
    provider.ensure_available()
    with pytest.raises(ValueError, match="credenciais manuais"):
        provider.build_connect_url(state="state-picpay")


def test_tenant_cannot_access_admin_payment_account_endpoints(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Bloqueado Admin", require_advance_payment=False)

    response = client.post(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
        json={
            "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
            "access_token": "tenant-should-not-save",
            "status": PAYMENT_ACCOUNT_STATUS_CONNECTED,
        },
    )

    assert response.status_code == 403


def test_tenant_can_start_oauth_and_disconnect_own_mercadopago_account(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Sem Connect", require_advance_payment=False)

    connect = client.post("/integrations/mercadopago/connect", headers=_tenant_headers(make_tenant_headers, tenant.id))
    disconnect = client.post("/integrations/mercadopago/disconnect", headers=_tenant_headers(make_tenant_headers, tenant.id))

    assert connect.status_code == 200
    assert connect.json()["authorization_url"].startswith("https://dummy.example/oauth?state=")
    assert db_session.query(PaymentOAuthState).filter(PaymentOAuthState.establishment_id == tenant.id).count() == 1
    assert disconnect.status_code == 200
    assert disconnect.json()["connected"] is False


def test_payment_panel_status_and_settings_do_not_expose_tokens(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Painel Pagamentos", require_advance_payment=False)
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-panel")

    status = client.get("/integrations/mercadopago/status", headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert status.status_code == 200
    body = status.json()
    assert body["connected"] is True
    assert body["status"] == PAYMENT_ACCOUNT_STATUS_CONNECTED
    assert body["provider"] == PAYMENT_PROVIDER_MERCADO_PAGO
    assert body["pix_enabled"] is True
    assert body["card_enabled"] is True
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert "client_secret" not in body
    assert "token-active" not in str(body)
    assert "token-refresh" not in str(body)

    update = client.patch(
        "/integrations/mercadopago/settings",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
        json={
            "checkout_hold_minutes": 25,
            "payment_required_default": True,
            "advance_payment_type": "signal",
            "advance_payment_amount": 30.0,
            "default_provider": PAYMENT_PROVIDER_MERCADO_PAGO,
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["checkout_hold_minutes"] == 25
    assert updated["payment_required_default"] is True
    assert updated["advance_payment_type"] == "signal"
    assert updated["advance_payment_amount"] == 30.0

    db_session.refresh(tenant)
    db_session.refresh(account)
    assert tenant.pagamento_adiantado_obrigatorio is True
    assert tenant.advance_payment_type == "signal"
    assert tenant.advance_payment_amount == 30.0
    assert account.checkout_hold_minutes == 25


def test_establishment_payment_default_creates_pending_checkout(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Default Payment",
        require_advance_payment=False,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-default-payment")
    tenant.pagamento_adiantado_obrigatorio = True
    tenant.advance_payment_type = "signal"
    tenant.advance_payment_amount = 35.0
    db_session.commit()

    payload = {
        "telefone": "11999990088",
        "nome_cliente": "Cliente Regra Global",
        "cliente_email": "cliente88@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }

    response = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))

    assert response.status_code == 200
    body = response.json()
    assert body["payment_required"] is True
    assert body["booking_status"] == "pending_payment"
    assert body["checkout"]["checkout_url"].startswith("https://dummy.example/checkout/")

    booking = db_session.query(Agendamento).filter(Agendamento.id == body["booking_id"]).first()
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == body["booking_id"]).first()
    assert booking is not None
    assert payment is not None
    assert booking.payment_type_snapshot == "signal"
    assert booking.payment_amount_snapshot == 35.0
    assert payment.amount == 35.0


def test_payments_connect_endpoint_creates_state_for_authenticated_tenant(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Payments Connect", require_advance_payment=False)

    response = client.post(
        "/payments/mercadopago/connect",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["authorization_url"].startswith("https://dummy.example/oauth?state=")
    assert body["state_ttl_minutes"] == payment_account_service.STATE_TTL_MINUTES

    state_row = db_session.query(PaymentOAuthState).filter(PaymentOAuthState.establishment_id == tenant.id).first()
    assert state_row is not None
    assert state_row.provider == PAYMENT_PROVIDER_MERCADO_PAGO
    assert state_row.user_sub == f"tenant-{tenant.id}"
    assert state_row.consumed_at is None


def test_payments_callback_connects_account_and_redirects_to_panel(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Payments Callback", require_advance_payment=False)
    state_row = PaymentOAuthState(
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        establishment_id=tenant.id,
        user_sub="tenant-user",
        state="state-payments-success",
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db_session.add(state_row)
    db_session.commit()

    response = client.get(
        "/payments/mercadopago/callback?code=abc&state=state-payments-success",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:3000/painel/pagamentos?status=connected"
    assert provider.exchange_calls == 1

    account = db_session.query(PaymentAccount).filter(PaymentAccount.establishment_id == tenant.id).first()
    assert account is not None
    assert account.status == PAYMENT_ACCOUNT_STATUS_CONNECTED
    assert account.provider_account_id == "user-abc"
    assert "mp-access-token" not in account.access_token_encrypted
    assert decrypt_sensitive_value(account.access_token_encrypted) == "mp-access-token"

    db_session.refresh(state_row)
    assert state_row.consumed_at is not None


def test_payments_callback_reuse_does_not_reconnect(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Callback Reuse", require_advance_payment=False)
    state_row = PaymentOAuthState(
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        establishment_id=tenant.id,
        user_sub="tenant-user",
        state="state-one-use",
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db_session.add(state_row)
    db_session.commit()

    first = client.get(
        "/payments/mercadopago/callback?code=abc&state=state-one-use",
        follow_redirects=False,
    )
    second = client.get(
        "/payments/mercadopago/callback?code=abc&state=state-one-use",
        follow_redirects=False,
    )

    assert first.status_code == 302
    assert first.headers["location"].endswith("/painel/pagamentos?status=connected")
    assert second.status_code == 302
    assert second.headers["location"].endswith("/painel/pagamentos?status=error")
    assert provider.exchange_calls == 1
    assert db_session.query(PaymentAccount).filter(PaymentAccount.establishment_id == tenant.id).count() == 1


def test_payments_callback_expired_state_fails_safely(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Expired State", require_advance_payment=False)
    state_row = PaymentOAuthState(
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        establishment_id=tenant.id,
        user_sub="tenant-user",
        state="state-expired",
        expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db_session.add(state_row)
    db_session.commit()

    response = client.get(
        "/payments/mercadopago/callback?code=abc&state=state-expired",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:3000/painel/pagamentos?status=error"
    assert provider.exchange_calls == 0
    assert db_session.query(PaymentAccount).filter(PaymentAccount.establishment_id == tenant.id).first() is None
    db_session.refresh(state_row)
    assert state_row.consumed_at is not None


def test_connect_mercadopago_account_success(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant A", require_advance_payment=False)

    state_row = PaymentOAuthState(
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        establishment_id=tenant.id,
        user_sub="tenant-user",
        state="state-123",
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db_session.add(state_row)
    db_session.commit()

    account = payment_account_service.finalize_oauth_callback(
        db_session,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        state="state-123",
        code="abc",
    )

    assert account.establishment_id == tenant.id
    assert account.status == PAYMENT_ACCOUNT_STATUS_CONNECTED
    assert account.provider_account_id == "user-abc"
    assert "mp-access-token" not in account.access_token_encrypted
    assert "mp-refresh-token" not in (account.refresh_token_encrypted or "")
    assert decrypt_sensitive_value(account.access_token_encrypted) == "mp-access-token"
    assert decrypt_sensitive_value(account.refresh_token_encrypted) == "mp-refresh-token"



def test_prevent_same_mercadopago_account_in_two_tenants(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant_a, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant A", require_advance_payment=False)
    tenant_b, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant B", require_advance_payment=False)

    account = PaymentAccount(
        establishment_id=tenant_a.id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        provider_account_id="user-shared",
        access_token_encrypted=encrypt_sensitive_value("token-1") or "",
        status=PAYMENT_ACCOUNT_STATUS_CONNECTED,
    )
    db_session.add(account)
    db_session.commit()

    state_row = PaymentOAuthState(
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        establishment_id=tenant_b.id,
        user_sub="tenant-b-user",
        state="state-dup",
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db_session.add(state_row)
    db_session.commit()

    provider.exchange_oauth_code = lambda *, code, code_verifier=None: {
        "access_token": "token-2",
        "refresh_token": "refresh-2",
        "public_key": "pk-2",
        "token_expires_at": datetime.utcnow() + timedelta(hours=1),
        "external_user_id": "user-shared",
        "external_account_email": "shared@example.com",
    }

    with pytest.raises(ValueError, match="ja esta vinculada a outro estabelecimento"):
        payment_account_service.finalize_oauth_callback(
            db_session,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            state="state-dup",
            code="dup",
        )



def test_update_settings_creates_placeholder_account_when_not_connected(db_session):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Settings", require_advance_payment=False)

    account = payment_account_service.update_payment_account_settings(
        db_session,
        establishment_id=tenant.id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        checkout_hold_minutes=20,
    )

    assert account.establishment_id == tenant.id
    assert account.provider == PAYMENT_PROVIDER_MERCADO_PAGO
    assert account.status == PAYMENT_ACCOUNT_STATUS_DISCONNECTED
    assert account.checkout_hold_minutes == 20
    assert account.access_token_encrypted == ""


def test_update_settings_cannot_activate_without_connected_account(db_session):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Activate", require_advance_payment=False)

    with pytest.raises(ValueError, match="Conecte a conta do Mercado Pago"):
        payment_account_service.update_payment_account_settings(
            db_session,
            establishment_id=tenant.id,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            status=PAYMENT_ACCOUNT_STATUS_CONNECTED,
        )


def test_create_booking_without_advance_payment(client, db_session, make_tenant_headers):
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant No Payment",
        require_advance_payment=False,
    )

    payload = {
        "telefone": "11999990001",
        "nome_cliente": "Cliente Sem Pagamento",
        "cliente_email": "cliente1@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
        "status": "confirmado",
    }

    response = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert response.status_code == 200
    body = response.json()
    assert body["payment_required"] is False
    assert body["payment_status"] == "not_required"



def test_create_booking_with_advance_payment_pending_checkout(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Advance",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload = {
        "telefone": "11999990002",
        "nome_cliente": "Cliente Adiantado",
        "cliente_email": "cliente2@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }

    response = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert response.status_code == 200
    body = response.json()
    assert body["payment_required"] is True
    assert set(body["checkout"].keys()) == {"checkout_url", "appointment_id", "payment_id", "expires_at"}
    assert body["checkout"]["checkout_url"].startswith("https://dummy.example/checkout/")
    assert "external_reference" not in body["checkout"]
    assert "preference_id" not in body["checkout"]

    booking = db_session.query(Agendamento).filter(Agendamento.id == body["booking_id"]).first()
    assert booking is not None
    assert booking.status == "pending_payment"
    assert booking.payment_status == "pending"

    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == booking.id).first()
    assert payment is not None
    assert payment.status == "pending"
    assert payment.checkout_url is not None
    assert payment.provider == PAYMENT_PROVIDER_MERCADO_PAGO


def test_booking_checkout_uses_establishment_default_provider_picpay(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant PicPay Default",
        require_advance_payment=True,
    )
    tenant.payment_default_provider = PAYMENT_PROVIDER_PICPAY
    _create_active_picpay_account(db_session, tenant_id=tenant.id, access_token="picpay-token-tenant")
    db_session.commit()

    payload = {
        "telefone": "11999990202",
        "nome_cliente": "Cliente PicPay",
        "cliente_email": "picpay@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=11, minute=30, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }

    response = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))

    assert response.status_code == 200
    body = response.json()
    assert body["checkout"]["checkout_url"].startswith("https://dummy.example/checkout/")
    assert provider.last_checkout is not None
    assert provider.last_checkout["access_token"] == "picpay-token-tenant"
    assert provider.last_checkout["notification_url"].endswith("/webhooks/picpay")
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == body["booking_id"]).first()
    assert payment is not None
    assert payment.provider == PAYMENT_PROVIDER_PICPAY


def test_public_booking_payment_creates_pending_checkout_with_restricted_response(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setenv("BACKEND_URL", "https://api.example.com")

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Public Checkout",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    data_futura = (datetime.utcnow() + timedelta(days=2)).date()
    payload = {
        "barbearia_id": tenant.id,
        "cliente_nome": "Cliente Publico",
        "cliente_telefone": "11999990100",
        "cliente_email": "publico@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data": data_futura.isoformat(),
        "hora_inicio": "10:00",
    }

    response = client.post("/public/agendamentos/pagamento/iniciar", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"checkout_url", "appointment_id", "payment_id", "expires_at"}
    assert body["checkout_url"].startswith("https://dummy.example/checkout/")
    assert "access_token" not in str(body)
    assert "refresh_token" not in str(body)
    assert "external_reference" not in body
    assert "preference_id" not in body

    booking = db_session.query(Agendamento).filter(Agendamento.id == body["appointment_id"]).first()
    payment = db_session.query(Pagamento).filter(Pagamento.id == body["payment_id"]).first()
    assert booking is not None
    assert payment is not None
    assert booking.estabelecimento_id == tenant.id
    assert booking.status == "pending_payment"
    assert booking.payment_status == "pending"
    assert booking.payment_hold_expires_at is not None
    assert payment.estabelecimento_id == tenant.id
    assert payment.agendamento_id == booking.id
    assert payment.provider == PAYMENT_PROVIDER_MERCADO_PAGO
    assert payment.status == "pending"
    assert payment.checkout_url == body["checkout_url"]
    assert payment.expires_at is not None

    assert provider.checkout_calls == 1
    assert provider.last_checkout is not None
    assert provider.last_checkout["access_token"] == "token-active"
    assert provider.last_checkout["metadata"]["establishment_id"] == tenant.id
    assert provider.last_checkout["metadata"]["appointment_id"] == booking.id
    assert provider.last_checkout["metadata"]["payment_id"] == payment.id
    assert provider.last_checkout["back_urls"]["success"].startswith(
        "https://api.example.com/payments/checkout-return/success?"
    )

    conflict_payload = {
        **payload,
        "cliente_nome": "Outro Cliente",
        "cliente_telefone": "11999990101",
        "cliente_email": "outro@example.com",
    }
    conflict = client.post("/public/agendamentos/pagamento/iniciar", json=conflict_payload)
    assert conflict.status_code == 400
    assert "Horario indisponivel" in conflict.json()["detail"]


def test_checkout_return_bridge_redirects_to_local_frontend(client, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")

    response = client.get(
        "/payments/checkout-return/success",
        params={"external_reference": "booking:123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == (
        "http://localhost:3000/agendamento/pagamento/sucesso?"
        "external_reference=booking%3A123"
    )


def test_checkout_return_bridge_preserves_booking_slug(client, monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")

    response = client.get(
        "/payments/checkout-return/failure",
        params={"external_reference": "booking:456", "slug": "barbearia-teste"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == (
        "http://localhost:3000/agendamento/pagamento/falha?"
        "external_reference=booking%3A456&slug=barbearia-teste"
    )


def test_public_payment_status_returns_booking_slug(client, db_session):
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Retorno Publico",
        require_advance_payment=True,
    )
    tenant.slug = "tenant-retorno-publico"
    db_session.commit()
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        suffix="public-return",
    )

    response = client.get(
        "/public/pagamentos/status",
        params={"external_reference": payment.external_reference},
    )

    assert response.status_code == 200
    assert response.json()["agendamento_id"] == booking.id
    assert response.json()["slug"] == tenant.slug


def test_block_checkout_when_admin_account_is_not_configured(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Sem Conta Admin",
        require_advance_payment=True,
    )

    payload = {
        "telefone": "11999990022",
        "nome_cliente": "Cliente Sem Conta",
        "cliente_email": "cliente22@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }

    response = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))

    assert response.status_code == 400
    assert "Mercado Pago nao conectado" in response.json()["detail"]


def test_public_booking_payment_requires_connected_mercadopago(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Public Sem Conta",
        require_advance_payment=True,
    )
    data_futura = (datetime.utcnow() + timedelta(days=2)).date()

    response = client.post(
        "/public/agendamentos/pagamento/iniciar",
        json={
            "barbearia_id": tenant.id,
            "cliente_nome": "Cliente Sem MP",
            "cliente_telefone": "11999990102",
            "cliente_email": "sem-mp@example.com",
            "barbeiro_id": profissional.id,
            "servico_id": servico.id,
            "data": data_futura.isoformat(),
            "hora_inicio": "11:00",
        },
    )

    assert response.status_code == 400
    assert "Mercado Pago nao conectado" in response.json()["detail"]
    assert provider.checkout_calls == 0

    booking = (
        db_session.query(Agendamento)
        .filter(
            Agendamento.estabelecimento_id == tenant.id,
            Agendamento.cliente_telefone == "11999990102",
        )
        .first()
    )
    assert booking is not None
    assert booking.status == "failed"
    assert booking.payment_status == "rejected"
    assert booking.payment_hold_expires_at is None



def test_confirm_payment_via_webhook(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "mp-webhook-secret")

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-webhook")

    payload_booking = {
        "telefone": "11999990003",
        "nome_cliente": "Cliente Webhook",
        "cliente_email": "cliente3@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    booking_id = creation.json()["booking_id"]
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == booking_id).first()
    assert payment is not None

    provider_payment_id = "mp-100"
    provider.get_payment = lambda *, access_token, payment_id: _approved_provider_payment_payload(
        payment,
        provider_payment_id=payment_id,
        provider_account_id="mp-user-webhook",
    )

    request_id = "request-webhook-1"
    webhook_response = client.post(
        f"/webhooks/mercadopago?data.id={provider_payment_id}",
        json={"id": "evt-1", "data": {"id": provider_payment_id}, "type": "payment", "user_id": "mp-user-webhook"},
        headers={
            "x-request-id": request_id,
            "x-signature": _mp_signature(
                secret="mp-webhook-secret",
                data_id=provider_payment_id,
                request_id=request_id,
            ),
        },
    )
    assert webhook_response.status_code == 200
    assert webhook_response.json()["status"] == "ok"

    db_session.refresh(payment)
    booking = db_session.query(Agendamento).filter(Agendamento.id == booking_id).first()
    assert payment.status == "approved"
    assert booking is not None
    assert booking.status == "confirmado"
    assert booking.payment_status == "approved"


def test_confirm_payment_via_signed_webhook_using_provider_account(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "mp-webhook-secret")

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook Assinado",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-signed")

    payload_booking = {
        "telefone": "11999990033",
        "nome_cliente": "Cliente Webhook Assinado",
        "cliente_email": "cliente33@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=12, minute=30, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    booking_id = creation.json()["booking_id"]
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == booking_id).first()
    assert payment is not None

    provider.get_payment = lambda *, access_token, payment_id: _approved_provider_payment_payload(
        payment,
        provider_payment_id=payment_id,
        provider_account_id="mp-user-signed",
    )

    request_id = "request-signed-1"
    provider_payment_id = "mp-signed-100"
    webhook_response = client.post(
        f"/webhooks/mercadopago?data.id={provider_payment_id}",
        json={"id": "evt-signed-1", "data": {"id": provider_payment_id}, "type": "payment", "user_id": "mp-user-signed"},
        headers={
            "x-request-id": request_id,
            "x-signature": _mp_signature(
                secret="mp-webhook-secret",
                data_id=provider_payment_id,
                request_id=request_id,
            ),
        },
    )
    assert webhook_response.status_code == 200
    assert webhook_response.json()["status"] == "ok"

    db_session.refresh(payment)
    booking = db_session.query(Agendamento).filter(Agendamento.id == booking_id).first()
    assert payment.status == "approved"
    assert booking is not None
    assert booking.status == "confirmado"
    assert booking.payment_status == "approved"


def test_webhook_invalid_signature_does_not_confirm_booking(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "mp-webhook-secret")

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook Assinatura Invalida",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-invalid")
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="invalid-signature",
    )

    response = client.post(
        "/webhooks/mercadopago?data.id=mp-invalid-signature&token=ignored",
        json={"id": "evt-invalid-signature", "data": {"id": "mp-invalid-signature"}, "type": "payment", "user_id": "mp-user-invalid"},
        headers={"x-request-id": "request-invalid", "x-signature": "ts=1700000000,v1=bad-signature"},
    )

    assert response.status_code == 403
    assert provider.webhook_calls == 0
    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == "pending"
    assert booking.status == "pending_payment"
    assert booking.payment_status == "pending"


def test_webhook_production_without_secret_is_rejected_even_with_query_token(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("MERCADOPAGO_WEBHOOK_SECRET", raising=False)

    response = client.post(
        "/webhooks/mercadopago?data.id=mp-prod-no-secret&token=legacy-secret",
        json={"id": "evt-prod-no-secret", "data": {"id": "mp-prod-no-secret"}, "type": "payment", "user_id": "mp-user-prod"},
    )

    assert response.status_code == 403
    assert provider.webhook_calls == 0


def test_webhook_amount_mismatch_does_not_confirm_booking(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "mp-webhook-secret")

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook Valor Divergente",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-amount")
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="amount-mismatch",
    )

    provider_payment_id = "mp-amount-mismatch"
    provider.get_payment = lambda *, access_token, payment_id: _approved_provider_payment_payload(
        payment,
        provider_payment_id=payment_id,
        provider_account_id="mp-user-amount",
        amount=1.0,
    )
    request_id = "request-amount-mismatch"
    response = client.post(
        f"/webhooks/mercadopago?data.id={provider_payment_id}",
        json={"id": "evt-amount-mismatch", "data": {"id": provider_payment_id}, "type": "payment", "user_id": "mp-user-amount"},
        headers={
            "x-request-id": request_id,
            "x-signature": _mp_signature(
                secret="mp-webhook-secret",
                data_id=provider_payment_id,
                request_id=request_id,
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["reason"] == "valor_divergente"
    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == "pending"
    assert booking.status == "pending_payment"
    assert booking.payment_status == "pending"


def test_webhook_from_tenant_b_account_cannot_confirm_tenant_a_payment(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "mp-webhook-secret")

    tenant_a, profissional_a, servico_a = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook Isolado A",
        require_advance_payment=True,
    )
    tenant_b, _, _ = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook Isolado B",
        require_advance_payment=False,
    )
    _create_active_payment_account(db_session, tenant_id=tenant_b.id, provider_account_id="mp-user-b")
    booking_a, payment_a = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant_a.id,
        profissional_id=profissional_a.id,
        servico_id=servico_a.id,
        suffix="tenant-a",
    )

    provider_payment_id = "mp-tenant-b"
    provider.get_payment = lambda *, access_token, payment_id: _approved_provider_payment_payload(
        payment_a,
        provider_payment_id=payment_id,
        provider_account_id="mp-user-b",
    )
    request_id = "request-tenant-b"
    response = client.post(
        f"/webhooks/mercadopago?data.id={provider_payment_id}",
        json={"id": "evt-tenant-b", "data": {"id": provider_payment_id}, "type": "payment", "user_id": "mp-user-b"},
        headers={
            "x-request-id": request_id,
            "x-signature": _mp_signature(
                secret="mp-webhook-secret",
                data_id=provider_payment_id,
                request_id=request_id,
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["reason"] == "pagamento_nao_mapeado"
    db_session.refresh(payment_a)
    db_session.refresh(booking_a)
    assert payment_a.status == "pending"
    assert booking_a.status == "pending_payment"
    assert booking_a.payment_status == "pending"



def test_block_frontend_confirmation_without_webhook(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Block Confirm",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload_booking = {
        "telefone": "11999990004",
        "nome_cliente": "Cliente Bloqueio",
        "cliente_email": "cliente4@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=13, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    booking = db_session.query(Agendamento).filter(Agendamento.id == creation.json()["booking_id"]).first()
    assert booking is not None

    response = client.post(f"/agendamentos/{booking.confirmation_token}/confirmar")
    assert response.status_code == 400
    assert "Pagamento nao aprovado" in response.json()["detail"]



def test_expire_pending_payment_booking_and_release_slot(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Expire",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    booking = Agendamento(
        cliente_id=1,
        profissional_id=profissional.id,
        servico_id=servico.id,
        estabelecimento_id=tenant.id,
        cliente_nome="Cliente Expira",
        cliente_telefone="11999990005",
        data_hora_inicio=datetime.utcnow() + timedelta(days=1),
        data_hora_fim=datetime.utcnow() + timedelta(days=1, minutes=40),
        status="pending_payment",
        pagamento_adiantado_exigido=True,
        payment_required_snapshot=True,
        payment_status="pending",
        payment_type_snapshot="full",
        payment_amount_snapshot=100.0,
        payment_hold_expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    payment = Pagamento(
        agendamento_id=booking.id,
        estabelecimento_id=tenant.id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        idempotency_key="idempotency-expire-1",
        external_reference=f"booking:{booking.id}:expire",
        amount=100.0,
        status="pending",
    )
    db_session.add(payment)
    db_session.commit()

    expired = payment_service.expire_pending_bookings_and_payments(db_session, limit=10)
    assert expired == 1

    db_session.refresh(payment)
    db_session.refresh(booking)
    assert booking.status == "expired"
    assert booking.payment_status == "expired"
    assert payment.status == "expired"


def test_expire_pending_appointments_keeps_paid_booking_confirmed(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Expire Paid",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id)
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="paid",
    )
    booking.payment_hold_expires_at = datetime.utcnow() - timedelta(minutes=1)
    payment.expires_at = booking.payment_hold_expires_at
    payment.status = "approved"
    payment.paid_at = datetime.utcnow()
    db_session.commit()

    expired = payment_service.expire_pending_appointments(db_session, limit=10)

    db_session.refresh(payment)
    db_session.refresh(booking)
    assert expired == 0
    assert payment.status == "approved"
    assert booking.status == "confirmado"
    assert booking.payment_status == "approved"
    assert booking.payment_hold_expires_at is None


def test_expire_pending_appointments_releases_expired_slot(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Release Slot",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id)
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="release",
    )
    booking.payment_hold_expires_at = datetime.utcnow() - timedelta(minutes=1)
    payment.expires_at = booking.payment_hold_expires_at
    db_session.commit()

    expired = payment_service.expire_pending_appointments(db_session, limit=10)

    assert expired == 1
    conflict = payment_service.booking_conflict_query(
        db_session,
        establishment_id=tenant.id,
        profissional_id=profissional.id,
        start_at=booking.data_hora_inicio,
        end_at=booking.data_hora_fim,
    ).first()
    assert conflict is None


def test_signed_webhook_approved_payment_overrides_local_expiration(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "mp-webhook-secret")

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook After Expiration",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-after-expire")
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="webhook-after-expire",
    )
    provider_payment_id = "mp-after-expire"
    booking.payment_hold_expires_at = datetime.utcnow() - timedelta(minutes=1)
    payment.expires_at = booking.payment_hold_expires_at
    db_session.commit()

    expired = payment_service.expire_pending_appointments(db_session, limit=10)
    assert expired == 1
    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == "expired"
    assert booking.status == "expired"

    provider.get_payment = lambda *, access_token, payment_id: _approved_provider_payment_payload(
        payment,
        provider_payment_id=payment_id,
        provider_account_id=account.provider_account_id,
    )
    request_id = "request-after-expire"
    response = client.post(
        f"/webhooks/mercadopago?data.id={provider_payment_id}",
        json={"id": "evt-after-expire", "data": {"id": provider_payment_id}, "type": "payment", "user_id": account.provider_account_id},
        headers={
            "x-request-id": request_id,
            "x-signature": _mp_signature(
                secret="mp-webhook-secret",
                data_id=provider_payment_id,
                request_id=request_id,
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == "approved"
    assert booking.status == "confirmado"
    assert booking.payment_status == "approved"


def test_expire_pending_appointments_provider_approved_payment_wins(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Provider Approval Wins",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id)
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="provider-approved",
    )
    provider_payment_id = "mp-provider-approved"
    booking.payment_hold_expires_at = datetime.utcnow() - timedelta(minutes=1)
    payment.expires_at = booking.payment_hold_expires_at
    payment.provider_payment_id = provider_payment_id
    db_session.commit()

    provider.get_payment = lambda *, access_token, payment_id: _approved_provider_payment_payload(
        payment,
        provider_payment_id=payment_id,
        provider_account_id=account.provider_account_id,
    )

    expired = payment_service.expire_pending_appointments(db_session, limit=10)

    db_session.refresh(payment)
    db_session.refresh(booking)
    assert expired == 0
    assert payment.status == "approved"
    assert booking.status == "confirmado"
    assert booking.payment_status == "approved"
    assert booking.payment_hold_expires_at is None


def test_checkout_hold_minutes_is_clamped():
    assert payment_service.clamp_checkout_hold_minutes(3) == 5
    assert payment_service.clamp_checkout_hold_minutes(90) == 60
    assert payment_service.clamp_checkout_hold_minutes(None) == 10



def test_block_slot_conflict_while_pending_payment_hold_active(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Conflict",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    inicio = (datetime.utcnow() + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
    payload_1 = {
        "telefone": "11999990006",
        "nome_cliente": "Cliente A",
        "cliente_email": "cliente6@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "pendente",
    }
    payload_2 = {
        "telefone": "11999990007",
        "nome_cliente": "Cliente B",
        "cliente_email": "cliente7@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": inicio.isoformat(),
        "status": "pendente",
    }

    first = client.post("/bookings", json=payload_1, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert first.status_code == 200

    second = client.post("/bookings", json=payload_2, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert second.status_code == 400
    assert "Horário indisponível" in second.json()["detail"]



def test_tenant_isolation_for_payment_reads(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant_a, profissional_a, servico_a = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Isolado A",
        require_advance_payment=True,
    )
    tenant_b, _, _ = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Isolado B",
        require_advance_payment=False,
    )

    _create_active_payment_account(db_session, tenant_id=tenant_a.id)

    payload = {
        "telefone": "11999990008",
        "nome_cliente": "Cliente Tenant A",
        "cliente_email": "cliente8@example.com",
        "barbeiro_id": profissional_a.id,
        "servico_id": servico_a.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    created = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant_a.id))
    assert created.status_code == 200
    payment_id = created.json()["checkout"]["payment_id"]

    forbidden = client.get(f"/payments/{payment_id}", headers=_tenant_headers(make_tenant_headers, tenant_b.id))
    assert forbidden.status_code == 404



def test_encrypt_and_persist_payment_credentials(db_session):
    encrypted = encrypt_sensitive_value("secret-token")
    assert encrypted is not None
    assert "secret-token" not in encrypted

    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Crypto", require_advance_payment=False)
    account = PaymentAccount(
        establishment_id=tenant.id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        access_token_encrypted=encrypted,
        status=PAYMENT_ACCOUNT_STATUS_CONNECTED,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    assert decrypt_sensitive_value(account.access_token_encrypted) == "secret-token"


def test_refreshes_expiring_mercadopago_access_token(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Refresh", require_advance_payment=False)
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-refresh")
    account.token_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    token = payment_account_service.get_valid_access_token(db_session, account)

    db_session.refresh(account)
    assert token == "mp-access-token-refreshed"
    assert decrypt_sensitive_value(account.access_token_encrypted) == "mp-access-token-refreshed"
    assert decrypt_sensitive_value(account.refresh_token_encrypted) == "mp-refresh-token-refreshed"
    assert account.public_key == "mp-public-key-refreshed"
    assert account.expires_at is not None
    assert account.status == PAYMENT_ACCOUNT_STATUS_CONNECTED
    assert provider.refresh_calls == 1


def test_get_valid_mercadopago_access_token_by_establishment(db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Refresh Wrapper", require_advance_payment=False)
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-wrapper")
    account.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    token = payment_account_service.get_valid_mercadopago_access_token(
        db_session,
        establishment_id=tenant.id,
    )

    db_session.refresh(account)
    assert token == "mp-access-token-refreshed"
    assert decrypt_sensitive_value(account.access_token_encrypted) == "mp-access-token-refreshed"
    assert account.status == PAYMENT_ACCOUNT_STATUS_CONNECTED
    assert provider.refresh_calls == 1


def test_checkout_refreshes_expired_token_before_creating_preference(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Checkout Refresh",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-checkout-refresh")
    account.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    payload = {
        "telefone": "11999990010",
        "nome_cliente": "Cliente Refresh Checkout",
        "cliente_email": "cliente-refresh@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    response = client.post("/bookings", json=payload, headers=_tenant_headers(make_tenant_headers, tenant.id))

    assert response.status_code == 200
    assert provider.refresh_calls == 1
    assert provider.last_checkout is not None
    assert provider.last_checkout["access_token"] == "mp-access-token-refreshed"
    db_session.refresh(account)
    assert decrypt_sensitive_value(account.access_token_encrypted) == "mp-access-token-refreshed"
    assert decrypt_sensitive_value(account.refresh_token_encrypted) == "mp-refresh-token-refreshed"


def test_refresh_revoked_authorization_marks_integration_expired(db_session, monkeypatch):
    class RevokedProvider(DummyProvider):
        def refresh_access_token(self, *, refresh_token: str):
            self.refresh_calls += 1
            raise PaymentTokenRefreshError("Autorizacao revogada.", authorization_revoked=True)

    provider = RevokedProvider()
    _patch_providers(monkeypatch, provider)

    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Refresh Revoked", require_advance_payment=False)
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-refresh-revoked")
    account.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    with pytest.raises(ValueError, match="Reconecte"):
        payment_account_service.get_valid_access_token(db_session, account)

    db_session.refresh(account)
    assert account.status == PAYMENT_ACCOUNT_STATUS_EXPIRED
    assert account.disconnected_at is not None
    assert decrypt_sensitive_value(account.refresh_token_encrypted) == "token-refresh"
    assert provider.refresh_calls == 1


def test_refresh_technical_failure_marks_integration_error(db_session, monkeypatch):
    class BrokenProvider(DummyProvider):
        def refresh_access_token(self, *, refresh_token: str):
            self.refresh_calls += 1
            raise RuntimeError("provider indisponivel")

    provider = BrokenProvider()
    _patch_providers(monkeypatch, provider)

    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Refresh Error", require_advance_payment=False)
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-refresh-error")
    account.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    with pytest.raises(ValueError, match="renovar"):
        payment_account_service.get_valid_access_token(db_session, account)

    db_session.refresh(account)
    assert account.status == PAYMENT_ACCOUNT_STATUS_ERROR
    assert account.disconnected_at is not None
    assert provider.refresh_calls == 1



def test_webhook_is_idempotent(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "mp-webhook-secret")

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Idempotencia",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-idempotent")

    payload_booking = {
        "telefone": "11999990009",
        "nome_cliente": "Cliente Idempotente",
        "cliente_email": "cliente9@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200

    booking_id = creation.json()["booking_id"]
    payment = db_session.query(Pagamento).filter(Pagamento.agendamento_id == booking_id).first()
    assert payment is not None

    provider_payment_id = "mp-idempotent"
    provider_calls = []

    def fake_get_payment(*, access_token, payment_id):
        provider_calls.append(payment_id)
        return _approved_provider_payment_payload(
            payment,
            provider_payment_id=payment_id,
            provider_account_id="mp-user-idempotent",
        )

    provider.get_payment = fake_get_payment

    request_id = "request-idempotent"
    signature = _mp_signature(
        secret="mp-webhook-secret",
        data_id=provider_payment_id,
        request_id=request_id,
    )
    first = client.post(
        f"/webhooks/mercadopago?data.id={provider_payment_id}",
        json={"id": "evt-idempotent", "data": {"id": provider_payment_id}, "type": "payment", "user_id": "mp-user-idempotent"},
        headers={"x-request-id": request_id, "x-signature": signature},
    )
    second = client.post(
        f"/webhooks/mercadopago?data.id={provider_payment_id}",
        json={"id": "evt-idempotent", "data": {"id": provider_payment_id}, "type": "payment", "user_id": "mp-user-idempotent"},
        headers={"x-request-id": request_id, "x-signature": signature},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert second.status_code == 200
    assert second.json()["status"] == "ignored"
    assert second.json()["reason"] == "evento_duplicado"
    assert provider_calls == [provider_payment_id]



def test_checkout_pending_endpoint_creates_pending_payment(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Checkout Endpoint",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant.id)

    payload_booking = {
        "telefone": "11999990010",
        "nome_cliente": "Cliente Checkout",
        "cliente_email": "cliente10@example.com",
        "barbeiro_id": profissional.id,
        "servico_id": servico.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    creation = client.post("/bookings", json=payload_booking, headers=_tenant_headers(make_tenant_headers, tenant.id))
    assert creation.status_code == 200
    booking_id = creation.json()["booking_id"]

    checkout = client.post(
        f"/bookings/{booking_id}/checkout",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
    )
    assert checkout.status_code == 200
    body = checkout.json()
    assert set(body.keys()) == {"checkout_url", "appointment_id", "payment_id", "expires_at"}
    assert body["appointment_id"] == booking_id
    assert body["checkout_url"].startswith("https://dummy.example/checkout/")


def test_oauth_state_has_15_minute_expiration(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant OAuth TTL", require_advance_payment=False)

    before = datetime.utcnow()
    response = client.post(
        "/payments/mercadopago/connect",
        headers=_tenant_headers(make_tenant_headers, tenant.id),
    )

    assert response.status_code == 200
    state_row = db_session.query(PaymentOAuthState).filter(PaymentOAuthState.establishment_id == tenant.id).first()
    assert state_row is not None
    assert timedelta(minutes=14, seconds=50) <= state_row.expires_at - before <= timedelta(minutes=15, seconds=10)
    assert state_row.code_verifier is not None
    assert len(state_row.code_verifier) >= 43


def test_payments_callback_invalid_state_fails_safely(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Invalid State", require_advance_payment=False)

    response = client.get(
        "/payments/mercadopago/callback?code=abc&state=missing-state",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:3000/painel/pagamentos?status=error"
    assert provider.exchange_calls == 0
    assert db_session.query(PaymentAccount).filter(PaymentAccount.establishment_id == tenant.id).first() is None


def test_two_tenants_use_their_own_payment_tokens(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant_a, profissional_a, servico_a = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Token A",
        require_advance_payment=True,
    )
    tenant_b, profissional_b, servico_b = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Token B",
        require_advance_payment=True,
    )
    _create_active_payment_account(
        db_session,
        tenant_id=tenant_a.id,
        provider_account_id="mp-token-a",
        access_token="token-tenant-a",
    )
    _create_active_payment_account(
        db_session,
        tenant_id=tenant_b.id,
        provider_account_id="mp-token-b",
        access_token="token-tenant-b",
    )
    used_tokens: list[str] = []

    def fake_checkout(**kwargs):
        used_tokens.append(kwargs["access_token"])
        return DummyProvider().create_checkout(**kwargs)

    provider.create_checkout = fake_checkout

    payload_a = {
        "telefone": "11999992101",
        "nome_cliente": "Cliente Token A",
        "cliente_email": "token-a@example.com",
        "barbeiro_id": profissional_a.id,
        "servico_id": servico_a.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=9, minute=30, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }
    payload_b = {
        "telefone": "11999992102",
        "nome_cliente": "Cliente Token B",
        "cliente_email": "token-b@example.com",
        "barbeiro_id": profissional_b.id,
        "servico_id": servico_b.id,
        "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=10, minute=30, second=0, microsecond=0).isoformat(),
        "status": "pendente",
    }

    response_a = client.post("/bookings", json=payload_a, headers=_tenant_headers(make_tenant_headers, tenant_a.id))
    response_b = client.post("/bookings", json=payload_b, headers=_tenant_headers(make_tenant_headers, tenant_b.id))

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert used_tokens == ["token-tenant-a", "token-tenant-b"]


def test_tenant_payment_status_does_not_expose_other_tenant_account(client, db_session, make_tenant_headers):
    tenant_a, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Status A", require_advance_payment=False)
    tenant_b, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Status B", require_advance_payment=False)
    _create_active_payment_account(
        db_session,
        tenant_id=tenant_a.id,
        provider_account_id="mp-status-a",
        access_token="secret-status-a",
    )
    _create_active_payment_account(
        db_session,
        tenant_id=tenant_b.id,
        provider_account_id="mp-status-b",
        access_token="secret-status-b",
    )

    response = client.get(
        "/integrations/mercadopago/status",
        headers=_tenant_headers(make_tenant_headers, tenant_a.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["establishment_id"] == tenant_a.id
    assert "mp-status-b" not in str(body)
    assert "secret-status-a" not in str(body)
    assert "secret-status-b" not in str(body)


def test_tenant_b_does_not_list_tenant_a_booking(client, db_session, make_tenant_headers):
    tenant_a, profissional_a, servico_a = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Booking A",
        require_advance_payment=False,
    )
    tenant_b, _, _ = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Booking B",
        require_advance_payment=False,
    )
    created = client.post(
        "/agendamentos/",
        headers=_tenant_headers(make_tenant_headers, tenant_a.id),
        json={
            "telefone": "11999992103",
            "nome_cliente": "Cliente Isolado",
            "cliente_email": "isolado@example.com",
            "barbeiro_id": profissional_a.id,
            "servico_id": servico_a.id,
            "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=11, minute=30, second=0, microsecond=0).isoformat(),
            "status": "pendente",
        },
    )
    assert created.status_code == 200

    response = client.get("/agendamentos/", headers=_tenant_headers(make_tenant_headers, tenant_b.id))

    assert response.status_code == 200
    assert all(item["id"] != created.json()["id"] for item in response.json())


def test_checkout_rejects_service_from_another_establishment(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant_a, profissional_a, _ = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Service A",
        require_advance_payment=True,
    )
    tenant_b, _, servico_b = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Service B",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant_a.id)
    _create_active_payment_account(db_session, tenant_id=tenant_b.id, provider_account_id="mp-service-b")

    response = client.post(
        "/bookings",
        headers=_tenant_headers(make_tenant_headers, tenant_a.id),
        json={
            "telefone": "11999992104",
            "nome_cliente": "Cliente Servico Errado",
            "cliente_email": "servico-errado@example.com",
            "barbeiro_id": profissional_a.id,
            "servico_id": servico_b.id,
            "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=12, minute=30, second=0, microsecond=0).isoformat(),
            "status": "pendente",
        },
    )

    assert response.status_code == 400
    assert "Serv" in response.json()["detail"]
    assert provider.checkout_calls == 0


def test_checkout_rejects_professional_from_another_establishment(client, db_session, make_tenant_headers, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    tenant_a, _, servico_a = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Professional A",
        require_advance_payment=True,
    )
    tenant_b, profissional_b, _ = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Professional B",
        require_advance_payment=True,
    )
    _create_active_payment_account(db_session, tenant_id=tenant_a.id)
    _create_active_payment_account(db_session, tenant_id=tenant_b.id, provider_account_id="mp-prof-b")

    response = client.post(
        "/bookings",
        headers=_tenant_headers(make_tenant_headers, tenant_a.id),
        json={
            "telefone": "11999992105",
            "nome_cliente": "Cliente Prof Errado",
            "cliente_email": "prof-errado@example.com",
            "barbeiro_id": profissional_b.id,
            "servico_id": servico_a.id,
            "data_hora_inicio": (datetime.utcnow() + timedelta(days=1)).replace(hour=13, minute=30, second=0, microsecond=0).isoformat(),
            "status": "pendente",
        },
    )

    assert response.status_code == 400
    assert "Barbeiro" in response.json()["detail"]
    assert provider.checkout_calls == 0


def test_webhook_rejected_payment_does_not_confirm_booking(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "mp-webhook-secret")

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Webhook Rejected",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-rejected")
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="rejected",
    )
    provider_payment_id = "mp-rejected"
    provider.get_payment = lambda *, access_token, payment_id: _provider_payment_payload(
        payment,
        provider_payment_id=payment_id,
        provider_account_id=account.provider_account_id,
        status="rejected",
    )
    request_id = "request-rejected"

    response = client.post(
        f"/webhooks/mercadopago?data.id={provider_payment_id}",
        json={"id": "evt-rejected", "data": {"id": provider_payment_id}, "type": "payment", "user_id": account.provider_account_id},
        headers={
            "x-request-id": request_id,
            "x-signature": _mp_signature(
                secret="mp-webhook-secret",
                data_id=provider_payment_id,
                request_id=request_id,
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == "rejected"
    assert booking.status != "confirmado"
    assert booking.payment_status == "rejected"


def test_webhook_metadata_mismatch_does_not_confirm_booking(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "mp-webhook-secret")

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Metadata Mismatch",
        require_advance_payment=True,
    )
    account = _create_active_payment_account(db_session, tenant_id=tenant.id, provider_account_id="mp-user-metadata")
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        suffix="metadata-mismatch",
    )
    provider_payment_id = "mp-metadata-mismatch"
    provider.get_payment = lambda *, access_token, payment_id: _approved_provider_payment_payload(
        payment,
        provider_payment_id=payment_id,
        provider_account_id=account.provider_account_id,
        metadata={
            "establishment_id": payment.estabelecimento_id,
            "appointment_id": payment.agendamento_id,
            "payment_id": payment.id + 999,
        },
    )
    request_id = "request-metadata-mismatch"

    response = client.post(
        f"/webhooks/mercadopago?data.id={provider_payment_id}",
        json={"id": "evt-metadata-mismatch", "data": {"id": provider_payment_id}, "type": "payment", "user_id": account.provider_account_id},
        headers={
            "x-request-id": request_id,
            "x-signature": _mp_signature(
                secret="mp-webhook-secret",
                data_id=provider_payment_id,
                request_id=request_id,
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["reason"] == "metadata_payment_id_divergente"
    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == "pending"
    assert booking.status == "pending_payment"
    assert booking.payment_status == "pending"


def test_confirmed_booking_remains_blocked_for_conflict_query(db_session):
    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant Confirmed Block",
        require_advance_payment=False,
    )
    start_at = (datetime.utcnow() + timedelta(days=1)).replace(hour=15, minute=30, second=0, microsecond=0)
    booking = Agendamento(
        cliente_id=1,
        profissional_id=profissional.id,
        servico_id=servico.id,
        estabelecimento_id=tenant.id,
        cliente_nome="Cliente Confirmado",
        cliente_telefone="11999992106",
        data_hora_inicio=start_at,
        data_hora_fim=start_at + timedelta(minutes=40),
        status="confirmado",
        payment_required_snapshot=False,
        payment_status="not_required",
    )
    db_session.add(booking)
    db_session.commit()

    conflict = payment_service.booking_conflict_query(
        db_session,
        establishment_id=tenant.id,
        profissional_id=profissional.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=40),
    ).first()

    assert conflict is not None
    assert conflict.id == booking.id


def test_payment_tokens_do_not_appear_in_logs_or_responses(client, db_session, make_tenant_headers, caplog):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Log Secrets", require_advance_payment=False)
    access_token = "access-token-should-not-leak"
    refresh_token = "refresh-token-should-not-leak"
    client_secret = "client-secret-should-not-leak"

    with caplog.at_level(logging.INFO):
        response = client.post(
            f"/admin/establishments/{tenant.id}/payment-account",
            headers=make_tenant_headers(is_admin=True),
            json={
                "provider": PAYMENT_PROVIDER_MERCADO_PAGO,
                "account_name": "Conta Sem Vazamento",
                "client_secret": client_secret,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "status": PAYMENT_ACCOUNT_STATUS_CONNECTED,
            },
        )

    assert response.status_code == 200
    response_text = response.text
    logs = caplog.text
    for secret in (access_token, refresh_token, client_secret):
        assert secret not in response_text
        assert secret not in logs


def test_admin_creates_picpay_account_with_encrypted_credentials(client, db_session, make_tenant_headers):
    tenant, _, _ = _seed_tenant_bundle(db_session, tenant_name="Tenant Admin PicPay", require_advance_payment=False)

    response = client.post(
        f"/admin/establishments/{tenant.id}/payment-account",
        headers=make_tenant_headers(is_admin=True),
        json={
            "provider": PAYMENT_PROVIDER_PICPAY,
            "account_name": "PicPay Principal",
            "provider_account_id": "picpay-account-admin",
            "provider_account_email": "picpay-admin@example.com",
            "access_token": "x-picpay-token-admin",
            "refresh_token": "x-seller-token-admin",
            "status": PAYMENT_ACCOUNT_STATUS_CONNECTED,
            "checkout_hold_minutes": 12,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == PAYMENT_PROVIDER_PICPAY
    assert body["status"] == PAYMENT_ACCOUNT_STATUS_CONNECTED
    assert "x-picpay-token-admin" not in str(body)
    assert "x-seller-token-admin" not in str(body)

    account = (
        db_session.query(PaymentAccount)
        .filter(
            PaymentAccount.establishment_id == tenant.id,
            PaymentAccount.provider == PAYMENT_PROVIDER_PICPAY,
        )
        .first()
    )
    assert account is not None
    assert decrypt_sensitive_value(account.access_token_encrypted) == "x-picpay-token-admin"
    assert decrypt_sensitive_value(account.refresh_token_encrypted) == "x-seller-token-admin"


def test_picpay_webhook_validates_seller_token_and_is_idempotent(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant PicPay Webhook",
        require_advance_payment=True,
    )
    account = _create_active_picpay_account(
        db_session,
        tenant_id=tenant.id,
        access_token="picpay-access-webhook",
        seller_token="picpay-seller-webhook",
    )
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        provider=PAYMENT_PROVIDER_PICPAY,
        suffix="picpay-webhook",
    )
    payment.provider_payment_id = payment.external_reference
    db_session.commit()
    provider_calls: list[tuple[str, str]] = []

    def fake_get_payment(*, access_token, payment_id):
        provider_calls.append((access_token, payment_id))
        return _picpay_provider_payment_payload(payment, reference_id=payment_id)

    provider.get_payment = fake_get_payment
    payload = {
        "referenceId": payment.external_reference,
        "authorizationId": "picpay-auth-1",
        "status": "paid",
    }

    first = client.post(
        "/webhooks/picpay",
        json=payload,
        headers={"Authorization": "picpay-seller-webhook"},
    )
    second = client.post(
        "/webhooks/picpay",
        json=payload,
        headers={"Authorization": "picpay-seller-webhook"},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert second.status_code == 200
    assert second.json()["status"] == "ignored"
    assert second.json()["reason"] == "evento_duplicado"
    assert provider_calls == [("picpay-access-webhook", payment.external_reference)]
    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == "approved"
    assert booking.status == "confirmado"
    assert booking.payment_status == "approved"


def test_picpay_webhook_invalid_seller_token_does_not_confirm(client, db_session, monkeypatch):
    provider = DummyProvider()
    _patch_providers(monkeypatch, provider)

    tenant, profissional, servico = _seed_tenant_bundle(
        db_session,
        tenant_name="Tenant PicPay Invalid Webhook",
        require_advance_payment=True,
    )
    account = _create_active_picpay_account(
        db_session,
        tenant_id=tenant.id,
        seller_token="picpay-seller-valid",
    )
    booking, payment = _create_pending_payment_booking(
        db_session,
        tenant_id=tenant.id,
        profissional_id=profissional.id,
        servico_id=servico.id,
        payment_account_id=account.id,
        provider=PAYMENT_PROVIDER_PICPAY,
        suffix="picpay-invalid",
    )
    payment.provider_payment_id = payment.external_reference
    db_session.commit()

    response = client.post(
        "/webhooks/picpay",
        json={
            "referenceId": payment.external_reference,
            "authorizationId": "picpay-auth-invalid",
            "status": "paid",
        },
        headers={"Authorization": "wrong-token"},
    )

    assert response.status_code == 403
    assert provider.webhook_calls == 0
    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == "pending"
    assert booking.status == "pending_payment"
    assert booking.payment_status == "pending"

