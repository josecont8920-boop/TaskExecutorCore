import os
from googleapiclient.http import MediaFileUpload

def subir_miniatura_video(youtube_service, video_id, ruta_imagen):
    """
    Sube y asigna una imagen de portada (miniatura) a un video de YouTube ya subido.
    """
    if not ruta_imagen or not os.path.exists(ruta_imagen):
        print(f"No se encontró la imagen de portada en la ruta: {ruta_imagen}")
        return None

    try:
        request = youtube_service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(ruta_imagen)
        )
        response = request.execute()
        print(f"¡Portada/miniatura asignada correctamente al video {video_id}!")
        return response
    except Exception as e:
        print(f"Error al subir la miniatura a YouTube: {e}")
        return None
