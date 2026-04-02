"""Gestión de plantillas y tamaños de etiquetas."""

import json
import os

# Tamaños de etiqueta predefinidos (en milímetros)
LABEL_SIZES = {
    "small_address": {
        "name": "Dirección pequeña",
        "width": 89,
        "height": 36,
    },
    "standard_address": {
        "name": "Dirección estándar",
        "width": 89,
        "height": 51,
    },
    "large_address": {
        "name": "Dirección grande",
        "width": 101,
        "height": 54,
    },
    "shipping": {
        "name": "Envío",
        "width": 101,
        "height": 152,
    },
    "product_small": {
        "name": "Producto pequeño",
        "width": 51,
        "height": 25,
    },
    "product_medium": {
        "name": "Producto mediano",
        "width": 70,
        "height": 37,
    },
    "badge": {
        "name": "Credencial/Badge",
        "width": 101,
        "height": 70,
    },
    "cd_dvd": {
        "name": "CD/DVD",
        "width": 117,
        "height": 117,
    },
    "file_folder": {
        "name": "Carpeta/Folder",
        "width": 190,
        "height": 38,
    },
    "custom": {
        "name": "Personalizado",
        "width": 100,
        "height": 50,
    },
}


class TemplateManager:
    """Gestiona plantillas de etiquetas guardadas por el usuario."""

    def __init__(self):
        self.templates_dir = os.path.join(
            os.path.expanduser("~"), ".local", "share", "label-printer", "templates"
        )
        os.makedirs(self.templates_dir, exist_ok=True)

    def save_template(self, name, data):
        filepath = os.path.join(self.templates_dir, f"{name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_template(self, name):
        filepath = os.path.join(self.templates_dir, f"{name}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def list_templates(self):
        templates = []
        if os.path.exists(self.templates_dir):
            for f in os.listdir(self.templates_dir):
                if f.endswith(".json"):
                    templates.append(f[:-5])
        return sorted(templates)

    def delete_template(self, name):
        filepath = os.path.join(self.templates_dir, f"{name}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
