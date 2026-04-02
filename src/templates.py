"""Plantillas predefinidas de etiquetas TSPL - basadas en ejemplos reales HT300."""

# Plantillas reales probadas en la HT300 (HPRT)
TEMPLATES = {
    "hellbam_producto": {
        "nombre": "HELLBAM - Producto",
        "descripcion": "Repuesto con código, descripción, precio y barcode",
        "icon": "package-x-generic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            'TEXT 60,0,"4",0,1,1,"WG9719230025"\n'
            'TEXT 60,40,"TSS24.BF2",0,1,1,"IMPORTADORA HELLBAM S.A"\n'
            'TEXT 60,80,"TSS24.BF2",0,1,1,"CANT: 1 U, USD 178.98"\n'
            'TEXT 60,120,"TSS24.BF2",0,1,1,"SINOTRUK CLUTCH BOOSTER"\n'
            'BARCODE 60,150,"39C",100,1,0,2,2,"WG9719230025"\n'
            'PRINT 1'
        ),
    },
    "hellbam_taladro": {
        "nombre": "HELLBAM - Herramienta",
        "descripcion": "Herramienta con item y referencia de contrato",
        "icon": "emblem-system-symbolic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            'TEXT 80,0,"4",0,1,1,"HELLBAM"\n'
            'TEXT 80,40,"TSS24.BF2",0,1,1,"TALADRO DE 1/2 (13MM)"\n'
            'TEXT 80,80,"TSS24.BF2",0,1,1,"QTY: 1 SETS"\n'
            'TEXT 80,120,"TSS24.BF2",0,1,1,"ITEM: 06; SIE-GADMCA-2017-027"\n'
            'BARCODE 80,150,"128M",100,1,0,2,2,"23082017"\n'
            'PRINT 1'
        ),
    },
    "komatsu": {
        "nombre": "Komatsu - Repuesto",
        "descripcion": "Repuesto Komatsu con precio y barcode Code 39",
        "icon": "emblem-system-symbolic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            'TEXT 60,0,"4",0,1,1,"HELLBAM"\n'
            'TEXT 60,40,"TSS24.BF2",0,1,1,"EJE REDUCTOR MANDO FINAL"\n'
            'TEXT 60,80,"TSS24.BF2",0,1,1,"CANT: 1  U, USD 234"\n'
            'TEXT 60,120,"TSS24.BF2",0,1,1,"KOMATSU PC200-7"\n'
            'BARCODE 60,150,"39C",100,1,0,2,2,"22U-27-21110"\n'
            'PRINT 1'
        ),
    },
    "hino": {
        "nombre": "Hino Motors",
        "descripcion": "Repuesto Hino con barcode arriba y texto abajo",
        "icon": "emblem-system-symbolic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            'BARCODE 60,0,"39",100,1,0,2,2,"S4934-51040"\n'
            'TEXT 60,150,"4",0,1,1,"WASHER SPRING"\n'
            'TEXT 60,180,"TSS24.BF2",0,1,1,"MATERIAL Zn-Cu"\n'
            'TEXT 60,210,"TSS24.BF2",0,1,1,"QTY: 20  EA, HJC17"\n'
            'TEXT 60,250,"4",0,1,1,"HINO MOTORS,LTD."\n'
            'PRINT 1'
        ),
    },
    "hyundai": {
        "nombre": "Hyundai Heavy Industries",
        "descripcion": "Repuesto maquinaria pesada Hyundai",
        "icon": "emblem-system-symbolic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            'BARCODE 60,0,"39",100,1,0,3,2,"S255-203006"\n'
            'TEXT 60,180,"3",0,1,1,"HYUNDAI HEAVY INDUSTRIES"\n'
            'TEXT 60,210,"TSS24.BF2",0,1,1,"QTY: 1  EA"\n'
            'TEXT 60,250,"4",0,1,1,"MODEL H940C"\n'
            'PRINT 1'
        ),
    },
    "caterpillar": {
        "nombre": "Caterpillar",
        "descripcion": "Repuesto Caterpillar con código de barras",
        "icon": "emblem-system-symbolic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            'TEXT 60,0,"4",0,1,1,"CATERPILLAR"\n'
            'TEXT 60,40,"TSS24.BF2",0,1,1,"WASHER"\n'
            'TEXT 60,80,"TSS24.BF2",0,1,1,"QTY: 4  EA"\n'
            'TEXT 60,120,"TSS24.BF2",0,1,1,"416-420 SERIES"\n'
            'BARCODE 60,150,"39",100,1,0,2,2,"9R-0158"\n'
            'PRINT 1'
        ),
    },
    "etiqueta_qr": {
        "nombre": "Etiqueta con QR",
        "descripcion": "Texto y código QR lateral",
        "icon": "view-grid-symbolic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'CLS\n'
            'TEXT 30,10,"4",0,1,1,"HELLBAM S.A."\n'
            'TEXT 30,50,"TSS24.BF2",0,1,1,"FILTRO DE ACEITE"\n'
            'TEXT 30,80,"TSS24.BF2",0,1,1,"REF: SH996C"\n'
            'QRCODE 350,10,H,5,A,0,"SH996C-HELLBAM"\n'
            'PRINT 1'
        ),
    },
    "estanteria": {
        "nombre": "Estantería / Bodega",
        "descripcion": "Ubicación de bodega con barcode Code 128M",
        "icon": "folder-symbolic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            'TEXT 30,90,"4",0,1,1,"MSL - C1P06k"\n'
            'BARCODE 30,150,"128M",100,1,0,2,2,"MSL - C1P06k"\n'
            'PRINT 1'
        ),
    },
    "ups_envio": {
        "nombre": "Envío UPS",
        "descripcion": "Etiqueta de envío con destino y barcode",
        "icon": "mail-send-symbolic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            'TEXT 80,0,"4",0,1,1,"UPS SERVICE"\n'
            'TEXT 80,60,"TSS24.BF2",0,1,1,"BRAZIL, Sao Paulo   <19859-901>"\n'
            'TEXT 80,90,"TSS24.BF2",0,1,1,"QTY: 7 SETS"\n'
            'BARCODE 80,150,"128M",100,1,0,2,2,"278262100005"\n'
            'PRINT 1'
        ),
    },
    "envio_grande": {
        "nombre": "Envío Grande",
        "descripcion": "Remitente y destinatario (100x60mm)",
        "icon": "mail-send-symbolic",
        "width_mm": 100,
        "height_mm": 60,
        "tspl": (
            'SIZE 100 mm,60 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'CLS\n'
            'TEXT 20,10,"4",0,1,1,"DE: HELLBAM S.A."\n'
            'TEXT 20,45,"3",0,1,1,"Guayaquil, Ecuador"\n'
            'BAR 20,75,760,2\n'
            'TEXT 20,90,"5",0,1,1,"PARA:"\n'
            'TEXT 20,140,"4",0,1,1,"Cliente Ejemplo"\n'
            'TEXT 20,175,"3",0,1,1,"Av. Principal 123, Quito"\n'
            'TEXT 20,205,"3",0,1,1,"Tel: 099-999-9999"\n'
            'BARCODE 20,250,"128",120,1,0,2,2,"ENV-2024-001"\n'
            'PRINT 1'
        ),
    },
    "coconut_sample": {
        "nombre": "Tula Bhavan (ejemplo)",
        "descripcion": "Ejemplo del archivo de pruebas original",
        "icon": "package-x-generic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            'TEXT 80,0,"4",0,1,1,"TULA BHAVAN"\n'
            'TEXT 80,60,"TSS24.BF2",0,1,1,"COCONUT     <COC>"\n'
            'TEXT 80,90,"TSS24.BF2",0,1,1,"QTY: 5 NOS"\n'
            'BARCODE 80,150,"128M",100,1,0,2,2,"222222100005"\n'
            'PRINT 1'
        ),
    },
    "vacio": {
        "nombre": "En blanco",
        "descripcion": "Plantilla vacía para TSPL manual",
        "icon": "document-new-symbolic",
        "width_mm": 60,
        "height_mm": 40,
        "tspl": (
            'SIZE 60 mm,40 mm\n'
            'GAP 2 mm,0 mm\n'
            'DIRECTION 1,0\n'
            'REFERENCE 0,0\n'
            'OFFSET 0 mm\n'
            'SET PEEL OFF\n'
            'SET TEAR ON\n'
            'CLS\n'
            '\n'
            'PRINT 1'
        ),
    },
}

# Tamaños de etiqueta comunes (mm)
LABEL_SIZES = {
    "60x40": {"name": "60 x 40 mm (estándar HT300)", "width": 60, "height": 40},
    "60x30": {"name": "60 x 30 mm", "width": 60, "height": 30},
    "60x20": {"name": "60 x 20 mm", "width": 60, "height": 20},
    "50x25": {"name": "50 x 25 mm (joyería)", "width": 50, "height": 25},
    "80x50": {"name": "80 x 50 mm", "width": 80, "height": 50},
    "80x30": {"name": "80 x 30 mm", "width": 80, "height": 30},
    "100x60": {"name": "100 x 60 mm (envío)", "width": 100, "height": 60},
    "100x80": {"name": "100 x 80 mm", "width": 100, "height": 80},
    "100x150": {"name": "100 x 150 mm (shipping)", "width": 100, "height": 150},
    "40x30": {"name": "40 x 30 mm (pequeña)", "width": 40, "height": 30},
}
