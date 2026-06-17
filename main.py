import threading
import logging
from src.bot import main as run_bot
from src.drive_watcher import watch_drive

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

if __name__ == "__main__":
    # Watcher en thread separado
    watcher_thread = threading.Thread(
        target=watch_drive,
        kwargs={"interval_seconds": 300},  # revisa cada 5 minutos
        daemon=True
    )
    watcher_thread.start()

    # Bot en hilo principal
    run_bot()
