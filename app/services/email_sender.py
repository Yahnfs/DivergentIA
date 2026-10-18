"""Envio de e-mail (confirmação de cadastro e recuperação de senha).

Dois modos, trocados pelo .env (EMAIL_PROVIDER), no mesmo espírito do LLM_PROVIDER:
  - "console" (padrão, grátis): escreve o link no log do servidor. Dá pra testar tudo sem configurar nada.
  - "smtp": envia de verdade, usando as variáveis SMTP_* do .env (ex.: Gmail com uma "senha de app").
"""
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("divergentia.email")


def enviar_email(destino: str, assunto: str, corpo: str) -> None:
    if settings.email_provider == "smtp":
        _enviar_smtp(destino, assunto, corpo)
    else:
        log.info("[e-mail simulado] Para: %s | Assunto: %s\n%s", destino, assunto, corpo)


def _enviar_smtp(destino: str, assunto: str, corpo: str) -> None:
    if not settings.smtp_host:
        log.warning("EMAIL_PROVIDER=smtp mas SMTP_HOST não está configurado; o e-mail para %s não foi enviado.", destino)
        return
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = settings.smtp_remetente
    msg["To"] = destino
    msg.set_content(corpo)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as servidor:
            servidor.starttls()
            if settings.smtp_usuario:
                servidor.login(settings.smtp_usuario, settings.smtp_senha or "")
            servidor.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Falha ao enviar e-mail para %s via SMTP: %s", destino, exc)
