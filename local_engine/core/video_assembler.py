"""Ensamblaje del video final: imagenes + audio + subtitulos + musica.
100% local con MoviePy y FFmpeg, sin dependencias de pago."""
from pathlib import Path
import sys
import random

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    OUTPUT_DIR, RESOLUCIONES, FORMATO_DEFAULT,
    SUBTITULO_FONT, SUBTITULO_TAMANO, SUBTITULO_COLOR,
    ASSETS_MUSIC,
)

# Parche de compatibilidad: Pillow >=10 elimino Image.ANTIALIAS,
# que MoviePy 1.0.3 todavia usa internamente.
from PIL import Image as _PILImage
if not hasattr(_PILImage, "ANTIALIAS"):
    _PILImage.ANTIALIAS = _PILImage.LANCZOS

from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, TextClip, CompositeAudioClip,
    afx,
)


def ensamblar_video(escenas: list[dict], run_id: str, titulo: str,
                     formato: str = None) -> Path:
    formato = formato or FORMATO_DEFAULT
    ancho, alto = RESOLUCIONES[formato]

    clips = []
    for escena in escenas:
        clip = _construir_clip_escena(escena, ancho, alto)
        clips.append(clip)

    video_final = concatenate_videoclips(clips, method="compose", padding=-0.3)
    video_final = _agregar_musica_fondo(video_final)

    salida = OUTPUT_DIR / f"{_slug(titulo)}_{run_id}.mp4"
    video_final.write_videofile(
        str(salida), fps=30, codec="libx264", audio_codec="aac",
        threads=4, preset="medium",
    )
    return salida


def _construir_clip_escena(escena: dict, ancho: int, alto: int):
    audio = AudioFileClip(escena["audio_ruta"])
    duracion = audio.duration

    imagen = ImageClip(escena["imagen_ruta"]).set_duration(duracion)
    imagen = imagen.resize(height=alto)
    if imagen.w < ancho:
        imagen = imagen.resize(width=ancho)

    imagen = _aplicar_ken_burns(imagen, duracion, ancho, alto)
    imagen = imagen.set_audio(audio)

    subtitulo = _crear_subtitulo(escena["texto"], duracion, ancho, alto)

    return CompositeVideoClip([imagen, subtitulo], size=(ancho, alto))


def _aplicar_ken_burns(clip, duracion, ancho, alto):
    zoom_inicial = 1.0
    zoom_final = random.uniform(1.08, 1.18)
    if random.random() > 0.5:
        zoom_inicial, zoom_final = zoom_final, zoom_inicial

    def efecto_zoom(t):
        progreso = t / duracion if duracion > 0 else 0
        return zoom_inicial + (zoom_final - zoom_inicial) * progreso

    return clip.resize(efecto_zoom).set_position("center")


def _crear_subtitulo(texto: str, duracion: float, ancho: int, alto: int):
    txt_clip = TextClip(
        texto, fontsize=SUBTITULO_TAMANO, color=SUBTITULO_COLOR,
        font=SUBTITULO_FONT, method="caption", size=(int(ancho * 0.85), None),
        stroke_color="black", stroke_width=2,
    )
    txt_clip = txt_clip.set_duration(duracion)
    txt_clip = txt_clip.set_position(("center", int(alto * 0.78)))
    return txt_clip.fadein(0.2).fadeout(0.2)


def _agregar_musica_fondo(video):
    pistas = list(ASSETS_MUSIC.glob("*.mp3")) + list(ASSETS_MUSIC.glob("*.wav"))
    if not pistas:
        return video

    pista = random.choice(pistas)
    musica = AudioFileClip(str(pista)).fx(afx.audio_loop, duration=video.duration)
    musica = musica.fx(afx.volumex, 0.15).fx(afx.audio_fadein, 1).fx(afx.audio_fadeout, 1)

    audio_final = CompositeAudioClip([video.audio, musica])
    return video.set_audio(audio_final)


def _slug(texto: str) -> str:
    import re
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9\s-]", "", texto)
    texto = re.sub(r"[\s-]+", "_", texto)
    return texto[:50]
