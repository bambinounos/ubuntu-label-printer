"""Generador de comandos ZPL (Zebra Programming Language).

Paralelo a tspl_generator.py. No modifica ningún código TSPL existente.
Compatible con impresoras Zebra y otras que soporten ZPL II.
203 DPI: 1mm = 8 dots (mismo que TSPL).
"""

DOTS_PER_MM = 8


class ZPLGenerator:
    """Genera código ZPL completo a partir de configuración y elementos."""

    def __init__(self, width_mm=60, height_mm=40, darkness=15):
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.darkness = darkness  # 0-30, default 15

    def generate(self, elements, copies=1):
        """Genera el código ZPL completo."""
        lines = []

        width_dots = self.width_mm * DOTS_PER_MM
        height_dots = self.height_mm * DOTS_PER_MM

        # Inicio de formato
        lines.append("^XA")

        # Configuración
        lines.append(f"^PW{width_dots}")
        lines.append(f"^LL{height_dots}")
        lines.append(f"~SD{self.darkness}")
        lines.append("^CI28")  # UTF-8 character set

        # Elementos
        for element in elements:
            zpl = element.to_zpl()
            if zpl:
                lines.append(zpl)

        # Imprimir y cerrar
        lines.append(f"^PQ{copies}")
        lines.append("^XZ")

        return "\n".join(lines)

    def parse_zpl(self, zpl_code):
        """Parsea código ZPL y extrae configuración y elementos."""
        from src.label_elements import (
            TextElement, BarcodeElement, QRElement,
            LineElement, BoxElement, CircleElement
        )

        elements = []
        config = {
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "copies": 1,
            "darkness": self.darkness,
        }

        # ZPL usa ^ como delimitador de comandos
        # Normalizar: separar por ^ y procesar cada comando
        code = zpl_code.replace("\n", "")
        commands = code.split("^")

        # Estado actual de posición (^FO afecta al siguiente campo)
        fo_x, fo_y = 0, 0
        # Estado de barcode module width
        by_w, by_r = 2, 3.0

        i = 0
        while i < len(commands):
            cmd = commands[i].strip()
            if not cmd:
                i += 1
                continue

            # También separar por ~ para comandos como ~SD
            if cmd.startswith("~"):
                cmd = cmd[1:]
                if cmd.startswith("SD"):
                    try:
                        config["darkness"] = int(cmd[2:].strip())
                    except ValueError:
                        pass
                i += 1
                continue

            upper = cmd.upper()

            if upper.startswith("PW"):
                try:
                    dots = int(cmd[2:].strip())
                    config["width_mm"] = dots // DOTS_PER_MM
                except ValueError:
                    pass

            elif upper.startswith("LL"):
                try:
                    dots = int(cmd[2:].strip())
                    config["height_mm"] = dots // DOTS_PER_MM
                except ValueError:
                    pass

            elif upper.startswith("PQ"):
                try:
                    parts = cmd[2:].strip().split(",")
                    config["copies"] = int(parts[0])
                except (ValueError, IndexError):
                    pass

            elif upper.startswith("FO"):
                # Field Origin: ^FOx,y
                try:
                    parts = cmd[2:].strip().split(",")
                    fo_x = int(parts[0])
                    fo_y = int(parts[1]) if len(parts) > 1 else 0
                except (ValueError, IndexError):
                    pass

            elif upper.startswith("BY"):
                # Barcode defaults: ^BYw,r
                try:
                    parts = cmd[2:].strip().split(",")
                    by_w = int(parts[0])
                    if len(parts) > 1:
                        by_r = float(parts[1])
                except (ValueError, IndexError):
                    pass

            elif upper.startswith("A0"):
                # Font + field data follows
                # ^A0N,h,w  then ^FDtext^FS
                elem = self._parse_text_field(cmd, commands, i, fo_x, fo_y)
                if elem:
                    elements.append(elem)

            elif upper.startswith("BC") or upper.startswith("B3") or \
                 upper.startswith("BE") or upper.startswith("B8") or \
                 upper.startswith("BU") or upper.startswith("B9"):
                elem = self._parse_barcode_field(cmd, commands, i, fo_x, fo_y, by_w)
                if elem:
                    elements.append(elem)

            elif upper.startswith("BQ"):
                elem = self._parse_qr_field(cmd, commands, i, fo_x, fo_y)
                if elem:
                    elements.append(elem)

            elif upper.startswith("GB"):
                elem = self._parse_graphic_box(cmd, fo_x, fo_y)
                if elem:
                    elements.append(elem)

            elif upper.startswith("GC"):
                elem = self._parse_graphic_circle(cmd, fo_x, fo_y)
                if elem:
                    elements.append(elem)

            i += 1

        return config, elements

    def _find_field_data(self, commands, start_idx):
        """Busca ^FD...^FS después de la posición actual."""
        for j in range(start_idx + 1, min(start_idx + 5, len(commands))):
            cmd = commands[j].strip()
            if cmd.upper().startswith("FD"):
                data = cmd[2:]
                # Remover ^FS al final si está concatenado
                if "^" in data:
                    data = data.split("^")[0]
                return data
        return ""

    def _parse_text_field(self, cmd, commands, idx, fo_x, fo_y):
        """Parsea ^A0N,h,w seguido de ^FDtext^FS"""
        from src.label_elements import TextElement
        try:
            # ^A0N,h,w or ^A0R,h,w etc.
            params = cmd[2:].strip()
            rotation_char = params[0] if params else 'N'
            rotation_map = {'N': 0, 'R': 90, 'I': 180, 'B': 270}
            rotation = rotation_map.get(rotation_char, 0)

            parts = params[1:].lstrip(",").split(",") if len(params) > 1 else []
            font_h = int(parts[0]) if parts else 24
            font_w = int(parts[1]) if len(parts) > 1 else font_h

            # Mapear altura ZPL a fuente TSPL más cercana
            font_map = {12: "1", 20: "2", 24: "3", 32: "4", 48: "5"}
            font = font_map.get(font_h, "3")
            if font_h == 24 and font_w == 24:
                font = "TSS24.BF2"

            text = self._find_field_data(commands, idx)
            if text:
                return TextElement(
                    x=fo_x, y=fo_y, text=text,
                    font=font, rotation=rotation,
                    mx=1, my=1
                )
        except (ValueError, IndexError):
            pass
        return None

    def _parse_barcode_field(self, cmd, commands, idx, fo_x, fo_y, module_width):
        """Parsea ^BCN,h,Y,N,N o ^B3N,... seguido de ^FDdata^FS"""
        from src.label_elements import BarcodeElement
        try:
            upper = cmd.upper()
            if upper.startswith("BC"):
                barcode_type = "128"
                params = cmd[2:]
            elif upper.startswith("B3"):
                barcode_type = "39"
                params = cmd[2:]
            elif upper.startswith("BE"):
                barcode_type = "EAN13"
                params = cmd[2:]
            elif upper.startswith("B8"):
                barcode_type = "EAN8"
                params = cmd[2:]
            elif upper.startswith("BU"):
                barcode_type = "UPCA"
                params = cmd[2:]
            elif upper.startswith("B9"):
                barcode_type = "UPCE"
                params = cmd[2:]
            else:
                return None

            rotation_char = params[0] if params else 'N'
            parts = params[1:].lstrip(",").split(",") if len(params) > 1 else []

            height = int(parts[0]) if parts and parts[0] else 100
            human_readable = 1 if len(parts) > 1 and parts[1].upper() == 'Y' else 0

            data = self._find_field_data(commands, idx)
            if data:
                return BarcodeElement(
                    x=fo_x, y=fo_y, data=data,
                    barcode_type=barcode_type,
                    height=height,
                    human_readable=human_readable,
                    narrow=module_width, wide=module_width,
                )
        except (ValueError, IndexError):
            pass
        return None

    def _parse_qr_field(self, cmd, commands, idx, fo_x, fo_y):
        """Parsea ^BQN,2,cell seguido de ^FDMA,data^FS"""
        from src.label_elements import QRElement
        try:
            params = cmd[2:].strip()
            parts = params.split(",")

            cell_size = 5
            if len(parts) >= 3:
                try:
                    cell_size = int(parts[2])
                except ValueError:
                    pass

            data = self._find_field_data(commands, idx)
            # ZPL QR data starts with "MA," or "QA," etc.
            if data and "," in data:
                data = data.split(",", 1)[1]

            if data:
                return QRElement(
                    x=fo_x, y=fo_y, data=data,
                    ecc="M", cell_size=cell_size,
                    mode="A",
                )
        except (ValueError, IndexError):
            pass
        return None

    def _parse_graphic_box(self, cmd, fo_x, fo_y):
        """Parsea ^GBw,h,t,c,r"""
        from src.label_elements import LineElement, BoxElement
        try:
            parts = cmd[2:].strip().split(",")
            w = int(parts[0]) if parts else 100
            h = int(parts[1]) if len(parts) > 1 else 100
            t = int(parts[2]) if len(parts) > 2 else 1

            # Si grosor = alto o ancho, es una barra sólida
            if t >= h or t >= w:
                return LineElement(x=fo_x, y=fo_y, width=w, height=h)
            else:
                return BoxElement(
                    x=fo_x, y=fo_y,
                    x2=fo_x + w, y2=fo_y + h,
                    thickness=t
                )
        except (ValueError, IndexError):
            pass
        return None

    def _parse_graphic_circle(self, cmd, fo_x, fo_y):
        """Parsea ^GCd,t,c"""
        from src.label_elements import CircleElement
        try:
            parts = cmd[2:].strip().split(",")
            diameter = int(parts[0]) if parts else 100
            thickness = int(parts[1]) if len(parts) > 1 else 1
            return CircleElement(x=fo_x, y=fo_y, diameter=diameter, thickness=thickness)
        except (ValueError, IndexError):
            pass
        return None
