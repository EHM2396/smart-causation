"""
ai_service.py – Capa de inteligencia artificial para clasificación de ítems.

Modos de operación:
  - sugerir()       : 1 ítem → 1 llamada (usado por endpoint individual)
  - sugerir_batch() : N ítems únicos → 1 sola llamada (usado por el batch endpoint)
                      Reduce el tiempo de ~5-10s a ~1-2s para 86 facturas.

Hardening:
  1. Sanitización de PII — limpia NITs, teléfonos, emails y montos antes de enviar
  2. Detección de prompt injection — rechaza descripciones con patrones sospechosos
  3. Tracking de tokens — acumula uso en session_state para auditoría y costo

Modelo por defecto: gpt-4o-mini
  - Costo bajo, alta calidad para clasificación contable colombiana
  - Respuesta JSON estructurada, temperatura 0 para máximo determinismo
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Importación defensiva ──────────────────────────────────────────────────────
try:
    from openai import OpenAI as _OpenAI
    _OPENAI_IMPORTADO = True
except ImportError:
    _OpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_IMPORTADO = False

# Modelo a usar (puede cambiarse sin tocar el resto del código)
_MODELO_DEFAULT = "gpt-4o-mini"

# Máximo de cuentas enviadas al modelo por ítem (después de rankear por relevancia)
_MAX_CUENTAS_PROMPT = 40

# Umbral de confianza para preselección automática (Fase 2)
_UMBRAL_CONFIANZA_ALTA = 0.80

# Límite de llamadas IA por sesión de usuario (protección de costo)
_LIMITE_LLAMADAS_POR_SESION = 60

# Claves de session_state para métricas
_SS_LLAMADAS = "_ia_llamadas_sesion"
_SS_TOKENS   = "_ia_tokens_sesion"

# Patrones PII a limpiar antes de enviar al modelo
_RE_NIT      = re.compile(r"\b\d{6,10}-?\d\b")          # NIT colombiano
_RE_TELEFONO = re.compile(r"\b(\+57[\s-]?)?\d{3}[\s-]?\d{3}[\s-]?\d{4}\b")
_RE_EMAIL    = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_RE_MONTO    = re.compile(r"\$\s?[\d.,]+")               # $1.234.567

# Palabras que indican intento de prompt injection (case-insensitive)
_PALABRAS_INYECCION = (
    "ignore previous",
    "ignore all",
    "system:",
    "you are now",
    "override",
    "jailbreak",
    "new instruction",
    "disregard",
    "act as",
)


# ── Sinónimos PUC colombianos para ranking de cuentas ────────────────────────
# Mapea palabras clave del ítem a palabras que aparecen en nombres de cuentas PUC.
# Permite que "cemento" encuentre cuentas con "materiales" aunque la palabra exacta no coincida.
_SINONIMOS_PUC: list[tuple[set[str], set[str]]] = [
    # (palabras del ítem)  →  (palabras que buscamos en el nombre de la cuenta)
    ({"cemento", "arena", "varilla", "ladrillo", "hierro", "tuberia", "tubería",
      "bloque", "madera", "agregado", "concreto", "acero", "viga", "tornillo",
      "pintura", "pvc", "cable", "alambre", "obra", "construccion", "construcción"},
     {"material", "suministro", "construccion", "construcción", "ferreter", "obra"}),

    ({"honorario", "honorarios", "asesoria", "asesoría", "consultoria", "consultoría",
      "juridico", "jurídico", "contable", "contador", "abogado", "ingeniero"},
     {"honorario", "asesoria", "asesoría", "consultoria", "profesional"}),

    ({"arrendamiento", "alquiler", "canon", "renta", "arriendo"},
     {"arrendamiento", "alquiler"}),

    ({"acueducto", "agua", "energia", "energía", "electricidad", "gas", "telefono",
      "teléfono", "internet", "vigilancia", "aseo", "correo", "domicilio"},
     {"servicio", "public", "acueducto", "energia", "energía", "telefono", "internet"}),

    ({"mantenimiento", "reparacion", "reparación", "repuesto", "pieza", "refaccion"},
     {"mantenimiento", "reparacion", "reparación"}),

    ({"papeleria", "papelería", "resma", "cartucho", "toner", "tóner", "lapiz",
      "lápiz", "boligrafo", "bolígrafo", "utiles", "útiles"},
     {"papeleria", "papelería", "utiles", "útiles", "oficina"}),

    ({"seguro", "poliza", "póliza", "arl", "prima"},
     {"seguro", "poliza", "póliza"}),

    ({"combustible", "gasolina", "acpm", "diesel", "lubricante"},
     {"combustible", "gasolina", "lubricante"}),

    ({"publicidad", "marketing", "propaganda", "aviso", "pauta", "impresion"},
     {"publicidad", "propaganda", "marketing"}),

    ({"transporte", "flete", "envio", "envío", "mensajeria", "mensajería", "courier"},
     {"transporte", "flete", "envio", "envío"}),

    ({"hotel", "hospedaje", "viatico", "viático", "tiquete", "aéreo", "aereo"},
     {"viaje", "viatico", "viático", "hospedaje"}),

    ({"nomina", "nómina", "salario", "sueldo", "prestacion", "cesantia"},
     {"nomina", "nómina", "salario", "personal"}),
]

_STOP_WORDS_ES = {
    "de", "la", "el", "los", "las", "del", "un", "una", "y", "o",
    "a", "en", "por", "para", "con", "que", "al", "se", "su",
}


def _rankear_cuentas(cuentas: list[dict], descripciones: list[str]) -> list[dict]:
    """
    Ordena las cuentas por relevancia a las descripciones dadas y retorna las
    primeras _MAX_CUENTAS_PROMPT. Usa matching de palabras clave + sinónimos PUC.
    Sin dependencias externas (solo regex/set), latencia <1ms.
    """
    if len(cuentas) <= _MAX_CUENTAS_PROMPT:
        return cuentas

    # Tokens de las descripciones
    tokens_items: set[str] = set()
    for desc in descripciones:
        tokens_items.update(
            t for t in re.findall(r"[a-záéíóúñ]{3,}", desc.lower())
            if t not in _STOP_WORDS_ES
        )

    # Expandir con sinónimos: si el ítem menciona "cemento", agregamos "material"
    tokens_expandidos = set(tokens_items)
    for palabras_item, palabras_cuenta in _SINONIMOS_PUC:
        if tokens_items & palabras_item:
            tokens_expandidos.update(palabras_cuenta)

    def _score(cuenta: dict) -> int:
        nombre = cuenta["nombre"].lower()
        # +2 por cada token expandido que aparece en el nombre de la cuenta
        return sum(2 for t in tokens_expandidos if t in nombre)

    scored = sorted(cuentas, key=_score, reverse=True)
    return scored[:_MAX_CUENTAS_PROMPT]


# ── Tipos de retorno ──────────────────────────────────────────────────────────

@dataclass
class SugerenciaIA:
    """Resultado de la sugerencia del modelo. Siempre debe revisarse antes de aplicar."""
    cuenta_gasto: str | None = None
    cod_impuesto: str | None = None
    cuenta_pago: str | None = None  # cuenta de pago/acreedor sugerida para el proveedor
    confianza: float = 0.0          # 0.0 – 1.0
    explicacion: str = ""
    origen: str = "ia"
    modelo: str = field(default=_MODELO_DEFAULT)

    @property
    def confianza_alta(self) -> bool:
        return self.confianza >= _UMBRAL_CONFIANZA_ALTA

    @property
    def confianza_media(self) -> bool:
        return 0.50 <= self.confianza < 0.80

    @property
    def etiqueta_confianza(self) -> str:
        if self.confianza_alta:
            return "IA alta confianza"
        if self.confianza_media:
            return "IA media confianza"
        return "IA baja confianza"


# ── Lectura de API key ────────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    """
    Lee la API key con prioridad:
      1. st.secrets (Streamlit Cloud / secrets.toml local)
      2. Variable de entorno OPENAI_API_KEY
    Retorna None si no está configurada.
    """
    # 1. st.secrets
    try:
        import streamlit as st
        key = st.secrets.get("OPENAI_API_KEY", "")
        if key and key != "sk-...":
            return key
    except Exception:
        pass

    # 2. Variable de entorno
    key = os.getenv("OPENAI_API_KEY", "")
    return key if key and key != "sk-..." else None


# ── Helpers de hardening (Fase 4) ────────────────────────────────────────────

def _sanitizar_descripcion(texto: str) -> str:
    """
    Elimina patrones de PII de la descripción antes de enviarla al modelo.
    Reemplaza NITs, teléfonos, emails y montos por marcadores neutros.
    Trunca a 300 caracteres para evitar tokens innecesarios.
    """
    t = _RE_NIT.sub("[NIT]", texto)
    t = _RE_TELEFONO.sub("[TEL]", t)
    t = _RE_EMAIL.sub("[EMAIL]", t)
    t = _RE_MONTO.sub("[MONTO]", t)
    return t[:300].strip()


def _detectar_inyeccion(texto: str) -> bool:
    """
    Retorna True si la descripción contiene patrones de prompt injection.
    En ese caso, la llamada a la IA se cancela y se registra en el log.
    """
    lower = texto.lower()
    return any(patron in lower for patron in _PALABRAS_INYECCION)


def _verificar_rate_limit() -> bool:
    """
    Comprueba que no se haya superado el límite de llamadas por sesión.
    Incrementa el contador si aún hay margen. Retorna True si se puede llamar.
    """
    try:
        import streamlit as st
        count = st.session_state.get(_SS_LLAMADAS, 0)
        if count >= _LIMITE_LLAMADAS_POR_SESION:
            logger.warning(
                "ai_service: rate limit de sesión alcanzado (%d/%d) — llamada omitida",
                count, _LIMITE_LLAMADAS_POR_SESION,
            )
            return False
        st.session_state[_SS_LLAMADAS] = count + 1
        return True
    except Exception:
        return True  # fuera de Streamlit (tests, scripts): sin límite


def _registrar_tokens(total_tokens: int) -> None:
    """Acumula tokens usados en la sesión para tracking de costo."""
    try:
        import streamlit as st
        st.session_state[_SS_TOKENS] = st.session_state.get(_SS_TOKENS, 0) + total_tokens
    except Exception:
        pass


def get_estadisticas_sesion() -> dict:
    """
    Retorna métricas de uso IA de la sesión actual.
    Seguro de llamar fuera de contexto Streamlit (retorna ceros).
    """
    try:
        import streamlit as st
        return {
            "llamadas": st.session_state.get(_SS_LLAMADAS, 0),
            "tokens":   st.session_state.get(_SS_TOKENS, 0),
            "limite":   _LIMITE_LLAMADAS_POR_SESION,
        }
    except Exception:
        return {"llamadas": 0, "tokens": 0, "limite": _LIMITE_LLAMADAS_POR_SESION}


# ── API pública ───────────────────────────────────────────────────────────────

def esta_disponible() -> bool:
    """
    Retorna True solo si openai está instalado y la key está configurada.
    Llamar antes de usar sugerir() si se quiere condicionar la UI.
    """
    return _OPENAI_IMPORTADO and bool(_get_api_key())


def sugerir(
    descripcion: str,
    cuentas_gasto: list[dict],         # [{"codigo": "51950501", "nombre": "..."}]
    codigos_impuesto: list[dict],      # [{"cod": "1", "porcentaje": 19.0, "naturaleza": "IVA"}]
    tipo_proveedor: str = "juridica",
    cuentas_pago: list[dict] | None = None,  # [{"codigo": "22050501", "nombre": "..."}]
    modelo: str = _MODELO_DEFAULT,
) -> SugerenciaIA | None:
    """
    Sugiere cuenta de gasto y código de impuesto para un ítem de factura.

    Retorna:
        SugerenciaIA  si la IA respondió correctamente
        None          si IA no disponible, key no configurada o error (falla silenciosa)

    La función NUNCA lanza excepción: degradación segura garantizada.
    """
    if not esta_disponible():
        return None

    if not descripcion or not descripcion.strip():
        return None

    # Guard 1: prompt injection
    if _detectar_inyeccion(descripcion):
        logger.warning(
            "ai_service: posible prompt injection detectado en descripcion — omitida. "
            "Primeros 80 chars: %r", descripcion[:80]
        )
        return None

    # Guard 2: rate limit de sesión
    if not _verificar_rate_limit():
        return None

    # Guard 3: sanitizar PII antes de enviar al modelo
    descripcion_segura = _sanitizar_descripcion(descripcion)

    try:
        return _llamar_openai(
            descripcion_segura,
            cuentas_gasto,
            codigos_impuesto,
            tipo_proveedor,
            cuentas_pago,
            modelo,
        )
    except Exception as exc:
        logger.warning("ai_service.sugerir falló (ignorado, flujo continúa): %s", exc)
        return None


# Ítems por llamada: balance entre round-trips y tokens de output generados.
# 1 sola llamada × 86 ítems → ~7700 tokens secuenciales ≈ 30s.
# 6 llamadas × 15 ítems en paralelo → ~1050 tokens c/u ≈ 3-5s.
_BATCH_CHUNK_SIZE = 15


def sugerir_batch(
    items: list[dict],
    cuentas_gasto: list[dict],
    codigos_impuesto: list[dict],
    cuentas_pago: list[dict] | None = None,
    ejemplos_aprendizaje: list[dict] | None = None,
    modelo: str = _MODELO_DEFAULT,
) -> dict[str, "SugerenciaIA | None"]:
    """
    Clasifica ítems dividiendo en chunks de ~15 y disparándolos en paralelo.
    Deduplica por (descripcion, tipo_proveedor). Retorna dict[key → SugerenciaIA | None].
    Nunca lanza excepción.
    """
    if not esta_disponible() or not items:
        return {item["key"]: None for item in items}

    # --- Deduplicar ---
    combo_to_keys: dict[tuple, list[str]] = {}
    for item in items:
        desc = _sanitizar_descripcion(item.get("descripcion") or "")
        tipo = item.get("tipo_proveedor") or None
        nombre_prov = (item.get("nombre_proveedor") or "")[:80]
        if not desc:
            continue
        if _detectar_inyeccion(desc):
            logger.warning("sugerir_batch: injection detectado en %r — omitido", desc[:80])
            continue
        combo = (desc, tipo, nombre_prov)
        combo_to_keys.setdefault(combo, []).append(item["key"])

    if not combo_to_keys:
        return {item["key"]: None for item in items}

    combo_list = list(combo_to_keys.keys())
    api_key    = _get_api_key()

    chunks = [
        combo_list[i: i + _BATCH_CHUNK_SIZE]
        for i in range(0, len(combo_list), _BATCH_CHUNK_SIZE)
    ]

    sug_por_combo: dict[tuple, SugerenciaIA] = {}

    if len(chunks) == 1:
        sug_por_combo.update(
            _procesar_chunk_batch(
                chunks[0], cuentas_gasto, codigos_impuesto, cuentas_pago, modelo, api_key,
                ejemplos_aprendizaje,
            )
        )
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=min(len(chunks), 6)) as executor:
            futures = {
                executor.submit(
                    _procesar_chunk_batch,
                    chunk, cuentas_gasto, codigos_impuesto, cuentas_pago, modelo, api_key,
                    ejemplos_aprendizaje,
                ): idx
                for idx, chunk in enumerate(chunks)
            }
            for future in as_completed(futures):
                try:
                    sug_por_combo.update(future.result())
                except Exception as exc:
                    logger.warning(
                        "sugerir_batch: chunk %d falló (ignorado): %s", futures[future], exc
                    )

    # --- Mapear de vuelta a keys ---
    result: dict[str, SugerenciaIA | None] = {item["key"]: None for item in items}
    for combo, keys in combo_to_keys.items():
        sug = sug_por_combo.get(combo)
        for key in keys:
            result[key] = sug

    return result


def _procesar_chunk_batch(
    chunk: list[tuple],
    cuentas_gasto: list[dict],
    codigos_impuesto: list[dict],
    cuentas_pago: list[dict] | None,
    modelo: str,
    api_key: str,
    ejemplos_aprendizaje: list[dict] | None = None,
) -> dict[tuple, SugerenciaIA]:
    """Procesa un chunk de combos en 1 llamada a la API."""
    codigos_gasto_validos = {c["codigo"] for c in cuentas_gasto}
    codigos_imp_validos   = {str(i["cod"]) for i in codigos_impuesto}
    codigos_pago_validos  = {c["codigo"] for c in (cuentas_pago or [])}

    try:
        client  = _OpenAI(api_key=api_key)
        prompt  = _construir_prompt_batch(chunk, cuentas_gasto, codigos_impuesto, cuentas_pago, ejemplos_aprendizaje)
        max_tok = min(2500, max(600, 150 * len(chunk)))

        response = client.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tok,
            response_format={"type": "json_object"},
        )

        if response.usage:
            _registrar_tokens(response.usage.total_tokens)

        raw = json.loads(response.choices[0].message.content)
        resultados_raw: list[dict] = raw.get("resultados", [])

    except Exception as exc:
        logger.warning("_procesar_chunk_batch falló: %s", exc)
        return {}

    sug_parcial: dict[tuple, SugerenciaIA] = {}
    for r in resultados_raw:
        idx = int(r.get("indice", 0)) - 1  # 1-based → 0-based
        if idx < 0 or idx >= len(chunk):
            continue
        combo = chunk[idx]

        cuenta_gasto = r.get("cuenta_gasto") or None
        cod_impuesto = r.get("cod_impuesto") or None
        cuenta_pago  = (r.get("cuenta_pago") or None) if cuentas_pago else None
        confianza    = float(r.get("confianza", 0.0))
        explicacion  = str(r.get("explicacion", ""))[:100]

        if cuenta_gasto and cuenta_gasto not in codigos_gasto_validos:
            logger.warning("chunk_batch: cuenta_gasto inválida %s — descartada", cuenta_gasto)
            cuenta_gasto = None
            confianza    = min(confianza, 0.3)

        if cod_impuesto and str(cod_impuesto) not in codigos_imp_validos:
            cod_impuesto = None

        if cuenta_pago and cuenta_pago not in codigos_pago_validos:
            cuenta_pago = None

        sug_parcial[combo] = SugerenciaIA(
            cuenta_gasto=cuenta_gasto,
            cod_impuesto=cod_impuesto,
            cuenta_pago=cuenta_pago,
            confianza=max(0.0, min(1.0, confianza)),
            explicacion=explicacion,
            origen="ia",
            modelo=modelo,
        )

    return sug_parcial


# ── Lógica interna ────────────────────────────────────────────────────────────

def _construir_prompt(
    descripcion: str,
    cuentas_gasto: list[dict],
    codigos_impuesto: list[dict],
    tipo_proveedor: str,
    cuentas_pago: list[dict] | None = None,
) -> str:
    cuentas_rankeadas = _rankear_cuentas(cuentas_gasto, [descripcion])
    cuentas_str = "\n".join(
        f"  {c['codigo']} - {c['nombre']}"
        for c in cuentas_rankeadas
    )
    impuestos_str = "\n".join(
        f"  {i['cod']} - {i['naturaleza']} {i['porcentaje']}%"
        for i in codigos_impuesto
    )

    pago_section = ""
    cuenta_pago_json_field = ""
    if cuentas_pago:
        pago_str = "\n".join(
            f"  {c['codigo']} - {c['nombre']}"
            for c in cuentas_pago[:50]
        )
        pago_section = f"""
Cuentas de pago/acreedor disponibles (código - nombre):
{pago_str}
"""
        cuenta_pago_json_field = '\n  "cuenta_pago": "<código de la lista de pago o null>",'

    return f"""Eres un experto en contabilidad colombiana bajo el PUC (Decreto 2650). \
Clasificas ítems de facturas DIAN para causación en SIIGO.

Ítem de factura: "{descripcion}"
Tipo de proveedor: {tipo_proveedor if tipo_proveedor else "desconocido"}

REGLAS DE CLASIFICACIÓN (en orden de prioridad):
- Materiales construcción, ferreterías, cemento, varillas, tubería, madera, cable → materiales/suministros. NUNCA papelería.
- Papelería, resmas, tóner, útiles de oficina → útiles y papelería.
- Honorarios, asesoría, consultoría, servicios profesionales → honorarios.
- Arrendamiento, alquiler, canon → arrendamiento.
- Servicios públicos, vigilancia, aseo, internet → servicios.
- Mantenimiento, reparación, repuestos → mantenimiento.
- Si ninguna cuenta coincide con el tipo real del ítem → null con confianza < 0.4.
  NO uses papelería como opción por defecto.

Cuentas PUC de gasto disponibles (código - nombre):
{cuentas_str}

Códigos de impuesto disponibles (código - tipo - tarifa):
{impuestos_str}
{pago_section}
Responde ÚNICAMENTE en este formato JSON exacto:
{{{cuenta_pago_json_field}
  "cuenta_gasto": "<código de 8 dígitos de la lista o null>",
  "cod_impuesto": "<código de impuesto de la lista o null>",
  "confianza": <número entre 0.0 y 1.0>,
  "explicacion": "<razón breve en español, máximo 80 caracteres>"
}}

Reglas adicionales:
- Usa SOLO códigos de las listas. Nunca inventes códigos.
- confianza >= 0.8 solo si la cuenta coincide claramente con el tipo del ítem.
- Responde solo con el JSON."""


def _llamar_openai(
    descripcion: str,
    cuentas_gasto: list[dict],
    codigos_impuesto: list[dict],
    tipo_proveedor: str,
    cuentas_pago: list[dict] | None,
    modelo: str,
) -> SugerenciaIA:
    api_key = _get_api_key()
    client = _OpenAI(api_key=api_key)

    prompt = _construir_prompt(descripcion, cuentas_gasto, codigos_impuesto, tipo_proveedor, cuentas_pago)

    response = client.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,            # determinismo máximo para contabilidad
        max_tokens=200,
        response_format={"type": "json_object"},
    )

    # Fase 4: registrar tokens consumidos para tracking de costo
    if response.usage:
        _registrar_tokens(response.usage.total_tokens)

    raw = json.loads(response.choices[0].message.content)

    # Validar que los códigos sugeridos existen en las listas originales
    codigos_gasto_validos = {c["codigo"] for c in cuentas_gasto}
    codigos_imp_validos   = {str(i["cod"]) for i in codigos_impuesto}
    codigos_pago_validos  = {c["codigo"] for c in (cuentas_pago or [])}

    cuenta_gasto  = raw.get("cuenta_gasto")
    cod_impuesto  = raw.get("cod_impuesto")
    cuenta_pago   = raw.get("cuenta_pago") if cuentas_pago else None
    confianza     = float(raw.get("confianza", 0.0))
    explicacion   = str(raw.get("explicacion", ""))[:100]

    # Rechazar códigos inventados por el modelo
    if cuenta_gasto and cuenta_gasto not in codigos_gasto_validos:
        logger.warning("IA sugirió cuenta_gasto no válida: %s — descartada", cuenta_gasto)
        cuenta_gasto = None
        confianza    = min(confianza, 0.3)

    if cod_impuesto and str(cod_impuesto) not in codigos_imp_validos:
        logger.warning("IA sugirió cod_impuesto no válido: %s — descartado", cod_impuesto)
        cod_impuesto = None

    if cuenta_pago and cuenta_pago not in codigos_pago_validos:
        logger.warning("IA sugirió cuenta_pago no válida: %s — descartada", cuenta_pago)
        cuenta_pago = None

    return SugerenciaIA(
        cuenta_gasto=cuenta_gasto,
        cod_impuesto=cod_impuesto,
        cuenta_pago=cuenta_pago,
        confianza=max(0.0, min(1.0, confianza)),
        explicacion=explicacion,
        origen="ia",
        modelo=modelo,
    )


def _construir_prompt_batch(
    combos: list[tuple],
    cuentas_gasto: list[dict],
    codigos_impuesto: list[dict],
    cuentas_pago: list[dict] | None = None,
    ejemplos_aprendizaje: list[dict] | None = None,
) -> str:
    # Rankear cuentas por relevancia a los ítems del chunk (desc + nombre proveedor)
    descripciones = [f"{desc} {nombre_prov}" for desc, _tipo, nombre_prov in combos]
    cuentas_rankeadas = _rankear_cuentas(cuentas_gasto, descripciones)

    cuentas_str = "\n".join(
        f"  {c['codigo']} - {c['nombre']}"
        for c in cuentas_rankeadas
    )
    impuestos_str = "\n".join(
        f"  {i['cod']} - {i['naturaleza']} {i['porcentaje']}%"
        for i in codigos_impuesto
    )

    pago_section = ""
    cuenta_pago_field = ""
    if cuentas_pago:
        pago_str = "\n".join(f"  {c['codigo']} - {c['nombre']}" for c in cuentas_pago[:50])
        pago_section = f"\nCuentas de pago/acreedor disponibles:\n{pago_str}\n"
        cuenta_pago_field = '\n      "cuenta_pago": "<código de la lista de pago o null>",'

    # Sección de ejemplos aprendidos — vacía para usuarios nuevos, crece con el uso
    ejemplos_section = ""
    if ejemplos_aprendizaje:
        # Seleccionar los ejemplos más relevantes a los ítems de este chunk
        tokens_chunk = set()
        for desc in [f"{d} {n}" for d, _t, n in combos]:
            tokens_chunk.update(
                t for t in re.findall(r"[a-záéíóúñ]{3,}", desc.lower())
                if t not in _STOP_WORDS_ES
            )

        def _relevancia_ejemplo(e: dict) -> int:
            nombre_e = e["descripcion"].lower()
            return sum(1 for t in tokens_chunk if t in nombre_e)

        ordenados = sorted(ejemplos_aprendizaje, key=_relevancia_ejemplo, reverse=True)
        top = ordenados[:25]  # máximo 25 ejemplos en el prompt

        if top:
            lineas = "\n".join(
                f'  "{e["descripcion"][:80]}" → {e["cuenta"]}'
                + (f' ({e["nombre_cuenta"][:40]})' if e.get("nombre_cuenta") else "")
                for e in top
            )
            ejemplos_section = f"""
Decisiones previas de esta empresa (úsalas como guía principal):
{lineas}

"""

    items_str = "\n".join(
        f'{i + 1}. descripcion="{desc}"'
        + (f', proveedor="{nombre_prov}"' if nombre_prov else "")
        + (f', tipo_proveedor="{tipo}"' if tipo else "")
        for i, (desc, tipo, nombre_prov) in enumerate(combos)
    )
    n = len(combos)

    return f"""Eres un experto en contabilidad colombiana bajo el PUC (Decreto 2650). \
Clasificas ítems de facturas electrónicas DIAN para causación en SIIGO.
{ejemplos_section}REGLAS DE CLASIFICACIÓN PUC (aplica cuando no hay ejemplo previo):
1. Materiales de construcción, ferreterías, cemento, varillas, arena, tubería, madera, pintura, cable → cuenta de materiales/suministros/construcción. NUNCA papelería.
2. Papelería, resmas, tóner, útiles de oficina, bolígrafos → cuenta de útiles y papelería.
3. Honorarios, asesorías, consultoría, servicios profesionales → cuenta de honorarios.
4. Arrendamiento, alquiler, canon → cuenta de arrendamiento.
5. Servicios públicos (agua, luz, gas, teléfono, internet), vigilancia, aseo → cuenta de servicios.
6. Mantenimiento, reparación, repuestos → cuenta de mantenimiento y reparaciones.
7. Combustibles, gasolina, ACPM, lubricantes → cuenta de combustibles.
8. Seguros, pólizas, ARL → cuenta de seguros.
9. Si no hay cuenta específica, retorna null con confianza < 0.4. NO uses papelería como comodín.

Cuentas PUC de gasto disponibles (código - nombre):
{cuentas_str}

Códigos de impuesto disponibles (código - tipo - tarifa):
{impuestos_str}
{pago_section}
Clasifica CADA uno de los siguientes {n} ítems:

{items_str}

Responde ÚNICAMENTE con este JSON exacto con {n} elementos en "resultados":
{{
  "resultados": [
    {{
      "indice": 1,{cuenta_pago_field}
      "cuenta_gasto": "<código de 8 dígitos de la lista o null>",
      "cod_impuesto": "<código de la lista o null>",
      "confianza": <0.0 a 1.0>,
      "explicacion": "<razón breve en español, máx 60 chars>"
    }},
    ...
  ]
}}

Reglas adicionales:
- Incluye exactamente {n} objetos en "resultados", uno por ítem en el mismo orden.
- Usa SOLO códigos de la lista. Nunca inventes códigos.
- Si hay un ejemplo previo para un ítem similar, priorízalo sobre las reglas genéricas.
- confianza >= 0.8 solo si la cuenta coincide claramente con el tipo de ítem.
- tipo_proveedor "juridica" = empresa; "natural" = persona natural. Afecta cuenta_pago."""
