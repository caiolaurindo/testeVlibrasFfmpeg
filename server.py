# =========================================================
# serve.py
# =========================================================

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import os
import re
import time
import requests
import tempfile
import shutil
import subprocess
import traceback

from datetime import datetime

# =========================================================
# CONFIG
# =========================================================

app = Flask(__name__)
CORS(app)

MEDIA_DIR = "media"

if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)

# =========================================================
# RUNWAY CONFIG
# =========================================================

RUNWAY_API_KEY = "key_76addf21d5598d6e3fbe6deba43e1aaeba41dc54574a040dd07d2ad96a68003c90fdcaf30c6d913932677d70cd97960518ca8294f1ac7a044b025317b5f7a2c6"

RUNWAY_API_URL = "https://api.dev.runwayml.com/v1"

HEADERS = {
    "Authorization": f"Bearer {RUNWAY_API_KEY}",
    "Content-Type": "application/json",
    "X-Runway-Version": "2024-11-06"
}

# =========================================================
# TIMESTAMP
# =========================================================

def timestamp_para_segundos(ts):

    h, m, s_ms = ts.split(':')

    s, ms = s_ms.split(',')

    return (
        int(h) * 3600 +
        int(m) * 60 +
        int(s) +
        int(ms) / 1000
    )

# =========================================================
# PARSE SRT
# =========================================================

def parse_srt(text):

    blocks = re.split(r'\r?\n\r?\n', text.strip())

    entries = []

    for block in blocks:

        lines = block.strip().splitlines()

        if len(lines) < 2:
            continue

        try:

            time_line = next(
                l for l in lines if '-->' in l
            )

            times = time_line.split(' --> ')

            text_start_idx = (
                lines.index(time_line) + 1
            )

            original_text = ' '.join(
                lines[text_start_idx:]
            ).strip()

            start = times[0].strip()
            end = times[1].strip()

            start_seconds = (
                timestamp_para_segundos(start)
            )

            end_seconds = (
                timestamp_para_segundos(end)
            )

            duration = (
                end_seconds - start_seconds
            )

            entries.append({

                "start": start,
                "end": end,

                "start_seconds":
                    start_seconds,

                "end_seconds":
                    end_seconds,

                "duration":
                    duration,

                "original":
                    original_text
            })

        except Exception:
            continue

    return entries

# =========================================================
# NORMALIZA
# =========================================================

def normalizar(texto):

    ruidos = (
        r'\b(hmm|hm|ux|chou|hein|né|ah|oh|uh|ai)\b'
    )

    texto = re.sub(
        ruidos,
        '',
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r'[^\w\s]',
        ' ',
        texto
    )

    texto = re.sub(
        r'\s+',
        ' ',
        texto
    )

    return texto.strip().upper()

# =========================================================
# PROCESSAR SRT
# =========================================================

@app.route('/processar', methods=['POST'])
def processar():

    try:

        text = request.data.decode('utf-8')

        entries = parse_srt(text)

        for e in entries:

            e['glossa'] = normalizar(
                e['original']
            )

        return jsonify(entries)

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500

# =========================================================
# UPLOAD VIDEO
# =========================================================

def upload_video(video_path):

    print("⬆️ Criando upload...")

    response = requests.post(
        f"{RUNWAY_API_URL}/uploads",
        headers=HEADERS,
        json={

            "filename":
                os.path.basename(video_path),

            "numberOfBytes":
                os.path.getsize(video_path),

            "type":
                "ephemeral"
        }
    )

    print(response.text)

    if response.status_code not in [200, 201]:

        raise Exception(
            f"Erro upload:\n{response.text}"
        )

    data = response.json()

    upload_url = data["uploadUrl"]

    asset_id = data["id"]

    print("⬆️ Enviando vídeo...")

    with open(video_path, "rb") as f:

        put = requests.put(
            upload_url,
            data=f,
            headers={
                "Content-Type":
                    "video/mp4"
            }
        )

    print(f"PUT STATUS: {put.status_code}")

    if put.status_code not in [200, 201]:

        raise Exception(
            f"Erro PUT:\n{put.text}"
        )

    return asset_id

# =========================================================
# CREATE TASK
# =========================================================

def create_task(asset_id):

    print("🎬 Criando task Runway...")

    payload = {

        "model":
            "gen3a_turbo/video-to-video",

        "input": {

            "videoUri":
                asset_id,

            "promptText": """
Transform this sign language avatar into a realistic 3D human.

Keep hand gestures EXACTLY identical.

Preserve timing and synchronization.

Brazilian sign language interpreter.

Natural facial expressions.

Professional cinematic lighting.

Studio quality.

Realistic skin and eyes.

Smooth movements.

Do not crop hands.

Do not change camera angle.
"""
        }
    }

    response = requests.post(
        f"{RUNWAY_API_URL}/tasks",
        headers=HEADERS,
        json=payload
    )

    print(response.text)

    if response.status_code not in [200, 201]:

        raise Exception(
            f"Erro task:\n{response.text}"
        )

    data = response.json()

    return data["id"]

# =========================================================
# WAIT TASK
# =========================================================

def wait_task(task_id):

    print("⏳ Esperando geração IA...")

    while True:

        response = requests.get(
            f"{RUNWAY_API_URL}/tasks/{task_id}",
            headers=HEADERS
        )

        if response.status_code != 200:

            raise Exception(
                f"Erro status:\n{response.text}"
            )

        data = response.json()

        status = data["status"]

        print(f"🎬 STATUS: {status}")

        if status == "SUCCEEDED":

            output = data.get("output")

            print(output)

            if isinstance(output, list):

                return output[0]

            if isinstance(output, dict):

                if "video" in output:
                    return output["video"]

                if "url" in output:
                    return output["url"]

            raise Exception(
                f"Output desconhecido:\n{output}"
            )

        elif status == "FAILED":

            raise Exception(
                f"Task falhou:\n{data}"
            )

        time.sleep(5)

# =========================================================
# DOWNLOAD VIDEO
# =========================================================

def download_video(url, output_path):

    print("⬇️ Baixando vídeo IA...")

    response = requests.get(
        url,
        stream=True
    )

    with open(output_path, "wb") as f:

        shutil.copyfileobj(
            response.raw,
            f
        )

# =========================================================
# FFMPEG
# =========================================================

def optimize_video(input_path, output_path):

    print("⚡ Convertendo MP4...")

    command = [

        "ffmpeg",
        "-y",

        "-i", input_path,

        "-c:v", "libx264",

        "-preset", "medium",

        "-pix_fmt", "yuv420p",

        "-movflags", "+faststart",

        output_path
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:

        raise Exception(
            f"Erro FFmpeg:\n{result.stderr}"
        )

# =========================================================
# MELHORAR AVATAR
# =========================================================

@app.route(
    '/melhorar-avatar',
    methods=['POST']
)
def melhorar_avatar():

    try:

        if 'video' not in request.files:

            return jsonify({
                "error":
                    "Vídeo não enviado"
            }), 400

        video_file = request.files['video']

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        final_name = (
            f"avatar_realista_{timestamp}.mp4"
        )

        final_path = os.path.join(
            MEDIA_DIR,
            final_name
        )

        with tempfile.TemporaryDirectory() as tmpdir:

            input_path = os.path.join(
                tmpdir,
                "input.mp4"
            )

            runway_path = os.path.join(
                tmpdir,
                "runway.mp4"
            )

            final_tmp = os.path.join(
                tmpdir,
                "final.mp4"
            )

            # =====================================
            # SAVE INPUT
            # =====================================

            video_file.save(input_path)

            print("✅ Vídeo recebido")

            # =====================================
            # UPLOAD
            # =====================================

            asset_id = upload_video(
                input_path
            )

            print(
                f"✅ Asset ID: {asset_id}"
            )

            # =====================================
            # CREATE TASK
            # =====================================

            task_id = create_task(
                asset_id
            )

            print(
                f"✅ Task ID: {task_id}"
            )

            # =====================================
            # WAIT TASK
            # =====================================

            output_url = wait_task(
                task_id
            )

            print(
                f"✅ VIDEO URL: {output_url}"
            )

            # =====================================
            # DOWNLOAD
            # =====================================

            download_video(
                output_url,
                runway_path
            )

            # =====================================
            # FFMPEG
            # =====================================

            optimize_video(
                runway_path,
                final_tmp
            )

            # =====================================
            # SAVE FINAL
            # =====================================

            shutil.copy(
                final_tmp,
                final_path
            )

            print(
                f"✅ SALVO: {final_path}"
            )

            return send_file(
                final_path,
                as_attachment=True,
                download_name=
                    "avatar_realista.mp4"
            )

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error": str(e)
        }), 500

# =========================================================
# HEALTH
# =========================================================

@app.route('/')
def home():

    return jsonify({
        "status": "online"
    })

# =========================================================
# START
# =========================================================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False
    )