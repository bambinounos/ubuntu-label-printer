"""Canvas visual interactivo para etiquetas.

Renderiza vista previa con Cairo. Soporta:
- Click para seleccionar elementos
- Drag para mover elementos
- Indicador visual de selección (borde azul + handles)
- Conversión coordenadas pantalla ↔ dots (203 DPI, 8 dots/mm)
"""

import math
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

import cairo

from src.label_elements import (
    TextElement, BarcodeElement, QRElement,
    LineElement, BoxElement, CircleElement, ImageElement
)

DOTS_PER_MM = 8
HIT_PADDING = 6  # dots de tolerancia para click en elementos finos
HANDLE_PX = 9    # tolerancia en píxeles de pantalla para agarrar un handle de resize
HANDLE_NAMES = ("nw", "ne", "sw", "se")


class LabelCanvas(Gtk.DrawingArea):
    """Canvas interactivo con vista previa de etiqueta y drag & drop."""

    def __init__(self):
        super().__init__()

        # Eventos de dibujo
        self.connect("draw", self._on_draw)

        # Eventos de mouse + teclado
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.KEY_PRESS_MASK
        )
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("motion-notify-event", self._on_motion_notify)
        self.connect("key-press-event", self._on_key_press)

        self.set_can_focus(True)

        # Estado de la etiqueta
        self.label_width_mm = 60
        self.label_height_mm = 40
        self.elements = []

        # Estado de renderizado (se calculan en _on_draw)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # Estado de interacción
        self.selected_element = None
        self.dragging = False
        self.resizing = None  # nombre del handle ('nw'/'ne'/'sw'/'se') o None
        self._mutated = False  # hubo cambio real durante el drag/resize actual
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        # Ajuste a grilla (snap)
        self.snap = True
        self.grid = DOTS_PER_MM  # 1 mm

        # Callbacks (app.py los conecta):
        #   on_element_moved : tras mover/redimensionar/borrar (regenera código)
        #   on_before_change : justo antes de una mutación (para apilar undo)
        #   on_element_edit  : doble clic sobre un elemento (abrir su diálogo)
        #   on_selection_changed : cambió el elemento seleccionado
        self.on_element_moved = None
        self.on_before_change = None
        self.on_element_edit = None
        self.on_selection_changed = None

    def set_label_size(self, width_mm, height_mm):
        self.label_width_mm = width_mm
        self.label_height_mm = height_mm
        self.queue_draw()

    def set_elements(self, elements):
        self.elements = elements
        self.queue_draw()

    # ── Conversión de coordenadas ──

    def screen_to_dots(self, sx, sy):
        """Convierte píxeles de pantalla a coordenadas TSPL (dots)."""
        dx = (sx - self.offset_x) / self.scale
        dy = (sy - self.offset_y) / self.scale
        return dx, dy

    def dots_to_screen(self, dx, dy):
        """Convierte dots TSPL a píxeles de pantalla."""
        sx = dx * self.scale + self.offset_x
        sy = dy * self.scale + self.offset_y
        return sx, sy

    # ── Hit testing ──

    def hit_test(self, dots_x, dots_y):
        """Busca qué elemento está bajo la coordenada (en dots). Último dibujado = arriba."""
        for elem in reversed(self.elements):
            bx, by, bw, bh = elem.get_bounds()
            # Padding para elementos finos (líneas de 2 dots)
            pad = HIT_PADDING
            if bw < pad * 2:
                bw = pad * 2
            if bh < pad * 2:
                bh = pad * 2
                by -= pad
            if bx - pad <= dots_x <= bx + bw + pad and \
               by - pad <= dots_y <= by + bh + pad:
                return elem
        return None

    # ── Handles de redimensión ──

    def _handle_at(self, sx, sy):
        """Nombre del handle de esquina bajo (sx,sy) en pantalla, o None.

        Se prueba en espacio de pantalla (los handles tienen tamaño fijo en px,
        independiente del zoom).
        """
        if not self.selected_element:
            return None
        bx, by, bw, bh = self.selected_element.get_bounds()
        corners = {
            "nw": (bx, by), "ne": (bx + bw, by),
            "sw": (bx, by + bh), "se": (bx + bw, by + bh),
        }
        for name, (cx, cy) in corners.items():
            hx, hy = self.dots_to_screen(cx, cy)
            if abs(sx - hx) <= HANDLE_PX and abs(sy - hy) <= HANDLE_PX:
                return name
        return None

    # ── Helpers de mutación ──

    def _notify_before_change(self):
        if self.on_before_change:
            self.on_before_change()

    def _notify_changed(self):
        if self.on_element_moved:
            self.on_element_moved()

    def _snap_val(self, v):
        if not self.snap:
            return int(v)
        return int(round(v / self.grid) * self.grid)

    def _translate(self, elem, dx, dy):
        """Mueve un elemento preservando dimensiones (x2/y2 en BoxElement)."""
        elem.x += dx
        elem.y += dy
        if hasattr(elem, "x2") and hasattr(elem, "y2"):
            elem.x2 += dx
            elem.y2 += dy

    def _resize_selected(self, handle, dots_x, dots_y):
        """Redimensiona el elemento seleccionado según el tipo y el handle."""
        e = self.selected_element
        dots_x = self._snap_val(dots_x)
        dots_y = self._snap_val(dots_y)

        if isinstance(e, BoxElement):
            if "e" in handle:
                e.x2 = max(e.x + 8, int(dots_x))
            if "s" in handle:
                e.y2 = max(e.y + 8, int(dots_y))
            if "w" in handle:
                e.x = min(e.x2 - 8, int(dots_x))
            if "n" in handle:
                e.y = min(e.y2 - 8, int(dots_y))
        elif isinstance(e, LineElement):
            e.width = max(2, int(dots_x - e.x))
            e.height = max(1, int(dots_y - e.y))
        elif isinstance(e, CircleElement):
            e.diameter = max(8, int(max(dots_x - e.x, dots_y - e.y)))
        elif isinstance(e, QRElement):
            target = (dots_x - e.x) / max(1, e.module_count())
            e.cell_size = min(e.CELL_SIZES, key=lambda s: abs(s - target))
        elif isinstance(e, BarcodeElement):
            new_h = int(dots_y - e.y)
            if new_h >= 20:
                e.height = new_h
            geom = e.barcode_geometry()
            total_modules = geom[1] if geom else max(1, len(e.data) * 11)
            new_narrow = max(1, round((dots_x - e.x) / max(1, total_modules)))
            e.narrow = new_narrow
            e.wide = new_narrow
        elif isinstance(e, TextElement):
            base_h = e.FONTS.get(e.font, (16, 24))[1]
            m = max(1, min(10, round((dots_y - e.y) / base_h)))
            e.my = m
            e.mx = m
        elif isinstance(e, ImageElement):
            if e.src_w > 0:
                new_scale = (dots_x - e.x) / e.src_w
                e.scale = max(0.05, min(8.0, round(new_scale, 3)))

    def _update_cursor(self, sx, sy):
        win = self.get_window()
        if not win:
            return
        handle = self._handle_at(sx, sy)
        name = {
            "nw": "nwse-resize", "se": "nwse-resize",
            "ne": "nesw-resize", "sw": "nesw-resize",
        }.get(handle)
        try:
            cursor = Gdk.Cursor.new_from_name(self.get_display(), name) if name else None
        except Exception:
            cursor = None
        win.set_cursor(cursor)

    # ── Eventos de mouse ──

    def _on_button_press(self, widget, event):
        if event.button != 1:
            return False
        self.grab_focus()

        # Doble clic: editar el elemento bajo el cursor
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            dx, dy = self.screen_to_dots(event.x, event.y)
            elem = self.hit_test(dx, dy)
            if elem and self.on_element_edit:
                self.on_element_edit(elem)
            return True

        # ¿Agarró un handle de resize del elemento ya seleccionado?
        handle = self._handle_at(event.x, event.y)
        if handle and self.selected_element:
            self.resizing = handle
            self.dragging = False
            self._mutated = False
            return True

        dx, dy = self.screen_to_dots(event.x, event.y)
        elem = self.hit_test(dx, dy)

        # Deseleccionar anterior
        if self.selected_element and self.selected_element is not elem:
            self.selected_element.selected = False

        changed_sel = elem is not self.selected_element
        self.selected_element = elem
        if elem:
            elem.selected = True
            self.dragging = True
            self._mutated = False
            self.drag_offset_x = dx - elem.x
            self.drag_offset_y = dy - elem.y
        else:
            self.dragging = False

        if changed_sel and self.on_selection_changed:
            self.on_selection_changed(elem)

        self.queue_draw()
        return True

    def _on_motion_notify(self, widget, event):
        # Redimensionando
        if self.resizing and self.selected_element:
            if not self._mutated:
                self._notify_before_change()
                self._mutated = True
            dx, dy = self.screen_to_dots(event.x, event.y)
            self._resize_selected(self.resizing, dx, dy)
            self.queue_draw()
            return True

        # Moviendo
        if self.dragging and self.selected_element:
            if not self._mutated:
                self._notify_before_change()
                self._mutated = True
            dx, dy = self.screen_to_dots(event.x, event.y)
            new_x = int(dx - self.drag_offset_x)
            new_y = int(dy - self.drag_offset_y)

            label_w = self.label_width_mm * DOTS_PER_MM
            label_h = self.label_height_mm * DOTS_PER_MM
            new_x = max(0, min(new_x, label_w - 10))
            new_y = max(0, min(new_y, label_h - 10))
            if self.snap:
                new_x = self._snap_val(new_x)
                new_y = self._snap_val(new_y)

            elem = self.selected_element
            self._translate(elem, new_x - elem.x, new_y - elem.y)
            self.queue_draw()
            return True

        # Hover: cursor de resize sobre un handle
        self._update_cursor(event.x, event.y)
        return False

    def _on_button_release(self, widget, event):
        if event.button != 1:
            return False

        was_active = self.dragging or self.resizing
        self.dragging = False
        self.resizing = None
        if was_active and self._mutated:
            self._mutated = False
            self._notify_changed()
        return True

    # ── Teclado: borrar, mover con flechas ──

    def _on_key_press(self, widget, event):
        if not self.selected_element:
            return False
        kv = event.keyval

        # Borrar elemento
        if kv in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
            self._notify_before_change()
            if self.selected_element in self.elements:
                self.elements.remove(self.selected_element)
            self.selected_element = None
            if self.on_selection_changed:
                self.on_selection_changed(None)
            self.queue_draw()
            self._notify_changed()
            return True

        # Mover con flechas (Shift = paso fino de 1 dot)
        fine = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        step = 1 if fine else DOTS_PER_MM
        moves = {
            Gdk.KEY_Left: (-step, 0), Gdk.KEY_Right: (step, 0),
            Gdk.KEY_Up: (0, -step), Gdk.KEY_Down: (0, step),
        }
        if kv in moves:
            self._notify_before_change()
            ddx, ddy = moves[kv]
            elem = self.selected_element
            label_w = self.label_width_mm * DOTS_PER_MM
            label_h = self.label_height_mm * DOTS_PER_MM
            new_x = max(0, min(elem.x + ddx, label_w - 10))
            new_y = max(0, min(elem.y + ddy, label_h - 10))
            self._translate(elem, new_x - elem.x, new_y - elem.y)
            self.queue_draw()
            self._notify_changed()
            return True

        return False

    # ── Dibujo ──

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
        gx = self.offset_x + grid_step
        while gx < self.offset_x + rendered_w:
            cr.move_to(gx, self.offset_y)
            cr.line_to(gx, self.offset_y + rendered_h)
            cr.stroke()
            gx += grid_step
        gy = self.offset_y + grid_step
        while gy < self.offset_y + rendered_h:
            cr.move_to(self.offset_x, gy)
            cr.line_to(self.offset_x + rendered_w, gy)
            cr.stroke()
            gy += grid_step

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

        # Dibujar indicador de selección
        if self.selected_element:
            self._draw_selection(cr, self.selected_element)

        cr.restore()

        # Placeholder si no hay elementos
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

    def _draw_selection(self, cr, elem):
        """Dibuja borde azul y handles alrededor del elemento seleccionado."""
        bx, by, bw, bh = elem.get_bounds()
        pad = 3

        # Borde azul punteado
        cr.set_source_rgba(0.2, 0.5, 1.0, 0.8)
        cr.set_line_width(2)
        cr.set_dash([4, 3])
        cr.rectangle(bx - pad, by - pad, bw + pad * 2, bh + pad * 2)
        cr.stroke()
        cr.set_dash([])

        # Handles en las esquinas
        handle_size = 5
        cr.set_source_rgba(0.2, 0.5, 1.0, 1.0)
        for hx, hy in [
            (bx - pad, by - pad),
            (bx + bw + pad - handle_size, by - pad),
            (bx - pad, by + bh + pad - handle_size),
            (bx + bw + pad - handle_size, by + bh + pad - handle_size),
        ]:
            cr.rectangle(hx, hy, handle_size, handle_size)
            cr.fill()

        # Coordenadas del elemento
        cr.set_source_rgba(0.2, 0.5, 1.0, 0.9)
        cr.set_font_size(10)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        coord_text = f"({elem.x}, {elem.y})"
        cr.move_to(bx - pad, by - pad - 4)
        cr.show_text(coord_text)

    # ── Dibujo de elementos ──

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
        elif isinstance(elem, ImageElement):
            self._draw_image(cr, elem)

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
        """Dibuja el código de barras REAL si la librería está disponible."""
        if not elem.data:
            return

        geom = elem.barcode_geometry()
        if not geom:
            return self._draw_barcode_fallback(cr, elem)

        runs, total_modules = geom
        scale = max(1, elem.narrow)  # 1 módulo = narrow dots
        cr.set_source_rgb(0, 0, 0)
        for start, width in runs:
            cr.rectangle(elem.x + start * scale, elem.y, width * scale, elem.height)
        cr.fill()

        if elem.human_readable:
            cr.set_font_size(12)
            cr.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            total_w = total_modules * scale
            te = cr.text_extents(elem.data)
            text_x = elem.x + (total_w - te.width) / 2
            cr.move_to(max(elem.x, text_x), elem.y + elem.height + 14)
            cr.show_text(elem.data)

    def _draw_barcode_fallback(self, cr, elem):
        """Render aproximado (hash) cuando python-barcode no está disponible
        o el tipo/dato no es soportado por el encoder."""
        x, y = elem.x, elem.y
        height = elem.height

        cr.set_source_rgb(0, 0, 0)

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
        """Dibuja el QR REAL (escaneable) si la librería está disponible."""
        if not elem.data:
            return

        matrix = elem.qr_matrix()
        if not matrix:
            return self._draw_qr_fallback(cr, elem)

        cell = elem.cell_size
        cr.set_source_rgb(0, 0, 0)
        for r, row in enumerate(matrix):
            for c, on in enumerate(row):
                if on:
                    cr.rectangle(elem.x + c * cell, elem.y + r * cell, cell, cell)
        cr.fill()

    def _draw_qr_fallback(self, cr, elem):
        """Render aproximado (hash) cuando `qrcode` no está disponible."""
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

    def _draw_image(self, cr, elem):
        """Dibuja la imagen 1-bit (dithered) como máscara negra (WYSIWYG)."""
        m = elem.mono()
        if not m:
            # Placeholder si no se pudo cargar la imagen
            cr.set_source_rgba(0.7, 0.7, 0.7, 0.6)
            w = int(elem.src_w * elem.scale) or 80
            h = int(elem.src_h * elem.scale) or 80
            cr.rectangle(elem.x, elem.y, w, h)
            cr.stroke()
            return
        surface = cairo.ImageSurface.create_for_data(
            bytearray(m["a8"]), cairo.FORMAT_A8, m["w"], m["h"], m["stride"]
        )
        cr.save()
        cr.set_source_rgb(0, 0, 0)
        cr.mask_surface(surface, elem.x, elem.y)
        cr.restore()
