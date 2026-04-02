"""Gestión de impresión de etiquetas via GTK PrintOperation y exportación PDF."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import cairo

from src.template_manager import LABEL_SIZES


class PrintManager:
    """Maneja la impresión de etiquetas y exportación a PDF."""

    def print_label(self, parent_window, label_data, label_size, copies=1):
        """Abre el diálogo de impresión GTK y envía la etiqueta a imprimir."""
        self._label_data = label_data
        self._label_size = label_size
        self._copies = copies

        print_op = Gtk.PrintOperation()
        print_op.set_n_pages(1)
        print_op.set_n_copies(copies)
        print_op.set_job_name("Etiqueta")

        # Configurar tamaño de papel personalizado
        paper_size = Gtk.PaperSize.new_custom(
            "label",
            "Etiqueta",
            label_size["width"],
            label_size["height"],
            Gtk.Unit.MM,
        )
        page_setup = Gtk.PageSetup()
        page_setup.set_paper_size(paper_size)
        page_setup.set_top_margin(0, Gtk.Unit.MM)
        page_setup.set_bottom_margin(0, Gtk.Unit.MM)
        page_setup.set_left_margin(0, Gtk.Unit.MM)
        page_setup.set_right_margin(0, Gtk.Unit.MM)
        print_op.set_default_page_setup(page_setup)

        print_op.connect("draw-page", self._on_draw_page)

        result = print_op.run(
            Gtk.PrintOperationAction.PRINT_DIALOG, parent_window
        )
        return result == Gtk.PrintOperationResult.APPLY

    def _on_draw_page(self, operation, context, page_nr):
        """Callback que dibuja la etiqueta en la página de impresión."""
        cr = context.get_cairo_context()
        width = context.get_width()
        height = context.get_height()

        self._render_label(cr, width, height, self._label_data, self._label_size)

    def _render_label(self, cr, width, height, label_data, label_size):
        """Renderiza el contenido de la etiqueta en un contexto Cairo."""
        from src.barcode_generator import generate_barcode_surface, generate_qr_surface

        lines = label_data.get("lines", [])
        barcode_enabled = label_data.get("barcode_enabled", False)
        barcode_data = label_data.get("barcode_data", "")
        barcode_type = label_data.get("barcode_type", "code128")

        padding = width * 0.05
        text_x = padding
        text_y = padding

        text_area_w = width - padding * 2
        text_area_h = height - padding * 2

        if barcode_enabled and barcode_data:
            barcode_area_h = height * 0.35
            text_area_h = height - padding * 2 - barcode_area_h
        else:
            barcode_area_h = 0

        # Texto
        font_sizes = [14, 11, 11, 10]
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
                cr.set_source_rgb(0, 0, 0)
            else:
                cr.select_font_face(
                    "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
                )
                cr.set_source_rgb(0.1, 0.1, 0.1)

            cr.move_to(text_x, current_y)
            cr.show_text(line)
            current_y += font_size + 3

        # Código de barras / QR
        if barcode_enabled and barcode_data:
            barcode_y = height - barcode_area_h
            barcode_x = padding
            barcode_w = int(text_area_w)
            barcode_h = int(barcode_area_h - padding)

            try:
                if barcode_type == "qr":
                    qr_size = min(barcode_w, barcode_h)
                    surface = generate_qr_surface(barcode_data, qr_size)
                    if surface:
                        qr_x = (width - qr_size) / 2
                        cr.set_source_surface(surface, qr_x, barcode_y)
                        cr.paint()
                else:
                    surface = generate_barcode_surface(
                        barcode_data, barcode_type, barcode_w, barcode_h
                    )
                    if surface:
                        cr.set_source_surface(surface, barcode_x, barcode_y)
                        cr.paint()
            except Exception:
                pass

    def export_pdf(self, filename, label_data, label_size):
        """Exporta la etiqueta como archivo PDF."""
        mm_to_pt = 2.835
        width_pt = label_size["width"] * mm_to_pt
        height_pt = label_size["height"] * mm_to_pt

        surface = cairo.PDFSurface(filename, width_pt, height_pt)
        cr = cairo.Context(surface)

        # Fondo blanco
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(0, 0, width_pt, height_pt)
        cr.fill()

        self._render_label(cr, width_pt, height_pt, label_data, label_size)

        cr.show_page()
        surface.finish()
