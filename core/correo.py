"""
Validación de correos electrónicos al crear usuarios.

El navegador (input type="email") acepta "usuario@dominio" sin extensión porque
el estándar HTML lo permite (sirve en redes internas). Para la plataforma eso es
un correo que nunca va a recibir nada, así que exigimos un dominio completo con
extensión: usuario@empresa.com, usuario@empresa.com.co, etc.
"""
from __future__ import annotations

import re

# parte local @ etiquetas.del.dominio . extensión (mínimo 2 letras)
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+"                      # parte local
    r"@(?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+"  # dominio(s)
    r"[A-Za-z]{2,}$"                             # extensión: com, co, net…
)

MENSAJE_EMAIL_INVALIDO = (
    "El correo no es válido. Revisa que esté completo, por ejemplo: usuario@empresa.com"
)


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


def email_valido(email: str) -> bool:
    e = normalizar_email(email)
    if len(e) > 254 or ".." in e:
        return False
    return bool(_EMAIL_RE.match(e))
