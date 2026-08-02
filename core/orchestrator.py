import logging
from core.profiles.manager import ProfileManager
from core.payments.vcc_provider import StripeVCCProvider
from core.batch.processor import BatchProcessor
from core.batch.task import Task
from config.settings import settings

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        self.profile_manager = ProfileManager()
        self.payment_gateway = StripeVCCProvider()
        self.batch_processor = BatchProcessor()

    def run_flow(self, task_list: list):
        logger.info("Iniciando flujo orquestado...")
        tasks = []
        for item in task_list:
            profile = self.profile_manager.create_profile(name=item.get("profile_name", "default"))
            card = self.payment_gateway.generate_card(budget=settings.VCC_DEFAULT_BUDGET)
            context = {
                "profile": profile,
                "card": card,
                "url": item.get("url"),
                "extra_data": item.get("data", {})
            }
            action = lambda ctx: self._execute_task_logic(ctx)
            task = Task(action=action, context=context, critical=item.get("critical", False))
            tasks.append(task)

        results = self.batch_processor.execute(tasks)
        for res in results:
            logger.info(f"Resultado tarea {res.task_id}: {'OK' if res.success else 'FAIL'}")
        logger.info("Flujo finalizado.")

    def _execute_task_logic(self, context: dict) -> dict:
        profile = context.get("profile")
        card = context.get("card")
        url = context.get("url")
        session = self.profile_manager.start_session(profile.id)
        try:
            session.navigate(url)
            return {"status": "success", "card_used": card.id}
        finally:
            session.close()
