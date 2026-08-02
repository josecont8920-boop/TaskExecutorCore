from typing import Callable, Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid

class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    action: Callable  # Función que ejecuta la lógica de negocio
    context: Dict[str, Any] = {}  # Perfil, tarjeta, etc.
    critical: bool = False  # Si falla, detiene el batch

class TaskResult(BaseModel):
    task_id: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 1
