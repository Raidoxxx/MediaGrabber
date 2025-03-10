from flask import Flask, render_template, request, jsonify, send_file
import download_youtube_video as downloadYouTube
import threading
import os
from uuid import uuid4
import time
from google.cloud import storage

app = Flask(__name__)

client_status = {}

DOWNLOAD_FOLDER = "/app/videos/base"

# Verifica se a pasta de downloads existe e cria se necessário
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Configura o caminho para o arquivo de credenciais do Google Cloud
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "keys.json"


def upload_to_gcs(source_file_name, destination_blob_name, bucket_name="mediagrabber"):
    # Inicializa o cliente do Google Cloud Storage
    storage_client = storage.Client()

    # Acessa o bucket
    bucket = storage_client.bucket(bucket_name)

    # Cria um objeto blob no bucket
    blob = bucket.blob(destination_blob_name)

    # Faz o upload do arquivo para o Google Cloud Storage
    blob.upload_from_filename(source_file_name)

    print(f"Arquivo {source_file_name} enviado para o bucket {bucket_name} como {destination_blob_name}.")


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    client_ip = request.remote_addr

    # Limita um download por cliente
    if client_status.get(client_ip) == "in_progress":
        return jsonify({'status': 'error', 'message': 'Você já tem um download em andamento.'}), 403

    client_status[client_ip] = "in_progress"

    url = request.form['url']
    session_id = str(uuid4())
    downloadYouTube.downloads[session_id] = {'filename': '', 'progress': 0}

    # Inicia o download em uma nova thread
    download_thread = threading.Thread(target=download_and_finalize, args=(url, session_id, client_ip))
    download_thread.start()

    return jsonify({'status': 'Download started', 'session_id': session_id})


def download_and_finalize(url, session_id, client_ip):
    downloadYouTube.download_video(url, session_id)

    # Aguarda o download ser concluído
    while downloadYouTube.downloads[session_id]['progress'] < 100:
        time.sleep(1)

    # Define o status do cliente como "completed"
    client_status[client_ip] = "completed"

    # Faz o upload para o Google Cloud Storage após o download
    filename = downloadYouTube.downloads[session_id]['filename']
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        upload_to_gcs(file_path, f"videos/{filename}")
        print(f"Upload do arquivo {filename} concluído no Google Cloud Storage.")


@app.route('/progress/<session_id>')
def progress(session_id):
    if session_id in downloadYouTube.downloads:
        data = downloadYouTube.downloads[session_id]
        return jsonify({'progress': data.get('progress', 0), 'title': data.get('filename', '')})
    else:
        return jsonify({'error': 'Session not found'}), 404


@app.route('/download/<session_id>')
def download_file(session_id):
    data = downloadYouTube.downloads.get(session_id)
    if data and 'filename' in data:
        file_path = os.path.join(DOWNLOAD_FOLDER, data['filename'])
        if os.path.exists(file_path):
            response = send_file(file_path, as_attachment=True)
            return response
    return jsonify({"error": "File not found"}), 404


def cleanup_old_files(delay=60):
    time.sleep(60)
    while True:
        now = time.time()
        for filename in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                file_age = now - os.path.getmtime(file_path)
                if file_age > delay:
                    try:
                        os.remove(file_path)
                        print(f"Arquivo {file_path} apagado após {delay} segundos.")
                    except Exception as e:
                        print(f"Erro ao tentar apagar o arquivo {file_path}: {e}")
        time.sleep(10)


# Inicia a thread para limpar arquivos antigos
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
