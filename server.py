from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from core.orchestrator import Orchestrator
import os

app = FastAPI(title="TaskExecutorCore API", version="1.0")
orchestrator = Orchestrator()

# Memoria temporal para el estado actual del flujo
current_flow_state = {
    "status": "Inactivo",
    "step": "Esperando ejecución",
    "tasks_total": 0,
    "completed": 0,
    "details": []
}

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

@app.get("/api/flow-status")
def get_flow_status():
    return current_flow_state

@app.post("/api/run-flow")
def run_flow(request: FlowRequest):
    global current_flow_state
    try:
        task_dicts = [t.model_dump() for t in request.tasks]
        
        current_flow_state = {
            "status": "Ejecutando",
            "step": "Procesando tareas en lote",
            "tasks_total": len(task_dicts),
            "completed": 0,
            "details": task_dicts
        }
        
        orchestrator.run_flow(task_dicts)
        
        current_flow_state["status"] = "Completado"
        current_flow_state["step"] = "Todas las tareas listas y orquestadas"
        current_flow_state["completed"] = len(task_dicts)
        
        return {"status": "success", "message": "Flujo ejecutado correctamente.", "state": current_flow_state}
    except Exception as e:
        current_flow_state["status"] = "Error"
        current_flow_state["step"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))
