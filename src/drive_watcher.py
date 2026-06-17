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
import openpyxl
from src.embeddings import add_document, get_chroma_client

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_NAME = "normas para bot"
PROCESSED_FILE = Path("/tmp/processed_files.json")

SUPPORTED_MIMETYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xlsx",
}


def get_drive_service():
    sa_env = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
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


def list_files_in_folder(service, folder_id):
    mime_conditions = " or ".join([f"mimeType='{m}'" for m in SUPPORTED_MIMETYPES])
    result = service.files().list(
        q=f"'{folder_id}' in parents and ({mime_conditions}) and trashed=false",
        fields="files(id, name, modifiedTime, mimeType)"
    ).execute()
    return result.get("files", [])


def download_file(service, file_id):
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buffer.seek(0)
    return buffer


def extract_text_from_pdf(buffer):
    chunks = []
    with pdfplumber.open(buffer) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                chunks.append({"page": i + 1, "text": text.strip()})
    return chunks


def extract_text_from_excel(buffer):
    chunks = []
    wb = openpyxl.load_workbook(buffer, read_only=True, data_only=True)
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows_text = []
        for row in ws.iter_rows(values_only=True):
            row_values = [str(cell) for cell in row if cell is not None and str(cell).strip()]
            if row_values:
                rows_text.append(" | ".join(row_values))
        if rows_text:
            for i in range(0, len(rows_text), 50):
                chunk_text = "\n".join(rows_text[i:i+50])
                chunks.append({"page": f"{sheet_name}-{i//50 + 1}", "text": chunk_text})
    wb.close()
    return chunks


def process_new_files():
    logger.info("Revisando carpeta Drive por archivos nuevos...")
    service = get_drive_service()
    processed = load_processed_files()
    folder_id = get_folder_id(service)
    files = list_files_in_folder(service, folder_id)
    new_count = 0
    for f in files:
        file_id = f["id"]
        modified = f["modifiedTime"]
        mime = f["mimeType"]
        if processed.get(file_id) == modified:
            continue
        logger.info(f"Procesando: {f['name']}")
        try:
            buffer = download_file(service, file_id)
            chunks = extract_text_from_pdf(buffer) if mime == "application/pdf" else extract_text_from_excel(buffer)
            for chunk in chunks:
                doc_id = f"{file_id}_p{chunk['page']}"
                metadata = {"source": f["name"], "file_id": file_id, "page": str(chunk["page"])}
                add_document(doc_id, chunk["text"], metadata)
            processed[file_id] = modified
            save_processed_files(processed)
            new_count += 1
            logger.info(f"✅ {f['name']} procesado ({len(chunks)} secciones)")
        except Exception as e:
            logger.error(f"Error procesando {f['name']}: {e}")
    logger.info(f"Revisión completa. {new_count} archivos nuevos procesados.")
    return new_count


def watch_drive(interval_seconds=300):
    logger.info(f"Watcher iniciado. Revisando cada {interval_seconds}s")
    while True:
        try:
            process_new_files()
        except Exception as e:
            logger.error(f"Error en watcher: {e}")
        time.sleep(interval_seconds)
