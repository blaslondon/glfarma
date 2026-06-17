import os
import io
import logging
import time
import json
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import pdfplumber
from src.embeddings import add_document, get_chroma_client

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_NAME = "normas para bot"
PROCESSED_FILE = Path("data/processed_files.json")


def get_drive_service():
    sa_env = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    # Soporta tanto path a archivo como JSON string directo
    if sa_env.strip().startswith("{"):
        info = json.loads(sa_env)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(sa_env, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def load_processed_files():
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE) as f:
            return json.load(f)
    return {}


def save_processed_files(processed):
    PROCESSED_FILE.parent.mkdir(exist_ok=True)
    with open(PROCESSED_FILE, "w") as f:
        json.dump(processed, f)


def get_folder_id(service):
    result = service.files().list(
        q=f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)"
    ).execute()
    files = result.get("files", [])
    if not files:
        raise ValueError(f"Carpeta '{FOLDER_NAME}' no encontrada en Drive")
    return files[0]["id"]


def list_pdfs_in_folder(service, folder_id):
    result = service.files().list(
        q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
        fields="files(id, name, modifiedTime)"
    ).execute()
    return result.get("files", [])


def download_pdf(service, file_id):
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buffer.seek(0)
    return buffer


def extract_text_from_pdf(pdf_buffer):
    text_chunks = []
    with pdfplumber.open(pdf_buffer) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                text_chunks.append({
                    "page": i + 1,
                    "text": text.strip()
                })
    return text_chunks


def process_new_pdfs():
    """Detecta PDFs nuevos en Drive y los procesa automáticamente."""
    logger.info("Revisando carpeta Drive por PDFs nuevos...")
    service = get_drive_service()
    processed = load_processed_files()

    folder_id = get_folder_id(service)
    pdfs = list_pdfs_in_folder(service, folder_id)

    new_count = 0
    for pdf in pdfs:
        file_id = pdf["id"]
        modified = pdf["modifiedTime"]

        # Si ya fue procesado con la misma fecha de modificación, saltear
        if processed.get(file_id) == modified:
            continue

        logger.info(f"Procesando: {pdf['name']}")
        try:
            buffer = download_pdf(service, file_id)
            chunks = extract_text_from_pdf(buffer)

            for chunk in chunks:
                doc_id = f"{file_id}_p{chunk['page']}"
                metadata = {
                    "source": pdf["name"],
                    "file_id": file_id,
                    "page": chunk["page"]
                }
                add_document(doc_id, chunk["text"], metadata)

            processed[file_id] = modified
            save_processed_files(processed)
            new_count += 1
            logger.info(f"✅ {pdf['name']} procesado ({len(chunks)} páginas)")

        except Exception as e:
            logger.error(f"Error procesando {pdf['name']}: {e}")

    logger.info(f"Revisión completa. {new_count} archivos nuevos procesados.")
    return new_count


def watch_drive(interval_seconds=300):
    """Loop continuo — revisa Drive cada X segundos."""
    logger.info(f"Watcher iniciado. Revisando cada {interval_seconds}s")
    while True:
        try:
            process_new_pdfs()
        except Exception as e:
            logger.error(f"Error en watcher: {e}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    watch_drive()
