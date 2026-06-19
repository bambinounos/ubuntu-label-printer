"""Render REAL de códigos de barras y QR para la vista previa (WYSIWYG).

Devuelve geometría pura (matrices / corridas de barras) en *unidades de módulo*,
sin dependencias de GTK/Cairo y sin archivos temporales, para que el canvas la
dibuje directamente. Si las librerías opcionales no están instaladas, expone
RENDER_AVAILABLE=False y las funciones retornan None → el canvas usa su render
aproximado de respaldo.

Librerías: `qrcode` (QR) y `python-barcode` (1D). Ambas puro-Python.
"""

try:
    import qrcode
    import barcode  # noqa: F401  (se importa por nombre dentro de las funciones)
    RENDER_AVAILABLE = True
except ImportError:
    RENDER_AVAILABLE = False


# ── QR ──

def qr_matrix(data, ecc="M", border=0):
    """Retorna la matriz booleana del QR real (incluye `border` módulos de quiet
    zone). Retorna None si la librería falta o el encoding falla.
    """
    if not RENDER_AVAILABLE or not data:
        return None
    try:
        ecc_map = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }
        qr = qrcode.QRCode(
            error_correction=ecc_map.get(ecc, qrcode.constants.ERROR_CORRECT_M),
            border=border,
            box_size=1,
        )
        qr.add_data(data)
        qr.make(fit=True)
        return qr.get_matrix()
    except Exception:
        return None


# ── Códigos de barras 1D ──

# Mapeo de tipo TSPL → clase de python-barcode.
# (Code93 "93" no existe en python-barcode → None → respaldo en preview.)
_TYPE_MAP = {
    "128": "code128", "128M": "code128",
    "39": "code39", "39C": "code39",
    "EAN13": "ean13", "EAN8": "ean8",
    "UPCA": "upca", "UPCE": "upce",
}


def barcode_runs(data, tspl_type):
    """Retorna (runs, total_modules) del código de barras real.

    `runs` es una lista de (inicio_en_modulos, ancho_en_modulos) SOLO de las
    barras negras. `total_modules` es el ancho total en módulos.
    Retorna None si el tipo no se soporta, falta la librería, o el dato es
    inválido para ese simbología (longitud/checksum incorrectos).
    """
    if not RENDER_AVAILABLE or not data:
        return None
    name = _TYPE_MAP.get(tspl_type)
    if not name:
        return None
    try:
        import barcode as _bc
        cls = _bc.get_barcode_class(name)
        if name == "code39":
            obj = cls(data, add_checksum=(tspl_type == "39C"))
        else:
            obj = cls(data)
        modules = obj.build()[0]  # string de '0'/'1', cada char = 1 módulo
    except Exception:
        return None

    runs = []
    i = 0
    n = len(modules)
    while i < n:
        if modules[i] == "1":
            start = i
            while i < n and modules[i] == "1":
                i += 1
            runs.append((start, i - start))
        else:
            i += 1
    return runs, n


def barcode_fullcode(data, tspl_type):
    """Retorna el código legible completo (con dígito verificador si aplica),
    o None si no se puede calcular."""
    if not RENDER_AVAILABLE or not data:
        return None
    name = _TYPE_MAP.get(tspl_type)
    if not name:
        return None
    try:
        import barcode as _bc
        cls = _bc.get_barcode_class(name)
        if name == "code39":
            obj = cls(data, add_checksum=(tspl_type == "39C"))
        else:
            obj = cls(data)
        return obj.get_fullcode()
    except Exception:
        return None
