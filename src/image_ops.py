"""Conversión de imágenes a bitmap monocromo 1-bit para impresión térmica.

Produce, en una sola pasada:
  - bytes empaquetados para TSPL `BITMAP` (modo 0: bit 0 = punto negro)
  - hex para ZPL `^GFA` (polaridad opuesta: bit 1 = punto negro)
  - superficie A8 (alpha) para la vista previa en Cairo

Requiere Pillow (ya presente en el sistema). El ancho se alinea a byte como
exige el comando BITMAP.
"""

import base64
import io

from PIL import Image

MAX_DIM = 1200  # dots: límite de seguridad para no generar payloads enormes


def _load_source(elem):
    """Abre la imagen original (desde data_b64 o path). None si no hay fuente."""
    if getattr(elem, "data_b64", None):
        raw = base64.b64decode(elem.data_b64)
        return Image.open(io.BytesIO(raw))
    if getattr(elem, "path", None):
        return Image.open(elem.path)
    return None


def _mono_image(elem):
    """Retorna (imagen PIL modo '1', w, h) al tamaño en dots (src * scale)."""
    img = _load_source(elem)
    if img is None:
        return None
    img = img.convert("L")
    w = max(1, min(MAX_DIM, int(elem.src_w * elem.scale)))
    h = max(1, min(MAX_DIM, int(elem.src_h * elem.scale)))
    img = img.resize((w, h))
    if elem.dither:
        bw = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    else:
        bw = img.point(lambda p: 255 if p >= elem.threshold else 0).convert("1")
    return bw, w, h


def render_mono(elem):
    """Convierte la imagen del elemento a sus tres representaciones.

    Retorna un dict con: w, h, width_bytes, total, tspl (bytes), zpl_hex (str),
    a8 (bytearray para Cairo FORMAT_A8) y stride. None si no hay imagen.
    """
    res = _mono_image(elem)
    if res is None:
        return None
    bw, w, h = res
    px = bw.load()

    import cairo
    width_bytes = (w + 7) // 8
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_A8, w)

    tspl = bytearray(width_bytes * h)  # BITMAP modo 0: bit 1 = blanco (no imprime)
    zpl = bytearray(width_bytes * h)   # ^GFA: bit 1 = negro (imprime)
    a8 = bytearray(stride * h)         # alpha: 255 donde se imprime negro

    invert = bool(elem.invert)
    for yy in range(h):
        tbase = yy * width_bytes
        abase = yy * stride
        for xx in range(w):
            black = (px[xx, yy] == 0)
            if invert:
                black = not black
            mask = 0x80 >> (xx & 7)
            if black:
                zpl[tbase + xx // 8] |= mask
                a8[abase + xx] = 255
            else:
                tspl[tbase + xx // 8] |= mask

    return {
        "w": w, "h": h,
        "width_bytes": width_bytes,
        "total": width_bytes * h,
        "tspl": bytes(tspl),
        "zpl_hex": zpl.hex().upper(),
        "a8": a8,
        "stride": stride,
    }


def encode_file_b64(path):
    """Lee un archivo de imagen y retorna (base64_str, src_w, src_h)."""
    with open(path, "rb") as f:
        raw = f.read()
    img = Image.open(io.BytesIO(raw))
    w, h = img.size
    return base64.b64encode(raw).decode("ascii"), w, h
