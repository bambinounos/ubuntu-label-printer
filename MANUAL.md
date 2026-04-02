# Manual de Usuario — Label Printer (TSPL)

Esta aplicación funciona con cualquier impresora térmica compatible con TSPL. Los ejemplos usan la HPRT HT300 como referencia (modelo principal de pruebas), pero los pasos aplican a cualquier impresora TSPL.

## 1. Primer uso

### 1.1 Instalar

```bash
git clone https://github.com/bambinounos/ubuntu-label-printer.git
cd ubuntu-label-printer
sudo ./install.sh
```

### 1.2 Abrir la aplicación

- Buscar **"Label Printer"** en el menú de Ubuntu (Activities / Dash)
- O ejecutar `label-printer` en terminal

### 1.3 Configurar la impresora

Al abrir por primera vez, click en el **icono de engranaje** (esquina superior derecha).

> **Requisito:** Tu impresora debe ser compatible con TSPL (TSC Printer Language). Si tu impresora soporta múltiples lenguajes, asegúrate de que esté configurada en modo TSPL. Consulta la sección "Impresoras compatibles" más abajo.

Seleccionar el modo de conexión:

| Si la impresora está... | Seleccionar | Configurar |
|-------------------------|-------------|------------|
| En CUPS (ya configurada) | **CUPS** | Nombre de cola (ej: `HT300`, `XP360B`, etc.) |
| En la red local | **Red TCP** | IP y puerto (ej: `192.168.1.100:9100`) |
| Conectada por USB directo | **USB directo** | Dispositivo (ej: `/dev/usb/lp0`) |

Click **"Probar Conexión"** para verificar. Si sale OK, click **"Aceptar"**.

---

## 2. Crear una etiqueta

### 2.1 Desde una plantilla

1. En el panel izquierdo, click en una plantilla (ej: "HELLBAM - Producto")
2. El código TSPL aparece en el editor (panel derecho)
3. La vista previa se actualiza automáticamente (panel central)
4. Editar los textos directamente en el código TSPL
5. Click **"TSPL → Visual"** para actualizar la vista previa

### 2.2 Desde cero

1. Click en la plantilla **"En blanco"**
2. Usar los botones del panel izquierdo para agregar elementos:

**Agregar texto:**
1. Click **"+ Texto"**
2. Escribir el contenido
3. Configurar posición X, Y (en dots: 8 dots = 1 mm)
4. Elegir fuente:
   - `"4"` = grande (24x32) — ideal para títulos
   - `"TSS24.BF2"` = asiática (24x24) — ideal para descripciones
   - `"3"` = estándar (16x24)
5. Click **"Aceptar"**

**Agregar código de barras:**
1. Click **"+ Barcode"**
2. Escribir los datos (número de parte, SKU, etc.)
3. Elegir tipo: `128` (general), `39` (alfanumérico), `EAN13` (productos)
4. Ajustar posición y altura
5. Click **"Aceptar"**

**Agregar código QR:**
1. Click **"+ QR"**
2. Escribir los datos (URL, código, texto)
3. Elegir tamaño de celda (5 = recomendado)
4. Click **"Aceptar"**

### 2.3 Editar el TSPL directamente

El editor TSPL es un editor de texto libre. Se puede escribir cualquier comando TSPL válido.

Después de editar, click **"TSPL → Visual"** para ver los cambios.

Para regenerar el TSPL desde los elementos visuales, click **"Visual → TSPL"**.

---

## 3. Imprimir

1. Verificar que el status en la barra superior muestre verde (●)
2. Ajustar **copias** (spinner al lado del botón imprimir)
3. Opcionalmente ajustar **velocidad** y **densidad**:
   - Velocidad: 0 = default de la impresora
   - Densidad: 8 = normal, mayor = más oscuro
4. Click **"Imprimir"**

Si aparece error, verificar la configuración de conexión (icono engranaje).

---

## 4. Interfaz web (alternativa)

Para usar desde el navegador (útil para acceso remoto o desde otro equipo):

```bash
cd /opt/label-printer
python3 ht300_web.py --port 5080
```

Abrir **http://localhost:5080** (o `http://IP_DEL_EQUIPO:5080` desde otro equipo).

La interfaz web permite:
- Seleccionar plantillas
- Editar código TSPL
- Enviar a imprimir directamente
- Ver estado de la impresora

> **Nota:** La interfaz web siempre usa CUPS para imprimir (ej: `lp -d HT300 -o raw`, donde `HT300` es el nombre de tu cola CUPS).
> Los modos Red TCP y USB directo solo están disponibles en la app de escritorio.

---

## 5. Tamaños de etiqueta

| Tamaño | Uso típico | Dots (203 DPI) |
|--------|------------|----------------|
| 60 x 40 mm | Estándar (productos, ej: HT300) | 480 x 320 |
| 60 x 30 mm | Producto pequeño | 480 x 240 |
| 60 x 20 mm | Estantería | 480 x 160 |
| 80 x 50 mm | Producto grande | 640 x 400 |
| 100 x 60 mm | Envío | 800 x 480 |
| 100 x 150 mm | Shipping internacional | 800 x 1200 |

Para cambiar el tamaño, usar el combo **"Tamaño etiqueta"** en el panel izquierdo
o editar manualmente los spinners W y H.

---

## 6. Referencia de posiciones

La etiqueta estándar (60 x 40 mm) tiene este layout en dots:

```
(0,0) ─────────────────────────── (480,0)
  │                                  │
  │  TEXT en (60,0) = título         │
  │  TEXT en (60,40) = línea 2       │
  │  TEXT en (60,80) = línea 3       │
  │  TEXT en (60,120) = línea 4      │
  │  BARCODE en (60,150) = código    │
  │                                  │
(0,320) ─────────────────────── (480,320)
```

**Regla:** 1 mm = 8 dots. Para posicionar a 10mm del borde izquierdo: X = 80.

---

## 7. Solución de problemas

### La impresora no responde

1. Verificar que está encendida y conectada
2. Click en icono engranaje -> **"Probar Conexion"**
3. Si usa CUPS: `lpstat -p NOMBRE_COLA` en terminal (ej: `lpstat -p HT300`)
4. Si usa red: `nc -zv IP 9100` en terminal

### Verificar compatibilidad TSPL

Si la impresora no responde a los comandos o imprime caracteres basura en lugar de etiquetas:

1. **Verificar que tu impresora soporta TSPL.** Consultar las especificaciones del fabricante o el manual del modelo.
2. **Si soporta múltiples lenguajes** (TSPL, EPL, ZPL, CPCL), verificar que esté configurada en **modo TSPL**. Muchas impresoras tienen un DIP switch, opción en menú, o utilidad de configuración para cambiar el lenguaje activo.
3. **Prueba rápida:** Enviar un comando simple directamente para verificar:
   ```bash
   # Via CUPS (reemplazar NOMBRE_COLA con tu cola)
   echo -e "SIZE 60 mm,40 mm\nGAP 2 mm,0 mm\nCLS\nTEXT 50,50,\"3\",0,1,1,\"TEST\"\nPRINT 1\n" | lp -d NOMBRE_COLA -o raw

   # Via USB directo
   echo -e "SIZE 60 mm,40 mm\nGAP 2 mm,0 mm\nCLS\nTEXT 50,50,\"3\",0,1,1,\"TEST\"\nPRINT 1\n" > /dev/usb/lp0

   # Via red (reemplazar IP)
   echo -e "SIZE 60 mm,40 mm\nGAP 2 mm,0 mm\nCLS\nTEXT 50,50,\"3\",0,1,1,\"TEST\"\nPRINT 1\n" | nc IP_IMPRESORA 9100
   ```
   Si imprime una etiqueta con "TEST", la impresora es compatible.

### Error de permisos USB

```bash
sudo usermod -aG lp $USER
# Cerrar sesión y volver a entrar
```

O temporalmente:
```bash
sudo chmod 666 /dev/usb/lp0
```

### No aparece en CUPS

```bash
# USB (ejemplo con HT300, adaptar URI a tu impresora)
sudo lpadmin -p HT300 -v "usb://HPRT/HT300" -m raw -E

# Red
sudo lpadmin -p HT300 -v "socket://192.168.1.100:9100" -m raw -E
```

> **Nota:** Siempre crear la cola como **raw** (`-m raw`) para impresoras TSPL. Un driver PPD procesaría los datos y corrompería los comandos TSPL.

### La etiqueta sale en blanco

- Verificar que el código TSPL tiene `PRINT 1` al final
- Verificar que `CLS` está antes de los elementos
- Aumentar la densidad (DENSITY 10 o más)
- Si la impresora soporta múltiples lenguajes, confirmar que está en modo TSPL

### El texto se corta

- La etiqueta tiene 480 dots de ancho (60mm)
- Dejar al menos 60 dots de margen a cada lado
- Reducir el tamaño de fuente o usar multiplicador 1

---

## 8. Impresoras compatibles

Esta aplicación funciona con cualquier impresora térmica que soporte **TSPL** (TSC Printer Language). A continuación las marcas y modelos conocidos:

| Marca | Modelos compatibles | Notas |
|-------|---------------------|-------|
| **HPRT** | HT300, HT100, HT130 | HT300 es el modelo principal de pruebas de esta aplicación |
| **TSC** | Todos (TDP-225, TE200, TE300, TC200, etc.) | TSC es el creador original de TSPL; todos sus modelos lo soportan |
| **Xprinter** | XP-360B, XP-365B y otros con TSPL | Impresoras económicas muy populares |
| **Gainscha / Gprinter** | Series GP y GS con soporte TSPL | Verificar que el modo TSPL esté activo |
| **iDPRT** | Modelos con modo TSPL | Algunos soportan múltiples lenguajes |
| **Genérica** | Cualquier impresora térmica TSPL | Consultar especificaciones del fabricante |

### Como verificar si tu impresora es compatible

1. **Revisar las especificaciones** del fabricante: buscar "TSPL", "TSC compatible" o "TSC Printer Language" en la hoja de datos.
2. **Si soporta múltiples lenguajes**, configurarla en modo TSPL (generalmente via DIP switch, menú en pantalla, o utilidad del fabricante).
3. **Hacer la prueba rápida** descrita en la sección de Solución de problemas.

> **Soporte futuro:** Está planificado agregar soporte para **ZPL** (Zebra Programming Language) en una versión futura, lo que ampliará la compatibilidad a impresoras Zebra y otras que usen ZPL.

---

## 9. Actualizar la aplicación

```bash
cd ubuntu-label-printer
./update.sh
```

El actualizador:
1. Descarga los cambios de GitHub
2. Muestra qué cambió
3. Reinstala en `/opt/label-printer/`
4. La configuración del usuario se conserva

---

## 10. Desinstalar

```bash
sudo ./uninstall.sh
```

O buscar **"Label Printer"** en GNOME Software y desinstalar desde ahí.

Se eliminan:
- `/opt/label-printer/`
- Icono, acceso directo, metadata
- Comando `label-printer`
- Opcionalmente: configuración en `~/.config/label-printer/`
