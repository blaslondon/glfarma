import io
import logging
import requests
from bs4 import BeautifulSoup
from src.drive_watcher import extract_text_from_excel
from src.embeddings import add_document, get_chroma_client

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0"}

BOLETIN_URL = "https://colfarma.org.ar/prensa/boletines-electronicos/boletin-electronico-de-obras-sociales/"
PRESTADORES_URL = "https://colfarma.org.ar/prestadores-y-prescriptores-up-junio-2026-actualizado/"
COLFARMA_BASE = "https://colfarma.org.ar"


def delete_source_docs(source_prefix: str):
    """Elimina todos los documentos de una fuente anterior."""
    _, collection = get_chroma_client()
    try:
        results = collection.get(where={"source": {"$contains": source_prefix}})
        if results["ids"]:
            collection.delete(ids=results["ids"])
            logger.info(f"🗑️ Eliminados {len(results['ids'])} docs anteriores de '{source_prefix}'")
    except Exception as e:
        logger.warning(f"No se pudieron eliminar docs anteriores: {e}")


def scrape_boletin():
    """Scraping del boletín de obras sociales — extrae texto de la página."""
    logger.info("Scrapeando boletín COLFARMA...")
    resp = requests.get(BOLETIN_URL, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Extraer contenido principal
    content = soup.find("article") or soup.find("div", class_="entry-content") or soup.find("main")
    if not content:
        logger.warning("No se encontró contenido en el boletín")
        return

    text = content.get_text(separator="\n", strip=True)
    if len(text) < 100:
        logger.warning("Contenido del boletín muy corto")
        return

    # Pisar documentos anteriores del boletín
    delete_source_docs("COLFARMA-BOLETIN")

    # Indexar en chunks de ~1000 chars
    chunks = []
    lines = text.split("\n")
    current = []
    for line in lines:
        current.append(line)
        if len("\n".join(current)) > 1000:
            chunks.append("\n".join(current))
            current = []
    if current:
        chunks.append("\n".join(current))

    for i, chunk in enumerate(chunks):
        add_document(
            f"colfarma_boletin_{i}",
            chunk,
            {"source": "COLFARMA-BOLETIN", "file_id": "colfarma_boletin", "page": str(i+1)}
        )

    logger.info(f"✅ Boletín COLFARMA indexado ({len(chunks)} secciones)")


def find_excel_link(url: str) -> str | None:
    """Busca un link a Excel en una página de COLFARMA."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(ext in href.lower() for ext in [".xlsx", ".xls", ".csv"]):
            if not href.startswith("http"):
                href = COLFARMA_BASE + href
            return href
    return None


def scrape_prestadores_up():
    """Descarga y reindexea el listado de prestadores UP desde COLFARMA."""
    logger.info("Buscando listado de prestadores UP en COLFARMA...")
    url = find_excel_link(PRESTADORES_URL)

    if not url:
        logger.warning("No se encontró Excel de prestadores en COLFARMA")
        return

    logger.info(f"Descargando: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    buffer = io.BytesIO(resp.content)
    filename = url.split("/")[-1]

    chunks = extract_text_from_excel(buffer)
    if not chunks:
        logger.warning("No se pudo extraer texto del Excel de prestadores")
        return

    # Pisar documentos anteriores de prestadores COLFARMA
    delete_source_docs("COLFARMA-PRESTADORES")

    for chunk in chunks:
        add_document(
            f"colfarma_prestadores_{chunk['page']}",
            chunk["text"],
            {"source": "COLFARMA-PRESTADORES", "file_id": "colfarma_prestadores", "page": str(chunk["page"])}
        )

    logger.info(f"✅ Prestadores UP COLFARMA indexados ({len(chunks)} secciones) — {filename}")


def run_all():
    """Corre todo el scraping de COLFARMA."""
    try:
        scrape_prestadores_up()
    except Exception as e:
        logger.error(f"Error scrapeando prestadores: {e}")
    try:
        scrape_boletin()
    except Exception as e:
        logger.error(f"Error scrapeando boletín: {e}")
