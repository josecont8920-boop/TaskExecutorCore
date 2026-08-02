from typing import List
import time
import logging
from .task import Task, TaskResult
from config.settings import settings

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(self, max_retries: int = settings.BATCH_MAX_RETRIES, delay: int = settings.BATCH_RETRY_DELAY_SECONDS):
        self.max_retries = max_retries
        self.delay = delay
        self.results: List[TaskResult] = []

    def execute(self, tasks: List[Task]) -> List[TaskResult]:
        for task in tasks:
            logger.info(f"Ejecutando tarea: {task.id}")
            result = self._execute_with_retry(task)
            self.results.append(result)
            
            if not result.success and task.critical:
                logger.error("Tarea crítica fallida. Deteniendo lote.")
                break
        return self.results

    def _execute_with_retry(self, task: Task) -> TaskResult:
        for attempt in range(1, self.max_retries + 1):
            try:
                result_data = task.action(task.context)
                logger.info(f"Tarea {task.id} completada en intento {attempt}")
                return TaskResult(task_id=task.id, success=True, data=result_data, attempts=attempt)
            except Exception as e:
                logger.warning(f"Intento {attempt} falló para tarea {task.id}: {e}")
                if attempt < self.max_retries:
                    time.sleep(self.delay * attempt)
                else:
                    logger.error(f"Tarea {task.id} falló después de {self.max_retries} intentos.")
                    return TaskResult(task_id=task.id, success=False, error=str(e), attempts=attempt)
        return TaskResult(task_id=task.id, success=False, error="Unknown error")
