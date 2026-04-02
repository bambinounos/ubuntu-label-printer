"""Canvas visual que renderiza la vista previa de la etiqueta usando Cairo.

Convierte coordenadas TSPL (dots a 203 DPI, 8 dots/mm) a píxeles de pantalla.
Compatible con HT300 (HPRT) - Manual Rev.1.2
"""

import math
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import cairo

from src.label_elements import (
    TextElement, BarcodeElement, QRElement,
    LineElement, BoxElement, CircleElement
)

DOTS_PER_MM = 8


class LabelCanvas(Gtk.DrawingArea):
    """Renderiza una vista previa de la etiqueta TSPL."""

    def __init__(self):
        super().__init__()
        self.connect("draw", self._on_draw)
        self.set_can_focus(True)

        self.label_width_mm = 60
        self.label_height_mm = 40
        self.elements = []
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

    def set_label_size(self, width_mm, height_mm):
        self.label_width_mm = width_mm
        self.label_height_mm = height_mm
        self.queue_draw()

    def set_elements(self, elements):
        self.elements = elements
        self.queue_draw()

    def _on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        w = alloc.width
        h = alloc.height

        # Fondo del widget
        cr.set_source_rgb(0.18, 0.20, 0.25)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        # Calcular escala
        label_w_dots = self.label_width_mm * DOTS_PER_MM
        label_h_dots = self.label_height_mm * DOTS_PER_MM
        margin = 30

        available_w = w - margin * 2
        available_h = h - margin * 2

        scale_x = available_w / label_w_dots
        scale_y = available_h / label_h_dots
        self.scale = min(scale_x, scale_y)

        rendered_w = label_w_dots * self.scale
        rendered_h = label_h_dots * self.scale

        self.offset_x = (w - rendered_w) / 2
        self.offset_y = (h - rendered_h) / 2

        # Sombra
        cr.set_source_rgba(0, 0, 0, 0.3)
        cr.rectangle(
            self.offset_x + 4, self.offset_y + 4,
            rendered_w, rendered_h
        )
        cr.fill()

        # Etiqueta blanca
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(self.offset_x, self.offset_y, rendered_w, rendered_h)
        cr.fill()

        # Borde
        cr.set_source_rgb(0.6, 0.6, 0.6)
        cr.set_line_width(1)
        cr.rectangle(self.offset_x, self.offset_y, rendered_w, rendered_h)
        cr.stroke()

        # Grilla (cada 10mm = 80 dots)
        cr.set_source_rgba(0.85, 0.85, 0.85, 0.3)
        cr.set_line_width(0.5)
        grid_step = 10 * DOTS_PER_MM * self.scale
        x = self.offset_x + grid_step
        while x < self.offset_x + rendered_w:
            cr.move_to(x, self.offset_y)
            cr.line_to(x, self.offset_y + rendered_h)
            cr.stroke()
            x += grid_step
        y = self.offset_y + grid_step
        while y < self.offset_y + rendered_h:
            cr.move_to(self.offset_x, y)
            cr.line_to(self.offset_x + rendered_w, y)
            cr.stroke()
            y += grid_step

        # Tamaño
        cr.set_source_rgba(0.6, 0.6, 0.7, 0.8)
        cr.set_font_size(10)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        size_text = f"{self.label_width_mm} x {self.label_height_mm} mm  ({label_w_dots} x {label_h_dots} dots)"
        extents = cr.text_extents(size_text)
        cr.move_to(
            self.offset_x + rendered_w / 2 - extents.width / 2,
            self.offset_y + rendered_h + 16
        )
        cr.show_text(size_text)

        # Renderizar elementos
        cr.save()
        cr.translate(self.offset_x, self.offset_y)
        cr.scale(self.scale, self.scale)

        for elem in self.elements:
            self._draw_element(cr, elem)

        cr.restore()

        # Placeholder
        if not self.elements:
            cr.set_source_rgba(0.6, 0.6, 0.6, 0.5)
            cr.set_font_size(13)
            text = "Selecciona una plantilla o agrega elementos"
            extents = cr.text_extents(text)
            cr.move_to(
                self.offset_x + rendered_w / 2 - extents.width / 2,
                self.offset_y + rendered_h / 2
            )
            cr.show_text(text)

    def _draw_element(self, cr, elem):
        if isinstance(elem, TextElement):
            self._draw_text(cr, elem)
        elif isinstance(elem, BarcodeElement):
            self._draw_barcode(cr, elem)
        elif isinstance(elem, QRElement):
            self._draw_qr(cr, elem)
        elif isinstance(elem, LineElement):
            self._draw_line(cr, elem)
        elif isinstance(elem, BoxElement):
            self._draw_box(cr, elem)
        elif isinstance(elem, CircleElement):
            self._draw_circle(cr, elem)

    def _draw_text(self, cr, elem):
        if not elem.text:
            return

        cw, ch = elem.FONTS.get(elem.font, (16, 24))
        font_size = ch * elem.my

        cr.set_font_size(font_size)

        if elem.font in ("4", "5"):
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        else:
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        cr.set_source_rgb(0, 0, 0)

        cr.save()
        if elem.rotation != 0:
            cr.translate(elem.x, elem.y)
            cr.rotate(math.radians(elem.rotation))
            cr.move_to(0, font_size * 0.8)
        else:
            cr.move_to(elem.x, elem.y + font_size * 0.8)

        cr.show_text(elem.text)
        cr.restore()

    def _draw_barcode(self, cr, elem):
        if not elem.data:
            return

        x, y = elem.x, elem.y
        height = elem.height

        cr.set_source_rgb(0, 0, 0)

        # Simular barras usando hash del dato para patrón consistente
        import hashlib
        seed = hashlib.md5(elem.data.encode()).digest()
        bar_x = x
        narrow = max(1, elem.narrow)
        wide = max(2, elem.wide)

        for i, ch in enumerate(elem.data):
            b = seed[i % len(seed)]
            bar_w = wide if (b & (1 << (i % 8))) else narrow
            cr.rectangle(bar_x, y, bar_w, height)
            cr.fill()
            bar_x += bar_w
            space_w = narrow if (b & (1 << ((i + 4) % 8))) else wide
            bar_x += space_w

        if elem.human_readable:
            cr.set_font_size(12)
            cr.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            text_extents = cr.text_extents(elem.data)
            text_x = x + ((bar_x - x) - text_extents.width) / 2
            cr.move_to(max(x, text_x), y + height + 14)
            cr.show_text(elem.data)

    def _draw_qr(self, cr, elem):
        if not elem.data:
            return

        cell = elem.cell_size
        modules = 21

        import hashlib
        h = hashlib.md5(elem.data.encode()).digest()

        cr.set_source_rgb(0, 0, 0)

        # Finder patterns
        for fx, fy in [(0, 0), (modules - 7, 0), (0, modules - 7)]:
            px = elem.x + fx * cell
            py = elem.y + fy * cell
            cr.rectangle(px, py, 7 * cell, 7 * cell)
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.rectangle(px + cell, py + cell, 5 * cell, 5 * cell)
            cr.fill()
            cr.set_source_rgb(0, 0, 0)
            cr.rectangle(px + 2 * cell, py + 2 * cell, 3 * cell, 3 * cell)
            cr.fill()

        # Data modules
        for row in range(modules):
            for col in range(modules):
                if (row < 8 and col < 8) or \
                   (row < 8 and col >= modules - 8) or \
                   (row >= modules - 8 and col < 8):
                    continue
                idx = (row * modules + col) % len(h)
                bit = (h[idx] >> ((row + col) % 8)) & 1
                if bit:
                    cr.rectangle(
                        elem.x + col * cell,
                        elem.y + row * cell,
                        cell, cell
                    )
                    cr.fill()

    def _draw_line(self, cr, elem):
        cr.set_source_rgb(0, 0, 0)
        cr.rectangle(elem.x, elem.y, elem.width, elem.height)
        cr.fill()

    def _draw_box(self, cr, elem):
        cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(elem.thickness)
        cr.rectangle(elem.x, elem.y, elem.x2 - elem.x, elem.y2 - elem.y)
        cr.stroke()

    def _draw_circle(self, cr, elem):
        cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(elem.thickness)
        radius = elem.diameter / 2
        cx = elem.x + radius
        cy = elem.y + radius
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.stroke()
