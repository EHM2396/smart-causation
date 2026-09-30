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
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# ── Endpoints DIAN ────────────────────────────────────────────────────────────
AUTH_URL_BASE = "https://catalogo-vpfe.dian.gov.co/User/AuthToken"
BILLER_BASE = "https://gratis-vpfe.dian.gov.co"
# Portal "catálogo": ahí viven los documentos soporte (GetDocumentsPageToken) y su
# descarga en ZIP (GetFilePdf). La sesión conserva las cookies de este dominio
# desde el GET inicial de AuthToken, así que se puede consultar sin re-autenticar.
CATALOGO_BASE = "https://catalogo-vpfe.dian.gov.co"

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


def solo_digitos(nit: str | None) -> str:
    return re.sub(r"[^0-9]", "", nit or "")


def nits_equivalentes(a: str | None, b: str | None) -> bool:
    """¿Dos NIT son el mismo? Tolera el dígito de verificación.

    En Colombia el NIT son 9 dígitos más uno de verificación, y cada fuente lo
    escribe distinto: '901694417', '901694417-1', '9016944171'. Comparar los
    textos tal cual daría "no coinciden" para el mismo NIT, así que si uno trae
    un dígito de más se compara sin él.
    """
    a, b = solo_digitos(a), solo_digitos(b)
    if not a or not b:
        return False
    if a == b:
        return True
    # Solo se acepta el dígito de más como verificación si lo que queda sigue
    # siendo un NIT plausible (9 dígitos o más). Si no, '901694417' y '90169441'
    # pasarían por el mismo NIT y son dos contribuyentes distintos.
    largo, corto = (a, b) if len(a) > len(b) else (b, a)
    if len(largo) == len(corto) + 1 and len(corto) >= 9:
        return largo[:-1] == corto
    return False


def nit_del_token(auth_url: str) -> str:
    """NIT del titular del token, que la DIAN pone en el parámetro `rk` de la URL
    de AuthToken. Permite avisar que el token no corresponde a la empresa
    seleccionada ANTES de descargar nada."""
    _pk, rk, _token = extraer_token_url(auth_url)
    return solo_digitos(rk)


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
            raise DianError(
                "TOKEN_EXPIRED",
                "El enlace de la DIAN ya no sirve: solo dura una hora. "
                "Generá uno nuevo en el portal de la DIAN y volvé a intentar.",
            )
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


# Documentos por página en los listados DataTables de la DIAN.
_PAGINA = 150
# El listado de documentos soporte (catálogo) usa un tope de página distinto.
_PAGINA_SOPORTE = 100


def _paginar_datatables(
    session: requests.Session, url: str, data: dict, headers: dict,
    *, url_alias: str | None = None, max_paginas: int | None = None,
) -> dict:
    """Recorre las páginas de un listado de la DIAN (hasta `max_paginas`, o todas).

    La DIAN devuelve como máximo `length` documentos por respuesta y los ordena
    por fecha DESCENDENTE. Pedir una sola página parecía suficiente y no lo es:
    en un rango con más documentos que el tope, los MÁS VIEJOS quedan afuera en
    silencio —meses enteros aparecen vacíos, sin ningún error— y el usuario cree
    que no hubo movimiento. Se detectó con un rango de enero a septiembre donde
    dos meses salían en cero y, consultados aparte, sí traían documentos.

    OJO con el paginado por offset (`start += length`): el portal corre sobre
    Cosmos DB, que NO pagina de forma confiable por offset. Al pedir la 2.ª página
    el orden se re-baraja y quedan documentos afuera en silencio. Por eso la ÚNICA
    página confiable es la primera; el llamador que necesite exactitud usa
    ``max_paginas=1`` como sonda y, si la primera página vino llena, parte el rango
    de fechas (ver ``consultar_documentos_completo``) en vez de pedir la 2.ª.
    """
    todos: list[dict] = []
    total: int | None = None
    start = 0
    paginas = 0

    while True:
        pagina = {**data, "start": str(start), "length": str(_PAGINA)}
        resp = session.post(url, data=pagina, headers=headers, timeout=_TIMEOUT)
        if resp.status_code == 404 and url_alias:
            resp = session.post(url_alias, data=pagina, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        try:
            payload = resp.json()
        except ValueError:
            # Si devuelve HTML en vez de JSON, la sesión dejó de estar autenticada.
            raise DianError(
                "SESSION_EXPIRED",
                "El enlace de la DIAN venció (solo dura una hora). Lo que alcanzó a "
                "descargarse quedó guardado: generá un enlace nuevo y volvé a traer "
                "el mismo periodo para completar lo que falte.",
            )

        registros = payload.get("data") or []
        todos.extend(registros)
        paginas += 1
        if total is None:
            total = payload.get("recordsTotal") or payload.get("recordsFiltered") or len(registros)

        # Tope de páginas (modo sonda): frenar tras la 1.ª página, que es la única
        # confiable. Quien pide max_paginas=1 solo quiere saber si el rango cabe.
        if max_paginas is not None and paginas >= max_paginas:
            break
        # Condición de parada robusta:
        # 1. Página vacía → no hay más (señal definitiva).
        # 2. Ya tenemos todos los que la DIAN dijo que había.
        # 3. Página parcial SIN total conocido → asumir última página.
        # IMPORTANTE: si la DIAN reportó total > 0 y la página vino parcial
        # pero no vacía, se sigue intentando (la DIAN a veces devuelve páginas
        # intermedias con menos de `length` registros sin que sea la última).
        if len(registros) == 0:
            break
        if total is not None and len(todos) >= total:
            break
        if total is None and len(registros) < _PAGINA:
            break
        start += _PAGINA
        if start > 20_000:  # red de seguridad: nunca un bucle infinito
            break

    return {"data": todos, "recordsTotal": total or len(todos)}


def _get_received(session: requests.Session, account_id: str, desde: str, hasta: str,
                  *, max_paginas: int | None = None) -> dict:
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
    return _paginar_datatables(
        session,
        f"{BILLER_BASE}/Document/GetReceivedDocuments",
        data,
        {**_HEADERS, "Referer": received_url, "X-Requested-With": "XMLHttpRequest"},
        max_paginas=max_paginas,
    )


def _get_soporte(session: requests.Session, account_id: str, desde: str, hasta: str, doc_type_id: str = "05",
                 *, max_paginas: int | None = None) -> dict:
    """Documentos SOPORTE (tipo 05) y su Nota de Ajuste (tipo 95).

    Viven en el portal ``catalogo-vpfe`` y se consultan con
    ``/Document/GetDocumentsPageToken`` (FilterType=2 = emitidos, DocumentTypeId=05
    o 95), con fechas en ISO y el ``__RequestVerificationToken`` de la página de
    emitidos. Fallback: ``/Document/GetIssuedDocuments`` con ese DocumentTypeId.
    """
    try:
        iso_desde = datetime.strptime(desde, "%d/%m/%Y").strftime("%Y-%m-%d")
        iso_hasta = datetime.strptime(hasta, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        iso_desde, iso_hasta = desde, hasta

    # 1) __RequestVerificationToken desde la vista de emitidos del catálogo.
    sent_url = f"{CATALOGO_BASE}/Document/Sent"
    rv_token = ""
    try:
        r_sent = session.get(sent_url, headers=_HEADERS, timeout=_TIMEOUT)
        soup = BeautifulSoup(r_sent.text, "html.parser")
        inp = soup.find("input", {"name": "__RequestVerificationToken"})
        if inp:
            rv_token = inp.get("value", "") or ""
    except requests.RequestException:
        pass

    headers_ajax = {
        **_HEADERS,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": sent_url,
    }
    url_token = f"{CATALOGO_BASE}/Document/GetDocumentsPageToken"
    length = _PAGINA_SOPORTE
    all_records: list[dict] = []
    payload = {
        "draw": 1, "start": 0, "length": length,
        "DocumentKey": "", "SerieAndNumber": "", "SenderCode": "", "ReceiverCode": "",
        "StartDate": iso_desde, "EndDate": iso_hasta,
        "DocumentTypeId": doc_type_id, "Status": "0", "IsNextPage": "false",
        "FilterType": "2", "blockIndex": 0, "RadianStatus": "0",
        "ContinuationToken": "", "__RequestVerificationToken": rv_token,
    }
    try:
        res = session.post(url_token, data=payload, headers=headers_ajax, timeout=_TIMEOUT)
        if res.status_code == 200:
            data_json = res.json()
            records = data_json.get("data", []) or []
            total = data_json.get("recordsTotal", len(records))
            all_records.extend(records)
            start = 0
            while max_paginas is None and len(all_records) < total and len(records) >= length:
                start += length
                payload["start"] = start
                r = session.post(url_token, data=payload, headers=headers_ajax, timeout=_TIMEOUT)
                if r.status_code != 200:
                    break
                records = r.json().get("data", []) or []
                if not records:
                    break
                all_records.extend(records)
            if all_records:
                return {"data": all_records}
    except (requests.RequestException, ValueError):
        pass

    # 2) Fallback: GetIssuedDocuments (DocumentTypeId=05) en el biller gratuito.
    payload_issued = {
        "draw": "1", "start": "0", "length": "150",
        "fromDate": desde, "toDate": hasta,
        "DocumentTypeId": doc_type_id, "CurrentAccountId": account_id,
    }
    try:
        r2 = session.post(
            f"{BILLER_BASE}/Document/GetIssuedDocuments",
            data=payload_issued,
            headers={**headers_ajax, "Referer": f"{BILLER_BASE}/Document/Sent"},
            timeout=_TIMEOUT,
        )
        if r2.status_code == 200:
            return {"data": r2.json().get("data", []) or []}
    except (requests.RequestException, ValueError):
        pass
    return {"data": []}


def _get_issued(session: requests.Session, account_id: str, desde: str, hasta: str,
                *, max_paginas: int | None = None) -> dict:
    """Aplica el rango de fechas y pide la lista JSON de documentos EMITIDOS (ventas).

    Espejo de ``_get_received`` pero contra ``/Document/Sent`` +
    ``GetIssuedDocuments`` (con alias ``GetSentDocuments`` si la DIAN responde 404),
    usando ``ReceiverName`` (cliente) en las columnas.
    """
    sent_url = f"{BILLER_BASE}/Document/Sent"

    # 1) POST que aplica los filtros de fecha en la vista de emitidos
    session.post(
        sent_url,
        data={
            "CurrentAccountId": account_id,
            "DocumentTypeId": "", "ReceiverName": "", "ReceiverCode": "",
            "StatusId": "", "Serie": "",
            "From": desde, "To": hasta,
        },
        headers={**_HEADERS, "Referer": sent_url},
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
        "columns[2][data]": "ReceiverName",
        "columns[3][data]": "DocumentDate",
    }
    return _paginar_datatables(
        session,
        f"{BILLER_BASE}/Document/GetIssuedDocuments",
        data,
        {**_HEADERS, "Referer": sent_url, "X-Requested-With": "XMLHttpRequest"},
        url_alias=f"{BILLER_BASE}/Document/GetSentDocuments",
        max_paginas=max_paginas,
    )


def _limpiar_html(valor) -> str:
    """La DIAN a veces envuelve valores en HTML (p.ej. la fecha en un <span>).
    Quita etiquetas y espacios sobrantes."""
    return re.sub(r"<[^>]+>", "", str(valor or "")).strip()


def _fecha_dian(valor) -> str:
    """Normaliza fechas de la DIAN: convierte ``/Date(ms)/`` (formato .NET que usa
    GetDocumentsPageToken) a DD/MM/YYYY; el resto se limpia de HTML."""
    s = str(valor or "")
    m = re.search(r"/Date\((\d+)\)/", s)
    if m:
        try:
            return datetime.fromtimestamp(int(m.group(1)) / 1000.0).strftime("%d/%m/%Y")
        except Exception:
            return ""
    return _limpiar_html(s)


_CODIGOS_FACTURA = {"01", "02", "03", "04"}


def clase_del_listado(tipo: str) -> str:
    """Clase del documento según el texto/código ``DocumentType`` del listado:
    ``factura`` | ``nota_credito`` | ``nota_debito`` | ``desconocido``.

    Sirve para separar los conteos ANTES de descargar. Lo que no se reconozca
    queda ``desconocido`` y se descarga igual: el XML decide, así nunca se oculta
    un documento por un texto inesperado de la DIAN.
    """
    t = unicodedata.normalize("NFD", tipo or "").encode("ascii", "ignore").decode().lower().strip()
    if not t:
        return "desconocido"
    if t == "91" or "credito" in t:
        return "nota_credito"
    if t == "92" or "debito" in t:
        return "nota_debito"
    if t in _CODIGOS_FACTURA or "factura" in t:
        return "factura"
    return "desconocido"


def _normalizar_documentos(resultado: dict, modo: str = "compras") -> list[dict]:
    """Normaliza la respuesta DataTables de la DIAN. En ``compras`` la contraparte
    es el emisor (SenderName / proveedor); en ``ventas`` es el receptor
    (ReceiverName / cliente). El campo ``proveedor`` guarda la contraparte que
    corresponda para no romper el frontend existente."""
    modo_l = (modo or "compras").lower()
    docs = []
    for d in resultado.get("data", []) or []:
        if modo_l == "ventas":
            contraparte = d.get("receiverName") or d.get("ReceiverName") or ""
        elif modo_l in ("soporte", "soporte_ajuste"):
            # DS y su ajuste: la contraparte es el vendedor no obligado.
            contraparte = (d.get("receiverName") or d.get("ReceiverName")
                           or d.get("senderName") or d.get("SenderName") or "")
        else:
            contraparte = d.get("senderName") or d.get("SenderName") or ""
        # GetReceivedDocuments/GetIssuedDocuments lo mandan en ``docTypeName``.
        tipo = _limpiar_html(d.get("docTypeName") or d.get("documentType") or d.get("DocumentType") or "")
        docs.append({
            "id": d.get("DT_RowId") or d.get("Id") or d.get("DocumentKey"),
            "numero": _limpiar_html(d.get("docNumber") or d.get("DocumentNumber")
                                    or d.get("SerieAndNumber") or d.get("Number") or ""),
            "fecha": _fecha_dian(d.get("docDate") or d.get("DocumentDate") or d.get("EmissionDate") or ""),
            "proveedor": _limpiar_html(contraparte),
            "tipo": tipo,
            "clase": clase_del_listado(tipo),
        })
    return docs


# ── API pública del servicio ──────────────────────────────────────────────────

def _tope_pagina(modo: str) -> int:
    """Tope de documentos por página del listado según el módulo (soporte usa 100)."""
    return _PAGINA_SOPORTE if (modo or "").lower() in ("soporte", "soporte_ajuste") else _PAGINA


def consultar_documentos(auth_url: str, fecha_desde: str, fecha_hasta: str, modo: str = "compras",
                         *, max_paginas: int | None = None) -> dict:
    """
    Consulta las facturas del rango [desde, hasta] (formato DD/MM/YYYY).
      - ``modo='compras'`` → documentos RECIBIDOS (proveedores → tu NIT).
      - ``modo='ventas'``  → documentos EMITIDOS (tu empresa → clientes).
    Retorna {'success', 'total', 'documents': [{id, numero, fecha, proveedor, tipo}]}.
    Lanza DianError en caso de token/sesión/conexión.

    ``max_paginas=1`` la usa ``consultar_documentos_completo`` como sonda: trae solo
    la primera página (la única confiable en el paginado por offset de la DIAN).
    """
    modo_l = (modo or "compras").lower()
    session, account_id = _sesion_para(auth_url)
    try:
        if modo_l == "soporte":
            resultado = _get_soporte(session, account_id, fecha_desde, fecha_hasta, doc_type_id="05", max_paginas=max_paginas)
        elif modo_l == "soporte_ajuste":
            resultado = _get_soporte(session, account_id, fecha_desde, fecha_hasta, doc_type_id="95", max_paginas=max_paginas)
        elif modo_l == "ventas":
            resultado = _get_issued(session, account_id, fecha_desde, fecha_hasta, max_paginas=max_paginas)
        else:
            resultado = _get_received(session, account_id, fecha_desde, fecha_hasta, max_paginas=max_paginas)
    except DianError as e:
        if e.code == "SESSION_EXPIRED":
            _evict(auth_url)  # sesión cacheada muerta → re-autenticar en el próximo intento
        raise
    except requests.RequestException:
        raise DianError("CONNECTION_ERROR", "No se pudo conectar con la DIAN (problema de red temporal).")
    docs = _normalizar_documentos(resultado, modo=modo)
    total_dian = resultado.get("recordsTotal") or len(docs)
    incompleto = len(docs) < total_dian
    respuesta: dict = {
        "success": True,
        "total": len(docs),
        "total_dian": total_dian,
        "incompleto": incompleto,
        "documents": docs,
    }
    if incompleto:
        respuesta["advertencia"] = (
            f"⚠️ La DIAN reporta {total_dian} documentos en este periodo pero solo se "
            f"pudieron traer {len(docs)}. Esto ocurre cuando el rango de fechas es muy "
            f"amplio y el portal de la DIAN corta la respuesta. Importa en rangos más "
            f"pequeños (máximo 2 meses) para garantizar que no quede ningún documento fuera."
        )
    return respuesta


# Tope de seguridad de consultas en la auto-división: evita que un rango absurdo
# (o un token con muchísimos documentos) dispare miles de peticiones a la DIAN.
_MAX_CONSULTAS_BISECCION = 400
# Reintentos cuando una respuesta de la DIAN no cuadra (fechas de otro rango o
# mitades que no suman el total reportado).
_REINTENTOS_RANGO = 3


def _en_rango(doc: dict, d1, d2) -> bool:
    """¿La fecha del documento cae en [d1, d2]? Sin fecha legible se da por buena
    (no se descarta un documento solo porque la DIAN no mandó la fecha)."""
    try:
        f = datetime.strptime(doc.get("fecha") or "", "%d/%m/%Y").date()
    except ValueError:
        return True
    return d1 <= f <= d2


def consultar_documentos_completo(auth_url: str, fecha_desde: str, fecha_hasta: str, modo: str = "compras") -> dict:
    """Consulta el rango GARANTIZANDO que no se pierda ningún documento.

    El portal de la DIAN corre sobre Cosmos DB y NO pagina de forma confiable por
    offset: al pedir la 2.ª página el orden se re-baraja y quedan documentos afuera
    en silencio (por eso "se perdían" facturas en rangos amplios sin ningún aviso).
    La ÚNICA página confiable es la primera.

    En vez de confiar en el paginado, se parte el rango de fechas a la mitad y se
    re-consulta cada mitad hasta que cada subrango entra en UNA sola página (la
    primera vino con menos del tope) — ahí no hubo salto de bloque y el resultado
    es EXACTO. Se deduplica por id, así que los solapes entre subrangos no molestan.
    Un token grande se recorre en más peticiones, pero ninguna factura queda fuera.
    """
    try:
        d_ini = datetime.strptime(fecha_desde, "%d/%m/%Y").date()
        d_fin = datetime.strptime(fecha_hasta, "%d/%m/%Y").date()
    except ValueError:
        # Formato inesperado: no se puede bisecar por fecha → una consulta normal.
        return consultar_documentos(auth_url, fecha_desde, fecha_hasta, modo=modo)

    tope = _tope_pagina(modo)
    docs_por_id: dict[str, dict] = {}
    dias_saturados: list[str] = []   # un solo día con >= tope documentos (caso extremo)
    contador = {"n": 0}

    def _fmt(d) -> str:
        return d.strftime("%d/%m/%Y")

    def _recolectar(docs: list[dict]) -> None:
        for doc in docs:
            _id = doc.get("id")
            if _id:
                docs_por_id[_id] = doc

    def _sondear(d1, d2) -> tuple[dict, list[dict]]:
        # El filtro de fechas vive en la sesión de la DIAN (se fija con un POST
        # aparte) y a veces no se aplica: la respuesta trae documentos de OTRO
        # rango. Se detecta por las fechas y se reintenta; si persiste, se
        # descartan los de afuera (los recoge el subrango que sí les corresponde).
        res: dict = {}
        docs: list[dict] = []
        for _ in range(_REINTENTOS_RANGO):
            contador["n"] += 1
            res = consultar_documentos(auth_url, _fmt(d1), _fmt(d2), modo=modo, max_paginas=1)
            docs = res.get("documents", []) or []
            if all(_en_rango(x, d1, d2) for x in docs):
                return res, docs
        return res, [x for x in docs if _en_rango(x, d1, d2)]

    def _rec(d1, d2) -> set[str]:
        """Recorre [d1, d2] y devuelve los ids que encontró en ese rango."""
        if contador["n"] >= _MAX_CONSULTAS_BISECCION:
            dias_saturados.append(f"{_fmt(d1)}–{_fmt(d2)}")
            return set()
        # Sonda: solo la primera página, que es la confiable.
        res, docs = _sondear(d1, d2)
        ids = {x["id"] for x in docs if x.get("id")}
        # Cabe en una página (y la DIAN no dice que haya más) → es exacto, se queda.
        if len(docs) < tope and not res.get("incompleto"):
            _recolectar(docs)
            return ids
        # No se puede partir más (un solo día) pero sigue saturado: caso extremo.
        if d1 >= d2:
            _recolectar(docs)
            dias_saturados.append(_fmt(d1))
            return ids
        # Partir el rango por la mitad (por días) y recurse en cada mitad. Las
        # mitades deben sumar lo que la DIAN reportó para el rango entero: si una
        # vino vacía o con datos de otro rango, se re-consultan.
        total_rango = int(res.get("total_dian") or 0)
        medio = d1 + timedelta(days=(d2 - d1).days // 2)
        hijos: set[str] = set()
        for _ in range(_REINTENTOS_RANGO):
            hijos |= _rec(d1, medio) | _rec(medio + timedelta(days=1), d2)
            if len(hijos) >= total_rango:
                return hijos
        faltantes.append((f"{_fmt(d1)} y {_fmt(d2)}", total_rango, len(hijos)))
        return hijos

    faltantes: list[tuple[str, int, int]] = []
    _rec(d_ini, d_fin)

    docs = list(docs_por_id.values())
    respuesta: dict = {
        "success": True,
        "total": len(docs),
        "total_dian": len(docs),
        "incompleto": bool(dias_saturados or faltantes),
        "documents": docs,
    }
    avisos: list[str] = []
    if faltantes:
        detalle = "; ".join(f"entre {r} reporta {t} y entregó {n}" for r, t, n in faltantes)
        avisos.append(
            f"⚠️ La DIAN no entregó completos algunos periodos aun reintentando ({detalle}). "
            f"Vuelve a consultar; si se repite, genera un enlace nuevo en el portal de la DIAN."
        )
    if dias_saturados:
        avisos.append(
            f"⚠️ Estos días tienen más de {tope} documentos y la DIAN no los entrega "
            f"todos ni consultando el día solo: {', '.join(dias_saturados)}. Es un caso "
            f"raro; si notás faltantes de esas fechas, revisalas directamente en el "
            f"portal de la DIAN."
        )
    if avisos:
        respuesta["advertencia"] = " ".join(avisos)
    return respuesta


def _descargar_bytes(session: requests.Session, transaction_id: str, modo: str) -> bytes:
    """Descarga UN documento en memoria según el módulo:
      - ``soporte``: paquete ZIP oficial (XML firmado + PDF) vía ``GetFilePdf?cune=``
        en el portal catálogo (DownloadXml no sirve para documentos soporte).
      - ``ventas``: ``DownloadXml?type=1`` (emitidos).
      - ``compras``: ``DownloadXml?type=2`` (recibidos).
    """
    if (modo or "").lower() in ("soporte", "soporte_ajuste"):
        resp = session.get(
            f"{CATALOGO_BASE}/Document/GetFilePdf",
            params={"cune": transaction_id},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
    else:
        tipo = "1" if (modo or "compras").lower() == "ventas" else "2"
        resp = session.get(
            f"{BILLER_BASE}/Document/DownloadXml",
            params={"transactionId": transaction_id, "type": tipo},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
    resp.raise_for_status()
    contenido = resp.content
    # Si volvió HTML (login), la sesión expiró.
    if contenido[:15].lstrip().lower().startswith(b"<!doctype html") or b"CompanyLoginFailed" in contenido[:2000]:
        raise DianError("SESSION_EXPIRED", "La sesión con la DIAN expiró durante la descarga.")
    return contenido


def descargar_xmls(auth_url: str, ids: list[str], modo: str = "compras") -> list[dict]:
    """
    Descarga EN MEMORIA los XML de los `ids` indicados (DT_RowId/transactionId/CUDS).
    Retorna [{'id': str, 'xml': bytes}]. No escribe nada en disco.
    Lanza DianError en caso de token/sesión/conexión.
    """
    session, _account_id = _sesion_para(auth_url)
    salida: list[dict] = []
    try:
        for transaction_id in ids:
            if not transaction_id:
                continue
            salida.append({"id": transaction_id, "xml": _descargar_bytes(session, transaction_id, modo)})
    except DianError:
        raise
    except requests.RequestException:
        raise DianError("CONNECTION_ERROR", "No se pudo conectar con la DIAN (problema de red temporal).")
    return salida


def descargar_xmls_stream(auth_url: str, ids: list[str], modo: str = "compras"):
    """
    Igual que descargar_xmls pero es un GENERADOR: autentica una vez y va
    entregando cada documento a medida que lo descarga, para informar progreso
    real al frontend. Cada yield es (done, total, id, bytes).
    """
    session, _account_id = _sesion_para(auth_url)
    limpios = [x for x in ids if x]
    total = len(limpios)
    for i, transaction_id in enumerate(limpios, 1):
        # Resiliencia por documento: un fallo de red puntual NO debe tumbar todo el
        # lote. Se reintenta este documento unas veces; si aun así falla, se entrega
        # None (el llamador lo cuenta como error y sigue). Solo un token/sesión
        # muertos abortan todo (son irrecuperables sin re-autenticar).
        contenido = None
        for intento in range(3):
            try:
                contenido = _descargar_bytes(session, transaction_id, modo)
                break
            except DianError as e:
                if e.code in ("SESSION_EXPIRED", "TOKEN_EXPIRED"):
                    _evict(auth_url)
                    raise
                # CONNECTION_ERROR u otro transitorio → reintentar este documento.
            except requests.RequestException:
                pass
            if intento < 2:
                time.sleep(0.7 * (intento + 1))
        yield i, total, transaction_id, contenido


def nombre_para_parser(contenido: bytes, id_: str) -> str:
    """
    El parser de causación enruta por extensión. Detecta si el contenido es ZIP
    (magic 'PK') o XML para asignar el nombre correcto.
    """
    if contenido[:2] == b"PK":
        return f"{id_}.zip"
    return f"{id_}.xml"
