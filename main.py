import sys
import logging
from config.settings import settings
from config.logging_config import setup_logging
from core.orchestrator import Orchestrator

def load_tasks_from_source():
    return [
        {"profile_name": "task_1", "url": "https://example.com/checkout", "data": {"product": "X"}, "critical": True},
        {"profile_name": "task_2", "url": "https://example.com/checkout", "data": {"product": "Y"}, "critical": False},
    ]

if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    
    if not settings.VCC_API_KEY:
        logger.warning("VCC_API_KEY no configurada. Usando proveedor mock por defecto.")

    try:
        orchestrator = Orchestrator()
        tasks = load_tasks_from_source()
        orchestrator.run_flow(tasks)
    except Exception as e:
        logger.critical(f"Error fatal en la orquestación: {e}", exc_info=True)
        sys.exit(1)
