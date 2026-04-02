#!/usr/bin/env python3
"""Punto de entrada principal de Label Printer."""

import sys
import logging
import traceback

LOG_FILE = "/tmp/label-printer.log"

# Logging a archivo y consola
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a"),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("label-printer")


def main():
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        log.info("Iniciando Label Printer...")

        from src.app import LabelPrinterApp
        app = LabelPrinterApp()
        exit_status = app.run(sys.argv)
        log.info(f"Cerrando (exit={exit_status})")
        sys.exit(exit_status)

    except Exception as e:
        log.error(f"Error fatal: {e}")
        log.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
