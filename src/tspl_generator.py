"""Generador de comandos TSPL a partir de elementos de etiqueta.

Compatible con HT300 (HPRT) - Manual Rev.1.2
203 DPI: 1mm = 8 dots
"""


class TSPLGenerator:
    """Genera código TSPL completo a partir de configuración y elementos."""

    def __init__(self, width_mm=60, height_mm=40, gap_mm=2, direction=1):
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.gap_mm = gap_mm
        self.direction = direction
        self.speed = None       # None = usar default de impresora
        self.density = None     # None = usar default (8)

    def generate(self, elements, copies=1):
        """Genera el código TSPL completo."""
        lines = []

        # Configuración de etiqueta
        lines.append(f"SIZE {self.width_mm} mm,{self.height_mm} mm")
        lines.append(f"GAP {self.gap_mm} mm,0 mm")
        lines.append(f"DIRECTION {self.direction},0")
        lines.append("REFERENCE 0,0")
        lines.append("OFFSET 0 mm")
        lines.append("SET PEEL OFF")
        lines.append("SET TEAR ON")

        if self.speed is not None:
            lines.append(f"SPEED {self.speed}")
        if self.density is not None:
            lines.append(f"DENSITY {self.density}")

        lines.append("CLS")

        # Elementos
        for element in elements:
            tspl = element.to_tspl()
            if tspl:
                lines.append(tspl)

        # Imprimir
        lines.append(f"PRINT {copies}")

        return "\n".join(lines)

    def parse_tspl(self, tspl_code):
        """Parsea código TSPL y extrae configuración y elementos."""
        from src.label_elements import (
            TextElement, BarcodeElement, QRElement,
            LineElement, BoxElement, CircleElement
        )

        elements = []
        config = {
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "gap_mm": self.gap_mm,
            "copies": 1,
            "speed": None,
            "density": None,
        }

        for line in tspl_code.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            upper = line.upper()

            if upper.startswith("SIZE"):
                parts = line[4:].strip()
                # Soportar "SIZE 60 mm,40 mm" y "SIZE 60MM,40MM"
                parts = parts.upper().replace("MM", "").replace("DOT", "")
                vals = parts.split(",")
                if len(vals) >= 2:
                    try:
                        config["width_mm"] = int(float(vals[0].strip()))
                        config["height_mm"] = int(float(vals[1].strip()))
                    except ValueError:
                        pass

            elif upper.startswith("GAP"):
                parts = line[3:].strip().upper().replace("MM", "")
                vals = parts.split(",")
                if vals:
                    try:
                        config["gap_mm"] = int(float(vals[0].strip()))
                    except ValueError:
                        pass

            elif upper.startswith("SPEED"):
                parts = line[5:].strip()
                try:
                    config["speed"] = int(parts)
                except ValueError:
                    pass

            elif upper.startswith("DENSITY"):
                parts = line[7:].strip()
                try:
                    config["density"] = int(parts)
                except ValueError:
                    pass

            elif upper.startswith("PRINT"):
                parts = line[5:].strip().split(",")
                if parts:
                    try:
                        config["copies"] = int(parts[0].strip())
                    except ValueError:
                        pass

            elif upper.startswith("TEXT "):
                elem = self._parse_text(line[5:])
                if elem:
                    elements.append(elem)

            elif upper.startswith("BARCODE "):
                elem = self._parse_barcode(line[8:])
                if elem:
                    elements.append(elem)

            elif upper.startswith("QRCODE "):
                elem = self._parse_qrcode(line[7:])
                if elem:
                    elements.append(elem)

            elif upper.startswith("BAR "):
                elem = self._parse_bar(line[4:])
                if elem:
                    elements.append(elem)

            elif upper.startswith("BOX "):
                elem = self._parse_box(line[4:])
                if elem:
                    elements.append(elem)

            elif upper.startswith("CIRCLE "):
                elem = self._parse_circle(line[7:])
                if elem:
                    elements.append(elem)

        return config, elements

    def _split_params(self, params):
        """Divide parámetros respetando comillas. Preserva campos vacíos."""
        parts = []
        current = ""
        in_quotes = False
        for ch in params:
            if ch == '"':
                in_quotes = not in_quotes
                if not in_quotes:
                    parts.append(current)
                    current = ""
                continue
            if ch == ',' and not in_quotes:
                parts.append(current.strip())
                current = ""
                continue
            current += ch
        if current.strip():
            parts.append(current.strip())
        return parts

    def _parse_text(self, params):
        """Parsea: x,y,"font",rotation,mx,my,"text" """
        from src.label_elements import TextElement
        try:
            parts = self._split_params(params)
            if len(parts) >= 7:
                return TextElement(
                    x=int(parts[0]), y=int(parts[1]),
                    font=parts[2], rotation=int(parts[3]),
                    mx=int(parts[4]), my=int(parts[5]),
                    text=parts[6]
                )
        except (ValueError, IndexError):
            pass
        return None

    def _parse_barcode(self, params):
        """Parsea: x,y,"type",height,readable,rotation,narrow,wide,"data" """
        from src.label_elements import BarcodeElement
        try:
            parts = self._split_params(params)
            if len(parts) >= 9:
                return BarcodeElement(
                    x=int(parts[0]), y=int(parts[1]),
                    barcode_type=parts[2], height=int(parts[3]),
                    human_readable=int(parts[4]), rotation=int(parts[5]),
                    narrow=int(parts[6]), wide=int(parts[7]),
                    data=parts[8]
                )
        except (ValueError, IndexError):
            pass
        return None

    def _parse_qrcode(self, params):
        """Parsea: x,y,ECC,cell,mode,rotation,"data" """
        from src.label_elements import QRElement
        try:
            parts = self._split_params(params)
            if len(parts) >= 7:
                return QRElement(
                    x=int(parts[0]), y=int(parts[1]),
                    ecc=parts[2], cell_size=int(parts[3]),
                    mode=parts[4], rotation=int(parts[5]),
                    data=parts[6]
                )
        except (ValueError, IndexError):
            pass
        return None

    def _parse_bar(self, params):
        """Parsea: x,y,width,height"""
        from src.label_elements import LineElement
        try:
            parts = [p.strip() for p in params.split(",")]
            if len(parts) >= 4:
                return LineElement(
                    x=int(parts[0]), y=int(parts[1]),
                    width=int(parts[2]), height=int(parts[3])
                )
        except (ValueError, IndexError):
            pass
        return None

    def _parse_box(self, params):
        """Parsea: x1,y1,x2,y2,thickness[,radius]"""
        from src.label_elements import BoxElement
        try:
            parts = [p.strip() for p in params.split(",")]
            if len(parts) >= 5:
                return BoxElement(
                    x=int(parts[0]), y=int(parts[1]),
                    x2=int(parts[2]), y2=int(parts[3]),
                    thickness=int(parts[4])
                )
        except (ValueError, IndexError):
            pass
        return None

    def _parse_circle(self, params):
        """Parsea: x,y,diameter,thickness"""
        from src.label_elements import CircleElement
        try:
            parts = [p.strip() for p in params.split(",")]
            if len(parts) >= 4:
                return CircleElement(
                    x=int(parts[0]), y=int(parts[1]),
                    diameter=int(parts[2]), thickness=int(parts[3])
                )
        except (ValueError, IndexError):
            pass
        return None
