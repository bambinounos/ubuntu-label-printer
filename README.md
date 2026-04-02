# Label Printer — TSPL Thermal Label Printer

Aplicación Ubuntu para diseñar e imprimir etiquetas en cualquier impresora térmica compatible con **TSPL** (TSC Printer Language).

Funciona con impresoras HPRT, TSC, Xprinter, Gainscha, iDPRT y cualquier modelo que soporte comandos TSPL. Incluye dos interfaces: **aplicación de escritorio GTK** y **interfaz web**.

![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%2B-E95420?logo=ubuntu&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)
![GTK3](https://img.shields.io/badge/GTK-3.0-4A86CF)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Características

- **Editor visual** con vista previa en tiempo real (Cairo)
- **Editor TSPL** con sincronización bidireccional (Visual ↔ TSPL)
- **12 plantillas** reales: Caterpillar, Komatsu, Hino, Hyundai, envío, bodega, QR
- **Códigos de barras**: Code 128, 128M, 39, 39C, EAN-13, UPC-A
- **Códigos QR** con niveles de corrección configurables
- **Elementos gráficos**: texto, líneas, cajas, círculos
- **3 modos de conexión**: CUPS, Red TCP (socket:9100), USB directo
- **Interfaz web** alternativa (puerto 5080)
- **Instalador profesional** con integración al menú de Ubuntu y GNOME Software

---

## Impresoras compatibles

Esta aplicación funciona con **cualquier impresora térmica que soporte el lenguaje TSPL** (TSC Printer Language). A continuación se listan marcas y modelos verificados o conocidos como compatibles:

| Marca | Modelos | Notas |
|-------|---------|-------|
| **HPRT** | HT300, HT100, HT130 | HT300 es el modelo principal de pruebas |
| **TSC** | Todos los modelos (TDP-225, TE200, TE300, TC200, etc.) | TSC es el creador original del lenguaje TSPL |
| **Xprinter** | XP-360B, XP-365B y otros modelos TSPL | Muy comunes y económicas |
| **Gainscha / Gprinter** | Series GP y GS con soporte TSPL | Verificar modo TSPL en configuración |
| **iDPRT** | Modelos con modo TSPL | Algunos modelos soportan múltiples lenguajes |
| **Genérica** | Cualquier impresora térmica TSPL | Verificar especificaciones del fabricante |

> **Nota:** Si tu impresora soporta múltiples lenguajes (TSPL, EPL, ZPL, CPCL), asegúrate de configurarla en **modo TSPL** antes de usar esta aplicación.

> **Soporte ZPL (Zebra):** Está planificado agregar soporte para el lenguaje ZPL (Zebra Programming Language) en una versión futura.

---

## Instalación

```bash
git clone https://github.com/bambinounos/ubuntu-label-printer.git
cd ubuntu-label-printer
sudo ./install.sh
```

El instalador:
1. Instala dependencias del sistema (`python3-gi`, `python3-gi-cairo`, `cups`)
2. Copia la aplicación a `/opt/label-printer/`
3. Registra icono, acceso directo y metadata AppStream
4. Crea el comando `label-printer` en el PATH

### Actualizar

```bash
cd ubuntu-label-printer
git pull
sudo ./install.sh
```

O con el script de actualización:

```bash
./update.sh
```

### Desinstalar

Desde terminal:

```bash
sudo ./uninstall.sh
```

O desde **GNOME Software / Ubuntu Software** (buscar "Label Printer").

---

## Uso

### Aplicación de escritorio (GTK)

Abrir de cualquiera de estas formas:

- Buscar **"Label Printer"** en Activities / Dash de Ubuntu
- Terminal: `label-printer`
- Directamente: `/opt/label-printer/run.sh`

#### Pantalla principal

La ventana tiene 3 paneles:

```
┌──────────────┬─────────────────┬──────────────────┐
│  PLANTILLAS  │                 │                  │
│              │   VISTA PREVIA  │   EDITOR TSPL    │
│  Caterpillar │   (Canvas)      │                  │
│  Komatsu     │                 │   SIZE 60 mm...  │
│  Hino        │   ┌──────────┐  │   GAP 2 mm...   │
│  Hyundai     │   │ etiqueta │  │   CLS            │
│  Envío       │   │ preview  │  │   TEXT 60,0...   │
│  Bodega      │   └──────────┘  │   BARCODE...     │
│  QR          │                 │   PRINT 1        │
│  ...         │   60 x 40 mm   │                  │
│──────────────│                 │──────────────────│
│  TAMAÑO      │                 │  Vel: __ Den: __ │
│  60x40 mm ▼  │                 │  CUPS  Copias: 1 │
│  W: 60 H: 40 │                 │  [ Imprimir ]    │
│──────────────│                 │                  │
│  + Texto     │                 │  ▶ Referencia    │
│  + Barcode   │                 │    TSPL          │
│  + QR        │                 │                  │
│  + Línea     │                 │                  │
│  + Caja      │                 │                  │
│  + Círculo   │                 │                  │
└──────────────┴─────────────────┴──────────────────┘
```

#### Flujo de trabajo típico

1. **Seleccionar plantilla** del panel izquierdo (o empezar desde "En blanco")
2. **Editar contenido** directamente en el editor TSPL (panel derecho)
3. Click **"TSPL → Visual"** para ver la vista previa actualizada
4. O **agregar elementos** con los botones `+ Texto`, `+ Barcode`, `+ QR`, etc.
5. Click **"Visual → TSPL"** para regenerar el código
6. Ajustar **copias**, **velocidad** y **densidad**
7. Click **"Imprimir"**

#### Agregar elementos

| Botón | Diálogo | Campos |
|-------|---------|--------|
| + Texto | Texto, posición X/Y, fuente, multiplicador | Fuentes: "1" a "5", "TSS24.BF2" |
| + Barcode | Datos, tipo, posición, altura, legible | Tipos: 128, 128M, 39, 39C, EAN13 |
| + QR | Datos, posición, tamaño celda, corrección | Celdas: 1,3,5,7,10,12 |
| + Línea | Agrega barra horizontal | BAR x,y,ancho,alto |
| + Caja | Agrega rectángulo | BOX x1,y1,x2,y2,grosor |
| + Círculo | Agrega círculo | CIRCLE x,y,diámetro,grosor |

#### Configurar conexión (icono engranaje ⚙)

| Modo | Descripción | Cuándo usar |
|------|-------------|-------------|
| **CUPS** | Cola de impresión del sistema | Impresora configurada en CUPS (por defecto) |
| **Red TCP** | Socket directo al puerto 9100 | Impresora en red sin CUPS |
| **USB directo** | Escribe a `/dev/usb/lp0` | Impresora USB sin CUPS |

Cada modo tiene un botón **"Probar Conexión"** para verificar.

La configuración se guarda en `~/.config/label-printer/connection.json`.

---

### Interfaz web

Para usar la interfaz web (alternativa al escritorio):

```bash
cd /opt/label-printer
python3 ht300_web.py
```

Abre el navegador en **http://localhost:5080**.

#### Pantalla web

```
┌─────────────────────────────────────────────────┐
│  Label Printer  TSPL        ● CUPS  ● USB      │
├───────────────┬─────────────────────────────────┤
│               │                                 │
│  Plantillas   │  Editor TSPL                    │
│               │                                 │
│  ┌─────────┐  │  SIZE 60 mm,40 mm               │
│  │Producto │  │  GAP 2 mm,0 mm                  │
│  └─────────┘  │  DIRECTION 1,0                  │
│  ┌─────────┐  │  CLS                            │
│  │  QR     │  │  TEXT 60,0,"4",0,1,1,"CODIGO"   │
│  └─────────┘  │  BARCODE 60,150,"128M",...       │
│  ┌─────────┐  │  PRINT 1                        │
│  │Estante  │  │                                 │
│  └─────────┘  │  Copias: [1]  [ Imprimir ]      │
│  ┌─────────┐  │                                 │
│  │  CAT    │  │  ▶ Referencia rápida TSPL       │
│  └─────────┘  │                                 │
└───────────────┴─────────────────────────────────┘
```

La interfaz web envía TSPL directamente via CUPS (ej: `lp -d HT300 -o raw`, donde `HT300` es el nombre de la cola CUPS configurada).

---

## Referencia TSPL rápida

Todas las coordenadas están en **dots** (203 DPI → **8 dots = 1 mm**).

Etiqueta estándar: **60 x 40 mm** = **480 x 320 dots** (ejemplo con HT300).

### Comandos de configuración

```
SIZE 60 mm,40 mm          Tamaño de etiqueta
GAP 2 mm,0 mm             Espacio entre etiquetas
DIRECTION 1,0             Dirección de impresión
SPEED 5                   Velocidad (pulgadas/seg)
DENSITY 8                 Oscuridad (0=claro, 15=oscuro)
CLS                       Limpiar buffer
PRINT 1                   Imprimir (1 copia)
PRINT 3,2                 3 juegos, 2 copias cada uno
```

### Comandos de contenido

```
TEXT x,y,"font",rot,mx,my,"texto"
  Fuentes: "1"=8x12  "2"=12x20  "3"=16x24  "4"=24x32  "5"=32x48
           "TSS24.BF2"=asiática 24x24

BARCODE x,y,"tipo",alto,legible,rot,estrecho,ancho,"datos"
  Tipos: "128" "128M" "39" "39C" "EAN13" "EAN8" "UPCA"
  legible: 0=sin texto, 1=con texto debajo

QRCODE x,y,ECC,celda,modo,rot,"datos"
  ECC: L(7%) M(15%) Q(25%) H(30%)
  celda: 1, 3, 5, 7, 10, 12

BAR x,y,ancho,alto              Barra/línea sólida
BOX x1,y1,x2,y2,grosor          Rectángulo
CIRCLE x,y,diámetro,grosor      Círculo
```

### Ejemplo completo

```
SIZE 60 mm,40 mm
GAP 2 mm,0 mm
DIRECTION 1,0
REFERENCE 0,0
OFFSET 0 mm
SET PEEL OFF
SET TEAR ON
CLS
TEXT 60,0,"4",0,1,1,"CATERPILLAR"
TEXT 60,40,"TSS24.BF2",0,1,1,"WASHER"
TEXT 60,80,"TSS24.BF2",0,1,1,"QTY: 4  EA"
TEXT 60,120,"TSS24.BF2",0,1,1,"416-420 SERIES"
BARCODE 60,150,"39",100,1,0,2,2,"9R-0158"
PRINT 1
```

---

## Configurar impresora TSPL en CUPS

Los ejemplos usan `HT300` como nombre de cola, pero puedes usar cualquier nombre que identifique tu impresora (ej: `XP360B`, `TSC_TE200`, `MiImpresora`).

### Por USB

```bash
# Conectar impresora y verificar detección
lsusb | grep -i "printer"   # buscar tu impresora en la lista

# Crear cola raw (ejemplo con HPRT HT300)
sudo lpadmin -p HT300 -v "usb://HPRT/HT300" -m raw -E

# Ejemplo con Xprinter XP-360B
# sudo lpadmin -p XP360B -v "usb://Xprinter/XP-360B" -m raw -E

# Ejemplo con TSC TE200
# sudo lpadmin -p TSC_TE200 -v "usb://TSC/TE200" -m raw -E

# Verificar
lpstat -p HT300
```

### Por red (puerto 9100)

```bash
# Verificar conectividad
nc -zv IP_IMPRESORA 9100

# Crear cola (cambiar nombre y URI según tu impresora)
sudo lpadmin -p HT300 -v "socket://IP_IMPRESORA:9100" -m raw -E

# Verificar
lpstat -v HT300
```

> **Importante:** La cola CUPS debe crearse como **raw** (`-m raw`) para que los comandos TSPL se envíen sin procesar. Esto aplica a todas las impresoras TSPL.

### Permisos USB (si usas modo USB directo)

```bash
sudo usermod -aG lp $USER
# O temporal:
sudo chmod 666 /dev/usb/lp0
```

---

## Estructura del proyecto

```
ubuntu-label-printer/
├── install.sh              # Instalador del sistema (/opt)
├── update.sh               # Actualizador (git pull + reinstall)
├── uninstall.sh            # Desinstalador limpio
├── run.sh                  # Lanzador
├── ht300_web.py            # Interfaz web (puerto 5080)
├── assets/
│   ├── label-printer.svg                          # Icono de la app
│   ├── label-printer.desktop                      # Plantilla desktop
│   └── com.antigravity.labelprinter.metainfo.xml  # AppStream metadata
├── src/
│   ├── main.py             # Punto de entrada
│   ├── app.py              # Ventana GTK principal + diálogos
│   ├── connection.py       # Gestión de conexión (CUPS/Red/USB)
│   ├── label_canvas.py     # Vista previa Cairo
│   ├── label_elements.py   # Elementos TSPL (Text, Barcode, QR, etc.)
│   ├── tspl_generator.py   # Generador y parser TSPL
│   ├── printer.py          # Impresión via CUPS (legacy)
│   └── templates.py        # Plantillas predefinidas
├── requirements.txt
└── setup.py
```

---

## Licencia

MIT

---

*Desarrollado por [Antigravity / HELLBAM S.A.](https://github.com/bambinounos) — Guayaquil, Ecuador*
