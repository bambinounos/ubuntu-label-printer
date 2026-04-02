"""Aplicación principal GTK para Label Printer con soporte TSPL/HT300."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from src.label_canvas import LabelCanvas
from src.tspl_generator import TSPLGenerator
from src.connection import (
    load_config, save_config, send_tspl, test_connection_async,
    get_status_async, list_printers,
)
from src.webserver import WebServerManager
from src.templates import TEMPLATES, LABEL_SIZES
from src.label_elements import (
    TextElement, BarcodeElement, QRElement, LineElement, BoxElement, CircleElement
)


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
        self.elements = []
        self.current_template = None
        self.conn_config = load_config()
        self.web_server = WebServerManager()

        self._apply_css()
        self._build_ui()

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

        self.template_buttons = {}
        for key, tmpl in TEMPLATES.items():
            btn = Gtk.Button()
            btn.get_style_context().add_class("template-btn")
            btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            btn_box.set_halign(Gtk.Align.START)

            name_lbl = Gtk.Label(label=tmpl["nombre"])
            name_lbl.set_xalign(0)
            name_lbl.set_markup(f"<b>{tmpl['nombre']}</b>")
            btn_box.pack_start(name_lbl, False, False, 0)

            desc_lbl = Gtk.Label(label=tmpl["descripcion"])
            desc_lbl.set_xalign(0)
            desc_lbl.set_line_wrap(True)
            desc_lbl.set_markup(
                f"<span size='small' color='#8b90a5'>{tmpl['descripcion']}</span>"
            )
            btn_box.pack_start(desc_lbl, False, False, 0)

            btn.add(btn_box)
            btn.connect("clicked", self._on_template_clicked, key)
            box.pack_start(btn, False, False, 0)
            self.template_buttons[key] = btn

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
            ("Línea", "BAR", self._on_add_line),
            ("Caja", "BOX", self._on_add_box),
            ("Círculo", "CIRCLE", self._on_add_circle),
        ]
        for label, icon_text, callback in add_buttons:
            btn = Gtk.Button(label=f"+ {label}")
            btn.set_halign(Gtk.Align.FILL)
            btn.connect("clicked", callback)
            box.pack_start(btn, False, False, 0)

        return scrolled

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
        box.pack_start(self.canvas, True, True, 0)

        return box

    # ── Panel Editor TSPL + Controles ──

    def _build_editor_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        # Título
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl = Gtk.Label()
        lbl.set_markup("<b>Editor TSPL</b>")
        title_box.pack_start(lbl, False, False, 0)

        # Botón sincronizar visual -> TSPL
        btn_sync_to_tspl = Gtk.Button(label="Visual → TSPL")
        btn_sync_to_tspl.set_tooltip_text("Regenerar TSPL desde los elementos visuales")
        btn_sync_to_tspl.connect("clicked", self._on_sync_to_tspl)
        title_box.pack_end(btn_sync_to_tspl, False, False, 0)

        btn_sync_to_visual = Gtk.Button(label="TSPL → Visual")
        btn_sync_to_visual.set_tooltip_text("Parsear TSPL y actualizar vista previa")
        btn_sync_to_visual.connect("clicked", self._on_sync_to_visual)
        title_box.pack_end(btn_sync_to_visual, False, False, 0)

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

    def _on_template_clicked(self, button, template_key):
        tmpl = TEMPLATES[template_key]
        self.current_template = template_key

        # Actualizar estilo de botones
        for key, btn in self.template_buttons.items():
            ctx = btn.get_style_context()
            if key == template_key:
                ctx.add_class("active")
            else:
                ctx.remove_class("active")

        # Cargar TSPL en editor
        self.tspl_buffer.set_text(tmpl["tspl"])

        # Parsear y mostrar en canvas
        config, elements = self.generator.parse_tspl(tmpl["tspl"])
        self.elements = elements

        # Actualizar tamaño
        w = tmpl.get("width_mm", config.get("width_mm", 60))
        h = tmpl.get("height_mm", config.get("height_mm", 40))
        self.spin_w.set_value(w)
        self.spin_h.set_value(h)
        self.canvas.set_label_size(w, h)
        self.canvas.set_elements(elements)

        # Actualizar copias
        self.spin_copies.set_value(config.get("copies", 1))

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
            elem = dialog.get_element()
            self.elements.append(elem)
            self._refresh_from_elements()
        dialog.destroy()

    def _on_add_barcode(self, button):
        dialog = BarcodeElementDialog(self)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            elem = dialog.get_element()
            self.elements.append(elem)
            self._refresh_from_elements()
        dialog.destroy()

    def _on_add_qr(self, button):
        dialog = QRElementDialog(self)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            elem = dialog.get_element()
            self.elements.append(elem)
            self._refresh_from_elements()
        dialog.destroy()

    def _on_add_line(self, button):
        elem = LineElement(x=20, y=160, width=440, height=2)
        self.elements.append(elem)
        self._refresh_from_elements()

    def _on_add_box(self, button):
        elem = BoxElement(x=10, y=10, x2=470, y2=310, thickness=2)
        self.elements.append(elem)
        self._refresh_from_elements()

    def _on_add_circle(self, button):
        elem = CircleElement(x=200, y=100, diameter=100, thickness=5)
        self.elements.append(elem)
        self._refresh_from_elements()

    def _refresh_from_elements(self):
        """Regenera TSPL desde elementos y actualiza canvas."""
        w = int(self.spin_w.get_value())
        h = int(self.spin_h.get_value())
        self.generator.width_mm = w
        self.generator.height_mm = h

        speed = int(self.spin_speed.get_value())
        density = int(self.spin_density.get_value())
        self.generator.speed = speed if speed > 0 else None
        self.generator.density = density if density != 8 else None

        copies = int(self.spin_copies.get_value())
        tspl = self.generator.generate(self.elements, copies)
        self.tspl_buffer.set_text(tspl)
        self.canvas.set_elements(self.elements)

    def _on_sync_to_tspl(self, button):
        self._refresh_from_elements()

    def _on_sync_to_visual(self, button):
        start, end = self.tspl_buffer.get_bounds()
        tspl = self.tspl_buffer.get_text(start, end, True)
        config, elements = self.generator.parse_tspl(tspl)
        self.elements = elements

        w = config.get("width_mm", 60)
        h = config.get("height_mm", 40)
        self.spin_w.set_value(w)
        self.spin_h.set_value(h)
        self.generator.width_mm = w
        self.generator.height_mm = h
        self.canvas.set_label_size(w, h)
        self.canvas.set_elements(elements)

        self.spin_copies.set_value(config.get("copies", 1))
        speed = config.get("speed")
        self.spin_speed.set_value(speed if speed else 0)
        density = config.get("density")
        self.spin_density.set_value(density if density else 8)

    def _on_print(self, button):
        start, end = self.tspl_buffer.get_bounds()
        tspl = self.tspl_buffer.get_text(start, end, True)

        if not tspl.strip():
            self._show_message("Error", "No hay código TSPL para imprimir.", Gtk.MessageType.ERROR)
            return

        # Ajustar copias (siempre aplicar el valor del spinner)
        import re
        copies = int(self.spin_copies.get_value())
        tspl = re.sub(r'^PRINT\s+\d+', f'PRINT {copies}', tspl, flags=re.MULTILINE)

        ok, msg = send_tspl(tspl, self.conn_config)

        msg_type = Gtk.MessageType.INFO if ok else Gtk.MessageType.ERROR
        self._show_message("Impresión" if ok else "Error", msg, msg_type)

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
    def __init__(self, parent):
        super().__init__(
            title="Agregar Texto", transient_for=parent, modal=True
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

        self.show_all()

    def get_element(self):
        return TextElement(
            x=int(self.spin_x.get_value()),
            y=int(self.spin_y.get_value()),
            text=self.entry_text.get_text(),
            font=self.font_combo.get_active_id() or "4",
            rotation=0,
            mx=int(self.spin_mx.get_value()),
            my=int(self.spin_my.get_value()),
        )


class BarcodeElementDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(
            title="Agregar Código de Barras", transient_for=parent, modal=True
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

        self.show_all()

    def get_element(self):
        return BarcodeElement(
            x=int(self.spin_x.get_value()),
            y=int(self.spin_y.get_value()),
            data=self.entry_data.get_text(),
            barcode_type=self.type_combo.get_active_id() or "128",
            height=int(self.spin_height.get_value()),
            human_readable=1 if self.check_readable.get_active() else 0,
            narrow=2, wide=2,
        )


class QRElementDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(
            title="Agregar Código QR", transient_for=parent, modal=True
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

        self.show_all()

    def get_element(self):
        return QRElement(
            x=int(self.spin_x.get_value()),
            y=int(self.spin_y.get_value()),
            data=self.entry_data.get_text(),
            ecc=self.ecc_combo.get_active_id() or "M",
            cell_size=int(self.cell_combo.get_active_id() or "5"),
            mode="A",
        )
