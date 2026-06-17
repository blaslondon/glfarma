import time
import threading
import logging
from src.bot import main as run_bot
from src.drive_watcher import process_new_files
from src.colfarma_scraper import run_all as colfarma_update

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

WATCHER_INTERVAL = 300      # 5 minutos
COLFARMA_INTERVAL = 86400   # 24 horas


def background_worker():
    last_colfarma = 0
    while True:
        now = time.time()

        # COLFARMA cada 24hs (y al arrancar)
        if now - last_colfarma >= COLFARMA_INTERVAL:
            try:
                colfarma_update()
            except Exception as e:
                logging.error(f"Error COLFARMA: {e}")
            last_colfarma = time.time()

        # Drive watcher cada 5 minutos
        try:
            process_new_files()
        except Exception as e:
            logging.error(f"Error watcher: {e}")

        time.sleep(WATCHER_INTERVAL)


if __name__ == "__main__":
    worker = threading.Thread(target=background_worker, daemon=True)
    worker.start()
    run_bot()
