import os
import random
import string
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from env_utils import load_app_env

load_app_env()

# Try aiosmtplib if available, otherwise use smtplib with asyncio
try:
    import aiosmtplib
    HAS_AIOSMTPLIB = True
except ImportError:
    HAS_AIOSMTPLIB = False

import smtplib
import asyncio

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_TIMEOUT = float(os.getenv("SMTP_TIMEOUT", "8"))


def generate_verification_code(length: int = 6) -> str:
    """Generate a random numeric verification code."""
    return ''.join(random.choices(string.digits, k=length))


def _build_verification_email(to_email: str, code: str, username: str) -> MIMEMultipart:
    """Build a beautiful HTML verification email."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Luggify — Код подтверждения: {code}"
    msg["From"] = f"Luggify <{SMTP_FROM}>"
    msg["To"] = to_email

    text_content = f"""
Привет, {username}!

Ваш код подтверждения для Luggify: {code}

Код действителен в течение 10 минут.

Если вы не регистрировались на Luggify, просто проигнорируйте это письмо.

— Команда Luggify
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #0a0a0a;">
    <tr>
      <td style="padding: 40px 20px;">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 480px; margin: 0 auto; background: linear-gradient(135deg, #1a1a1a 0%, #141414 100%); border-radius: 20px; border: 1px solid rgba(255, 153, 0, 0.15); overflow: hidden;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 20px; text-align: center;">
              <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #ff9900; letter-spacing: -0.5px;">✈️ Luggify</h1>
              <p style="margin: 8px 0 0; font-size: 14px; color: #888;">Умный помощник для путешествий</p>
            </td>
          </tr>
          
          <!-- Body -->
          <tr>
            <td style="padding: 0 32px 24px;">
              <p style="margin: 0 0 8px; font-size: 16px; color: #e0e0e0;">Привет, <strong style="color: #ff9900;">{username}</strong>! 👋</p>
              <p style="margin: 0 0 24px; font-size: 14px; color: #999; line-height: 1.5;">Введите этот код в приложении для подтверждения email:</p>
              
              <!-- Code Box -->
              <div style="background: rgba(255, 153, 0, 0.08); border: 1px solid rgba(255, 153, 0, 0.2); border-radius: 12px; padding: 24px; text-align: center; margin: 0 0 24px;">
                <span style="font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #ff9900; font-family: 'SF Mono', 'Fira Code', monospace;">{code}</span>
              </div>
              
              <p style="margin: 0 0 4px; font-size: 13px; color: #666;">⏱️ Код действителен <strong style="color: #999;">10 минут</strong></p>
              <p style="margin: 0; font-size: 13px; color: #666;">🔒 Никому не сообщайте этот код</p>
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; border-top: 1px solid rgba(255, 255, 255, 0.05); text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #555;">Если вы не регистрировались на Luggify, просто проигнорируйте это письмо.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    return msg


async def send_verification_email(to_email: str, code: str, username: str) -> bool:
    """Send verification email. Returns True on success."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[EMAIL] SMTP not configured. Code for {to_email}: {code}")
        return False

    msg = _build_verification_email(to_email, code, username)

    def _resolve_smtp_targets():
        targets = []
        seen = set()

        try:
            for family, socktype, proto, _, sockaddr in socket.getaddrinfo(
                SMTP_HOST,
                SMTP_PORT,
                0,
                socket.SOCK_STREAM,
            ):
                target = (family, socktype, proto, sockaddr)
                if target in seen:
                    continue
                seen.add(target)
                targets.append(target)
        except Exception as resolve_error:
            print(f"[EMAIL] Failed to resolve SMTP host {SMTP_HOST}: {resolve_error}")

        return targets

    def _send_sync():
        last_error = None
        targets = _resolve_smtp_targets()
        if not targets:
            raise RuntimeError(f"No SMTP targets resolved for {SMTP_HOST}:{SMTP_PORT}")

        for family, socktype, proto, sockaddr in targets:
            try:
                with socket.socket(family, socktype, proto) as raw_sock:
                    raw_sock.settimeout(SMTP_TIMEOUT)
                    raw_sock.connect(sockaddr)
                    with smtplib.SMTP(timeout=SMTP_TIMEOUT) as server:
                        server.sock = raw_sock
                        server.file = raw_sock.makefile("rb")
                        server.helo_resp = None
                        server.ehlo_resp = None
                        server.esmtp_features = {}
                        server.does_esmtp = False
                        server.default_port = SMTP_PORT
                        server._host = SMTP_HOST
                        server.getreply()
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                        server.login(SMTP_USER, SMTP_PASSWORD)
                        server.send_message(msg)
                        print(f"[EMAIL] Verification email sent to {to_email} via {sockaddr[0]}:{sockaddr[1]}")
                        return
            except Exception as send_error:
                last_error = send_error
                print(f"[EMAIL] SMTP candidate {sockaddr[0]}:{sockaddr[1]} failed: {send_error}")

        raise last_error or RuntimeError("SMTP send failed without a specific error")

    try:
        await asyncio.get_event_loop().run_in_executor(None, _send_sync)
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send email to {to_email}: {e}")
        return False
