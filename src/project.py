"""Persistencia de diseños de etiqueta (.label JSON) y plantillas de usuario.

Formato canónico: JSON nativo vía element.to_dict() (no round-trip TSPL, que es
lossy). TSPL/ZPL quedan solo como salida de exportación/impresión.

Las plantillas de usuario se guardan junto a la configuración de conexión, en
~/.config/label-printer/templates.json (mismo patrón que connection.py).
"""

import json
import os

from src.label_elements import element_from_dict

FORMAT = "label-printer-design"
VERSION = 1

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "label-printer")
TEMPLATES_FILE = os.path.join(CONFIG_DIR, "templates.json")


# ── Diseños .label ──

def build_doc(*, width_mm, height_mm, gap_mm, language, speed, density, copies, elements):
    """Construye el dict serializable de un diseño."""
    return {
        "format": FORMAT,
        "version": VERSION,
        "label": {"width_mm": width_mm, "height_mm": height_mm, "gap_mm": gap_mm},
        "settings": {
            "language": language, "speed": speed,
            "density": density, "copies": copies,
        },
        "elements": [e.to_dict() for e in elements],
    }


def save_design(path, **kwargs):
    """Guarda un diseño en disco. Acepta los mismos kwargs que build_doc()."""
    doc = build_doc(**kwargs)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)


def parse_doc(doc):
    """Reconstruye (label, settings, elements) desde un dict de diseño."""
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ValueError("No es un archivo de diseño válido (.label)")
    label = doc.get("label", {})
    settings = doc.get("settings", {})
    elements = [e for e in (element_from_dict(d) for d in doc.get("elements", [])) if e]
    return label, settings, elements


def load_design(path):
    """Carga un diseño .label. Retorna (label_dict, settings_dict, elements)."""
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    return parse_doc(doc)


# ── Plantillas de usuario ──

def load_user_templates():
    """Carga las plantillas guardadas por el usuario (dict key -> entry)."""
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_user_templates(templates):
    """Persiste el dict completo de plantillas de usuario."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)


def _slugify(name):
    base = "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")
    return base or "plantilla"


def add_user_template(nombre, descripcion, *, width_mm, height_mm, gap_mm,
                      language, speed, density, copies, elements):
    """Agrega/actualiza una plantilla de usuario. Retorna su clave."""
    templates = load_user_templates()
    doc = build_doc(
        width_mm=width_mm, height_mm=height_mm, gap_mm=gap_mm,
        language=language, speed=speed, density=density, copies=copies,
        elements=elements,
    )
    # Clave única basada en el nombre
    key = "user_" + _slugify(nombre)
    suffix = 2
    base = key
    while key in templates and templates[key].get("nombre") != nombre:
        key = f"{base}_{suffix}"
        suffix += 1
    entry = dict(doc)
    entry["nombre"] = nombre
    entry["descripcion"] = descripcion
    entry["user"] = True
    templates[key] = entry
    save_user_templates(templates)
    return key


def delete_user_template(key):
    """Elimina una plantilla de usuario por su clave."""
    templates = load_user_templates()
    if key in templates:
        del templates[key]
        save_user_templates(templates)
        return True
    return False
