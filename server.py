from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from core.orchestrator import Orchestrator
import os

app = FastAPI(title="TaskExecutorCore API", version="1.0")
orchestrator = Orchestrator()

class TaskItem(BaseModel):
    profile_name: str
    url: str
    data: Dict[str, Any] = {}
    critical: bool = False

class FlowRequest(BaseModel):
    tasks: List[TaskItem]

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    path = "frontend/index.html"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>TaskExecutorCore Online</h1>"

@app.get("/health")
@app.get("/api/health")
def health_check():
    return {"status": "online", "system": "TaskExecutorCore"}

@app.post("/api/run-flow")
def run_flow(request: FlowRequest):
    try:
        task_dicts = [t.model_dump() for t in request.tasks]
        orchestrator.run_flow(task_dicts)
        return {"status": "success", "message": "Flujo ejecutado correctamente en el servidor."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
