import uuid
from typing import Optional
from .gateway import IPaymentGateway
from .models import PaymentCard
from config.settings import settings

class StripeVCCProvider(IPaymentGateway):
    def __init__(self, api_key: Optional[str] = settings.VCC_API_KEY):
        self.api_key = api_key

    def generate_card(self, budget: float, metadata: Optional[dict] = None) -> PaymentCard:
        return PaymentCard(
            id=f"card_{uuid.uuid4().hex[:8]}",
            number="4242 4242 4242 4242",
            cvv="123",
            expiry="12/28",
            budget=budget,
            balance=budget
        )

    def get_balance(self, card_id: str) -> float:
        return 10.0

    def close_card(self, card_id: str) -> bool:
        return True
