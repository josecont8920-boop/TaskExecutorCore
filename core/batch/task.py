from typing import Callable, Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid

class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    action: Callable
    context: Dict[str, Any] = {}
    critical: bool = False
    max_retries: Optional[int] = None

class TaskResult(BaseModel):
    task_id: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    attempts: int = 0
