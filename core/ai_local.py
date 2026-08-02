import subprocess
import json

def ejecutar_comando_ia(prompt: str, modelo: str = "llama3") -> str:
    """
    Ejecuta un modelo de código abierto localmente en tu entorno 
    bajo parámetros estrictos de comandos.
    """
    try:
        # Comando directo para interactuar con Ollama en la terminal
        cmd = ["ollama", "run", modelo, prompt]
        resultado = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return resultado.stdout.strip()
    except Exception as e:
        return f"Error ejecutando modelo local: {str(e)}"
