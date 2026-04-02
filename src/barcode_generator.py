"""Generación de códigos de barras y QR como superficies Cairo."""

import io

import cairo


def generate_barcode_surface(data, barcode_type, width, height):
    """Genera una superficie Cairo con un código de barras."""
    try:
        import barcode
        from barcode.writer import ImageWriter

        code_class = barcode.get_barcode_class(barcode_type)
        writer = ImageWriter()
        code = code_class(data, writer=writer)

        buffer = io.BytesIO()
        code.write(buffer, options={
            "module_width": 0.3,
            "module_height": 8,
            "quiet_zone": 2,
            "font_size": 8,
            "text_distance": 3,
        })
        buffer.seek(0)

        from PIL import Image
        img = Image.open(buffer)
        img = img.resize((width, height), Image.LANCZOS)
        img = img.convert("RGBA")

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(surface)

        # Convertir PIL Image a Cairo surface
        data_bytes = img.tobytes()
        # PIL RGBA -> Cairo ARGB (pre-multiplied)
        arr = bytearray(len(data_bytes))
        for i in range(0, len(data_bytes), 4):
            r, g, b, a = data_bytes[i], data_bytes[i + 1], data_bytes[i + 2], data_bytes[i + 3]
            arr[i] = b      # Blue
            arr[i + 1] = g  # Green
            arr[i + 2] = r  # Red
            arr[i + 3] = a  # Alpha

        src_surface = cairo.ImageSurface.create_for_data(
            arr, cairo.FORMAT_ARGB32, width, height, width * 4
        )
        ctx.set_source_surface(src_surface, 0, 0)
        ctx.paint()

        return surface

    except Exception:
        return _generate_placeholder_barcode(width, height)


def generate_qr_surface(data, size):
    """Genera una superficie Cairo con un código QR."""
    try:
        import qrcode

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((size, size))
        img = img.convert("RGBA")

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        ctx = cairo.Context(surface)

        data_bytes = img.tobytes()
        arr = bytearray(len(data_bytes))
        for i in range(0, len(data_bytes), 4):
            r, g, b, a = data_bytes[i], data_bytes[i + 1], data_bytes[i + 2], data_bytes[i + 3]
            arr[i] = b
            arr[i + 1] = g
            arr[i + 2] = r
            arr[i + 3] = a

        src_surface = cairo.ImageSurface.create_for_data(
            arr, cairo.FORMAT_ARGB32, size, size, size * 4
        )
        ctx.set_source_surface(src_surface, 0, 0)
        ctx.paint()

        return surface

    except Exception:
        return _generate_placeholder_barcode(size, size)


def _generate_placeholder_barcode(width, height):
    """Genera un placeholder cuando no se puede generar el código."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)

    # Fondo blanco
    ctx.set_source_rgb(1, 1, 1)
    ctx.rectangle(0, 0, width, height)
    ctx.fill()

    # Barras simuladas
    ctx.set_source_rgb(0, 0, 0)
    bar_width = max(1, width // 40)
    x = 5
    import random
    random.seed(42)
    while x < width - 5:
        w = random.choice([bar_width, bar_width * 2, bar_width * 3])
        ctx.rectangle(x, 5, w, height - 15)
        ctx.fill()
        x += w + random.choice([bar_width, bar_width * 2])

    return surface
