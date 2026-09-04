"""
Servicio de integración con el portal de Facturación Electrónica de la DIAN.

Permite, a partir de una URL AuthToken que el usuario obtiene tras autenticarse
él mismo en el portal DIAN, consultar sus facturas RECIBIDAS en un rango de
fechas y traer los XML EN MEMORIA (sin descargarlos a disco) para pasarlos por
el parser de causación.

Importante:
  - No se evade ningún control anti-bot: el usuario pasa el login/captcha como
    humano y solo entrega el token resultante.
  - El token y las cookies de sesión viven SOLO en el backend, de forma temporal
    (stateless: se re-autentica en cada request). No se persisten ni se loguean.

Portado de dian_script.py (CLI) a un servicio reutilizable por la API.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse, parse_qs

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# ── Endpoints DIAN ────────────────────────────────────────────────────────────
AUTH_URL_BASE = "https://catalogo-vpfe.dian.gov.co/User/AuthToken"
BILLER_BASE = "https://gratis-vpfe.dian.gov.co"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9",
}

_TIMEOUT = 30


def _nueva_sesion() -> requests.Session:
    """Sesión con reintentos automáticos rápidos ante fallos transitorios de red/DNS
    (p.ej. NameResolutionError) o respuestas 5xx. Los reintentos son silenciosos y
    cortos; si el problema persiste, la excepción sube y se muestra al usuario."""
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,        # cubre fallos de conexión y de resolución DNS
        read=1,
        backoff_factor=0.5,   # esperas 0s, 0.5s, 1s entre intentos
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ── Caché de sesión DIAN (en memoria, temporal) ───────────────────────────────
# Guarda la sesión autenticada (cookies + CurrentAccountId) por unos minutos,
# indexada por el token, para NO re-autenticar entre "consultar" y "traer".
# Es temporal y se descarta al expirar (no persiste el token en disco/BD).
_SESSION_CACHE: dict[str, tuple[float, requests.Session, str]] = {}
_SESSION_TTL = 600.0  # 10 minutos (dentro de la vida del token, ~1h)


def _sesion_para(auth_url: str) -> tuple[requests.Session, str]:
    """Devuelve (session, CurrentAccountId) reutilizando la sesión cacheada del
    token si existe y sigue vigente; si no, autentica una vez y la cachea."""
    pk, rk, token = extraer_token_url(auth_url)
    ahora = time.time()
    # Limpiar entradas expiradas
    for k in [k for k, v in _SESSION_CACHE.items() if v[0] <= ahora]:
        _SESSION_CACHE.pop(k, None)
    cached = _SESSION_CACHE.get(token)
    if cached:
        return cached[1], cached[2]
    session, account_id = _crear_sesion_autenticada(pk, rk, token)
    _SESSION_CACHE[token] = (ahora + _SESSION_TTL, session, account_id)
    return session, account_id


def _evict(auth_url: str) -> None:
    """Descarta la sesión cacheada de este token (p.ej. si la DIAN la invalidó),
    para forzar una re-autenticación limpia en el próximo intento."""
    try:
        _, _, token = extraer_token_url(auth_url)
        _SESSION_CACHE.pop(token, None)
    except DianError:
        pass


# ── Errores estructurados ─────────────────────────────────────────────────────

class DianError(Exception):
    """Error de negocio del flujo DIAN. `code` sirve para mapear a HTTP/UI."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# ── Utilidades ────────────────────────────────────────────────────────────────

def extraer_token_url(url: str) -> tuple[str, str, str]:
    """Extrae (pk, rk, token) de una URL /User/AuthToken. Lanza DianError si es inválida."""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        raise DianError("TOKEN_INVALID", "La URL de AuthToken no es válida.")

    if parsed.netloc.lower() != "catalogo-vpfe.dian.gov.co":
        raise DianError("TOKEN_INVALID", "La URL no pertenece a catalogo-vpfe.dian.gov.co")
    if parsed.path.rstrip("/") != "/User/AuthToken":
        raise DianError("TOKEN_INVALID", "La URL debe apuntar a /User/AuthToken")

    params = parse_qs(parsed.query)
    pk = params.get("pk", [None])[0]
    rk = params.get("rk", [None])[0]
    token = params.get("token", [None])[0]
    if not (pk and rk and token):
        raise DianError("TOKEN_INVALID", "La URL de AuthToken está incompleta (faltan pk/rk/token).")
    return pk, rk, token


def _token_expirado(response: requests.Response) -> bool:
    """La DIAN puede responder HTTP 200 con un HTML de login si el token expiró."""
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        el = soup.find("span", attrs={"data-valmsg-for": "CompanyLoginFailed"})
        if el and "token expirado" in el.get_text(" ", strip=True).lower():
            return True
    except Exception:
        pass
    return "token expirado" in (response.text or "").lower()


def _crear_sesion_autenticada(pk: str, rk: str, token: str) -> tuple[requests.Session, str]:
    """
    Autentica contra la DIAN y devuelve (session con cookies, CurrentAccountId).
    Lanza DianError('TOKEN_EXPIRED' | 'SESSION_EXPIRED' | 'CONNECTION_ERROR').
    """
    session = _nueva_sesion()
    try:
        # 1) AuthToken → establece cookies de sesión
        resp = session.get(
            AUTH_URL_BASE,
            params={"pk": pk, "rk": rk, "token": token},
            headers=_HEADERS,
            allow_redirects=True,
            timeout=_TIMEOUT,
        )
        if _token_expirado(resp):
            raise DianError("TOKEN_EXPIRED", "Token expirado, por favor genera uno nuevo en la DIAN.")
        if resp.status_code >= 400:
            raise DianError("SESSION_EXPIRED", f"La DIAN rechazó la autenticación (HTTP {resp.status_code}).")

        # 2) Redirigir al portal de facturación gratuita
        catalogo_base = AUTH_URL_BASE.rsplit("/User/AuthToken", 1)[0]
        session.get(
            f"{catalogo_base}/User/RedirectToBiller",
            headers=_HEADERS,
            allow_redirects=True,
            timeout=_TIMEOUT,
        )

        # 3) Obtener CurrentAccountId desde Document/Received
        account_id = _obtener_account_id(session)
        return session, account_id
    except DianError:
        raise
    except requests.RequestException:
        raise DianError("CONNECTION_ERROR", "No se pudo conectar con la DIAN (problema de red temporal).")


def _obtener_account_id(session: requests.Session) -> str:
    resp = session.get(f"{BILLER_BASE}/Document/Received", headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    campo = soup.find("input", attrs={"name": "CurrentAccountId"}) or soup.find(
        "input", attrs={"id": "CurrentAccountId"}
    )
    if campo and campo.get("value"):
        return campo["value"]
    # Si no aparece, lo más probable es que la sesión no quedó autenticada.
    raise DianError(
        "SESSION_EXPIRED",
        "No se pudo iniciar sesión con la DIAN (token inválido o sesión expirada).",
    )


def _get_received(session: requests.Session, account_id: str, desde: str, hasta: str) -> dict:
    """Aplica el rango de fechas y pide la lista JSON de documentos recibidos."""
    received_url = f"{BILLER_BASE}/Document/Received"

    # 1) POST que aplica los filtros de fecha en la vista
    session.post(
        received_url,
        data={
            "CurrentAccountId": account_id,
            "DocumentTypeId": "", "SenderName": "", "SenderCode": "",
            "StatusId": "", "Serie": "",
            "From": desde, "To": hasta,
        },
        headers={**_HEADERS, "Referer": received_url},
        timeout=_TIMEOUT,
    )

    # 2) POST DataTables → JSON
    data = {
        "draw": "1", "start": "0", "length": "150",
        "search[value]": "", "search[regex]": "false",
        "order[0][column]": "3", "order[0][dir]": "desc",
        "blockIndex": "0", "inBlockStart": "0",
        "IsNextPage": "true", "PageCurrentCosmos": "0",
        "CurrentAccountId": account_id,
        "columns[0][data]": "DocumentType",
        "columns[1][data]": "DocumentNumber",
        "columns[2][data]": "SenderName",
        "columns[3][data]": "DocumentDate",
    }
    resp = session.post(
        f"{BILLER_BASE}/Document/GetReceivedDocuments",
        data=data,
        headers={**_HEADERS, "Referer": received_url, "X-Requested-With": "XMLHttpRequest"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        # Si devuelve HTML en vez de JSON, la sesión dejó de estar autenticada.
        raise DianError("SESSION_EXPIRED", "La sesión con la DIAN expiró. Autentícate nuevamente.")


def _limpiar_html(valor) -> str:
    """La DIAN a veces envuelve valores en HTML (p.ej. la fecha en un <span>).
    Quita etiquetas y espacios sobrantes."""
    return re.sub(r"<[^>]+>", "", str(valor or "")).strip()


def _normalizar_documentos(resultado: dict) -> list[dict]:
    docs = []
    for d in resultado.get("data", []) or []:
        docs.append({
            "id": d.get("DT_RowId"),
            "numero": _limpiar_html(d.get("docNumber") or d.get("DocumentNumber") or ""),
            "fecha": _limpiar_html(d.get("docDate") or d.get("DocumentDate") or ""),
            "proveedor": _limpiar_html(d.get("senderName") or d.get("SenderName") or ""),
            "tipo": _limpiar_html(d.get("documentType") or d.get("DocumentType") or ""),
        })
    return docs


# ── API pública del servicio ──────────────────────────────────────────────────

def consultar_documentos(auth_url: str, fecha_desde: str, fecha_hasta: str) -> dict:
    """
    Consulta las facturas recibidas en el rango [desde, hasta] (formato DD/MM/YYYY).
    Retorna {'success', 'total', 'documents': [{id, numero, fecha, proveedor, tipo}]}.
    Lanza DianError en caso de token/sesión/conexión.
    """
    session, account_id = _sesion_para(auth_url)
    try:
        resultado = _get_received(session, account_id, fecha_desde, fecha_hasta)
    except DianError as e:
        if e.code == "SESSION_EXPIRED":
            _evict(auth_url)  # sesión cacheada muerta → re-autenticar en el próximo intento
        raise
    except requests.RequestException:
        raise DianError("CONNECTION_ERROR", "No se pudo conectar con la DIAN (problema de red temporal).")
    docs = _normalizar_documentos(resultado)
    return {"success": True, "total": len(docs), "documents": docs}


def descargar_xmls(auth_url: str, ids: list[str]) -> list[dict]:
    """
    Descarga EN MEMORIA los XML de los `ids` indicados (DT_RowId/transactionId).
    Retorna [{'id': str, 'xml': bytes}]. No escribe nada en disco.
    Lanza DianError en caso de token/sesión/conexión.
    """
    session, _account_id = _sesion_para(auth_url)
    salida: list[dict] = []
    try:
        for transaction_id in ids:
            if not transaction_id:
                continue
            resp = session.get(
                f"{BILLER_BASE}/Document/DownloadXml",
                params={"transactionId": transaction_id, "type": "2"},
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            contenido = resp.content
            # Si volvió HTML (login), la sesión expiró.
            if contenido[:15].lstrip().lower().startswith(b"<!doctype html") or b"CompanyLoginFailed" in contenido[:2000]:
                raise DianError("SESSION_EXPIRED", "La sesión con la DIAN expiró durante la descarga.")
            salida.append({"id": transaction_id, "xml": contenido})
    except DianError:
        raise
    except requests.RequestException:
        raise DianError("CONNECTION_ERROR", "No se pudo conectar con la DIAN (problema de red temporal).")
    return salida


def descargar_xmls_stream(auth_url: str, ids: list[str]):
    """
    Igual que descargar_xmls pero es un GENERADOR: autentica una vez y va
    entregando cada XML a medida que lo descarga, para poder informar progreso
    real al frontend. Cada yield es (done, total, id, xml_bytes).
    """
    session, _account_id = _sesion_para(auth_url)
    limpios = [x for x in ids if x]
    total = len(limpios)
    for i, transaction_id in enumerate(limpios, 1):
        try:
            resp = session.get(
                f"{BILLER_BASE}/Document/DownloadXml",
                params={"transactionId": transaction_id, "type": "2"},
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            contenido = resp.content
            if contenido[:15].lstrip().lower().startswith(b"<!doctype html") or b"CompanyLoginFailed" in contenido[:2000]:
                raise DianError("SESSION_EXPIRED", "La sesión con la DIAN expiró durante la descarga.")
        except DianError as e:
            if e.code == "SESSION_EXPIRED":
                _evict(auth_url)  # sesión cacheada muerta → re-autenticar en el próximo intento
            raise
        except requests.RequestException:
            raise DianError("CONNECTION_ERROR", "No se pudo conectar con la DIAN (problema de red temporal).")
        yield i, total, transaction_id, contenido


def nombre_para_parser(contenido: bytes, id_: str) -> str:
    """
    El parser de causación enruta por extensión. Detecta si el contenido es ZIP
    (magic 'PK') o XML para asignar el nombre correcto.
    """
    if contenido[:2] == b"PK":
        return f"{id_}.zip"
    return f"{id_}.xml"
