# ContentBotMXL

Motor backend aislado que genera los videos verticales del canal
**mxl Aprende** (robot MXL, contenido educativo infantil). Diseñado para
correr como el **Servidor 2** de una arquitectura de dos servidores
independientes:

- **Servidor 1 — n8n (externo):** orquestador principal. Dispara los
  flujos, decide cuándo generar un video, y llama al webhook de este
  servicio.
- **Servidor 2 — este repo (Railway):** motor aislado. No orquesta nada,
  no llama a n8n, **no usa base de datos**. Todo lo que necesita
  (imágenes del robot MXL y `prompt_maestro.txt`) vive versionado en este
  mismo repositorio de GitHub, del cual Railway despliega directamente.

## Flujo

```
n8n  --POST /webhook/generar {"tema": "..."}-->  ContentBotMXL (Railway)
                                                       |
                                                       v
                                          Gemini genera el guion
                                          (usa prompt_maestro.txt)
                                                       |
                                                       v
                                  Google Cloud TTS sintetiza la voz
                                          de cada escena
                                                       |
                                                       v
                                  Se arma el video con las imágenes
                                  de assets/mxl_robot/<emocion>/
                                                       |
                                                       v
n8n  <---------- estructura final del video (JSON) ----------
```

## Variables de entorno (únicas que usa el servicio)

| Variable | Uso |
|---|---|
| `GEMINI_API_KEY` | Generación del guion con Gemini |
| `GOOGLE_TTS_API_KEY` | Voz — Google Cloud TTS, método API key |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Voz — cuenta de servicio de Google Cloud (tiene prioridad sobre la API key si ambas están presentes) |
| `N8N_WEBHOOK_SECRET` | Autenticación del webhook (header `X-Webhook-Secret`) |

No hay ninguna otra variable ni integración externa. Sin base de datos.

## Endpoints

- `GET /health` — healthcheck de Railway.
- `POST /webhook/generar` — endpoint que llama n8n.
  Header: `X-Webhook-Secret: <N8N_WEBHOOK_SECRET>`
  Body: `{"tema": "Los colores primarios", "num_escenas": 4}`
  Responde de forma **síncrona** con la estructura final:
  ```json
  {
    "titulo": "Los colores primarios",
    "run_id": "20260719_120500",
    "archivo": "los_colores_primarios_20260719_120500.mp4",
    "ruta_relativa": "output/los_colores_primarios_20260719_120500.mp4",
    "duracion_total_seg": 24.8,
    "musica": "assets/musica/fondo_01.mp3",
    "escenas": [
      {"orden": 1, "emocion": "feliz", "texto": "...", "imagen": "assets/mxl_robot/feliz/01.png", "duracion_seg": 4.2}
    ]
  }
  ```
  Configura un timeout de 2-3 minutos en el nodo HTTP Request de n8n:
  Gemini + TTS + render de video no son instantáneos.
- `GET /output/{nombre_archivo}` — descarga el mp4 generado (mismo header
  de autenticación). Usa el valor de `archivo` de la respuesta anterior.

## Estructura del repo

```
assets/mxl_robot/<emocion>/   -> imágenes del robot MXL por emoción
                                  (feliz, pensativo, sorprendido, con_amigos, hablando)
assets/musica/                -> pistas de fondo opcionales (.mp3/.wav/.ogg)
prompt_maestro.txt            -> instrucción base que Gemini usa para escribir el guion
core/gemini_client.py         -> llama a Gemini y genera el guion (titulo + escenas)
core/tts_client.py            -> llama a Google Cloud TTS y sintetiza la voz
core/asset_manager.py         -> indexa y elige imágenes por emoción
productor_mxl.py              -> ensambla el video final (moviepy)
main.py                       -> API FastAPI / webhook para n8n
```

## Uso manual (sin pasar por n8n)

También se puede procesar un lote de guiones JSON locales, sin Gemini,
colocándolos en `data/guiones/pendientes/`:

```bash
python3 productor_mxl.py                    # procesa todos los pendientes
python3 productor_mxl.py ruta/al/guion.json  # procesa uno especifico
```

Cada JSON debe tener la forma:
```json
{"titulo": "...", "escenas": [{"emocion": "feliz", "texto": "..."}]}
```
