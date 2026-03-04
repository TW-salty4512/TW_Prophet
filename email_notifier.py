"""
#################################################
2025/02
-TW_Prophet-
email_notifier.py
#################################################
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate


class EmailNotifier:
    def __init__(self):
        # Gmail の例
        self.smtp_server = os.getenv("TW_SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("TW_SMTP_PORT", "587"))
        self.username = os.getenv("TW_SMTP_USER", "")
        self.password = os.getenv("TW_SMTP_PASS", "")
        self.from_addr = os.getenv("TW_SMTP_FROM", "") or self.username
        self.to_addrs: list[str] = []

    def set_to_addrs(self, addr_list):
        """送信先の設定

        - list[str] / tuple / set だけでなく、単一の文字列にも対応
        - 重複を除去して保存
        """
        if addr_list is None:
            self.to_addrs = []
            return

        if isinstance(addr_list, str):
            addrs = [addr_list]
        else:
            addrs = list(addr_list)

        # 空文字の除去 + 重複除去（順序は維持）
        seen = set()
        cleaned: list[str] = []
        for a in addrs:
            a = str(a).strip()
            if not a:
                continue
            if a in seen:
                continue
            seen.add(a)
            cleaned.append(a)

        self.to_addrs = cleaned

    def _validate(self):
        if not self.username:
            raise ValueError("TW_SMTP_USER が未設定です")
        if not self.password:
            raise ValueError("TW_SMTP_PASS が未設定です")
        if not self.from_addr:
            raise ValueError("TW_SMTP_FROM が未設定です")
        if not self.to_addrs:
            raise ValueError("送信先メールアドレス(to_addrs)が未設定です")

    def send_notification(self, subject, body, html_mode=False):
        """メール送信

        ★変更点★
        - 送信前に _validate() を必ず実行（設定不備を早期に検知）
        """
        self._validate()

        if html_mode:
            msg = MIMEText(body, "html", "utf-8")
        else:
            msg = MIMEText(body, "plain", "utf-8")

        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg["Date"] = formatdate(localtime=True)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
        except Exception as e:
            raise e
