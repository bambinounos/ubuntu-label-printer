"""Datos variables / impresión por lotes (mail-merge) desde CSV.

Sintaxis de placeholder: {{columna}}  (doble llave). Se sustituye en el texto
de los elementos TextElement y en el `data` de Barcode/QR (y en `path` de
imágenes). El diseño original NUNCA se muta: se clona vía to_dict/from_dict.
"""

import csv
import re

from src.label_elements import element_from_dict

# {{ columna }} con espacios opcionales; nombres con letras, números, ._-
PLACEHOLDER = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")

# Campos de los elementos donde se aplican las sustituciones
SUBST_FIELDS = ("text", "data", "path")


def find_placeholders(text):
    """Lista de nombres de columna referenciados en un texto."""
    return PLACEHOLDER.findall(text or "")


def substitute(text, row):
    """Reemplaza {{col}} por row[col]. Deja intacto lo que no encuentre."""
    if not text:
        return text
    return PLACEHOLDER.sub(lambda m: str(row.get(m.group(1), m.group(0))), text)


def design_placeholders(elements):
    """Conjunto ordenado de columnas usadas por todos los elementos."""
    found = []
    seen = set()
    for e in elements:
        d = e.to_dict()
        for fld in SUBST_FIELDS:
            val = d.get(fld)
            if isinstance(val, str):
                for name in find_placeholders(val):
                    if name not in seen:
                        seen.add(name)
                        found.append(name)
    return found


def render_row(elements, row):
    """Retorna una NUEVA lista de elementos con los placeholders sustituidos.

    No modifica los elementos originales (clona vía to_dict/from_dict).
    """
    out = []
    for e in elements:
        d = e.to_dict()
        for fld in SUBST_FIELDS:
            if isinstance(d.get(fld), str):
                d[fld] = substitute(d[fld], row)
        clone = element_from_dict(d)
        if clone is not None:
            out.append(clone)
    return out


def read_csv(path):
    """Lee un CSV y retorna (columnas, filas) donde filas es lista de dicts.

    Usa utf-8-sig para tolerar BOM de Excel.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
        columns = list(reader.fieldnames or [])
    return columns, rows
