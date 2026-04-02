#!/usr/bin/env python3
"""Punto de entrada principal de la aplicación Label Printer."""

import sys
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from src.app import LabelPrinterApp


def main():
    app = LabelPrinterApp()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)


if __name__ == "__main__":
    main()
