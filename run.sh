#!/bin/bash
# Lanzador de Label Printer
# Log en: /tmp/label-printer.log
cd "$(dirname "$0")"
echo "=== Label Printer $(date) ===" >> /tmp/label-printer.log
exec python3 -m src.main "$@"
