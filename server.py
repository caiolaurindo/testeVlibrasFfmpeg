from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import re
import os
import subprocess
import tempfile
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuração da pasta de mídia
MEDIA_DIR = os.path.join(os.getcwd(), 'media')
if not os.path.exists(MEDIA_DIR):
    os.makedirs(MEDIA_DIR)

def parse_srt(text):
    blocks = re.split(r'\n\s*\n|\r\n\s*\r\n', text.strip())
    entries = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2: continue
        try:
            time_line = next(l for l in lines if '-->' in l)
            times = time_line.split(' --> ')
            text_start_idx = lines.index(time_line) + 1
            original_text = ' '.join(lines[text_start_idx:]).strip()
            
            entries.append({
                'start': times[0].strip(),
                'end': times[1].strip(),
                'original': original_text
            })
        except (StopIteration, IndexError): continue
    return entries

def normalizar(texto):
    ruidos = r'\b(hmm|hm|ux|chou|hein|né|ah|oh|uh|ai)\b'
    texto = re.sub(ruidos, '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'[^\w\s]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip().upper()

@app.route('/processar', methods=['POST'])
def processar():
    try:
        text = request.data.decode('utf-8')
        entries = parse_srt(text)
        for e in entries:
            e['glossa'] = normalizar(e['original'])
        return jsonify(entries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/converter', methods=['POST'])
def converter():
    if 'video' not in request.files:
        return jsonify({'error': 'Arquivo de vídeo não encontrado'}), 400

    webm_file = request.files['video']
    
    # Gera um nome de arquivo único para a pasta media
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_filename = f"libras_{timestamp}.mp4"
    final_path = os.path.join(MEDIA_DIR, final_filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        input_p = os.path.join(tmpdir, 'in.webm')
        # No Windows, caminhos com espaços precisam de aspas no comando shell
        output_p = os.path.join(tmpdir, 'out.mp4')
        
        webm_file.save(input_p)
        
        # Comando do FFmpeg otimizado
        # Usamos shell=True no Windows para facilitar a localização do executável
        command = [
            'ffmpeg', '-y',
            '-i', f'"{input_p}"',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            f'"{output_p}"'
        ]
        
        command_str = " ".join(command)

        try:
            result = subprocess.run(command_str, capture_output=True, text=True, shell=True)
            
            if result.returncode != 0:
                print(f"Erro FFmpeg: {result.stderr}")
                return jsonify({'error': 'Erro no FFmpeg', 'details': result.stderr}), 500
            
            # Move ou copia o arquivo para a pasta media permanente
            import shutil
            shutil.copy(output_p.replace('"', ''), final_path)
            
            print(f"✅ Vídeo salvo em: {final_path}")
                
            return send_file(final_path, as_attachment=True, download_name='libras.mp4')
        except Exception as e:
            print(f"Erro no Servidor: {str(e)}")
            return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)