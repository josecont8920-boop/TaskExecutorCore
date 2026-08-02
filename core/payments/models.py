from pydantic import BaseModel

class PaymentCard(BaseModel):
    id: str
    number: str
    cvv: str
    expiry: str
    budget: float
    balance: float

class Transaction(BaseModel):
    id: str
    card_id: str
    amount: float
    status: str
