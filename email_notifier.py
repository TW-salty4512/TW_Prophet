"""Public wrapper for email notifier."""

from public.email_notifier import EmailNotifier

# 既定でメール送信無効の公開版実装へ委譲。
__all__ = ["EmailNotifier"]

