# download_youtube_video.py
import os
from yt_dlp import YoutubeDL

downloads = {}


def progress_hook(session_id):
    def hook(d):
        if d['status'] == 'downloading':
            downloads[session_id]['progress'] = int(float(d['_percent_str'].strip('%')))
        elif d['status'] == 'finished':
            downloads[session_id]['progress'] = 100
            print(f"Download concluído para a sessão: {session_id}")

    return hook


def download_video(video_url, session_id, output_folder="videos/base"):
    os.makedirs(output_folder, exist_ok=True)

    try:
        with YoutubeDL({'quiet': True}) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            filename = "".join(
                c for c in info_dict.get('title', 'video') if c.isalnum() or c in (" ", ".", "_")).rstrip() + ".mp4"
            downloads[session_id] = {'filename': filename, 'progress': 0}

        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': f'{output_folder}/{filename}',
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook(session_id)],
            'nocheckcertificate': True
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        print(f"Arquivo salvo em: {os.path.join(output_folder, filename)}")

    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        downloads[session_id]['error'] = str(e)
