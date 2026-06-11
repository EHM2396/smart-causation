"""
ai_service.py – Capa de inteligencia artificial para clasificación de ítems.

Modo operación: FASE 2 (preselección por alta confianza)
  - Con alta confianza: preselecciona cuenta/impuesto directamente en UI.
  - Con confianza media: muestra sugerencia pero no impone selección.
  - Si la API key no está disponible o falla, retorna None silenciosamente.

Hardening de Fase 4:
  1. Sanitización de PII — limpia NITs, teléfonos, emails y montos antes de enviar
  2. Detección de prompt injection — rechaza descripciones con patrones sospechosos
  3. Rate limiter por sesión — máx. 60 llamadas por sesión de usuario
  4. Tracking de tokens — acumula uso en session_state para auditoría y costo
  5. Métricas de sesión — get_estadisticas_sesion() expone stats a la UI

Datos enviados al modelo (minimizados, sin PII):
  - Descripción del ítem sanitizada (sin NITs, teléfonos, emails ni montos)
  - Lista de cuentas PUC disponibles (código + nombre)
  - Lista de códigos de impuesto disponibles (código + tipo + tarifa)
  - Tipo de proveedor: "juridica" | "natural"  ← sin NIT ni razón social

Modelo por defecto: gpt-4o-mini
  - Costo bajo, alta calidad para clasificación contable
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

# Máximo de cuentas enviadas al modelo para no exceder tokens
_MAX_CUENTAS_PROMPT = 100

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


# ── Tipos de retorno ──────────────────────────────────────────────────────────

@dataclass
class SugerenciaIA:
    """Resultado de la sugerencia del modelo. Siempre debe revisarse antes de aplicar."""
    cuenta_gasto: str | None = None
    cod_impuesto: str | None = None
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
    cuentas_gasto: list[dict],    # [{"codigo": "51950501", "nombre": "..."}]
    codigos_impuesto: list[dict], # [{"cod": "1", "porcentaje": 19.0, "naturaleza": "IVA"}]
    tipo_proveedor: str = "juridica",
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
            modelo,
        )
    except Exception as exc:
        logger.warning("ai_service.sugerir falló (ignorado, flujo continúa): %s", exc)
        return None


# ── Lógica interna ────────────────────────────────────────────────────────────

def _construir_prompt(
    descripcion: str,
    cuentas_gasto: list[dict],
    codigos_impuesto: list[dict],
    tipo_proveedor: str,
) -> str:
    cuentas_str = "\n".join(
        f"  {c['codigo']} - {c['nombre']}"
        for c in cuentas_gasto[:_MAX_CUENTAS_PROMPT]
    )
    impuestos_str = "\n".join(
        f"  {i['cod']} - {i['naturaleza']} {i['porcentaje']}%"
        for i in codigos_impuesto
    )

    return f"""Eres un asistente de contabilidad colombiana especializado en causación \
de facturas electrónicas DIAN para importar a SIIGO.

Ítem de factura: "{descripcion}"
Tipo de proveedor: {tipo_proveedor}

Cuentas PUC de gasto disponibles (código - nombre):
{cuentas_str}

Códigos de impuesto disponibles (código - tipo - tarifa):
{impuestos_str}

Responde ÚNICAMENTE en este formato JSON exacto, sin texto adicional:
{{
  "cuenta_gasto": "<código de 8 dígitos de la lista o null>",
  "cod_impuesto": "<código de impuesto de la lista o null>",
  "confianza": <número entre 0.0 y 1.0>,
  "explicacion": "<razón breve en español, máximo 80 caracteres>"
}}

Reglas estrictas:
- Usa SOLO códigos de las listas proporcionadas. Nunca inventes códigos.
- confianza >= 0.8 solo si estás muy seguro de la clasificación.
- Si el ítem no coincide claramente con ninguna cuenta, usa null y baja confianza.
- Responde solo con el JSON, sin explicaciones fuera del JSON."""


def _llamar_openai(
    descripcion: str,
    cuentas_gasto: list[dict],
    codigos_impuesto: list[dict],
    tipo_proveedor: str,
    modelo: str,
) -> SugerenciaIA:
    api_key = _get_api_key()
    client = _OpenAI(api_key=api_key)

    prompt = _construir_prompt(descripcion, cuentas_gasto, codigos_impuesto, tipo_proveedor)

    response = client.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,            # determinismo máximo para contabilidad
        max_tokens=150,
        response_format={"type": "json_object"},
    )

    # Fase 4: registrar tokens consumidos para tracking de costo
    if response.usage:
        _registrar_tokens(response.usage.total_tokens)

    raw = json.loads(response.choices[0].message.content)

    # Validar que los códigos sugeridos existen en las listas originales
    codigos_gasto_validos = {c["codigo"] for c in cuentas_gasto}
    codigos_imp_validos   = {str(i["cod"]) for i in codigos_impuesto}

    cuenta_gasto  = raw.get("cuenta_gasto")
    cod_impuesto  = raw.get("cod_impuesto")
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

    return SugerenciaIA(
        cuenta_gasto=cuenta_gasto,
        cod_impuesto=cod_impuesto,
        confianza=max(0.0, min(1.0, confianza)),
        explicacion=explicacion,
        origen="ia",
        modelo=modelo,
    )
