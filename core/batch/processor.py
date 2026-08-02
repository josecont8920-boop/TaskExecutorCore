from typing import List, Callable, Any
import time
import logging
from datetime import datetime
from .task import Task, TaskResult
from config.settings import settings
from tqdm import tqdm

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(self, max_retries: int = settings.BATCH_MAX_RETRIES, delay: int = settings.BATCH_RETRY_DELAY_SECONDS):
        self.max_retries = max_retries
        self.delay = delay
        self.results: List[TaskResult] = []
        self.start_time = None
        self.end_time = None
    
    def execute(self, tasks: List[Task]) -> List[TaskResult]:
        self.start_time = datetime.now()
        logger.info(f"🚀 Iniciando ejecución de {len(tasks)} tareas")
        
        with tqdm(total=len(tasks), desc="Procesando tareas", unit="tarea") as pbar:
            for task in tasks:
                result = self._execute_with_retry(task)
                self.results.append(result)
                pbar.update(1)
                pbar.set_postfix({
                    "éxito": sum(1 for r in self.results if r.success),
                    "fallo": sum(1 for r in self.results if not r.success)
                })
                if not result.success and task.critical:
                    logger.error(f"❌ Tarea crítica {task.id} falló. Deteniendo lote.")
                    break
        
        self.end_time = datetime.now()
        return self.results

    def _execute_with_retry(self, task: Task) -> TaskResult:
        max_retries = task.max_retries or self.max_retries
        for attempt in range(1, max_retries + 1):
            try:
                result_data = task.action(task.context)
                return TaskResult(task_id=task.id, success=True, data=result_data, attempts=attempt)
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(self.delay)
                else:
                    return TaskResult(task_id=task.id, success=False, error=str(e), attempts=attempt)
        return TaskResult(task_id=task.id, success=False, error="Máximo de reintentos alcanzado", attempts=max_retries)

    def get_summary(self) -> dict:
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        return {
            "total_tasks": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "elapsed_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0
        }
