"""Orquesta el pipeline completo: texto -> escenas -> audio -> video final."""
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.text_input import cargar_texto
from core.scene_processor import dividir_en_escenas
from core.tts_engine import sintetizar_escena
from core.video_assembler import ensamblar_video
from core.asset_selector import elegir_imagen_por_emocion


def generar_video(fuente_texto: str, titulo: str, formato: str = None) -> dict:
    """Punto de entrada unico. fuente_texto puede ser texto plano, .txt o .pdf"""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    texto = cargar_texto(fuente_texto)
    if not texto.strip():
        raise ValueError("El texto de entrada esta vacio")

    escenas_base = dividir_en_escenas(texto)
    if not escenas_base:
        raise ValueError("No se pudo dividir el texto en escenas")

    escenas_completas = []
    for escena in escenas_base:
        audio_info = sintetizar_escena(escena["texto"], run_id, escena["orden"])
        imagen_ruta = elegir_imagen_por_emocion(escena["emocion"])

        escenas_completas.append({
            "orden": escena["orden"],
            "texto": escena["texto"],
            "emocion": escena["emocion"],
            "audio_ruta": audio_info["ruta"],
            "duracion_seg": audio_info["duracion_seg"],
            "imagen_ruta": imagen_ruta,
        })

    ruta_video = ensamblar_video(escenas_completas, run_id, titulo, formato)

    return {
        "run_id": run_id,
        "titulo": titulo,
        "archivo": ruta_video.name,
        "ruta_completa": str(ruta_video),
        "num_escenas": len(escenas_completas),
        "duracion_total_seg": round(sum(e["duracion_seg"] for e in escenas_completas), 2),
    }
