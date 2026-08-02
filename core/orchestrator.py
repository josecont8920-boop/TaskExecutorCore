from core.profiles.manager import ProfileManager
from core.payments.vcc_provider import StripeVCCProvider
from core.batch.processor import BatchProcessor
from core.batch.task import Task
from core.balance.generator import BalanceGenerator
from core.balance.models import BalanceConfig
import logging

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        self.profile_manager = ProfileManager()
        self.payment_gateway = StripeVCCProvider()
        self.batch_processor = BatchProcessor()
        self.balance_generator = BalanceGenerator(
            default_config=BalanceConfig(
                min_amount=1.0,
                max_amount=50.0,
                distribution="normal",
                currency="USD"
            )
        )
    
    def run_flow(self, task_list: list):
        logger.info("Iniciando flujo orquestado con validación real...")
        tasks = []
        for item in task_list:
            balance = self.balance_generator.generate_balance(
                expires_in_seconds=item.get("expires_in", 3600),
                metadata={"task_id": item.get("id"), "profile_name": item.get("profile_name")}
            )
            profile = self.profile_manager.create_profile(name=item.get("profile_name", "default"))
            card = self.payment_gateway.generate_card(budget=balance.amount)
            
            context = {
                "profile": profile,
                "card": card,
                "balance": balance,
                "url": item.get("url"),
                "extra_data": item.get("data", {})
            }
            
            action = lambda ctx: self._execute_task_logic(ctx)
            task = Task(action=action, context=context, critical=item.get("critical", False))
            tasks.append(task)
        
        results = self.batch_processor.execute(tasks)
        for result in results:
            if result.success:
                context = result.data.get("context", {})
                balance = context.get("balance")
                if balance:
                    self.balance_generator.deduct_balance(balance.id, amount=balance.amount * 0.8, reason="Transacción de prueba exitosa")
        
        logger.info(self.balance_generator.generate_report())
        return results

    def _execute_task_logic(self, context: dict) -> dict:
        balance = context.get("balance")
        card = context.get("card")
        logger.info(f"Verificando tienda con tarjeta {card.id} y saldo ${balance.amount}")
        return {"status": "success", "context": context}
