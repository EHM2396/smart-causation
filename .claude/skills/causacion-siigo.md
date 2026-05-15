# Skill: Causación Contable Automática para SIIGO

## Descripción
Genera el archivo de importación de compras para SIIGO a partir de facturas electrónicas en formato xlsx (token DIAN). Razona las cuentas contables correspondientes, respeta consecutivos vigentes y produce el archivo listo para cargar en SIIGO.

## Cuándo usar este skill
El usuario proporciona uno o varios archivos `.xlsx` con facturas del token DIAN y solicita causarlas / importarlas a SIIGO.

---

## Paso 1 — Leer archivos de referencia del proyecto

Antes de procesar cualquier factura, leer los archivos de la raíz del proyecto:

| Archivo | Propósito |
|---|---|
| `modelo_importacion.xlsx` | Estructura exacta de columnas que acepta SIIGO para importación de compras |
| `codigos_impuestos.xlsx` | Catálogo de códigos de impuestos, porcentajes y su cuenta contable asignada |
| `Cuentas_contables.xlsx` | Plan de cuentas del cliente; usar para mapear naturaleza del gasto al PUC |
| `Tipos de comprobante contable.xlsx` | Prefijos y rangos de consecutivos por tipo de comprobante |
| `facturas_electronicas.xlsx` (si existe) | Historial de facturas ya causadas; sirve para detectar el último consecutivo usado |

Leer **todas las hojas** de cada archivo. Guardar en memoria de trabajo:
- Columnas del modelo (orden y nombre exacto).
- Tabla: código impuesto → porcentaje → cuenta débito / crédito.
- Último consecutivo registrado para el tipo de comprobante de compras por factura electrónica.

---

## Paso 2 — Identificar el último consecutivo

1. Revisar `Tipos de comprobante contable.xlsx` para obtener el **prefijo** y el **rango** del comprobante de compras por factura electrónica (ej. `CE`, `FE`, `CP`, etc.).
2. Buscar en el historial (`facturas_electronicas.xlsx` u otro archivo de causaciones previas) el número más alto ya usado para ese prefijo.
3. El próximo comprobante será `último + 1`. **Nunca reutilizar ni saltar un consecutivo.**
4. Si no existe historial, preguntar al usuario cuál es el último consecutivo registrado en SIIGO antes de continuar.

---

## Paso 3 — Parsear las facturas proporcionadas por el usuario

Por cada archivo xlsx entregado:

### 3.1 Datos del encabezado de la factura
- Número de factura del proveedor (CUFE / número DIAN)
- Fecha de emisión
- NIT / cédula del proveedor (tercero)
- Razón social / nombre completo
- Dirección, ciudad, departamento
- Tipo de proveedor: **persona natural** o **persona jurídica**
- Régimen tributario (Responsable de IVA, No responsable, Gran contribuyente, etc.)

### 3.2 Ítems / líneas de la factura
Por cada ítem extraer:
- Descripción del bien o servicio
- Valor base (antes de impuestos)
- Código de impuesto (ej. `IVA_19`, `RTE_11`, `ICA_01`, etc.)
- Porcentaje del impuesto
- Valor del impuesto

### 3.3 Validaciones mínimas
- Suma de bases + impuestos debe cuadrar con el total de la factura.
- Si hay discrepancia > $1 COP, alertar al usuario antes de continuar.
- Verificar que cada código de impuesto exista en `codigos_impuestos.xlsx`. Si no existe, solicitar la cuenta contable al usuario.

---

## Paso 4 — Razonar las cuentas contables (PUC)

Para cada línea de la factura aplicar la siguiente lógica:

### Cuenta del gasto / costo (débito)
1. Identificar la naturaleza del ítem (compra de mercancía, servicio, activo fijo, gasto administrativo, etc.).
2. Consultar `Cuentas_contables.xlsx` y buscar la cuenta más específica que corresponda.
3. Reglas generales PUC Colombia:
   - Compra de mercancía para venta → `6` (Costo de ventas) o `14` (Inventarios) según el método de costeo.
   - Servicios administrativos → `51XXXX` o `52XXXX`.
   - Activos fijos → `15XXXX` o `16XXXX`.
   - Gastos de venta → `53XXXX`.
4. Si el ítem es ambiguo, listar las 2-3 opciones más probables y preguntar al usuario cuál aplicar.

### Cuenta del impuesto (débito o crédito según tipo)
Consultar directamente `codigos_impuestos.xlsx`:
- **IVA descontable** → `240810XX` o la que indique el catálogo (débito).
- **Retención en la fuente** → `236XXX` (crédito sobre el proveedor).
- **Retención ICA** → `236810` o la que indique el catálogo.
- **IVA retenido** → `240701XX`.

### Cuenta del proveedor (crédito)
- Persona jurídica → usar cuenta `220505` (o la configurada en el plan de cuentas).
- Persona natural → usar cuenta `220510` (o la configurada en el plan de cuentas).
- Siempre vincular el NIT/cédula como tercero en SIIGO.

---

## Paso 5 — Construir el archivo de importación

Generar un DataFrame / hoja xlsx que respete **exactamente** el orden y nombre de columnas de `modelo_importacion.xlsx`.

### Campos críticos de SIIGO (adaptar si el modelo difiere)

| Columna SIIGO | Valor a completar |
|---|---|
| `Tipo Comprobante` | Código del comprobante de compras (del paso 2) |
| `Consecutivo` | Número correlativo asignado (paso 2) |
| `Fecha` | Fecha de la factura (`DD/MM/AAAA`) |
| `Tercero NIT` | NIT o cédula sin DV o con DV según exija SIIGO |
| `Cuenta Contable` | Código PUC (sin puntos ni guiones) |
| `Débito` | Valor positivo si la cuenta va al débito |
| `Crédito` | Valor positivo si la cuenta va al crédito |
| `Concepto / Descripción` | Descripción breve del ítem o impuesto |
| `Centro de Costo` | Dejar en blanco si no aplica; preguntar al usuario si hay centros configurados |
| `Documento Referencia` | Número de factura del proveedor |
| `Cod. Impuesto` | Código del impuesto según `codigos_impuestos.xlsx` |
| `% Impuesto` | Porcentaje numérico (ej. `19`, `3.5`) |

### Reglas de generación de filas
- Una fila por cada movimiento contable (débito o crédito).
- Todas las filas de una misma factura comparten el mismo consecutivo.
- El asiento debe **cuadrar**: suma débitos = suma créditos por comprobante.
- Si no cuadra, **no generar el archivo** y reportar la diferencia al usuario.

---

## Partida Doble — Validación Global de la Importación

Además de validar cada comprobante individualmente, se debe verificar la **partida doble a nivel de toda la importación**:

### Regla fundamental
```
SUMA TOTAL DÉBITOS (todas las filas) = SUMA TOTAL CRÉDITOS (todas las filas)
```
Si esta igualdad no se cumple, el archivo **no debe generarse**.

### Niveles de validación (aplicar en orden)

#### Nivel 1 — Por comprobante (asiento individual)
Por cada consecutivo / factura:
- Sumar todas las filas donde `Débito > 0` → `total_debito_comprobante`
- Sumar todas las filas donde `Crédito > 0` → `total_credito_comprobante`
- Verificar: `total_debito_comprobante == total_credito_comprobante`
- Si no cuadra: detener ese comprobante, reportar diferencia y no incluirlo en el archivo.

#### Nivel 2 — Global de la importación (partida doble)
Sobre el conjunto completo de comprobantes que sí cuadraron:
- `GRAN_TOTAL_DÉBITOS = Σ total_debito_comprobante (todos los comprobantes válidos)`
- `GRAN_TOTAL_CRÉDITOS = Σ total_credito_comprobante (todos los comprobantes válidos)`
- Verificar: `GRAN_TOTAL_DÉBITOS == GRAN_TOTAL_CRÉDITOS`
- Si no son iguales: hay un error de lógica en el mapeo de cuentas; **bloquear la generación del archivo** y reportar.

### Estructura esperada de la partida doble por factura

| Movimiento | Naturaleza | Cuenta típica |
|---|---|---|
| Base del gasto / costo | **Débito** | `51XXXX`, `52XXXX`, `6XXXXX`, `14XXXX`, etc. |
| IVA descontable | **Débito** | `240810XX` |
| Retención en la fuente practicada | **Crédito** | `236XXX` |
| Retención ICA practicada | **Crédito** | `236810` |
| IVA retenido | **Crédito** | `240701XX` |
| Cuenta por pagar al proveedor (neto) | **Crédito** | `220505` / `220510` |

> El crédito del proveedor debe ser igual a: Base + IVA − Retenciones practicadas.  
> Esto garantiza que débitos = créditos en el asiento.

### Reporte de cuadre al usuario

Al finalizar, mostrar tabla resumen:

```
╔══════════════════════════════════════════════════════╗
║         VALIDACIÓN DE PARTIDA DOBLE                  ║
╠══════════╦══════════════╦══════════════╦═════════════╣
║ Consec.  ║   Débitos    ║   Créditos   ║  Diferencia ║
╠══════════╬══════════════╬══════════════╬═════════════╣
║ CE-00246 ║  1.500.000   ║  1.500.000   ║      0  ✓   ║
║ CE-00247 ║    890.000   ║    890.000   ║      0  ✓   ║
║ CE-00248 ║  2.100.000   ║  2.090.000   ║  10.000  ✗  ║
╠══════════╬══════════════╬══════════════╬═════════════╣
║ TOTAL    ║  4.490.000   ║  4.480.000   ║  10.000  ✗  ║
╚══════════╩══════════════╩══════════════╩═════════════╝
⚠ CE-00248 no cuadra — revisar retención o IVA.
⛔ Importación bloqueada hasta resolver diferencias.
```

Solo cuando todas las filas muestren diferencia `0` se genera el archivo final.

---

## Paso 6 — Guardar y reportar

1. Guardar el archivo generado como `importacion_SIIGO_YYYYMMDD.xlsx` en la raíz del proyecto.
2. Mostrar al usuario un resumen:
   - Total de facturas procesadas.
   - Rango de consecutivos usados (del X al Y).
   - Total débitos y créditos (deben ser iguales).
   - Advertencias o cuentas que requieren confirmación.
3. Indicar el consecutivo hasta el que se llegó para que el usuario lo actualice como punto de partida la próxima vez.

---

## Manejo de errores y casos especiales

| Situación | Acción |
|---|---|
| Código de impuesto no encontrado en catálogo | Preguntar cuenta contable al usuario; no asumir |
| Factura ya causada (número DIAN duplicado) | Alertar y omitir; no generar duplicado |
| Proveedor sin NIT en el archivo | Solicitar el NIT antes de continuar |
| Retención > base (error de cálculo) | Alertar; no causarla hasta que el usuario confirme |
| Régimen simple / no responsable de IVA | No contabilizar IVA descontable; solo el gasto por el total |
| Nota crédito / devolución | Invertir débitos y créditos; usar comprobante de nota crédito |

---

## Memoria persistente entre sesiones

Al finalizar cada ejecución exitosa, guardar en un archivo de memoria del proyecto:

```
Último consecutivo usado: [prefijo][número]
Fecha de la última importación: YYYY-MM-DD
Facturas causadas (CUFE / número): [lista]
```

Leer este archivo al inicio de cada nueva sesión para retomar desde el consecutivo correcto.

---

## Ejemplo de invocación

```
Usuario: "Aquí te dejo facturas_octubre.xlsx con 12 facturas del token DIAN, cáusalas."

Asistente:
1. Lee modelo_importacion.xlsx, codigos_impuestos.xlsx, Cuentas_contables.xlsx.
2. Detecta último consecutivo: CE-00245.
3. Parsea facturas_octubre.xlsx → 12 facturas, 38 líneas de impuestos.
4. Mapea cuentas contables por ítem y por impuesto.
5. Genera importacion_SIIGO_20261015.xlsx con consecutivos CE-00246 al CE-00257.
6. Reporta resumen y advierte sobre 1 cuenta ambigua que requiere confirmación.
```
