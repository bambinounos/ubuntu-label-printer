"""Aplicación principal GTK para Label Printer con soporte TSPL/HT300."""

import logging
import os

log = logging.getLogger("label-printer")

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

import cairo

from src.label_canvas import LabelCanvas
from src.tspl_generator import TSPLGenerator
from src.zpl_generator import ZPLGenerator
from src.connection import (
    load_config, save_config, send_raw, test_connection_async,
    get_status_async, list_printers,
)
from src.webserver import WebServerManager
from src.templates import TEMPLATES, LABEL_SIZES
from src.label_elements import (
    TextElement, BarcodeElement, QRElement, LineElement, BoxElement, CircleElement,
    ImageElement, element_from_dict,
)
from src.project import (
    save_design, load_design, parse_doc,
    load_user_templates, add_user_template, delete_user_template,
)
from src.mailmerge import read_csv, render_row, design_placeholders


class LabelPrinterApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.antigravity.labelprinter")
        self.window = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        self.window = MainWindow(application=self)
        self.window.show_all()


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(
            title="Label Printer - HT300 TSPL",
            default_width=1200,
            default_height=750,
            **kwargs,
        )

        self.generator = TSPLGenerator()
        self.zpl_generator = ZPLGenerator()
        self.language = "tspl"  # "tspl" o "zpl"
        self.elements = []
        self.current_template = None
        self.gap_mm = 2
        self.current_path = None  # ruta del .label abierto (para "Guardar")
        self.conn_config = load_config()
        self.user_templates = load_user_templates()
        self.web_server = WebServerManager()

        # Historial deshacer/rehacer (snapshots vía to_dict)
        self._undo = []
        self._redo = []
        self._restoring = False

        self._apply_css()
        self._build_ui()

        # Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y a nivel de ventana
        self.connect("key-press-event", self._on_window_key_press)

        # Detener servidor web al cerrar la ventana
        self.connect("destroy", lambda w: self._cleanup_web_server())

        # Estado de impresora
        GLib.timeout_add_seconds(10, self._update_printer_status)
        GLib.idle_add(self._update_printer_status)

    def _apply_css(self):
        css = b"""
        .dark-sidebar { background: #1a1d27; }
        .template-btn {
            background: #242836;
            border: 1px solid #2e3347;
            border-radius: 6px;
            padding: 8px 12px;
            color: #e4e7f1;
        }
        .template-btn:hover {
            border-color: #f59e0b;
            background: #2e3347;
        }
        .template-btn.active, .template-btn:checked {
            border-color: #f59e0b;
            background: rgba(245, 158, 11, 0.12);
        }
        .section-label {
            font-weight: bold;
            font-size: 11px;
            color: #8b90a5;
            letter-spacing: 1px;
        }
        .accent-button {
            background: #f59e0b;
            color: #000;
            font-weight: bold;
            border-radius: 6px;
            padding: 8px 20px;
        }
        .accent-button:hover { background: #fbbf24; }
        .tspl-view {
            font-family: monospace;
            font-size: 12px;
            background: #1a1d27;
            color: #e4e7f1;
        }
        .status-label { font-size: 11px; color: #8b90a5; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(self):
        # Header
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Label Printer")
        header.set_subtitle("HT300 - TSPL")
        self.set_titlebar(header)

        # Botón configurar conexión
        btn_conn = Gtk.Button.new_from_icon_name("preferences-system", Gtk.IconSize.BUTTON)
        btn_conn.set_tooltip_text("Configurar conexión de impresora")
        btn_conn.connect("clicked", self._on_connection_settings)
        header.pack_end(btn_conn)

        # Botones Abrir / Guardar diseño (.label)
        btn_open = Gtk.Button.new_from_icon_name("document-open", Gtk.IconSize.BUTTON)
        btn_open.set_tooltip_text("Abrir diseño (.label)")
        btn_open.connect("clicked", self._on_open_design)
        header.pack_start(btn_open)

        btn_save = Gtk.Button.new_from_icon_name("document-save", Gtk.IconSize.BUTTON)
        btn_save.set_tooltip_text("Guardar diseño (.label)")
        btn_save.connect("clicked", self._on_save_design)
        header.pack_start(btn_save)

        # Botón servidor web
        self.btn_web = Gtk.ToggleButton()
        web_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        web_box.pack_start(
            Gtk.Image.new_from_icon_name("network-server", Gtk.IconSize.BUTTON),
            False, False, 0
        )
        self.lbl_web_btn = Gtk.Label(label="Web")
        web_box.pack_start(self.lbl_web_btn, False, False, 0)
        self.btn_web.add(web_box)
        self.btn_web.set_tooltip_text("Iniciar/detener interfaz web (puerto 5080)")
        self.btn_web.connect("toggled", self._on_web_toggle)
        header.pack_end(self.btn_web)

        # Status en el header
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lbl_status = Gtk.Label(label="...")
        self.lbl_status.get_style_context().add_class("status-label")
        self.lbl_conn = Gtk.Label(label="...")
        self.lbl_conn.get_style_context().add_class("status-label")
        self.status_box.pack_start(self.lbl_status, False, False, 0)
        self.status_box.pack_start(self.lbl_conn, False, False, 0)
        header.pack_end(self.status_box)

        # Layout principal: 3 columnas
        main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(main_paned)

        # Col 1: Plantillas + Elementos
        left_panel = self._build_left_panel()
        main_paned.pack1(left_panel, False, False)
        main_paned.set_position(260)

        # Col 2+3: Canvas + Editor TSPL
        right_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_paned.pack2(right_paned, True, True)

        # Canvas (vista previa)
        canvas_box = self._build_canvas_panel()
        right_paned.pack1(canvas_box, True, True)

        # Editor TSPL + controles
        editor_box = self._build_editor_panel()
        right_paned.pack2(editor_box, True, True)
        right_paned.set_position(450)

    # ── Panel Izquierdo: Plantillas + Agregar Elementos ──

    def _build_left_panel(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_size_request(260, -1)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.get_style_context().add_class("dark-sidebar")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(10)
        box.set_margin_end(10)
        scrolled.add(box)

        # -- Plantillas --
        lbl = Gtk.Label(label="PLANTILLAS")
        lbl.get_style_context().add_class("section-label")
        lbl.set_xalign(0)
        box.pack_start(lbl, False, False, 0)

        # Contenedor reconstruible (built-in + usuario)
        self.templates_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.pack_start(self.templates_box, False, False, 0)
        self.template_buttons = {}
        self._populate_templates()

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(8)
        sep.set_margin_bottom(8)
        box.pack_start(sep, False, False, 0)

        # -- Tamaño etiqueta --
        lbl_size = Gtk.Label(label="TAMAÑO ETIQUETA")
        lbl_size.get_style_context().add_class("section-label")
        lbl_size.set_xalign(0)
        box.pack_start(lbl_size, False, False, 0)

        self.size_combo = Gtk.ComboBoxText()
        for key, size in LABEL_SIZES.items():
            self.size_combo.append(key, size["name"])
        self.size_combo.set_active_id("60x40")
        self.size_combo.connect("changed", self._on_size_changed)
        box.pack_start(self.size_combo, False, False, 0)

        # Custom size
        custom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_w = Gtk.Label(label="W:")
        self.spin_w = Gtk.SpinButton.new_with_range(10, 200, 1)
        self.spin_w.set_value(60)
        lbl_h = Gtk.Label(label="H:")
        self.spin_h = Gtk.SpinButton.new_with_range(10, 200, 1)
        self.spin_h.set_value(40)
        lbl_mm = Gtk.Label(label="mm")
        custom_box.pack_start(lbl_w, False, False, 0)
        custom_box.pack_start(self.spin_w, True, True, 0)
        custom_box.pack_start(lbl_h, False, False, 0)
        custom_box.pack_start(self.spin_h, True, True, 0)
        custom_box.pack_start(lbl_mm, False, False, 0)
        self.spin_w.connect("value-changed", self._on_custom_size_changed)
        self.spin_h.connect("value-changed", self._on_custom_size_changed)
        box.pack_start(custom_box, False, False, 0)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(8)
        sep2.set_margin_bottom(8)
        box.pack_start(sep2, False, False, 0)

        # -- Agregar elementos --
        lbl_add = Gtk.Label(label="AGREGAR ELEMENTO")
        lbl_add.get_style_context().add_class("section-label")
        lbl_add.set_xalign(0)
        box.pack_start(lbl_add, False, False, 0)

        add_buttons = [
            ("Texto", "TEXT", self._on_add_text),
            ("Código de Barras", "BARCODE", self._on_add_barcode),
            ("Código QR", "QRCODE", self._on_add_qr),
            ("Imagen / Logo", "IMAGE", self._on_add_image),
            ("Línea", "BAR", self._on_add_line),
            ("Caja", "BOX", self._on_add_box),
            ("Círculo", "CIRCLE", self._on_add_circle),
        ]
        for label, icon_text, callback in add_buttons:
            btn = Gtk.Button(label=f"+ {label}")
            btn.set_halign(Gtk.Align.FILL)
            btn.connect("clicked", callback)
            box.pack_start(btn, False, False, 0)

        sep3 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep3.set_margin_top(8)
        sep3.set_margin_bottom(8)
        box.pack_start(sep3, False, False, 0)

        btn_save_tmpl = Gtk.Button(label="★ Guardar como plantilla")
        btn_save_tmpl.set_halign(Gtk.Align.FILL)
        btn_save_tmpl.set_tooltip_text("Guarda el diseño actual como plantilla reutilizable")
        btn_save_tmpl.connect("clicked", self._on_save_as_template)
        box.pack_start(btn_save_tmpl, False, False, 0)

        return scrolled

    # ── Plantillas (built-in + usuario) ──

    def all_templates(self):
        """Combina plantillas built-in con las del usuario."""
        return {**TEMPLATES, **self.user_templates}

    def _populate_templates(self):
        """(Re)construye la lista de botones de plantilla en el panel."""
        for child in self.templates_box.get_children():
            self.templates_box.remove(child)
        self.template_buttons = {}

        for key, tmpl in self.all_templates().items():
            is_user = bool(tmpl.get("user"))
            btn = Gtk.Button()
            btn.get_style_context().add_class("template-btn")
            if key == self.current_template:
                btn.get_style_context().add_class("active")
            btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            btn_box.set_halign(Gtk.Align.START)

            prefix = "★ " if is_user else ""
            name_lbl = Gtk.Label()
            name_lbl.set_xalign(0)
            name_lbl.set_markup(f"<b>{prefix}{GLib.markup_escape_text(tmpl['nombre'])}</b>")
            btn_box.pack_start(name_lbl, False, False, 0)

            desc_lbl = Gtk.Label()
            desc_lbl.set_xalign(0)
            desc_lbl.set_line_wrap(True)
            desc_lbl.set_markup(
                f"<span size='small' color='#8b90a5'>"
                f"{GLib.markup_escape_text(tmpl.get('descripcion', ''))}</span>"
            )
            btn_box.pack_start(desc_lbl, False, False, 0)
            btn.add(btn_box)
            btn.connect("clicked", self._on_template_clicked, key)
            self.template_buttons[key] = btn

            if is_user:
                # Fila con botón de plantilla + botón eliminar
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
                btn.set_hexpand(True)
                row.pack_start(btn, True, True, 0)
                btn_del = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
                btn_del.set_tooltip_text("Eliminar esta plantilla")
                btn_del.connect("clicked", self._on_delete_template, key)
                row.pack_start(btn_del, False, False, 0)
                self.templates_box.pack_start(row, False, False, 0)
            else:
                self.templates_box.pack_start(btn, False, False, 0)

        self.templates_box.show_all()

    # ── Canvas (Vista Previa) ──

    def _build_canvas_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        lbl = Gtk.Label()
        lbl.set_markup("<b>Vista Previa</b>")
        lbl.set_margin_top(8)
        lbl.set_margin_bottom(4)
        box.pack_start(lbl, False, False, 0)

        self.canvas = LabelCanvas()
        self.canvas.set_size_request(300, 250)
        self.canvas.on_element_moved = self._on_element_moved_on_canvas
        self.canvas.on_before_change = self._push_undo
        self.canvas.on_element_edit = self._on_canvas_edit_element
        box.pack_start(self.canvas, True, True, 0)

        # Barra de herramientas del canvas (snap)
        tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tools.set_margin_start(8)
        tools.set_margin_end(8)
        tools.set_margin_bottom(4)
        self.check_snap = Gtk.CheckButton(label="Ajustar a grilla (1mm)")
        self.check_snap.set_active(True)
        self.check_snap.set_tooltip_text("Alinea los elementos a la grilla de 1mm al mover")
        self.check_snap.connect("toggled", self._on_snap_toggled)
        tools.pack_start(self.check_snap, False, False, 0)

        hint = Gtk.Label()
        hint.set_markup(
            '<span size="small" color="#8b90a5">'
            'Doble clic: editar · Supr: borrar · Flechas: mover · Ctrl+Z: deshacer'
            '</span>'
        )
        tools.pack_end(hint, False, False, 0)
        box.pack_start(tools, False, False, 0)

        return box

    def _on_snap_toggled(self, check):
        self.canvas.snap = check.get_active()

    def _on_element_moved_on_canvas(self):
        """Regenera código cuando un elemento se mueve/redimensiona/borra."""
        self._refresh_from_elements()

    def _on_canvas_edit_element(self, elem):
        """Doble clic sobre un elemento: abrir su diálogo de edición."""
        dialog = None
        if isinstance(elem, TextElement):
            dialog = TextElementDialog(self, element=elem)
        elif isinstance(elem, BarcodeElement):
            dialog = BarcodeElementDialog(self, element=elem)
        elif isinstance(elem, QRElement):
            dialog = QRElementDialog(self, element=elem)
        elif isinstance(elem, ImageElement):
            dialog = ImageElementDialog(self, element=elem)
        elif isinstance(elem, (LineElement, BoxElement, CircleElement)):
            dialog = ShapeElementDialog(self, element=elem)
        if dialog is None:
            return
        if dialog.run() == Gtk.ResponseType.OK:
            new_elem = dialog.get_element()
            self._push_undo()
            try:
                idx = self.elements.index(elem)
                self.elements[idx] = new_elem
            except ValueError:
                self.elements.append(new_elem)
            self.canvas.selected_element = new_elem
            new_elem.selected = True
            self._refresh_from_elements()
        dialog.destroy()

    # ── Panel Editor TSPL/ZPL + Controles ──

    def _build_editor_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        # Título + selector de lenguaje
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lbl_editor_title = Gtk.Label()
        self.lbl_editor_title.set_markup("<b>Editor TSPL</b>")
        title_box.pack_start(self.lbl_editor_title, False, False, 0)

        # Combo lenguaje
        self.lang_combo = Gtk.ComboBoxText()
        self.lang_combo.append("tspl", "TSPL")
        self.lang_combo.append("zpl", "ZPL")
        self.lang_combo.set_active_id("tspl")
        self.lang_combo.connect("changed", self._on_language_changed)
        title_box.pack_start(self.lang_combo, False, False, 0)

        # Botón sincronizar visual -> código
        self.btn_sync_to_code = Gtk.Button(label="Visual → TSPL")
        self.btn_sync_to_code.set_tooltip_text("Regenerar código desde los elementos visuales")
        self.btn_sync_to_code.connect("clicked", self._on_sync_to_tspl)
        title_box.pack_end(self.btn_sync_to_code, False, False, 0)

        self.btn_sync_to_visual = Gtk.Button(label="TSPL → Visual")
        self.btn_sync_to_visual.set_tooltip_text("Parsear código y actualizar vista previa")
        self.btn_sync_to_visual.connect("clicked", self._on_sync_to_visual)
        title_box.pack_end(self.btn_sync_to_visual, False, False, 0)

        box.pack_start(title_box, False, False, 0)

        # Editor TSPL
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)

        self.tspl_buffer = Gtk.TextBuffer()
        self.tspl_view = Gtk.TextView(buffer=self.tspl_buffer)
        self.tspl_view.get_style_context().add_class("tspl-view")
        self.tspl_view.set_monospace(True)
        self.tspl_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.tspl_view.set_left_margin(8)
        self.tspl_view.set_top_margin(8)
        scrolled.add(self.tspl_view)
        box.pack_start(scrolled, True, True, 0)

        # Controles avanzados (SPEED / DENSITY)
        advanced_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        lbl_speed = Gtk.Label(label="Velocidad:")
        lbl_speed.set_tooltip_text("SPEED: velocidad de impresión (pulgadas/seg)")
        advanced_box.pack_start(lbl_speed, False, False, 0)
        self.spin_speed = Gtk.SpinButton.new_with_range(0, 15, 1)
        self.spin_speed.set_value(0)
        self.spin_speed.set_tooltip_text("0 = default impresora")
        advanced_box.pack_start(self.spin_speed, False, False, 0)

        lbl_density = Gtk.Label(label="Densidad:")
        lbl_density.set_tooltip_text("DENSITY: oscuridad 0-15 (default=8)")
        advanced_box.pack_start(lbl_density, False, False, 0)
        self.spin_density = Gtk.SpinButton.new_with_range(0, 15, 1)
        self.spin_density.set_value(8)
        self.spin_density.set_tooltip_text("0=claro, 8=normal, 15=oscuro")
        advanced_box.pack_start(self.spin_density, False, False, 0)

        box.pack_start(advanced_box, False, False, 0)

        # Controles de impresión
        print_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Modo actual
        mode_names = {"cups": "CUPS", "network": "Red TCP", "usb": "USB directo"}
        mode = self.conn_config.get("mode", "cups")
        self.lbl_print_mode = Gtk.Label()
        self.lbl_print_mode.set_markup(
            f'<span size="small" color="#8b90a5">{mode_names.get(mode, mode)}</span>'
        )
        print_box.pack_start(self.lbl_print_mode, False, False, 0)

        # Copias
        lbl_copies = Gtk.Label(label="Copias:")
        print_box.pack_start(lbl_copies, False, False, 0)

        self.spin_copies = Gtk.SpinButton.new_with_range(1, 99, 1)
        self.spin_copies.set_value(1)
        print_box.pack_start(self.spin_copies, False, False, 0)

        # Espaciador
        print_box.pack_start(Gtk.Label(), True, True, 0)

        # Botón imprimir
        btn_print = Gtk.Button(label="   Imprimir   ")
        btn_print.get_style_context().add_class("accent-button")
        btn_print.connect("clicked", self._on_print)
        print_box.pack_end(btn_print, False, False, 0)

        # Botón datos variables / lotes CSV
        btn_batch = Gtk.Button(label="Datos / CSV…")
        btn_batch.set_tooltip_text(
            "Imprimir por lotes desde un CSV usando placeholders {{columna}}"
        )
        btn_batch.connect("clicked", self._on_batch_print)
        print_box.pack_end(btn_batch, False, False, 0)

        box.pack_start(print_box, False, False, 0)

        # Referencia rápida
        expander = Gtk.Expander(label="Referencia TSPL")
        ref_label = Gtk.Label()
        ref_label.set_markup(
            '<span size="small" font_family="monospace">'
            '<b>TEXT</b> x,y,"font",rot,mx,my,"texto"\n'
            '  Fuentes: "1"=8x12  "2"=12x20  "3"=16x24  "4"=24x32  "5"=32x48  "TSS24.BF2"=24x24\n'
            '<b>BARCODE</b> x,y,"tipo",alto,legible,rot,estrecho,ancho,"datos"\n'
            '  Tipos: "128" "128M" "39" "39C" "EAN13" "UPCA"\n'
            '<b>QRCODE</b> x,y,ECC,celda,modo,rot,"datos"   ECC: L M Q H | Celda: 1-12\n'
            '<b>BAR</b> x,y,ancho,alto   <b>BOX</b> x1,y1,x2,y2,grosor\n'
            '<b>Nota:</b> 203 DPI → 8 dots/mm → Área 60x40mm = 480x320 dots'
            '</span>'
        )
        ref_label.set_xalign(0)
        ref_label.set_margin_start(8)
        ref_label.set_margin_top(4)
        ref_label.set_selectable(True)
        expander.add(ref_label)
        box.pack_start(expander, False, False, 0)

        return box

    # ── Callbacks ──

    def _on_language_changed(self, combo):
        lang = combo.get_active_id()
        if lang == self.language:
            return
        self.language = lang
        label = "TSPL" if lang == "tspl" else "ZPL"
        self.lbl_editor_title.set_markup(f"<b>Editor {label}</b>")
        self.btn_sync_to_code.set_label(f"Visual → {label}")
        self.btn_sync_to_visual.set_label(f"{label} → Visual")
        # Regenerar código desde elementos actuales
        if self.elements:
            self._refresh_from_elements()

    def _get_active_generator(self):
        """Retorna el generador activo según el lenguaje seleccionado."""
        if self.language == "zpl":
            return self.zpl_generator
        return self.generator

    def _on_template_clicked(self, button, template_key):
        tmpl = self.all_templates().get(template_key)
        if not tmpl:
            return

        if self.elements:
            self._push_undo()

        if "elements" in tmpl:
            # Plantilla de usuario (formato JSON nativo .label)
            label, settings, elements = parse_doc(tmpl)
        else:
            # Plantilla built-in (TSPL canónico)
            config, elements = self.generator.parse_tspl(tmpl["tspl"])
            label = {
                "width_mm": tmpl.get("width_mm", config.get("width_mm", 60)),
                "height_mm": tmpl.get("height_mm", config.get("height_mm", 40)),
                "gap_mm": config.get("gap_mm", 2),
            }
            settings = {
                "copies": config.get("copies", 1),
                "speed": config.get("speed"),
                "density": config.get("density"),
            }

        self.current_path = None
        self._apply_state(label, settings, elements, template_key=template_key)

    def _highlight_template(self, template_key):
        """Marca visualmente la plantilla activa (o ninguna)."""
        for key, btn in self.template_buttons.items():
            ctx = btn.get_style_context()
            if key == template_key:
                ctx.add_class("active")
            else:
                ctx.remove_class("active")

    def _apply_state(self, label, settings, elements, *, template_key=None,
                     regenerate_code=True):
        """Punto único de restauración de estado (cargar, plantilla, undo/redo).

        Aplica tamaño, lenguaje, settings y elementos al canvas y los controles.
        """
        self.elements = elements

        w = int(label.get("width_mm", 60))
        h = int(label.get("height_mm", 40))
        self.gap_mm = int(label.get("gap_mm", self.gap_mm))

        self.spin_w.set_value(w)
        self.spin_h.set_value(h)
        self.generator.width_mm = w
        self.generator.height_mm = h
        self.zpl_generator.width_mm = w
        self.zpl_generator.height_mm = h
        self.canvas.set_label_size(w, h)

        self.spin_copies.set_value(settings.get("copies") or 1)
        self.spin_speed.set_value(settings.get("speed") or 0)
        density = settings.get("density")
        self.spin_density.set_value(density if density is not None else 8)

        lang = settings.get("language")
        if lang in ("tspl", "zpl"):
            # Dispara _on_language_changed (actualiza self.language y etiquetas)
            self.lang_combo.set_active_id(lang)

        self.current_template = template_key
        self._highlight_template(template_key)

        self.canvas.set_elements(elements)
        if regenerate_code:
            self._refresh_from_elements()

    def _on_size_changed(self, combo):
        size_id = combo.get_active_id()
        if size_id and size_id in LABEL_SIZES:
            size = LABEL_SIZES[size_id]
            self.spin_w.set_value(size["width"])
            self.spin_h.set_value(size["height"])

    def _on_custom_size_changed(self, spin):
        w = int(self.spin_w.get_value())
        h = int(self.spin_h.get_value())
        self.generator.width_mm = w
        self.generator.height_mm = h
        self.canvas.set_label_size(w, h)

    def _on_add_text(self, button):
        dialog = TextElementDialog(self)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self._push_undo()
            self.elements.append(dialog.get_element())
            self._refresh_from_elements()
        dialog.destroy()

    def _on_add_barcode(self, button):
        dialog = BarcodeElementDialog(self)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self._push_undo()
            self.elements.append(dialog.get_element())
            self._refresh_from_elements()
        dialog.destroy()

    def _on_add_qr(self, button):
        dialog = QRElementDialog(self)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self._push_undo()
            self.elements.append(dialog.get_element())
            self._refresh_from_elements()
        dialog.destroy()

    def _on_add_image(self, button):
        dialog = ImageElementDialog(self)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            elem = dialog.get_element()
            if elem is not None:
                self._push_undo()
                self.elements.append(elem)
                self._refresh_from_elements()
        dialog.destroy()

    def _on_add_line(self, button):
        self._push_undo()
        self.elements.append(LineElement(x=20, y=160, width=440, height=2))
        self._refresh_from_elements()

    def _on_add_box(self, button):
        self._push_undo()
        self.elements.append(BoxElement(x=10, y=10, x2=470, y2=310, thickness=2))
        self._refresh_from_elements()

    def _on_add_circle(self, button):
        self._push_undo()
        self.elements.append(CircleElement(x=200, y=100, diameter=100, thickness=5))
        self._refresh_from_elements()

    def _refresh_from_elements(self):
        """Regenera código desde elementos y actualiza canvas."""
        w = int(self.spin_w.get_value())
        h = int(self.spin_h.get_value())

        gen = self._get_active_generator()
        gen.width_mm = w
        gen.height_mm = h

        # Configurar parámetros específicos del generador
        speed = int(self.spin_speed.get_value())
        density = int(self.spin_density.get_value())
        if self.language == "tspl":
            self.generator.speed = speed if speed > 0 else None
            self.generator.density = density if density != 8 else None
        else:
            self.zpl_generator.darkness = density * 2  # TSPL 0-15 -> ZPL 0-30

        copies = int(self.spin_copies.get_value())
        code = gen.generate(self.elements, copies)
        self.tspl_buffer.set_text(code)
        self.canvas.set_elements(self.elements)

    def _on_sync_to_tspl(self, button):
        self._refresh_from_elements()

    def _on_sync_to_visual(self, button):
        start, end = self.tspl_buffer.get_bounds()
        code = self.tspl_buffer.get_text(start, end, True)

        if self.language == "zpl":
            config, elements = self.zpl_generator.parse_zpl(code)
        else:
            config, elements = self.generator.parse_tspl(code)

        label = {
            "width_mm": config.get("width_mm", 60),
            "height_mm": config.get("height_mm", 40),
            "gap_mm": config.get("gap_mm", self.gap_mm),
        }
        density = config.get("density") or config.get("darkness")
        if density and self.language == "zpl":
            density = min(15, density // 2)
        settings = {
            "copies": config.get("copies", 1),
            "speed": config.get("speed"),
            "density": density,
        }
        # No regenerar el buffer: respetar el código que escribió el usuario.
        self._apply_state(label, settings, elements, template_key=None,
                          regenerate_code=False)

    # ── Deshacer / Rehacer ──

    def _snapshot(self):
        return {
            "width_mm": int(self.spin_w.get_value()),
            "height_mm": int(self.spin_h.get_value()),
            "gap_mm": self.gap_mm,
            "language": self.language,
            "speed": int(self.spin_speed.get_value()),
            "density": int(self.spin_density.get_value()),
            "copies": int(self.spin_copies.get_value()),
            "elements": [e.to_dict() for e in self.elements],
        }

    def _push_undo(self):
        """Apila el estado actual antes de una mutación."""
        if self._restoring:
            return
        self._undo.append(self._snapshot())
        if len(self._undo) > 50:
            self._undo.pop(0)
        self._redo.clear()

    def _restore_snapshot(self, snap):
        self._restoring = True
        try:
            elements = [e for e in (element_from_dict(d) for d in snap["elements"]) if e]
            label = {"width_mm": snap["width_mm"], "height_mm": snap["height_mm"],
                     "gap_mm": snap.get("gap_mm", 2)}
            settings = {"language": snap.get("language"), "speed": snap.get("speed"),
                        "density": snap.get("density"), "copies": snap.get("copies")}
            self._apply_state(label, settings, elements,
                              template_key=self.current_template)
        finally:
            self._restoring = False

    def _undo_action(self):
        if not self._undo:
            return
        self._redo.append(self._snapshot())
        self._restore_snapshot(self._undo.pop())

    def _redo_action(self):
        if not self._redo:
            return
        self._undo.append(self._snapshot())
        self._restore_snapshot(self._redo.pop())

    def _on_window_key_press(self, widget, event):
        if not (event.state & Gdk.ModifierType.CONTROL_MASK):
            return False
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        kv = event.keyval
        if kv in (Gdk.KEY_z, Gdk.KEY_Z):
            self._redo_action() if shift else self._undo_action()
            return True
        if kv in (Gdk.KEY_y, Gdk.KEY_Y):
            self._redo_action()
            return True
        return False

    # ── Guardar / Cargar diseños .label ──

    def _current_design_kwargs(self):
        """Recolecta el estado actual para serializar un diseño."""
        speed = int(self.spin_speed.get_value())
        density = int(self.spin_density.get_value())
        return dict(
            width_mm=int(self.spin_w.get_value()),
            height_mm=int(self.spin_h.get_value()),
            gap_mm=self.gap_mm,
            language=self.language,
            speed=speed if speed > 0 else None,
            density=density,
            copies=int(self.spin_copies.get_value()),
            elements=self.elements,
        )

    def _on_save_design(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Guardar diseño", transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialog.set_do_overwrite_confirmation(True)
        if self.current_path:
            dialog.set_filename(self.current_path)
        else:
            dialog.set_current_name("etiqueta.label")
        flt = Gtk.FileFilter()
        flt.set_name("Diseños de etiqueta (*.label)")
        flt.add_pattern("*.label")
        dialog.add_filter(flt)

        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            if not path.endswith(".label"):
                path += ".label"
            try:
                save_design(path, **self._current_design_kwargs())
                self.current_path = path
                self._show_message(
                    "Diseño guardado",
                    f"Guardado en:\n{path}", Gtk.MessageType.INFO,
                )
            except Exception as e:
                log.error(f"Error al guardar diseño: {e}", exc_info=True)
                self._show_message("Error", f"No se pudo guardar: {e}",
                                   Gtk.MessageType.ERROR)
        dialog.destroy()

    def _on_open_design(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Abrir diseño", transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        flt = Gtk.FileFilter()
        flt.set_name("Diseños de etiqueta (*.label)")
        flt.add_pattern("*.label")
        dialog.add_filter(flt)

        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            try:
                label, settings, elements = load_design(path)
                self._push_undo()
                self.current_path = path
                self._apply_state(label, settings, elements, template_key=None)
            except Exception as e:
                log.error(f"Error al abrir diseño: {e}", exc_info=True)
                self._show_message("Error", f"No se pudo abrir: {e}",
                                   Gtk.MessageType.ERROR)
        dialog.destroy()

    # ── Plantillas de usuario ──

    def _on_save_as_template(self, button):
        if not self.elements:
            self._show_message(
                "Sin contenido",
                "Agrega elementos antes de guardar una plantilla.",
                Gtk.MessageType.WARNING,
            )
            return

        dialog = Gtk.Dialog(title="Guardar como plantilla", transient_for=self, modal=True)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        grid.attach(Gtk.Label(label="Nombre:", xalign=0), 0, 0, 1, 1)
        entry_name = Gtk.Entry()
        entry_name.set_hexpand(True)
        entry_name.set_activates_default(True)
        grid.attach(entry_name, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label="Descripción:", xalign=0), 0, 1, 1, 1)
        entry_desc = Gtk.Entry()
        entry_desc.set_hexpand(True)
        grid.attach(entry_desc, 1, 1, 1, 1)
        dialog.get_content_area().add(grid)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            nombre = entry_name.get_text().strip() or "Mi plantilla"
            descripcion = entry_desc.get_text().strip() or "Plantilla personalizada"
            kwargs = self._current_design_kwargs()
            kwargs.pop("elements")
            try:
                key = add_user_template(
                    nombre, descripcion, elements=self.elements, **kwargs,
                )
                self.user_templates = load_user_templates()
                self.current_template = key
                self._populate_templates()
                self._show_message(
                    "Plantilla guardada",
                    f"'{nombre}' está disponible en el panel de plantillas.",
                    Gtk.MessageType.INFO,
                )
            except Exception as e:
                log.error(f"Error al guardar plantilla: {e}", exc_info=True)
                self._show_message("Error", f"No se pudo guardar: {e}",
                                   Gtk.MessageType.ERROR)
        dialog.destroy()

    def _on_delete_template(self, button, key):
        tmpl = self.user_templates.get(key)
        if not tmpl:
            return
        confirm = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"¿Eliminar la plantilla '{tmpl.get('nombre', key)}'?",
        )
        confirm.format_secondary_text("Esta acción no se puede deshacer.")
        resp = confirm.run()
        confirm.destroy()
        if resp == Gtk.ResponseType.YES:
            delete_user_template(key)
            self.user_templates = load_user_templates()
            if self.current_template == key:
                self.current_template = None
            self._populate_templates()

    def _has_image(self):
        return any(isinstance(e, ImageElement) for e in self.elements)

    def _build_print_payload(self):
        """Regenera el payload desde los elementos (bytes si hay imagen)."""
        w = int(self.spin_w.get_value())
        h = int(self.spin_h.get_value())
        copies = int(self.spin_copies.get_value())
        speed = int(self.spin_speed.get_value())
        density = int(self.spin_density.get_value())
        if self.language == "zpl":
            self.zpl_generator.width_mm = w
            self.zpl_generator.height_mm = h
            self.zpl_generator.darkness = density * 2
            return self.zpl_generator.generate(self.elements, copies)  # str (hex ASCII)
        self.generator.width_mm = w
        self.generator.height_mm = h
        self.generator.speed = speed if speed > 0 else None
        self.generator.density = density if density != 8 else None
        return self.generator.generate_bytes(self.elements, copies)  # bytes

    def _on_print(self, button):
        copies = int(self.spin_copies.get_value())

        if self._has_image():
            # El TextView no puede contener BITMAP binario: regenerar desde elementos
            payload = self._build_print_payload()
            if not payload:
                self._show_message("Error", "No se pudo generar la etiqueta.",
                                   Gtk.MessageType.ERROR)
                return
        else:
            start, end = self.tspl_buffer.get_bounds()
            tspl = self.tspl_buffer.get_text(start, end, True)
            if not tspl.strip():
                self._show_message("Error", "No hay código para imprimir.",
                                   Gtk.MessageType.ERROR)
                return
            import re
            tspl = re.sub(r'^PRINT\s+\d+', f'PRINT {copies}', tspl, flags=re.MULTILINE)
            payload = tspl

        size = len(payload)
        log.info(f"Imprimiendo: mode={self.conn_config.get('mode')}, "
                 f"copies={copies}, image={self._has_image()}, bytes={size}")

        try:
            ok, msg = send_raw(payload, self.conn_config)
            log.info(f"Resultado: ok={ok}, msg={msg}")
        except Exception as e:
            log.error(f"Excepción al imprimir: {e}", exc_info=True)
            ok, msg = False, f"Error inesperado: {e}"

        msg_type = Gtk.MessageType.INFO if ok else Gtk.MessageType.ERROR
        self._show_message("Impresión" if ok else "Error", msg, msg_type)

    def _on_batch_print(self, button):
        if not self.elements:
            self._show_message(
                "Sin diseño",
                "Crea un diseño con placeholders {{columna}} antes de imprimir por lotes.",
                Gtk.MessageType.WARNING,
            )
            return
        dialog = BatchPrintDialog(self)
        dialog.run()
        dialog.destroy()

    def _on_connection_settings(self, button):
        dialog = ConnectionDialog(self, self.conn_config)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.conn_config = dialog.get_config()
            save_config(self.conn_config)
            self._update_print_mode_label()
            self._update_printer_status()
        dialog.destroy()

    def _update_print_mode_label(self):
        mode_names = {"cups": "CUPS", "network": "Red TCP", "usb": "USB directo"}
        mode = self.conn_config.get("mode", "cups")
        detail = ""
        if mode == "cups":
            detail = self.conn_config.get("cups_printer", "HT300")
        elif mode == "network":
            ip = self.conn_config.get("network_ip", "?")
            port = self.conn_config.get("network_port", 9100)
            detail = f"{ip}:{port}"
        elif mode == "usb":
            detail = self.conn_config.get("usb_device", "/dev/usb/lp0")
        self.lbl_print_mode.set_markup(
            f'<span size="small" color="#8b90a5">{mode_names.get(mode, mode)} ({detail})</span>'
        )

    def _show_message(self, title, message, msg_type):
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=msg_type,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def _on_web_toggle(self, button):
        if button.get_active():
            ok, msg = self.web_server.start(port=5080)
            if ok:
                self.lbl_web_btn.set_text("Web ON")
                self.btn_web.set_tooltip_text(
                    f"Servidor web activo — {self.web_server.get_url()}\nClick para detener"
                )
                # Ofrecer abrir en navegador
                dialog = Gtk.MessageDialog(
                    transient_for=self, modal=True,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text="Servidor web iniciado",
                )
                dialog.format_secondary_text(
                    f"{msg}\n\n¿Abrir en el navegador?"
                )
                response = dialog.run()
                dialog.destroy()
                if response == Gtk.ResponseType.YES:
                    import subprocess
                    subprocess.Popen(["xdg-open", self.web_server.get_url()])
            else:
                button.set_active(False)
                self._show_message("Error", msg, Gtk.MessageType.ERROR)
        else:
            ok, msg = self.web_server.stop()
            self.lbl_web_btn.set_text("Web")
            self.btn_web.set_tooltip_text("Iniciar/detener interfaz web (puerto 5080)")

    def _cleanup_web_server(self):
        """Detiene el servidor web al cerrar la app."""
        if self.web_server.running:
            self.web_server.stop()

    def _update_printer_status(self):
        get_status_async(self.conn_config, self._apply_printer_status)
        return True  # Continuar timer

    def _apply_printer_status(self, info):
        """Callback que actualiza la UI con el estado (llamado en main thread)."""
        dot = "●"
        status_text = info.get('status', '?')
        ok = info.get('ok', False)
        conn = info.get('connection', '')

        color = "#34d399" if ok else "#f87171"
        self.lbl_status.set_markup(
            f'<span color="{color}">{dot}</span> {status_text}'
        )
        self.lbl_conn.set_markup(
            f'<span size="small" color="#8b90a5">{conn}</span>'
        )


# ── Diálogo de configuración de conexión ──

class ConnectionDialog(Gtk.Dialog):
    """Diálogo para configurar la conexión con la impresora (CUPS, Red, USB)."""

    def __init__(self, parent, config):
        super().__init__(
            title="Configuración de Conexión", transient_for=parent, modal=True
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        self.set_default_size(500, -1)
        self.config = config.copy()
        self._parent = parent

        content = self.get_content_area()
        content.set_spacing(8)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        content.add(main_box)

        # ── Modo de conexión ──
        lbl_mode = Gtk.Label()
        lbl_mode.set_markup("<b>Modo de conexión</b>")
        lbl_mode.set_xalign(0)
        main_box.pack_start(lbl_mode, False, False, 0)

        self.radio_cups = Gtk.RadioButton.new_with_label(None, "CUPS (cola de impresión)")
        self.radio_network = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_cups, "Red TCP directo (socket)"
        )
        self.radio_usb = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_cups, "USB directo (/dev/usb/lp0)"
        )

        main_box.pack_start(self.radio_cups, False, False, 0)
        main_box.pack_start(self.radio_network, False, False, 0)
        main_box.pack_start(self.radio_usb, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.pack_start(sep, False, False, 4)

        # ── Stack con las opciones de cada modo ──
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        main_box.pack_start(self.stack, False, False, 0)

        self.stack.add_named(self._build_cups_page(), "cups")
        self.stack.add_named(self._build_network_page(), "network")
        self.stack.add_named(self._build_usb_page(), "usb")

        # Conectar radios
        self.radio_cups.connect("toggled", self._on_mode_toggled, "cups")
        self.radio_network.connect("toggled", self._on_mode_toggled, "network")
        self.radio_usb.connect("toggled", self._on_mode_toggled, "usb")

        # ── Resultado de prueba ──
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.pack_start(sep2, False, False, 4)

        test_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.btn_test = Gtk.Button(label="Probar Conexión")
        self.btn_test.connect("clicked", self._on_test)
        test_box.pack_start(self.btn_test, False, False, 0)

        self.spinner = Gtk.Spinner()
        test_box.pack_start(self.spinner, False, False, 0)
        main_box.pack_start(test_box, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(80)
        scrolled.set_max_content_height(120)
        self.test_result = Gtk.Label(label="")
        self.test_result.set_xalign(0)
        self.test_result.set_line_wrap(True)
        self.test_result.set_selectable(True)
        scrolled.add(self.test_result)
        main_box.pack_start(scrolled, False, False, 0)

        # Cargar valores actuales
        self._load_from_config()
        self.show_all()

    def _build_cups_page(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(4)

        grid.attach(Gtk.Label(label="Nombre de cola CUPS:", xalign=0), 0, 0, 1, 1)
        self.entry_cups_printer = Gtk.ComboBoxText.new_with_entry()
        # Agregar impresoras detectadas
        printers = list_printers()
        for p in printers:
            self.entry_cups_printer.append_text(p)
        self.entry_cups_printer.set_hexpand(True)
        grid.attach(self.entry_cups_printer, 1, 0, 1, 1)

        lbl_help = Gtk.Label()
        lbl_help.set_markup(
            '<span size="small" color="#8b90a5">'
            'Usa <b>lpstat -a</b> para ver colas disponibles.\n'
            'Crear cola raw: <b>sudo lpadmin -p HT300 -v "usb://..." -m raw -E</b>'
            '</span>'
        )
        lbl_help.set_xalign(0)
        lbl_help.set_line_wrap(True)
        grid.attach(lbl_help, 0, 1, 2, 1)

        return grid

    def _build_network_page(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(4)

        grid.attach(Gtk.Label(label="Dirección IP:", xalign=0), 0, 0, 1, 1)
        self.entry_ip = Gtk.Entry()
        self.entry_ip.set_placeholder_text("192.168.1.100")
        self.entry_ip.set_hexpand(True)
        grid.attach(self.entry_ip, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Puerto:", xalign=0), 0, 1, 1, 1)
        self.spin_port = Gtk.SpinButton.new_with_range(1, 65535, 1)
        self.spin_port.set_value(9100)
        grid.attach(self.spin_port, 1, 1, 1, 1)

        lbl_help = Gtk.Label()
        lbl_help.set_markup(
            '<span size="small" color="#8b90a5">'
            'Puerto <b>9100</b> = Raw TCP (JetDirect). '
            'Envía TSPL directamente sin pasar por CUPS.\n'
            'La impresora debe estar en la misma red.'
            '</span>'
        )
        lbl_help.set_xalign(0)
        lbl_help.set_line_wrap(True)
        grid.attach(lbl_help, 0, 2, 2, 1)

        return grid

    def _build_usb_page(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(4)

        grid.attach(Gtk.Label(label="Dispositivo:", xalign=0), 0, 0, 1, 1)
        self.entry_usb_device = Gtk.ComboBoxText.new_with_entry()
        self.entry_usb_device.append_text("/dev/usb/lp0")
        self.entry_usb_device.append_text("/dev/usb/lp1")
        self.entry_usb_device.set_hexpand(True)
        grid.attach(self.entry_usb_device, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="USB Vendor:Product:", xalign=0), 0, 1, 1, 1)
        self.entry_usb_id = Gtk.Entry()
        self.entry_usb_id.set_placeholder_text("0483:5743")
        grid.attach(self.entry_usb_id, 1, 1, 1, 1)

        lbl_help = Gtk.Label()
        lbl_help.set_markup(
            '<span size="small" color="#8b90a5">'
            'Escribe directamente al dispositivo USB sin CUPS.\n'
            'Requiere permisos: <b>sudo chmod 666 /dev/usb/lp0</b>\n'
            'O agregar usuario al grupo lp: <b>sudo usermod -aG lp $USER</b>'
            '</span>'
        )
        lbl_help.set_xalign(0)
        lbl_help.set_line_wrap(True)
        grid.attach(lbl_help, 0, 2, 2, 1)

        return grid

    def _load_from_config(self):
        mode = self.config.get("mode", "cups")
        if mode == "network":
            self.radio_network.set_active(True)
        elif mode == "usb":
            self.radio_usb.set_active(True)
        else:
            self.radio_cups.set_active(True)
        self.stack.set_visible_child_name(mode)

        # CUPS
        child = self.entry_cups_printer.get_child()
        if child:
            child.set_text(self.config.get("cups_printer", "HT300"))

        # Network
        self.entry_ip.set_text(self.config.get("network_ip", "192.168.1.100"))
        self.spin_port.set_value(self.config.get("network_port", 9100))

        # USB
        child_usb = self.entry_usb_device.get_child()
        if child_usb:
            child_usb.set_text(self.config.get("usb_device", "/dev/usb/lp0"))
        self.entry_usb_id.set_text(self.config.get("usb_vendor_product", "0483:5743"))

    def _on_mode_toggled(self, radio, mode):
        if radio.get_active():
            self.stack.set_visible_child_name(mode)

    def _on_test(self, button):
        self.btn_test.set_sensitive(False)
        self.spinner.start()
        self.test_result.set_text("Probando...")

        config = self.get_config()
        test_connection_async(config, self._on_test_result)

    def _on_test_result(self, ok, message):
        self.btn_test.set_sensitive(True)
        self.spinner.stop()
        color = "#34d399" if ok else "#f87171"
        icon = "OK" if ok else "ERROR"
        self.test_result.set_markup(
            f'<span color="{color}"><b>{icon}</b></span>\n{message}'
        )

    def get_config(self):
        config = self.config.copy()

        if self.radio_network.get_active():
            config["mode"] = "network"
        elif self.radio_usb.get_active():
            config["mode"] = "usb"
        else:
            config["mode"] = "cups"

        child = self.entry_cups_printer.get_child()
        config["cups_printer"] = child.get_text() if child else "HT300"
        config["network_ip"] = self.entry_ip.get_text()
        config["network_port"] = int(self.spin_port.get_value())

        child_usb = self.entry_usb_device.get_child()
        config["usb_device"] = child_usb.get_text() if child_usb else "/dev/usb/lp0"
        config["usb_vendor_product"] = self.entry_usb_id.get_text()

        return config


# ── Diálogos para agregar elementos ──

class TextElementDialog(Gtk.Dialog):
    def __init__(self, parent, element=None):
        self._rotation = element.rotation if element else 0
        super().__init__(
            title="Editar Texto" if element else "Agregar Texto",
            transient_for=parent, modal=True
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        self.set_default_size(380, -1)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        self.get_content_area().add(grid)

        row = 0
        grid.attach(Gtk.Label(label="Texto:", xalign=0), 0, row, 1, 1)
        self.entry_text = Gtk.Entry()
        self.entry_text.set_placeholder_text("Contenido del texto")
        self.entry_text.set_hexpand(True)
        grid.attach(self.entry_text, 1, row, 2, 1)

        row += 1
        grid.attach(Gtk.Label(label="Posición X (dots):", xalign=0), 0, row, 1, 1)
        self.spin_x = Gtk.SpinButton.new_with_range(0, 800, 1)
        self.spin_x.set_value(60)
        grid.attach(self.spin_x, 1, row, 1, 1)

        row += 1
        grid.attach(Gtk.Label(label="Posición Y (dots):", xalign=0), 0, row, 1, 1)
        self.spin_y = Gtk.SpinButton.new_with_range(0, 800, 1)
        self.spin_y.set_value(0)
        grid.attach(self.spin_y, 1, row, 1, 1)

        row += 1
        grid.attach(Gtk.Label(label="Fuente:", xalign=0), 0, row, 1, 1)
        self.font_combo = Gtk.ComboBoxText()
        self.font_combo.append("1", '"1" - 8x12 (pequeña)')
        self.font_combo.append("2", '"2" - 12x20')
        self.font_combo.append("3", '"3" - 16x24 (estándar)')
        self.font_combo.append("4", '"4" - 24x32 (grande)')
        self.font_combo.append("5", '"5" - 32x48 (extra)')
        self.font_combo.append("TSS24.BF2", '"TSS24.BF2" - Asiática 24x24')
        self.font_combo.set_active_id("4")
        grid.attach(self.font_combo, 1, row, 2, 1)

        row += 1
        grid.attach(Gtk.Label(label="Multiplicador:", xalign=0), 0, row, 1, 1)
        mx_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        mx_box.pack_start(Gtk.Label(label="X:"), False, False, 0)
        self.spin_mx = Gtk.SpinButton.new_with_range(1, 10, 1)
        self.spin_mx.set_value(1)
        mx_box.pack_start(self.spin_mx, False, False, 0)
        mx_box.pack_start(Gtk.Label(label="Y:"), False, False, 0)
        self.spin_my = Gtk.SpinButton.new_with_range(1, 10, 1)
        self.spin_my.set_value(1)
        mx_box.pack_start(self.spin_my, False, False, 0)
        grid.attach(mx_box, 1, row, 2, 1)

        if element:
            self.entry_text.set_text(element.text)
            self.spin_x.set_value(element.x)
            self.spin_y.set_value(element.y)
            self.font_combo.set_active_id(element.font)
            self.spin_mx.set_value(element.mx)
            self.spin_my.set_value(element.my)

        self.show_all()

    def get_element(self):
        return TextElement(
            x=int(self.spin_x.get_value()),
            y=int(self.spin_y.get_value()),
            text=self.entry_text.get_text(),
            font=self.font_combo.get_active_id() or "4",
            rotation=self._rotation,
            mx=int(self.spin_mx.get_value()),
            my=int(self.spin_my.get_value()),
        )


class BarcodeElementDialog(Gtk.Dialog):
    def __init__(self, parent, element=None):
        self._rotation = element.rotation if element else 0
        self._narrow = element.narrow if element else 2
        self._wide = element.wide if element else 2
        super().__init__(
            title="Editar Código de Barras" if element else "Agregar Código de Barras",
            transient_for=parent, modal=True
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        self.set_default_size(380, -1)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        self.get_content_area().add(grid)

        row = 0
        grid.attach(Gtk.Label(label="Datos:", xalign=0), 0, row, 1, 1)
        self.entry_data = Gtk.Entry()
        self.entry_data.set_placeholder_text("Contenido del código")
        self.entry_data.set_hexpand(True)
        grid.attach(self.entry_data, 1, row, 2, 1)

        row += 1
        grid.attach(Gtk.Label(label="Tipo:", xalign=0), 0, row, 1, 1)
        self.type_combo = Gtk.ComboBoxText()
        for t in ["128", "128M", "39", "39C", "EAN13", "EAN8", "UPCA"]:
            self.type_combo.append(t, t)
        self.type_combo.set_active_id("128")
        grid.attach(self.type_combo, 1, row, 2, 1)

        row += 1
        grid.attach(Gtk.Label(label="Posición X:", xalign=0), 0, row, 1, 1)
        self.spin_x = Gtk.SpinButton.new_with_range(0, 800, 1)
        self.spin_x.set_value(60)
        grid.attach(self.spin_x, 1, row, 1, 1)

        row += 1
        grid.attach(Gtk.Label(label="Posición Y:", xalign=0), 0, row, 1, 1)
        self.spin_y = Gtk.SpinButton.new_with_range(0, 800, 1)
        self.spin_y.set_value(150)
        grid.attach(self.spin_y, 1, row, 1, 1)

        row += 1
        grid.attach(Gtk.Label(label="Altura:", xalign=0), 0, row, 1, 1)
        self.spin_height = Gtk.SpinButton.new_with_range(20, 300, 5)
        self.spin_height.set_value(100)
        grid.attach(self.spin_height, 1, row, 1, 1)

        row += 1
        self.check_readable = Gtk.CheckButton(label="Mostrar texto debajo")
        self.check_readable.set_active(True)
        grid.attach(self.check_readable, 0, row, 3, 1)

        if element:
            self.entry_data.set_text(element.data)
            # Asegurar que el tipo actual exista en el combo
            if not self.type_combo.set_active_id(element.barcode_type):
                self.type_combo.append(element.barcode_type, element.barcode_type)
                self.type_combo.set_active_id(element.barcode_type)
            self.spin_x.set_value(element.x)
            self.spin_y.set_value(element.y)
            self.spin_height.set_value(element.height)
            self.check_readable.set_active(bool(element.human_readable))

        self.show_all()

    def get_element(self):
        return BarcodeElement(
            x=int(self.spin_x.get_value()),
            y=int(self.spin_y.get_value()),
            data=self.entry_data.get_text(),
            barcode_type=self.type_combo.get_active_id() or "128",
            height=int(self.spin_height.get_value()),
            human_readable=1 if self.check_readable.get_active() else 0,
            rotation=self._rotation,
            narrow=self._narrow, wide=self._wide,
        )


class QRElementDialog(Gtk.Dialog):
    def __init__(self, parent, element=None):
        self._rotation = element.rotation if element else 0
        self._mode = element.mode if element else "A"
        super().__init__(
            title="Editar Código QR" if element else "Agregar Código QR",
            transient_for=parent, modal=True
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        self.set_default_size(380, -1)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        self.get_content_area().add(grid)

        row = 0
        grid.attach(Gtk.Label(label="Datos:", xalign=0), 0, row, 1, 1)
        self.entry_data = Gtk.Entry()
        self.entry_data.set_placeholder_text("Contenido del QR")
        self.entry_data.set_hexpand(True)
        grid.attach(self.entry_data, 1, row, 2, 1)

        row += 1
        grid.attach(Gtk.Label(label="Posición X:", xalign=0), 0, row, 1, 1)
        self.spin_x = Gtk.SpinButton.new_with_range(0, 800, 1)
        self.spin_x.set_value(350)
        grid.attach(self.spin_x, 1, row, 1, 1)

        row += 1
        grid.attach(Gtk.Label(label="Posición Y:", xalign=0), 0, row, 1, 1)
        self.spin_y = Gtk.SpinButton.new_with_range(0, 800, 1)
        self.spin_y.set_value(10)
        grid.attach(self.spin_y, 1, row, 1, 1)

        row += 1
        grid.attach(Gtk.Label(label="Tamaño celda:", xalign=0), 0, row, 1, 1)
        self.cell_combo = Gtk.ComboBoxText()
        for s in ["1", "3", "5", "7", "10", "12"]:
            self.cell_combo.append(s, f"{s} dots")
        self.cell_combo.set_active_id("5")
        grid.attach(self.cell_combo, 1, row, 1, 1)

        row += 1
        grid.attach(Gtk.Label(label="Corrección error:", xalign=0), 0, row, 1, 1)
        self.ecc_combo = Gtk.ComboBoxText()
        self.ecc_combo.append("L", "L - Bajo (7%)")
        self.ecc_combo.append("M", "M - Medio (15%)")
        self.ecc_combo.append("Q", "Q - Alto (25%)")
        self.ecc_combo.append("H", "H - Máximo (30%)")
        self.ecc_combo.set_active_id("M")
        grid.attach(self.ecc_combo, 1, row, 2, 1)

        if element:
            self.entry_data.set_text(element.data)
            self.spin_x.set_value(element.x)
            self.spin_y.set_value(element.y)
            self.cell_combo.set_active_id(str(element.cell_size))
            self.ecc_combo.set_active_id(element.ecc)

        self.show_all()

    def get_element(self):
        return QRElement(
            x=int(self.spin_x.get_value()),
            y=int(self.spin_y.get_value()),
            data=self.entry_data.get_text(),
            ecc=self.ecc_combo.get_active_id() or "M",
            cell_size=int(self.cell_combo.get_active_id() or "5"),
            mode=self._mode,
            rotation=self._rotation,
        )


class ShapeElementDialog(Gtk.Dialog):
    """Editar Línea (BAR), Caja (BOX) o Círculo (CIRCLE)."""

    def __init__(self, parent, element):
        self.element = element
        if isinstance(element, LineElement):
            title = "Editar Línea"
        elif isinstance(element, BoxElement):
            title = "Editar Caja"
        else:
            title = "Editar Círculo"
        super().__init__(title=title, transient_for=parent, modal=True)
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        self.set_default_size(360, -1)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        self.get_content_area().add(grid)
        self.spins = {}

        if isinstance(element, LineElement):
            spec = [("X (dots):", "x", element.x), ("Y (dots):", "y", element.y),
                    ("Ancho:", "width", element.width), ("Alto:", "height", element.height)]
        elif isinstance(element, BoxElement):
            spec = [("X1:", "x", element.x), ("Y1:", "y", element.y),
                    ("X2:", "x2", element.x2), ("Y2:", "y2", element.y2),
                    ("Grosor:", "thickness", element.thickness)]
        else:  # CircleElement
            spec = [("X:", "x", element.x), ("Y:", "y", element.y),
                    ("Diámetro:", "diameter", element.diameter),
                    ("Grosor:", "thickness", element.thickness)]

        for r, (label, key, val) in enumerate(spec):
            grid.attach(Gtk.Label(label=label, xalign=0), 0, r, 1, 1)
            sp = Gtk.SpinButton.new_with_range(0, 2000, 1)
            sp.set_value(val)
            grid.attach(sp, 1, r, 1, 1)
            self.spins[key] = sp

        self.show_all()

    def get_element(self):
        v = {k: int(sp.get_value()) for k, sp in self.spins.items()}
        e = self.element
        if isinstance(e, LineElement):
            return LineElement(x=v["x"], y=v["y"], width=v["width"], height=v["height"])
        if isinstance(e, BoxElement):
            return BoxElement(x=v["x"], y=v["y"], x2=v["x2"], y2=v["y2"],
                              thickness=v["thickness"])
        return CircleElement(x=v["x"], y=v["y"], diameter=v["diameter"],
                             thickness=v["thickness"])


class ImageElementDialog(Gtk.Dialog):
    """Insertar/editar una imagen o logo (monocromo 1-bit)."""

    def __init__(self, parent, element=None):
        super().__init__(
            title="Editar Imagen" if element else "Agregar Imagen / Logo",
            transient_for=parent, modal=True,
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        self.set_default_size(460, -1)
        self.elem = element  # ImageElement existente o None (nuevo)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        self.get_content_area().add(grid)
        r = 0

        grid.attach(Gtk.Label(label="Imagen:", xalign=0), 0, r, 1, 1)
        self.file_btn = Gtk.FileChooserButton(
            title="Selecciona imagen", action=Gtk.FileChooserAction.OPEN
        )
        flt = Gtk.FileFilter()
        flt.set_name("Imágenes")
        for pat in ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif"):
            flt.add_pattern(pat)
        self.file_btn.add_filter(flt)
        self.file_btn.set_hexpand(True)
        self.file_btn.connect("file-set", self._on_file_set)
        grid.attach(self.file_btn, 1, r, 2, 1)
        r += 1

        grid.attach(Gtk.Label(label="Escala:", xalign=0), 0, r, 1, 1)
        self.spin_scale = Gtk.SpinButton.new_with_range(0.05, 8.0, 0.05)
        self.spin_scale.set_digits(2)
        self.spin_scale.set_value(element.scale if element else 1.0)
        self.spin_scale.connect("value-changed", lambda *_: self._update_preview())
        grid.attach(self.spin_scale, 1, r, 2, 1)
        r += 1

        grid.attach(Gtk.Label(label="Umbral:", xalign=0), 0, r, 1, 1)
        self.scale_thr = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.scale_thr.set_value(element.threshold if element else 128)
        self.scale_thr.set_hexpand(True)
        self.scale_thr.connect("value-changed", lambda *_: self._update_preview())
        grid.attach(self.scale_thr, 1, r, 2, 1)
        r += 1

        self.check_dither = Gtk.CheckButton(label="Difuminado (dither)")
        self.check_dither.set_active(element.dither if element else True)
        self.check_dither.connect("toggled", lambda *_: self._on_dither_toggled())
        grid.attach(self.check_dither, 0, r, 2, 1)
        self.check_invert = Gtk.CheckButton(label="Invertir")
        self.check_invert.set_active(element.invert if element else False)
        self.check_invert.connect("toggled", lambda *_: self._update_preview())
        grid.attach(self.check_invert, 2, r, 1, 1)
        r += 1

        self.preview = Gtk.DrawingArea()
        self.preview.set_size_request(280, 160)
        self.preview.connect("draw", self._on_draw_preview)
        grid.attach(self.preview, 0, r, 3, 1)
        r += 1

        self.lbl_dim = Gtk.Label(xalign=0)
        self.lbl_dim.get_style_context().add_class("status-label")
        grid.attach(self.lbl_dim, 0, r, 3, 1)

        self._sync_threshold_sensitivity()
        self.show_all()
        self._update_preview()

    def _on_dither_toggled(self):
        self._sync_threshold_sensitivity()
        self._update_preview()

    def _sync_threshold_sensitivity(self):
        # El umbral solo aplica cuando NO hay difuminado
        self.scale_thr.set_sensitive(not self.check_dither.get_active())

    def _on_file_set(self, btn):
        path = btn.get_filename()
        if not path:
            return
        try:
            from src.image_ops import encode_file_b64
            b64, w, h = encode_file_b64(path)
        except Exception as e:
            log.error(f"Error cargando imagen: {e}", exc_info=True)
            self.lbl_dim.set_markup(
                f'<span color="#f87171">{GLib.markup_escape_text(str(e))}</span>'
            )
            return
        if self.elem is None:
            self.elem = ImageElement(x=10, y=10)
        self.elem.path = path
        self.elem.data_b64 = b64
        self.elem.src_w = w
        self.elem.src_h = h
        self._update_preview()

    def _collect(self):
        if self.elem is None:
            return None
        self.elem.scale = round(self.spin_scale.get_value(), 3)
        self.elem.threshold = int(self.scale_thr.get_value())
        self.elem.dither = self.check_dither.get_active()
        self.elem.invert = self.check_invert.get_active()
        self.elem._mono_key = None  # invalidar cache tras cambiar parámetros
        return self.elem

    def _update_preview(self):
        self._collect()
        self.preview.queue_draw()
        if self.elem and self.elem.data_b64:
            m = self.elem.mono()
            if m:
                self.lbl_dim.set_text(
                    f"{m['w']} x {m['h']} dots  (≈ {m['w']/8:.0f} x {m['h']/8:.0f} mm)"
                )

    def _on_draw_preview(self, widget, cr):
        alloc = widget.get_allocation()
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        if not (self.elem and self.elem.data_b64):
            return
        m = self.elem.mono()
        if not m:
            return
        scale = min(alloc.width / m["w"], alloc.height / m["h"], 1.0)
        cr.save()
        cr.translate((alloc.width - m["w"] * scale) / 2,
                     (alloc.height - m["h"] * scale) / 2)
        cr.scale(scale, scale)
        surf = cairo.ImageSurface.create_for_data(
            bytearray(m["a8"]), cairo.FORMAT_A8, m["w"], m["h"], m["stride"]
        )
        cr.set_source_rgb(0, 0, 0)
        cr.mask_surface(surf, 0, 0)
        cr.restore()

    def get_element(self):
        return self._collect()


class BatchPrintDialog(Gtk.Dialog):
    """Impresión por lotes desde CSV con placeholders {{columna}}."""

    def __init__(self, parent):
        super().__init__(
            title="Datos variables / Impresión por lotes",
            transient_for=parent, modal=True,
        )
        self.parent_win = parent
        self.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        self.set_default_size(580, 500)
        self.columns = []
        self.rows = []

        box = self.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)

        # Placeholders detectados en el diseño actual
        ph = design_placeholders(parent.elements)
        lbl_ph = Gtk.Label(xalign=0)
        lbl_ph.set_line_wrap(True)
        if ph:
            chips = ", ".join("<tt>{{%s}}</tt>" % p for p in ph)
            lbl_ph.set_markup(f"Placeholders en el diseño: {chips}")
        else:
            lbl_ph.set_markup(
                '<span color="#d97706">El diseño no tiene placeholders. '
                'Edita un texto o código y escribe <tt>{{nombre}}</tt> donde quieras '
                'insertar datos de cada fila.</span>'
            )
        box.pack_start(lbl_ph, False, False, 0)

        # Selector de CSV
        file_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        file_box.pack_start(Gtk.Label(label="Archivo CSV:"), False, False, 0)
        self.file_btn = Gtk.FileChooserButton(
            title="Selecciona CSV", action=Gtk.FileChooserAction.OPEN
        )
        flt = Gtk.FileFilter()
        flt.set_name("CSV (*.csv)")
        flt.add_pattern("*.csv")
        self.file_btn.add_filter(flt)
        self.file_btn.connect("file-set", self._on_file_set)
        file_box.pack_start(self.file_btn, True, True, 0)
        box.pack_start(file_box, False, False, 0)

        self.lbl_info = Gtk.Label(xalign=0)
        box.pack_start(self.lbl_info, False, False, 0)

        # Vista previa de filas (TreeView dinámico)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        self.tree = Gtk.TreeView()
        scroll.add(self.tree)
        box.pack_start(scroll, True, True, 0)

        # Vista previa por fila en el canvas
        prev_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        prev_box.pack_start(Gtk.Label(label="Vista previa fila:"), False, False, 0)
        self.spin_row = Gtk.SpinButton.new_with_range(1, 1, 1)
        self.spin_row.connect("value-changed", self._on_preview_row)
        prev_box.pack_start(self.spin_row, False, False, 0)
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        prev_box.pack_start(self.progress, True, True, 0)
        box.pack_start(prev_box, False, False, 0)

        # Imprimir todas
        self.btn_print_all = Gtk.Button(label="Imprimir todas")
        self.btn_print_all.get_style_context().add_class("accent-button")
        self.btn_print_all.set_sensitive(False)
        self.btn_print_all.connect("clicked", self._on_print_all)
        box.pack_start(self.btn_print_all, False, False, 0)

        self.connect("response", lambda *_: self._restore_canvas())
        self.connect("destroy", lambda *_: self._restore_canvas())
        self.show_all()

    def _on_file_set(self, btn):
        path = btn.get_filename()
        if not path:
            return
        try:
            self.columns, self.rows = read_csv(path)
        except Exception as e:
            log.error(f"Error leyendo CSV: {e}", exc_info=True)
            self.parent_win._show_message("Error CSV", str(e), Gtk.MessageType.ERROR)
            return
        n = len(self.rows)
        self.lbl_info.set_markup(
            f"<b>{n}</b> filas · columnas: {GLib.markup_escape_text(', '.join(self.columns))}"
        )
        self._build_tree()
        self.spin_row.set_range(1, max(1, n))
        self.spin_row.set_value(1)
        self.btn_print_all.set_sensitive(n > 0)
        self.btn_print_all.set_label(f"Imprimir todas ({n})")
        self.progress.set_fraction(0)
        self.progress.set_text("")
        if n:
            self._on_preview_row(self.spin_row)

    def _build_tree(self):
        for col in self.tree.get_columns():
            self.tree.remove_column(col)
        if not self.columns:
            self.tree.set_model(None)
            return
        store = Gtk.ListStore(*([str] * len(self.columns)))
        for r in self.rows[:200]:  # límite de preview
            store.append([str(r.get(c, "")) for c in self.columns])
        self.tree.set_model(store)
        for i, c in enumerate(self.columns):
            self.tree.append_column(
                Gtk.TreeViewColumn(c, Gtk.CellRendererText(), text=i)
            )

    def _on_preview_row(self, spin):
        if not self.rows:
            return
        idx = max(0, min(int(spin.get_value()) - 1, len(self.rows) - 1))
        elems = render_row(self.parent_win.elements, self.rows[idx])
        self.parent_win.canvas.set_elements(elems)

    def _restore_canvas(self):
        self.parent_win.canvas.set_elements(self.parent_win.elements)

    def _on_print_all(self, button):
        if not self.rows:
            return
        self.btn_print_all.set_sensitive(False)
        gen = self.parent_win._get_active_generator()
        config = self.parent_win.conn_config
        copies = int(self.parent_win.spin_copies.get_value())
        rows = list(self.rows)
        base = list(self.parent_win.elements)
        total = len(rows)

        is_zpl = (self.parent_win.language == "zpl")

        def worker():
            sent = 0
            for i, row in enumerate(rows):
                elems = render_row(base, row)
                # generate_bytes soporta imágenes (BITMAP binario) y texto normal
                code = gen.generate(elems, copies) if is_zpl \
                    else gen.generate_bytes(elems, copies)
                try:
                    ok, msg = send_raw(code, config)
                except Exception as e:
                    ok, msg = False, str(e)
                if not ok:
                    GLib.idle_add(self._batch_error, i + 1, msg)
                    return
                sent += 1
                GLib.idle_add(self._batch_progress, sent, total)
            GLib.idle_add(self._batch_done, sent, total)

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _batch_progress(self, sent, total):
        self.progress.set_fraction(sent / total)
        self.progress.set_text(f"{sent}/{total}")
        return False

    def _batch_error(self, row_num, msg):
        self.btn_print_all.set_sensitive(True)
        self.parent_win._show_message(
            "Error en lote", f"Falló en la fila {row_num}:\n{msg}",
            Gtk.MessageType.ERROR,
        )
        return False

    def _batch_done(self, sent, total):
        self.btn_print_all.set_sensitive(True)
        self.parent_win._show_message(
            "Lote completado", f"Se enviaron {sent}/{total} etiquetas.",
            Gtk.MessageType.INFO,
        )
        return False
