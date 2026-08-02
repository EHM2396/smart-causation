"""
EmailService – envío de correos transaccionales vía SMTP (Gmail).

Configuración por variables de entorno:
    MAIL_USERNAME   noreply.ciolix@gmail.com
    MAIL_PASSWORD   app-password de 16 caracteres generada en Google
    MAIL_FROM       noreply.ciolix@gmail.com
    MAIL_FROM_NAME  Ciolix
    MAIL_SERVER     smtp.gmail.com
    MAIL_PORT       587
    MAIL_TLS        true
    MAIL_SSL        false

Si MAIL_USERNAME no está configurado el servicio lanza un warning y no envía
el correo, para que el entorno de desarrollo funcione sin cuenta de email.
"""

from __future__ import annotations

import logging
import os

from core.brand import APP_NAME, APP_TAGLINE

logger = logging.getLogger(__name__)

# ── Configuración desde entorno ───────────────────────────────────────────────

_USERNAME   = os.getenv("MAIL_USERNAME", "")
_PASSWORD   = os.getenv("MAIL_PASSWORD", "")
_FROM       = os.getenv("MAIL_FROM", _USERNAME)
_FROM_NAME    = os.getenv("MAIL_FROM_NAME", APP_NAME)
_SERVER       = os.getenv("MAIL_SERVER", "smtp.gmail.com")
_FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")
_PORT       = int(os.getenv("MAIL_PORT", "587"))
_TLS        = os.getenv("MAIL_TLS", "true").lower() == "true"
_SSL        = os.getenv("MAIL_SSL", "false").lower() == "true"

_configured = bool(_USERNAME and _PASSWORD)

if not _configured:
    logger.warning(
        "Email no configurado: MAIL_USERNAME / MAIL_PASSWORD ausentes. "
        "Los correos transaccionales no se enviarán."
    )


# ── Función principal ─────────────────────────────────────────────────────────

async def send_email(*, to: str, subject: str, body_html: str) -> bool:
    """
    Envía un correo HTML. Retorna True si se envió, False si el servicio
    no está configurado (entorno de desarrollo).
    """
    if not _configured:
        logger.warning("send_email ignorado (sin configuración): to=%s subject=%s", to, subject)
        return False

    from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

    conf = ConnectionConfig(
        MAIL_USERNAME=_USERNAME,
        MAIL_PASSWORD=_PASSWORD,
        MAIL_FROM=_FROM,
        MAIL_FROM_NAME=_FROM_NAME,
        MAIL_PORT=_PORT,
        MAIL_SERVER=_SERVER,
        MAIL_STARTTLS=_TLS,
        MAIL_SSL_TLS=_SSL,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )

    message = MessageSchema(
        subject=subject,
        recipients=[to],
        body=body_html,
        subtype=MessageType.html,
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info("Correo enviado: to=%s subject=%s", to, subject)
        return True
    except Exception as exc:
        logger.error("Error enviando correo a %s: %s", to, exc)
        raise


# ── Plantillas ────────────────────────────────────────────────────────────────

def _base_template(titulo: str, cuerpo: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#e9ecf1;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#e9ecf1;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#f5f6f8;border-radius:14px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.08);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#4F46E5 0%,#4338CA 100%);padding:28px 40px;">
            <img src="{_FRONTEND_URL}/brand/Logo%20blanco.png"
                 alt="{APP_NAME}" width="140" height="44"
                 style="display:block;max-width:140px;height:auto;" />
            <p style="margin:8px 0 0;font-size:12px;color:#c7d2fe;font-family:Arial,sans-serif;">{APP_TAGLINE}</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px;background:#ffffff;">
            <h1 style="margin:0 0 16px;font-size:22px;color:#0f172a;font-weight:700;">{titulo}</h1>
            {cuerpo}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:24px 40px;background:#f5f6f8;border-top:1px solid #e2e8f0;">
            <p style="margin:0;font-size:12px;color:#9ca3af;">
              Este correo fue enviado por {APP_NAME}.<br>
              Si no solicitaste este correo puedes ignorarlo.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def plantilla_recuperacion(nombre: str, enlace: str) -> str:
    cuerpo = f"""
    <p style="color:#374151;font-size:15px;line-height:1.6;">
      Hola <strong>{nombre}</strong>,<br><br>
      Recibimos una solicitud para restablecer la contraseña de tu cuenta.
      Haz clic en el botón para crear una nueva contraseña:
    </p>
    <p style="text-align:center;margin:32px 0;">
      <a href="{enlace}"
         style="display:inline-block;background:#4F46E5;color:#ffffff;font-weight:700;
                font-size:15px;padding:14px 32px;border-radius:8px;text-decoration:none;">
        Restablecer contraseña
      </a>
    </p>
    <p style="color:#6b7280;font-size:13px;">
      Este enlace expira en <strong>30 minutos</strong>.<br>
      Si no solicitaste este cambio, ignora este correo — tu contraseña no cambiará.
    </p>
    """
    return _base_template("Restablece tu contraseña", cuerpo)


def plantilla_verificacion(nombre: str, enlace: str) -> str:
    cuerpo = f"""
    <p style="color:#374151;font-size:15px;line-height:1.6;">
      Hola <strong>{nombre}</strong>,<br><br>
      Gracias por registrarte en {APP_NAME}.
      Confirma tu correo electrónico haciendo clic en el botón:
    </p>
    <p style="text-align:center;margin:32px 0;">
      <a href="{enlace}"
         style="display:inline-block;background:#4F46E5;color:#ffffff;font-weight:700;
                font-size:15px;padding:14px 32px;border-radius:8px;text-decoration:none;">
        Verificar mi correo
      </a>
    </p>
    <p style="color:#6b7280;font-size:13px;">
      Este enlace expira en <strong>24 horas</strong>.
    </p>
    """
    return _base_template("Verifica tu correo electrónico", cuerpo)
