"""Widget de edición y vista previa de etiquetas con Cairo."""

import math
import io

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

import cairo

from src.template_manager import LABEL_SIZES
from src.barcode_generator import generate_barcode_surface, generate_qr_surface


class LabelEditor(Gtk.DrawingArea):
    """Área de dibujo que renderiza la vista previa de la etiqueta."""

    def __init__(self):
        super().__init__()
        self.connect("draw", self._on_draw)
        self.label_data = {
            "lines": ["", "", "", ""],
            "barcode_enabled": False,
            "barcode_type": "code128",
            "barcode_data": "",
            "label_size": "small_address",
        }

    def update_label(self, data):
        self.label_data = data
        self.queue_draw()

    def _on_draw(self, widget, cr):
        allocation = widget.get_allocation()
        widget_w = allocation.width
        widget_h = allocation.height

        size_id = self.label_data.get("label_size", "small_address")
        label_size = LABEL_SIZES.get(size_id, LABEL_SIZES["small_address"])

        # Dimensiones de la etiqueta en mm
        label_w_mm = label_size["width"]
        label_h_mm = label_size["height"]

        # Escalar para que quepa en el widget con margen
        margin = 40
        available_w = widget_w - margin * 2
        available_h = widget_h - margin * 2

        scale_x = available_w / label_w_mm
        scale_y = available_h / label_h_mm
        scale = min(scale_x, scale_y)

        # Centrar la etiqueta
        rendered_w = label_w_mm * scale
        rendered_h = label_h_mm * scale
        offset_x = (widget_w - rendered_w) / 2
        offset_y = (widget_h - rendered_h) / 2

        # Fondo del widget
        cr.set_source_rgb(0.925, 0.937, 0.945)
        cr.rectangle(0, 0, widget_w, widget_h)
        cr.fill()

        # Sombra de la etiqueta
        cr.set_source_rgba(0, 0, 0, 0.15)
        cr.rectangle(offset_x + 3, offset_y + 3, rendered_w, rendered_h)
        cr.fill()

        # Fondo blanco de la etiqueta
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(offset_x, offset_y, rendered_w, rendered_h)
        cr.fill()

        # Borde de la etiqueta
        cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.set_line_width(1)
        cr.rectangle(offset_x, offset_y, rendered_w, rendered_h)
        cr.stroke()

        # Borde punteado interior (área de impresión segura)
        cr.set_dash([4, 4])
        cr.set_source_rgba(0.8, 0.8, 0.8, 0.5)
        inner_margin = 3 * scale
        cr.rectangle(
            offset_x + inner_margin,
            offset_y + inner_margin,
            rendered_w - inner_margin * 2,
            rendered_h - inner_margin * 2,
        )
        cr.stroke()
        cr.set_dash([])

        # Dibujar contenido
        self._draw_content(cr, offset_x, offset_y, rendered_w, rendered_h, scale)

    def _draw_content(self, cr, x, y, w, h, scale):
        lines = self.label_data.get("lines", [])
        barcode_enabled = self.label_data.get("barcode_enabled", False)
        barcode_data = self.label_data.get("barcode_data", "")
        barcode_type = self.label_data.get("barcode_type", "code128")

        padding = 5 * scale
        text_x = x + padding
        text_y = y + padding

        # Área disponible para texto
        text_area_w = w - padding * 2
        text_area_h = h - padding * 2

        if barcode_enabled and barcode_data:
            # Reservar espacio inferior para el código
            barcode_area_h = h * 0.35
            text_area_h = h - padding * 2 - barcode_area_h
        else:
            barcode_area_h = 0

        # Dibujar líneas de texto
        has_content = any(line.strip() for line in lines)
        if not has_content and not (barcode_enabled and barcode_data):
            # Placeholder
            cr.set_source_rgba(0.6, 0.6, 0.6, 0.7)
            font_size = max(10, 12 * scale / 3)
            cr.set_font_size(font_size)
            cr.move_to(x + w / 2 - 60, y + h / 2)
            cr.show_text("Escribe el contenido...")
            return

        # Primera línea: título (más grande y bold)
        font_sizes = [
            max(8, 14 * scale / 3),  # Título
            max(7, 11 * scale / 3),  # Normal
            max(7, 11 * scale / 3),  # Normal
            max(6, 10 * scale / 3),  # Pequeño
        ]

        current_y = text_y + font_sizes[0]

        for i, line in enumerate(lines):
            if not line.strip():
                current_y += font_sizes[min(i, len(font_sizes) - 1)] + 2
                continue

            font_size = font_sizes[min(i, len(font_sizes) - 1)]
            cr.set_font_size(font_size)

            if i == 0:
                cr.select_font_face(
                    "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD
                )
                cr.set_source_rgb(0.1, 0.1, 0.1)
            else:
                cr.select_font_face(
                    "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
                )
                cr.set_source_rgb(0.2, 0.2, 0.2)

            # Truncar texto si es muy largo
            extents = cr.text_extents(line)
            display_text = line
            while extents.width > text_area_w and len(display_text) > 1:
                display_text = display_text[:-1]
                extents = cr.text_extents(display_text + "...")
            if display_text != line:
                display_text += "..."

            cr.move_to(text_x, current_y)
            cr.show_text(display_text)
            current_y += font_size + 4

        # Dibujar código de barras / QR
        if barcode_enabled and barcode_data:
            barcode_y = y + h - barcode_area_h
            barcode_x = x + padding
            barcode_w = w - padding * 2
            barcode_h_avail = barcode_area_h - padding

            try:
                if barcode_type == "qr":
                    qr_size = min(barcode_w, barcode_h_avail)
                    surface = generate_qr_surface(barcode_data, int(qr_size))
                    if surface:
                        qr_x = x + (w - qr_size) / 2
                        cr.set_source_surface(surface, qr_x, barcode_y)
                        cr.paint()
                else:
                    surface = generate_barcode_surface(
                        barcode_data, barcode_type, int(barcode_w), int(barcode_h_avail)
                    )
                    if surface:
                        cr.set_source_surface(surface, barcode_x, barcode_y)
                        cr.paint()
            except Exception:
                # Si falla el código, mostrar placeholder
                cr.set_source_rgba(0.8, 0.2, 0.2, 0.5)
                cr.set_font_size(max(8, 10 * scale / 3))
                cr.move_to(barcode_x, barcode_y + barcode_h_avail / 2)
                cr.show_text("Error en código")

    def render_to_cairo(self, cr, width_pt, height_pt):
        """Renderiza la etiqueta a un contexto Cairo (para impresión/PDF)."""
        label_data = self.label_data
        size_id = label_data.get("label_size", "small_address")
        label_size = LABEL_SIZES.get(size_id, LABEL_SIZES["small_address"])

        label_w_mm = label_size["width"]
        label_h_mm = label_size["height"]

        # 1 mm = 2.835 puntos
        mm_to_pt = 2.835
        label_w_pt = label_w_mm * mm_to_pt
        label_h_pt = label_h_mm * mm_to_pt

        scale = min(width_pt / label_w_mm, height_pt / label_h_mm)

        # Fondo blanco
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, label_w_pt, label_h_pt)
        cr.fill()

        self._draw_content(cr, 0, 0, label_w_pt, label_h_pt, scale)
