"""Aplicación principal GTK para Label Printer."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from src.label_editor import LabelEditor
from src.print_manager import PrintManager
from src.template_manager import TemplateManager, LABEL_SIZES


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
            title="Label Printer",
            default_width=1000,
            default_height=700,
            **kwargs,
        )

        self.template_manager = TemplateManager()
        self.print_manager = PrintManager()
        self.current_label_size = "small_address"

        self._apply_css()
        self._build_ui()

    def _apply_css(self):
        css = b"""
        .header-bar { background: #2c3e50; }
        .sidebar { background: #f5f6fa; border-right: 1px solid #dcdde1; }
        .preview-area { background: #ecf0f1; }
        .field-label { font-weight: bold; font-size: 12px; color: #2c3e50; }
        .section-title { font-weight: bold; font-size: 14px; color: #2c3e50; margin-top: 8px; }
        .print-button { background: #27ae60; color: white; font-weight: bold; font-size: 14px; }
        .print-button:hover { background: #2ecc71; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _build_ui(self):
        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Label Printer")
        header.set_subtitle("Diseño e impresión de etiquetas")
        self.set_titlebar(header)

        # Botón nueva etiqueta
        btn_new = Gtk.Button.new_from_icon_name("document-new", Gtk.IconSize.BUTTON)
        btn_new.set_tooltip_text("Nueva etiqueta")
        btn_new.connect("clicked", self._on_new_label)
        header.pack_start(btn_new)

        # Botón exportar PDF
        btn_export = Gtk.Button.new_from_icon_name(
            "document-save-as", Gtk.IconSize.BUTTON
        )
        btn_export.set_tooltip_text("Exportar a PDF")
        btn_export.connect("clicked", self._on_export_pdf)
        header.pack_end(btn_export)

        # Layout principal
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(main_box)

        # Panel izquierdo - Configuración
        sidebar = self._build_sidebar()
        main_box.pack_start(sidebar, False, False, 0)

        # Panel derecho - Vista previa
        preview_box = self._build_preview()
        main_box.pack_start(preview_box, True, True, 0)

    def _build_sidebar(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_size_request(320, -1)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.get_style_context().add_class("sidebar")

        sidebar = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=12
        )
        scrolled.add(sidebar)

        # === Tamaño de etiqueta ===
        title_size = Gtk.Label(label="Tamaño de Etiqueta")
        title_size.get_style_context().add_class("section-title")
        title_size.set_xalign(0)
        sidebar.pack_start(title_size, False, False, 0)

        self.size_combo = Gtk.ComboBoxText()
        for key, size in LABEL_SIZES.items():
            self.size_combo.append(key, f"{size['name']} ({size['width']}x{size['height']}mm)")
        self.size_combo.set_active_id("small_address")
        self.size_combo.connect("changed", self._on_size_changed)
        sidebar.pack_start(self.size_combo, False, False, 0)

        sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar.pack_start(sep1, False, False, 4)

        # === Contenido de texto ===
        title_content = Gtk.Label(label="Contenido")
        title_content.get_style_context().add_class("section-title")
        title_content.set_xalign(0)
        sidebar.pack_start(title_content, False, False, 0)

        # Línea 1
        lbl1 = Gtk.Label(label="Línea 1 (título)")
        lbl1.get_style_context().add_class("field-label")
        lbl1.set_xalign(0)
        sidebar.pack_start(lbl1, False, False, 0)

        self.entry_line1 = Gtk.Entry()
        self.entry_line1.set_placeholder_text("Nombre / Título")
        self.entry_line1.connect("changed", self._on_content_changed)
        sidebar.pack_start(self.entry_line1, False, False, 0)

        # Línea 2
        lbl2 = Gtk.Label(label="Línea 2")
        lbl2.get_style_context().add_class("field-label")
        lbl2.set_xalign(0)
        sidebar.pack_start(lbl2, False, False, 0)

        self.entry_line2 = Gtk.Entry()
        self.entry_line2.set_placeholder_text("Dirección / Descripción")
        self.entry_line2.connect("changed", self._on_content_changed)
        sidebar.pack_start(self.entry_line2, False, False, 0)

        # Línea 3
        lbl3 = Gtk.Label(label="Línea 3")
        lbl3.get_style_context().add_class("field-label")
        lbl3.set_xalign(0)
        sidebar.pack_start(lbl3, False, False, 0)

        self.entry_line3 = Gtk.Entry()
        self.entry_line3.set_placeholder_text("Ciudad / Info adicional")
        self.entry_line3.connect("changed", self._on_content_changed)
        sidebar.pack_start(self.entry_line3, False, False, 0)

        # Línea 4
        lbl4 = Gtk.Label(label="Línea 4")
        lbl4.get_style_context().add_class("field-label")
        lbl4.set_xalign(0)
        sidebar.pack_start(lbl4, False, False, 0)

        self.entry_line4 = Gtk.Entry()
        self.entry_line4.set_placeholder_text("Teléfono / Código postal")
        self.entry_line4.connect("changed", self._on_content_changed)
        sidebar.pack_start(self.entry_line4, False, False, 0)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar.pack_start(sep2, False, False, 4)

        # === Código de barras / QR ===
        title_barcode = Gtk.Label(label="Código de Barras / QR")
        title_barcode.get_style_context().add_class("section-title")
        title_barcode.set_xalign(0)
        sidebar.pack_start(title_barcode, False, False, 0)

        self.barcode_check = Gtk.CheckButton(label="Incluir código de barras")
        self.barcode_check.connect("toggled", self._on_content_changed)
        sidebar.pack_start(self.barcode_check, False, False, 0)

        self.barcode_type_combo = Gtk.ComboBoxText()
        self.barcode_type_combo.append("code128", "Code 128")
        self.barcode_type_combo.append("ean13", "EAN-13")
        self.barcode_type_combo.append("qr", "Código QR")
        self.barcode_type_combo.set_active_id("code128")
        self.barcode_type_combo.connect("changed", self._on_content_changed)
        sidebar.pack_start(self.barcode_type_combo, False, False, 0)

        lbl_barcode = Gtk.Label(label="Dato del código")
        lbl_barcode.get_style_context().add_class("field-label")
        lbl_barcode.set_xalign(0)
        sidebar.pack_start(lbl_barcode, False, False, 0)

        self.entry_barcode = Gtk.Entry()
        self.entry_barcode.set_placeholder_text("Valor del código")
        self.entry_barcode.connect("changed", self._on_content_changed)
        sidebar.pack_start(self.entry_barcode, False, False, 0)

        sep3 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar.pack_start(sep3, False, False, 4)

        # === Cantidad ===
        title_qty = Gtk.Label(label="Impresión")
        title_qty.get_style_context().add_class("section-title")
        title_qty.set_xalign(0)
        sidebar.pack_start(title_qty, False, False, 0)

        qty_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_qty = Gtk.Label(label="Cantidad de copias:")
        qty_box.pack_start(lbl_qty, False, False, 0)

        self.spin_qty = Gtk.SpinButton.new_with_range(1, 100, 1)
        self.spin_qty.set_value(1)
        qty_box.pack_start(self.spin_qty, False, False, 0)
        sidebar.pack_start(qty_box, False, False, 0)

        # Botón imprimir
        btn_print = Gtk.Button(label="  Imprimir  ")
        btn_print.get_style_context().add_class("print-button")
        btn_print.set_margin_top(12)
        btn_print.connect("clicked", self._on_print)
        sidebar.pack_start(btn_print, False, False, 0)

        return scrolled

    def _build_preview(self):
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        preview_box.get_style_context().add_class("preview-area")

        lbl_preview = Gtk.Label(label="Vista Previa")
        lbl_preview.get_style_context().add_class("section-title")
        lbl_preview.set_margin_top(8)
        preview_box.pack_start(lbl_preview, False, False, 0)

        # Drawing area para la vista previa
        self.label_editor = LabelEditor()
        self.label_editor.set_size_request(400, 300)
        self.label_editor.set_halign(Gtk.Align.CENTER)
        self.label_editor.set_valign(Gtk.Align.CENTER)
        self.label_editor.set_margin_top(20)
        preview_box.pack_start(self.label_editor, True, True, 0)

        return preview_box

    def _get_label_data(self):
        return {
            "lines": [
                self.entry_line1.get_text(),
                self.entry_line2.get_text(),
                self.entry_line3.get_text(),
                self.entry_line4.get_text(),
            ],
            "barcode_enabled": self.barcode_check.get_active(),
            "barcode_type": self.barcode_type_combo.get_active_id(),
            "barcode_data": self.entry_barcode.get_text(),
            "label_size": self.size_combo.get_active_id(),
        }

    def _on_content_changed(self, widget):
        data = self._get_label_data()
        self.label_editor.update_label(data)

    def _on_size_changed(self, combo):
        size_id = combo.get_active_id()
        self.current_label_size = size_id
        data = self._get_label_data()
        self.label_editor.update_label(data)

    def _on_new_label(self, button):
        self.entry_line1.set_text("")
        self.entry_line2.set_text("")
        self.entry_line3.set_text("")
        self.entry_line4.set_text("")
        self.entry_barcode.set_text("")
        self.barcode_check.set_active(False)
        self.label_editor.update_label(self._get_label_data())

    def _on_print(self, button):
        data = self._get_label_data()
        copies = int(self.spin_qty.get_value())
        size_id = data["label_size"]
        label_size = LABEL_SIZES.get(size_id, LABEL_SIZES["small_address"])

        success = self.print_manager.print_label(self, data, label_size, copies)
        if success:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Etiqueta enviada a imprimir",
            )
            dialog.run()
            dialog.destroy()

    def _on_export_pdf(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Exportar etiqueta como PDF",
            parent=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialog.set_current_name("etiqueta.pdf")

        filter_pdf = Gtk.FileFilter()
        filter_pdf.set_name("PDF files")
        filter_pdf.add_mime_type("application/pdf")
        dialog.add_filter(filter_pdf)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
            data = self._get_label_data()
            size_id = data["label_size"]
            label_size = LABEL_SIZES.get(size_id, LABEL_SIZES["small_address"])
            self.print_manager.export_pdf(filename, data, label_size)

            info = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=f"PDF exportado: {filename}",
            )
            info.run()
            info.destroy()

        dialog.destroy()
