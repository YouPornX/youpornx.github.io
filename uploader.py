"""
uploader.py — Automatiza la subida de videos a YouPornX
=========================================================
Por cada video en la carpeta indicada:
  1. Extrae una captura de pantalla con ffmpeg
  2. Sube la imagen a ImgBB
  3. Sube el video a Catbox
  4. Genera la línea lista para pegar en data.js

REQUISITOS:
  pip install requests
  ffmpeg instalado (https://www.gyan.dev/ffmpeg/builds/)

USO:
  python uploader.py
  python uploader.py --carpeta C:/Videos --categoria Sex --segundo 5
"""

import sys
import base64
import argparse
import subprocess
import requests
from pathlib import Path
from datetime import datetime

# ══════════════════════════════════════════════════════
#  CONFIGURACIÓN — edita esto
# ══════════════════════════════════════════════════════
IMGBB_API_KEY     = "3ff115cfbfa713f24ce89cc2f39e8823"
CARPETA_VIDEOS    = "./videos"
CARPETA_CAPTURAS  = "./capturas"
SEGUNDO_CAPTURA   = 12
CATEGORIA_DEFAULT = "Sex"
OUTPUT_FILE       = "nuevos_videos.txt"
# ══════════════════════════════════════════════════════

EXTENSIONES_VIDEO = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv"}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def duracion_video(ruta):
    try:
        r = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(ruta)
        ], capture_output=True, text=True, timeout=30)
        segundos = float(r.stdout.strip())
        return f"{int(segundos // 60)}:{int(segundos % 60):02d}"
    except Exception:
        return "0:00"


def sacar_captura(ruta_video, ruta_salida, segundo):
    try:
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(segundo),
            "-i", str(ruta_video),
            "-frames:v", "1", "-q:v", "2",
            str(ruta_salida)
        ], capture_output=True, timeout=60)
        return ruta_salida.exists()
    except Exception as e:
        log(f"  ERROR ffmpeg: {e}")
        return False


def subir_imgbb(ruta_imagen, api_key):
    """Sube imagen a ImgBB y devuelve la URL completa."""
    try:
        with open(ruta_imagen, "rb") as f:
            imagen_b64 = base64.b64encode(f.read()).decode("utf-8")

        r = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "image": imagen_b64},
            timeout=60
        )
        resp = r.json()
        if resp.get("success"):
            # Guardamos la URL completa porque ImgBB la necesita para mostrar la imagen
            url = resp["data"]["url"]
            return url
        else:
            log(f"  ERROR ImgBB: {resp.get('error', {}).get('message', 'desconocido')}")
            return None
    except Exception as e:
        log(f"  ERROR ImgBB: {e}")
        return None


def subir_catbox(ruta_video):
    """Sube video a Catbox y devuelve el ID."""
    try:
        with open(ruta_video, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload", "userhash": ""},
                files={"fileToUpload": (ruta_video.name, f)},
                timeout=300
            )
        url = r.text.strip()
        if url.startswith("https://files.catbox.moe/"):
            return Path(url).stem, url
        else:
            log(f"  ERROR Catbox: {url[:100]}")
            return None, None
    except Exception as e:
        log(f"  ERROR Catbox: {e}")
        return None, None


def nombre_a_titulo(nombre):
    stem = Path(nombre).stem
    return stem.replace("_", " ").replace("-", " ").title()


def procesar_videos(carpeta, categoria, segundo, api_key):
    carpeta = Path(carpeta)
    cap_dir = Path(CARPETA_CAPTURAS)
    cap_dir.mkdir(exist_ok=True)

    videos = sorted([f for f in carpeta.iterdir() if f.suffix.lower() in EXTENSIONES_VIDEO])

    if not videos:
        log(f"No se encontraron videos en '{carpeta}'")
        return

    log(f"Videos encontrados: {len(videos)}")
    log("=" * 55)

    lineas = []

    for i, video in enumerate(videos, 1):
        log(f"\n[{i}/{len(videos)}] {video.name}")

        dur = duracion_video(video)
        log(f"  Duración: {dur}")

        captura = cap_dir / (video.stem + ".jpg")
        log(f"  Extrayendo captura en segundo {segundo}...")
        if not sacar_captura(video, captura, segundo):
            log("  ⚠ No se pudo extraer captura, saltando.")
            continue
        log(f"  ✅ Captura guardada")

        log(f"  Subiendo a ImgBB...")
        img_url = subir_imgbb(captura, api_key)
        if not img_url:
            log("  ⚠ Error subiendo a ImgBB, saltando.")
            continue
        log(f"  ✅ ImgBB → {img_url}")

        log(f"  Subiendo a Catbox (puede tardar)...")
        catbox_id, catbox_url = subir_catbox(video)
        if not catbox_id:
            log("  ⚠ Error subiendo a Catbox, saltando.")
            continue
        log(f"  ✅ Catbox → {catbox_url}")

        titulo = nombre_a_titulo(video.name)
        # img_url es la URL completa de ImgBB, catbox_id es solo el ID
        linea = f'    ["{titulo}","{dur}","{categoria}","{img_url}","{catbox_id}"],'
        lineas.append(linea)
        log(f"  📋 {linea}")

    log("\n" + "=" * 55)
    if lineas:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("// Pega estas líneas dentro del array v: [] en tu data.js\n\n")
            for l in lineas:
                f.write(l + "\n")
        log(f"✅ {len(lineas)} líneas guardadas en '{OUTPUT_FILE}'")
    else:
        log("No se generó ninguna línea.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--carpeta",   default=CARPETA_VIDEOS)
    parser.add_argument("--categoria", default=CATEGORIA_DEFAULT)
    parser.add_argument("--segundo",   default=SEGUNDO_CAPTURA, type=int)
    parser.add_argument("--apikey",    default=IMGBB_API_KEY)
    args = parser.parse_args()

    print("=" * 55)
    print("  YouPornX — Uploader automático")
    print("=" * 55)

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
    except FileNotFoundError:
        print("\n❌ ffmpeg no está instalado.")
        sys.exit(1)

    procesar_videos(args.carpeta, args.categoria, args.segundo, args.apikey)


if __name__ == "__main__":
    main()
