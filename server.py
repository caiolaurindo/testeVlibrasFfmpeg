from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import re
import os
import subprocess
import tempfile
import shutil
from datetime import datetime

app = Flask(__name__)
CORS(app)

# =========================================================
# CONFIG
# =========================================================

MEDIA_DIR = os.path.join(os.getcwd(), 'media')

if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)

# =========================================================
# UTILIDADES
# =========================================================

def timestamp_para_segundos(ts):
    """
    Converte:
    00:00:02,500
    para:
    2.5
    """

    h, m, s_ms = ts.split(':')
    s, ms = s_ms.split(',')

    return (
        int(h) * 3600 +
        int(m) * 60 +
        int(s) +
        int(ms) / 1000
    )

def segundos_para_ffmpeg(segundos):
    """
    Converte segundos float para formato:
    HH:MM:SS.mmm
    """

    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    secs = segundos % 60

    return f"{horas:02}:{minutos:02}:{secs:06.3f}"

# =========================================================
# PARSER SRT
# =========================================================

def parse_srt(text):

    blocks = re.split(r'\r?\n\r?\n', text.strip())

    entries = []

    for block in blocks:

        lines = block.strip().splitlines()

        if len(lines) < 2:
            continue

        try:
            time_line = next(l for l in lines if '-->' in l)

            times = time_line.split(' --> ')

            text_start_idx = lines.index(time_line) + 1

            original_text = ' '.join(lines[text_start_idx:]).strip()

            start = times[0].strip()
            end = times[1].strip()

            start_seconds = timestamp_para_segundos(start)
            end_seconds = timestamp_para_segundos(end)

            duration = end_seconds - start_seconds

            entries.append({
                'start': start,
                'end': end,
                'start_seconds': start_seconds,
                'end_seconds': end_seconds,
                'duration': duration,
                'original': original_text
            })

        except Exception:
            continue

    return entries

# =========================================================
# NORMALIZAÇÃO PARA GLOSSA
# =========================================================

def normalizar(texto):

    ruidos = r'\b(hmm|hm|ux|chou|hein|né|ah|oh|uh|ai)\b'

    texto = re.sub(ruidos, '', texto, flags=re.IGNORECASE)

    texto = re.sub(r'[^\w\s]', ' ', texto)

    texto = re.sub(r'\s+', ' ', texto)

    return texto.strip().upper()

# =========================================================
# ENDPOINT PROCESSAR SRT
# =========================================================

@app.route('/processar', methods=['POST'])
def processar():

    try:

        text = request.data.decode('utf-8')

        entries = parse_srt(text)

        for e in entries:
            e['glossa'] = normalizar(e['original'])

        return jsonify(entries)

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

# =========================================================
# CONVERTER WEBM -> MP4
# =========================================================

@app.route('/converter', methods=['POST'])
def converter():

    if 'video' not in request.files:
        return jsonify({
            'error': 'Arquivo de vídeo não encontrado'
        }), 400

    webm_file = request.files['video']

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    final_filename = f"libras_{timestamp}.mp4"

    final_path = os.path.join(MEDIA_DIR, final_filename)

    with tempfile.TemporaryDirectory() as tmpdir:

        input_p = os.path.join(tmpdir, 'input.webm')

        output_p = os.path.join(tmpdir, 'output.mp4')

        webm_file.save(input_p)

        command = [
            'ffmpeg',
            '-y',
            '-i', input_p,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_p
        ]

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:

                print(result.stderr)

                return jsonify({
                    'error': 'Erro no FFmpeg',
                    'details': result.stderr
                }), 500

            shutil.copy(output_p, final_path)

            print(f'✅ Vídeo salvo em: {final_path}')

            return send_file(
                final_path,
                as_attachment=True,
                download_name='libras.mp4'
            )

        except Exception as e:

            return jsonify({
                'error': str(e)
            }), 500

# =========================================================
# RECORTAR VIDEO PELO SRT
# =========================================================

@app.route('/sincronizar', methods=['POST'])
def sincronizar():

    """
    Espera:
    - video => gravação completa do VLibras
    - srt => arquivo srt

    Retorna:
    - vídeo sincronizado
    """

    if 'video' not in request.files:
        return jsonify({
            'error': 'Vídeo não enviado'
        }), 400

    if 'srt' not in request.files:
        return jsonify({
            'error': 'SRT não enviado'
        }), 400

    video_file = request.files['video']
    srt_file = request.files['srt']

    srt_text = srt_file.read().decode('utf-8')

    entries = parse_srt(srt_text)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    final_filename = f'sincronizado_{timestamp}.mp4'

    final_path = os.path.join(MEDIA_DIR, final_filename)

    with tempfile.TemporaryDirectory() as tmpdir:

        input_video = os.path.join(tmpdir, 'input.webm')

        converted_video = os.path.join(tmpdir, 'converted.mp4')

        concat_file = os.path.join(tmpdir, 'concat.txt')

        video_file.save(input_video)

        # =====================================================
        # CONVERTE WEBM PARA MP4
        # =====================================================

        convert_command = [
            'ffmpeg',
            '-y',
            '-i', input_video,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            converted_video
        ]

        result = subprocess.run(
            convert_command,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:

            return jsonify({
                'error': result.stderr
            }), 500

        segment_paths = []

        # =====================================================
        # CRIA SEGMENTOS BASEADOS NO SRT
        # =====================================================

        for idx, entry in enumerate(entries):

            start = entry['start_seconds']
            duration = entry['duration']

            segment_path = os.path.join(
                tmpdir,
                f'segment_{idx}.mp4'
            )

            segment_command = [
                'ffmpeg',
                '-y',
                '-ss', str(start),
                '-i', converted_video,
                '-t', str(duration),
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-pix_fmt', 'yuv420p',
                '-an',
                segment_path
            ]

            result = subprocess.run(
                segment_command,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:

                print(result.stderr)

                continue

            segment_paths.append(segment_path)

        # =====================================================
        # CONCATENA TODOS OS SEGMENTOS
        # =====================================================

        with open(concat_file, 'w', encoding='utf-8') as f:

            for path in segment_paths:
                f.write(f"file '{path}'\n")

        concat_command = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            final_path
        ]

        result = subprocess.run(
            concat_command,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:

            return jsonify({
                'error': result.stderr
            }), 500

        print(f'✅ Vídeo sincronizado salvo em: {final_path}')

        return send_file(
            final_path,
            as_attachment=True,
            download_name='video_sincronizado.mp4'
        )

# =========================================================
# HEALTH CHECK
# =========================================================

@app.route('/')
def home():
    return jsonify({
        'status': 'online'
    })

# =========================================================
# START
# =========================================================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )