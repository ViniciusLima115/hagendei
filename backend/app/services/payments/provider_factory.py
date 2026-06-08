from app.services.payments.constants import (
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_PROVIDER_PICPAY,
    normalize_payment_provider,
)
from app.services.payments.providers.base import PaymentProvider
from app.services.payments.providers.mercadopago import MercadoPagoProvider
from app.services.payments.providers.picpay import PicPayProvider


def get_payment_provider(provider: str) -> PaymentProvider:
    normalized = normalize_payment_provider(provider)
    if normalized == PAYMENT_PROVIDER_MERCADO_PAGO:
        return MercadoPagoProvider()
    if normalized == PAYMENT_PROVIDER_PICPAY:
        return PicPayProvider()
    raise ValueError(f"Provider de pagamento nao suportado: {provider}")
