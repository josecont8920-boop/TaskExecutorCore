from abc import ABC, abstractmethod
from typing import Optional
from .models import PaymentCard

class IPaymentGateway(ABC):
    @abstractmethod
    def generate_card(self, budget: float, metadata: Optional[dict] = None) -> PaymentCard:
        pass

    @abstractmethod
    def get_balance(self, card_id: str) -> float:
        pass

    @abstractmethod
    def close_card(self, card_id: str) -> bool:
        pass
