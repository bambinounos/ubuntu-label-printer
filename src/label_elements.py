"""Elementos que componen una etiqueta TSPL (texto, barcode, QR, líneas, cajas, círculos).

Referencia HT300: 203 DPI, 1mm = 8 dots.
Todas las coordenadas y dimensiones están en dots.
"""


class LabelElement:
    """Elemento base de una etiqueta."""

    def __init__(self, x=0, y=0):
        self.x = x  # posición en dots (8 dots = 1mm a 203 DPI)
        self.y = y
        self.selected = False

    def to_tspl(self):
        raise NotImplementedError

    def get_bounds(self):
        """Retorna (x, y, width, height) en dots."""
        return (self.x, self.y, 0, 0)


class TextElement(LabelElement):
    """Elemento de texto TSPL.

    Sintaxis: TEXT x,y,"font",rotation,mx,my,"text"
    Fuentes internas:
        "1" = 8x12    "2" = 12x20    "3" = 16x24
        "4" = 24x32   "5" = 32x48
        "TSS24.BF2" = fuente asiática 24x24
    """

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

    def get_bounds(self):
        cw, ch = self.FONTS.get(self.font, (16, 24))
        w = len(self.text) * cw * self.mx
        h = ch * self.my
        return (self.x, self.y, w, h)


class BarcodeElement(LabelElement):
    """Elemento de código de barras TSPL.

    Sintaxis: BARCODE x,y,"code type",height,human readable,rotation,narrow,wide,"code"
    Tipos soportados HT300: 128, 128M, 39, 39C, 93, EAN13, EAN8, UPCA, UPCE
    human readable: 0=no, 1=sí
    rotation: 0, 90, 180, 270
    narrow/wide: ancho en dots del elemento angosto/ancho
    """

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

    def to_tspl(self):
        if not self.data:
            return ""
        rot = {0: 0, 90: 90, 180: 180, 270: 270}.get(self.rotation, 0)
        return (f'BARCODE {self.x},{self.y},"{self.barcode_type}",'
                f'{self.height},{self.human_readable},{rot},'
                f'{self.narrow},{self.wide},"{self.data}"')

    def get_bounds(self):
        w = len(self.data) * (self.narrow + self.wide) * 4
        h = self.height + (20 if self.human_readable else 0)
        return (self.x, self.y, w, h)


class QRElement(LabelElement):
    """Elemento de código QR TSPL.

    Sintaxis: QRCODE x,y,ECC Level,cell width,mode,rotation,"Data string"
    ECC: L(7%), M(15%), Q(25%), H(30%)
    cell width: 1, 3, 5, 7, 10, 12
    mode: A=auto, M=manual
    rotation: 0, 90, 180, 270
    """

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

    def get_bounds(self):
        # QR v1 = 21 módulos, cada módulo = cell_size dots
        size = 21 * self.cell_size + 2 * self.cell_size
        return (self.x, self.y, size, size)


class LineElement(LabelElement):
    """Línea/barra TSPL (BAR command).

    Sintaxis: BAR x,y,width,height  (todo en dots)
    """

    def __init__(self, x=0, y=0, width=200, height=2):
        super().__init__(x, y)
        self.width = width
        self.height = height

    def to_tspl(self):
        return f"BAR {self.x},{self.y},{self.width},{self.height}"

    def get_bounds(self):
        return (self.x, self.y, self.width, self.height)


class BoxElement(LabelElement):
    """Caja/rectángulo TSPL (BOX command).

    Sintaxis: BOX x_start,y_start,x_end,y_end,line thickness  (todo en dots)
    Grosor máximo recomendado: 12 dots.
    """

    def __init__(self, x=0, y=0, x2=100, y2=100, thickness=2):
        super().__init__(x, y)
        self.x2 = x2
        self.y2 = y2
        self.thickness = thickness

    def to_tspl(self):
        return f"BOX {self.x},{self.y},{self.x2},{self.y2},{self.thickness}"

    def get_bounds(self):
        return (self.x, self.y, self.x2 - self.x, self.y2 - self.y)


class CircleElement(LabelElement):
    """Círculo TSPL (CIRCLE command).

    Sintaxis: CIRCLE x_start,y_start,diameter,thickness  (todo en dots)
    """

    def __init__(self, x=0, y=0, diameter=100, thickness=5):
        super().__init__(x, y)
        self.diameter = diameter
        self.thickness = thickness

    def to_tspl(self):
        return f"CIRCLE {self.x},{self.y},{self.diameter},{self.thickness}"

    def get_bounds(self):
        return (self.x, self.y, self.diameter, self.diameter)
