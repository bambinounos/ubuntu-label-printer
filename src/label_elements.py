"""Elementos que componen una etiqueta (texto, barcode, QR, líneas, cajas, círculos).

Soporta generación TSPL y ZPL desde los mismos elementos.
Referencia: 203 DPI, 1mm = 8 dots.
Todas las coordenadas y dimensiones están en dots.
"""

# Mapeo de rotación para ZPL: grados -> caracter ZPL
_ZPL_ROT = {0: "N", 90: "R", 180: "I", 270: "B"}


class LabelElement:
    """Elemento base de una etiqueta."""

    TYPE = "base"  # discriminador para serialización JSON

    def __init__(self, x=0, y=0):
        self.x = x  # posición en dots (8 dots = 1mm a 203 DPI)
        self.y = y
        self.selected = False

    def to_tspl(self):
        raise NotImplementedError

    def to_tspl_bytes(self):
        """Bytes del comando TSPL para el payload de impresión.

        Por defecto codifica el texto de to_tspl(). ImageElement lo sobrescribe
        para emitir datos binarios (BITMAP).
        """
        s = self.to_tspl()
        return s.encode("utf-8", errors="replace") if s else b""

    def to_zpl(self):
        raise NotImplementedError

    def get_bounds(self):
        """Retorna (x, y, width, height) en dots."""
        return (self.x, self.y, 0, 0)

    # ── Serialización JSON (formato canónico .label) ──

    def _fields(self):
        """Retorna exactamente los kwargs del constructor (sin 'type')."""
        raise NotImplementedError

    def to_dict(self):
        """Serializa el elemento a un dict con discriminador 'type'."""
        return {"type": self.TYPE, **self._fields()}


class TextElement(LabelElement):
    """Elemento de texto TSPL.

    Sintaxis: TEXT x,y,"font",rotation,mx,my,"text"
    Fuentes internas:
        "1" = 8x12    "2" = 12x20    "3" = 16x24
        "4" = 24x32   "5" = 32x48
        "TSS24.BF2" = fuente asiática 24x24
    """

    TYPE = "text"

    FONTS = {
        "1": (8, 12),
        "2": (12, 20),
        "3": (16, 24),
        "4": (24, 32),
        "5": (32, 48),
        "TSS24.BF2": (24, 24),
    }

    def __init__(self, x=0, y=0, text="", font="3", rotation=0, mx=1, my=1):
        super().__init__(x, y)
        self.text = text
        self.font = font
        self.rotation = rotation  # 0, 90, 180, 270
        self.mx = mx  # multiplicador horizontal
        self.my = my  # multiplicador vertical

    def to_tspl(self):
        if not self.text:
            return ""
        rot = {0: 0, 90: 90, 180: 180, 270: 270}.get(self.rotation, 0)
        return f'TEXT {self.x},{self.y},"{self.font}",{rot},{self.mx},{self.my},"{self.text}"'

    def to_zpl(self):
        if not self.text:
            return ""
        cw, ch = self.FONTS.get(self.font, (16, 24))
        font_h = ch * self.my
        font_w = cw * self.mx
        rot = _ZPL_ROT.get(self.rotation, "N")
        return f"^FO{self.x},{self.y}^A0{rot},{font_h},{font_w}^FD{self.text}^FS"

    def get_bounds(self):
        cw, ch = self.FONTS.get(self.font, (16, 24))
        w = len(self.text) * cw * self.mx
        h = ch * self.my
        return (self.x, self.y, w, h)

    def _fields(self):
        return {"x": self.x, "y": self.y, "text": self.text, "font": self.font,
                "rotation": self.rotation, "mx": self.mx, "my": self.my}


class BarcodeElement(LabelElement):
    """Elemento de código de barras TSPL.

    Sintaxis: BARCODE x,y,"code type",height,human readable,rotation,narrow,wide,"code"
    Tipos soportados HT300: 128, 128M, 39, 39C, 93, EAN13, EAN8, UPCA, UPCE
    human readable: 0=no, 1=sí
    rotation: 0, 90, 180, 270
    narrow/wide: ancho en dots del elemento angosto/ancho
    """

    TYPE = "barcode"

    TYPES = ["128", "128M", "39", "39C", "93", "EAN13", "EAN8", "UPCA", "UPCE"]

    def __init__(self, x=0, y=0, data="", barcode_type="128", height=100,
                 human_readable=1, rotation=0, narrow=2, wide=2):
        super().__init__(x, y)
        self.data = data
        self.barcode_type = barcode_type
        self.height = height
        self.human_readable = human_readable
        self.rotation = rotation
        self.narrow = narrow
        self.wide = wide

    # Mapeo de tipo TSPL a comando ZPL
    _ZPL_TYPE_MAP = {
        "128": "BC", "128M": "BC", "39": "B3", "39C": "B3",
        "93": "BA", "EAN13": "BE", "EAN8": "B8", "UPCA": "BU", "UPCE": "B9",
    }

    def to_tspl(self):
        if not self.data:
            return ""
        rot = {0: 0, 90: 90, 180: 180, 270: 270}.get(self.rotation, 0)
        return (f'BARCODE {self.x},{self.y},"{self.barcode_type}",'
                f'{self.height},{self.human_readable},{rot},'
                f'{self.narrow},{self.wide},"{self.data}"')

    def to_zpl(self):
        if not self.data:
            return ""
        zpl_type = self._ZPL_TYPE_MAP.get(self.barcode_type, "BC")
        rot = _ZPL_ROT.get(self.rotation, "N")
        hr = "Y" if self.human_readable else "N"
        lines = []
        if self.narrow != 2:
            lines.append(f"^BY{self.narrow}")
        lines.append(f"^FO{self.x},{self.y}^{zpl_type}{rot},{self.height},{hr},N,N^FD{self.data}^FS")
        return "\n".join(lines)

    def barcode_geometry(self):
        """(runs, total_modules) del código de barras real (cacheado).

        `runs`: lista de (inicio_modulo, ancho_modulos) de barras negras.
        Retorna None si el tipo no se soporta, falta la librería o el dato es
        inválido para esa simbología.
        """
        key = (self.data, self.barcode_type)
        if getattr(self, "_bc_key", None) != key:
            from src.render_codes import barcode_runs
            self._bc_cache = barcode_runs(self.data, self.barcode_type)
            self._bc_key = key
        return self._bc_cache

    def get_bounds(self):
        geom = self.barcode_geometry()
        if geom:
            _runs, total_modules = geom
            w = total_modules * max(1, self.narrow)
        else:
            w = len(self.data) * (self.narrow + self.wide) * 4
        h = self.height + (20 if self.human_readable else 0)
        return (self.x, self.y, w, h)

    def _fields(self):
        return {"x": self.x, "y": self.y, "data": self.data,
                "barcode_type": self.barcode_type, "height": self.height,
                "human_readable": self.human_readable, "rotation": self.rotation,
                "narrow": self.narrow, "wide": self.wide}


class QRElement(LabelElement):
    """Elemento de código QR TSPL.

    Sintaxis: QRCODE x,y,ECC Level,cell width,mode,rotation,"Data string"
    ECC: L(7%), M(15%), Q(25%), H(30%)
    cell width: 1, 3, 5, 7, 10, 12
    mode: A=auto, M=manual
    rotation: 0, 90, 180, 270
    """

    TYPE = "qr"

    CELL_SIZES = [1, 3, 5, 7, 10, 12]

    def __init__(self, x=0, y=0, data="", ecc="M", cell_size=5, mode="A", rotation=0):
        super().__init__(x, y)
        self.data = data
        self.ecc = ecc
        self.cell_size = cell_size
        self.mode = mode
        self.rotation = rotation

    def to_tspl(self):
        if not self.data:
            return ""
        rot = {0: 0, 90: 90, 180: 180, 270: 270}.get(self.rotation, 0)
        return f'QRCODE {self.x},{self.y},{self.ecc},{self.cell_size},{self.mode},{rot},"{self.data}"'

    def to_zpl(self):
        if not self.data:
            return ""
        return f"^FO{self.x},{self.y}^BQN,2,{self.cell_size}^FDMA,{self.data}^FS"

    def qr_matrix(self):
        """Matriz booleana del QR real (cacheada por data+ecc).

        Retorna None si la librería `qrcode` no está disponible.
        """
        key = (self.data, self.ecc)
        if getattr(self, "_qr_key", None) != key:
            from src.render_codes import qr_matrix
            self._qr_cache = qr_matrix(self.data, self.ecc, border=0)
            self._qr_key = key
        return self._qr_cache

    def module_count(self):
        """Número de módulos por lado del QR real (21 si no hay librería)."""
        matrix = self.qr_matrix()
        return len(matrix) if matrix else 21

    def get_bounds(self):
        modules = self.module_count()
        size = modules * self.cell_size
        return (self.x, self.y, size, size)

    def _fields(self):
        return {"x": self.x, "y": self.y, "data": self.data, "ecc": self.ecc,
                "cell_size": self.cell_size, "mode": self.mode,
                "rotation": self.rotation}


class LineElement(LabelElement):
    """Línea/barra TSPL (BAR command).

    Sintaxis: BAR x,y,width,height  (todo en dots)
    """

    TYPE = "line"

    def __init__(self, x=0, y=0, width=200, height=2):
        super().__init__(x, y)
        self.width = width
        self.height = height

    def to_tspl(self):
        return f"BAR {self.x},{self.y},{self.width},{self.height}"

    def to_zpl(self):
        return f"^FO{self.x},{self.y}^GB{self.width},{self.height},{self.height}^FS"

    def get_bounds(self):
        return (self.x, self.y, self.width, self.height)

    def _fields(self):
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


class BoxElement(LabelElement):
    """Caja/rectángulo TSPL (BOX command).

    Sintaxis: BOX x_start,y_start,x_end,y_end,line thickness  (todo en dots)
    Grosor máximo recomendado: 12 dots.
    """

    TYPE = "box"

    def __init__(self, x=0, y=0, x2=100, y2=100, thickness=2):
        super().__init__(x, y)
        self.x2 = x2
        self.y2 = y2
        self.thickness = thickness

    def to_tspl(self):
        return f"BOX {self.x},{self.y},{self.x2},{self.y2},{self.thickness}"

    def to_zpl(self):
        w = self.x2 - self.x
        h = self.y2 - self.y
        return f"^FO{self.x},{self.y}^GB{w},{h},{self.thickness}^FS"

    def get_bounds(self):
        return (self.x, self.y, self.x2 - self.x, self.y2 - self.y)

    def _fields(self):
        return {"x": self.x, "y": self.y, "x2": self.x2, "y2": self.y2,
                "thickness": self.thickness}


class CircleElement(LabelElement):
    """Círculo TSPL (CIRCLE command).

    Sintaxis: CIRCLE x_start,y_start,diameter,thickness  (todo en dots)
    """

    TYPE = "circle"

    def __init__(self, x=0, y=0, diameter=100, thickness=5):
        super().__init__(x, y)
        self.diameter = diameter
        self.thickness = thickness

    def to_tspl(self):
        return f"CIRCLE {self.x},{self.y},{self.diameter},{self.thickness}"

    def to_zpl(self):
        return f"^FO{self.x},{self.y}^GC{self.diameter},{self.thickness},B^FS"

    def get_bounds(self):
        return (self.x, self.y, self.diameter, self.diameter)

    def _fields(self):
        return {"x": self.x, "y": self.y, "diameter": self.diameter,
                "thickness": self.thickness}


class ImageElement(LabelElement):
    """Imagen/logo monocromo.

    Persiste la imagen ORIGINAL en base64 (data_b64) para poder re-ajustar
    umbral/dither tras reabrir. La conversión a 1-bit se hace en image_ops.
    TSPL: comando BITMAP (binario). ZPL: ^GFA (hex ASCII).
    """

    TYPE = "image"

    def __init__(self, x=0, y=0, path=None, data_b64=None, scale=1.0,
                 threshold=128, dither=True, invert=False, src_w=0, src_h=0):
        super().__init__(x, y)
        self.path = path          # ruta original (si no hay data_b64)
        self.data_b64 = data_b64  # imagen original embebida (autocontenida)
        self.scale = scale
        self.threshold = threshold
        self.dither = dither
        self.invert = invert
        self.src_w = src_w        # px nativos
        self.src_h = src_h

    def mono(self):
        """Render 1-bit cacheado (dict de image_ops.render_mono) o None."""
        key = (self.scale, self.threshold, self.dither, self.invert,
               self.src_w, self.src_h)
        if getattr(self, "_mono_key", None) != key:
            from src.image_ops import render_mono
            try:
                self._mono_cache = render_mono(self)
            except Exception:
                self._mono_cache = None
            self._mono_key = key
        return self._mono_cache

    def to_tspl(self):
        """Representación de DISPLAY (el binario real va por to_tspl_bytes())."""
        m = self.mono()
        if not m:
            return ""
        return f"; BITMAP {self.x},{self.y} {m['w']}x{m['h']}px (imagen embebida)"

    def to_tspl_bytes(self):
        m = self.mono()
        if not m:
            return b""
        header = f"BITMAP {self.x},{self.y},{m['width_bytes']},{m['h']},0,"
        return header.encode("latin-1") + m["tspl"]

    def to_zpl(self):
        m = self.mono()
        if not m:
            return ""
        total = m["total"]
        return (f"^FO{self.x},{self.y}"
                f"^GFA,{total},{total},{m['width_bytes']},{m['zpl_hex']}^FS")

    def get_bounds(self):
        m = self.mono()
        if m:
            return (self.x, self.y, m["w"], m["h"])
        return (self.x, self.y, int(self.src_w * self.scale),
                int(self.src_h * self.scale))

    def _fields(self):
        return {"x": self.x, "y": self.y, "path": self.path,
                "data_b64": self.data_b64, "scale": self.scale,
                "threshold": self.threshold, "dither": self.dither,
                "invert": self.invert, "src_w": self.src_w, "src_h": self.src_h}


# ── Registro de tipos para deserialización JSON ──
ELEMENT_REGISTRY = {
    cls.TYPE: cls for cls in (
        TextElement, BarcodeElement, QRElement,
        LineElement, BoxElement, CircleElement, ImageElement,
    )
}


def element_from_dict(d):
    """Reconstruye un elemento desde un dict serializado.

    Ignora claves desconocidas (forward-compat) y retorna None si el tipo
    no está registrado o los campos no encajan en el constructor.
    """
    if not isinstance(d, dict):
        return None
    cls = ELEMENT_REGISTRY.get(d.get("type"))
    if cls is None:
        return None
    kwargs = {k: v for k, v in d.items() if k != "type"}
    try:
        return cls(**kwargs)
    except TypeError:
        # Tolerar claves extra: filtrar a las soportadas por el constructor.
        import inspect
        params = set(inspect.signature(cls.__init__).parameters) - {"self"}
        filtered = {k: v for k, v in kwargs.items() if k in params}
        try:
            return cls(**filtered)
        except TypeError:
            return None
