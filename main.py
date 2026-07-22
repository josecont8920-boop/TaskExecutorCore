from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import os

app = FastAPI()

VIDEOS_DIR = "videos"

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/webhook/generar")
async def recibir_webhook_generar(request: Request, x_webhook_secret: str = Header(None)):
    # Validar opcionalmente el secreto si lo deseas
    datos = await request.json()
    # Aquí puedes procesar la data que te manda n8n
    return {"status": "success", "message": "Webhook recibido correctamente", "data": datos}

@app.get("/videos", response_class=HTMLResponse)
def listar_y_descargar_videos():
    if not os.path.exists(VIDEOS_DIR):
        os.makedirs(VIDEOS_DIR)
    archivos = os.listdir(VIDEOS_DIR)
    videos = [f for f in archivos if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]
    
    html = "<html><body style='font-family:Arial;background:#0f172a;color:#f8fafc;padding:40px;'>"
    html += "<h1 style='color:#38bdf8;'>Panel de Videos - ContentBotMXL</h1>"
    if not videos:
        html += "<p>No hay videos generados todavía.</p>"
    else:
        for v in videos:
            html += f"<div style='background:#1e293b;padding:15px;margin-bottom:10px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;'><span>{v}</span><a style='background:#0284c7;color:white;padding:10px 18px;text-decoration:none;border-radius:5px;font-weight:bold;' href='/videos/download/{v}' target='_blank'>Descargar</a></div>"
    html += "</body></html>"
    return HTMLResponse(content=html)

@app.get("/videos/download/{nombre_archivo}")
def descargar_video_archivo(nombre_archivo: str):
    ruta_archivo = os.path.join(VIDEOS_DIR, nombre_archivo)
    if os.path.exists(ruta_archivo):
        return FileResponse(ruta_archivo, media_type="video/mp4", filename=nombre_archivo)
    return {"detail": "Video no encontrado"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
