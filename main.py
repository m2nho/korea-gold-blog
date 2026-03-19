import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from config.settings import APP_DIR
from ui.main_window import MainWindow

LOG_DIR = APP_DIR / "logs"


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "app.log"

    handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def main():
    setup_logging()
    logging.info("애플리케이션 시작")
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
