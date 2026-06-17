#!/usr/bin/env python3
"""
Corré este script el 1ro de cada mes para actualizar los datos de COLFARMA.
Uso: python3 scripts/actualizar_colfarma.py
"""

import io
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_NAME = "normas para bot"
CREDENTIALS_PATH = "credentials/service_account.json"

PRESTADORES_URL = "https://colfarma.org.ar/prestadores-y-prescriptores-up-junio-2026-actualizado/"
BOLETIN_URL = "https://colfarma.org.ar/prensa/boletines-electronicos/boletin-electronico-de-obras-sociales/"
COLFARMA_BASE = "https://colfarma.org.ar"


def get_drive_service():
    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def get_folder_id(service):
    result = service.files().list(
        q=f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)"
    ).execute()
    files = result.get("files", [])
    if not files:
        raise ValueError(f"Carpeta '{FOLDER_NAME}' no encontrada")
    return files[0]["id"]


def delete_old_file(service, folder_id, prefix):
    result = service.files().list(
        q=f"'{folder_id}' in parents and name contains '{prefix}' and trashed=false",
        fields="files(id, name)"
    ).execute()
    for f in result.get("files", []):
        service.files().delete(fileId=f["id"]).execute()
        print(f"🗑️  Eliminado: {f['name']}")


def upload_file(service, folder_id, filename, content, mime_type):
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type)
    file_metadata = {"name": filename, "parents": [folder_id]}
    f = service.files().create(body=file_metadata, media_body=media, fields="id, name").execute()
    print(f"✅ Subido: {f['name']}")


def scrape_prestadores(service, folder_id):
    print("\n📥 Buscando listado de prestadores UP...")
    resp = requests.get(PRESTADORES_URL, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    excel_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(ext in href.lower() for ext in [".xlsx", ".xls"]):
            if not href.startswith("http"):
                href = COLFARMA_BASE + href
            excel_url = href
            break
    if not excel_url:
        print("❌ No se encontró el Excel de prestadores")
        return
    print(f"📥 Descargando: {excel_url}")
    resp = requests.get(excel_url, headers=HEADERS, timeout=30)
    mes = datetime.now().strftime("%Y-%m")
    filename = f"COLFARMA-Prestadores-UP-{mes}.xlsx"
    delete_old_file(service, folder_id, "COLFARMA-Prestadores-UP")
    upload_file(service, folder_id, filename, resp.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def scrape_boletin(service, folder_id):
    print("\n📥 Bajando boletín de obras sociales...")
    resp = requests.get(BOLETIN_URL, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    content = soup.find("article") or soup.find("div", class_="entry-content") or soup.find("main")
    if not content:
        print("❌ No se encontró contenido del boletín")
        return
    text = content.get_text(separator="\n", strip=True)
    mes = datetime.now().strftime("%Y-%m")
    filename = f"COLFARMA-Boletin-OS-{mes}.txt"
    delete_old_file(service, folder_id, "COLFARMA-Boletin-OS")
    upload_file(service, folder_id, filename, text.encode("utf-8"), "text/plain")


def main():
    print("🚀 Actualizando datos de COLFARMA...")
    service = get_drive_service()
    folder_id = get_folder_id(service)
    scrape_prestadores(service, folder_id)
    scrape_boletin(service, folder_id)
    print("\n✅ Listo. El bot procesará los archivos en los próximos 5 minutos.")


if __name__ == "__main__":
    main()
