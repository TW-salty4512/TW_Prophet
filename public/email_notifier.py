from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate


class EmailNotifier:
    def __init__(self):
        # 公開版の既定は送信無効。明示的に TW_ENABLE_EMAIL=1 のときだけ送信。
        self.enabled = os.getenv("TW_ENABLE_EMAIL", "0").strip() == "1"
        self.smtp_host = os.getenv("TW_SMTP_HOST", "").strip()
        self.smtp_port = int(os.getenv("TW_SMTP_PORT", "587"))
        self.username = os.getenv("TW_SMTP_USER", "").strip()
        self.password = os.getenv("TW_SMTP_PASS", "").strip()
        self.from_addr = os.getenv("TW_SMTP_FROM", "").strip() or self.username
        self.to_addrs: list[str] = []

    def set_to_addrs(self, addr_list) -> None:
        if addr_list is None:
            self.to_addrs = []
            return
        if isinstance(addr_list, str):
            values = [addr_list]
        else:
            values = list(addr_list)
        cleaned = []
        seen = set()
        for value in values:
            addr = str(value).strip()
            if not addr or addr in seen:
                continue
            seen.add(addr)
            cleaned.append(addr)
        self.to_addrs = cleaned

    def _can_send(self) -> bool:
        return bool(
            self.enabled
            and self.smtp_host
            and self.username
            and self.password
            and self.from_addr
            and self.to_addrs
        )

    def send_notification(self, subject: str, body: str, html_mode: bool = False) -> bool:
        # SMTP未設定時は例外を投げず no-op で False を返す。
        if not self._can_send():
            return False

        msg = MIMEText(body, "html" if html_mode else "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg["Date"] = formatdate(localtime=True)

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
        return True

