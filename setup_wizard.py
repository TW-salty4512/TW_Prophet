"""
setup_wizard.py  –  TW_Prophet セットアップウィザード（Tkinter GUI）

初回インストール後またはインストーラから呼び出す。
設定内容を %ProgramData%\TW_Prophet\settings.json に書き込む。
必要に応じてタスクスケジューラへの登録も行う。

使い方:
    python setup_wizard.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
APP_TITLE   = "TW_Prophet セットアップウィザード"
TASK_NAME   = "TW_Prophet_Web"
PROGRAMDATA = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
SETTINGS_DIR  = PROGRAMDATA / "TW_Prophet"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

MODES = {"internal (MDB/MySQL)": "internal", "sample (サンプルCSV)": "sample"}

COLOR_BG     = "#221B44"
COLOR_FG     = "#80FFEA"
COLOR_PANEL  = "#2E2E3E"
COLOR_BUTTON = "#1565C0"
COLOR_OK     = "#388E3C"


# ---------------------------------------------------------------------------
# ウィザード
# ---------------------------------------------------------------------------

class SetupWizard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("720x600")
        self.configure(bg=COLOR_BG)
        self.resizable(False, False)

        # 入力変数
        self.v_mode           = tk.StringVar(value="internal (MDB/MySQL)")
        self.v_port           = tk.IntVar(value=8000)
        self.v_mdb_base       = tk.StringVar(value=r"\\File-server\データベース")
        self.v_shipment_mdb   = tk.StringVar(value="")
        self.v_post_ship_mdb  = tk.StringVar(value="")
        self.v_mfg_mdb        = tk.StringVar(value="")
        self.v_mysql_host     = tk.StringVar(value="127.0.0.1")
        self.v_mysql_port     = tk.IntVar(value=3306)
        self.v_mysql_user     = tk.StringVar(value="")
        self.v_mysql_password = tk.StringVar(value="")
        self.v_mysql_database = tk.StringVar(value="")
        self.v_data_dir       = tk.StringVar(value=str(SETTINGS_DIR / "data"))
        self.v_models_dir     = tk.StringVar(value=str(SETTINGS_DIR / "data" / "models"))
        self.v_auto_start     = tk.BooleanVar(value=True)

        # ページ管理
        self._pages: list[tk.Frame] = []
        self._current = 0

        self._build_ui()
        self._show_page(0)

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # ヘッダー
        hdr = tk.Frame(self, bg=COLOR_BG, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text=APP_TITLE, bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 14, "bold")).pack()

        # コンテンツ
        self._content = tk.Frame(self, bg=COLOR_BG, padx=20, pady=10)
        self._content.pack(fill="both", expand=True)

        # ページフレーム
        self._pages = [
            self._page_mode(),
            self._page_mdb(),
            self._page_mysql(),
            self._page_dirs(),
            self._page_startup(),
            self._page_confirm(),
        ]
        for p in self._pages:
            p.place(in_=self._content, x=0, y=0, relwidth=1, relheight=1)

        # ナビゲーションボタン
        nav = tk.Frame(self, bg=COLOR_BG, pady=8)
        nav.pack(fill="x", side="bottom")
        self._btn_back = tk.Button(nav, text="< 戻る", width=10,
                                   bg=COLOR_PANEL, fg=COLOR_FG,
                                   command=self._prev_page)
        self._btn_back.pack(side="left", padx=20)
        self._btn_next = tk.Button(nav, text="次へ >", width=10,
                                   bg=COLOR_BUTTON, fg="white",
                                   command=self._next_page)
        self._btn_next.pack(side="right", padx=20)

    def _lf(self, parent: tk.Widget, text: str) -> ttk.LabelFrame:
        """スタイル付き LabelFrame を返す。"""
        lf = tk.LabelFrame(parent, text=text, bg=COLOR_PANEL, fg=COLOR_FG,
                           font=("Segoe UI", 10, "bold"), relief="groove",
                           padx=10, pady=8)
        lf.pack(fill="x", pady=6)
        return lf

    def _row(self, parent: tk.Widget, label: str,
             widget_factory, **kw) -> tk.Widget:
        """ラベル + 入力ウィジェット 1 行を作成して返す。"""
        f = tk.Frame(parent, bg=COLOR_PANEL)
        f.pack(fill="x", pady=2)
        tk.Label(f, text=label, width=22, anchor="w",
                 bg=COLOR_PANEL, fg=COLOR_FG).pack(side="left")
        w = widget_factory(f, **kw)
        w.pack(side="left", fill="x", expand=True, padx=4)
        return w

    def _entry(self, parent: tk.Widget, textvariable: tk.Variable, **kw) -> tk.Entry:
        return tk.Entry(parent, textvariable=textvariable,
                        bg="#1E1E2F", fg=COLOR_FG, insertbackground=COLOR_FG,
                        relief="flat", **kw)

    def _browse_dir(self, var: tk.StringVar) -> None:
        d = filedialog.askdirectory(initialdir=var.get() or "/")
        if d:
            var.set(d)

    def _browse_file(self, var: tk.StringVar, filetypes=(("MDB", "*.mdb *.accdb"), ("All", "*"))) -> None:
        f = filedialog.askopenfilename(initialdir="/", filetypes=filetypes)
        if f:
            var.set(f)

    # ------------------------------------------------------------------
    # ページ定義
    # ------------------------------------------------------------------
    def _page(self) -> tk.Frame:
        f = tk.Frame(self._content, bg=COLOR_BG)
        return f

    def _page_mode(self) -> tk.Frame:
        p = self._page()
        tk.Label(p, text="ステップ 1 / 5  –  動作モード", bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        lf = self._lf(p, "データ取得方法")
        for label, val in MODES.items():
            tk.Radiobutton(lf, text=label, variable=self.v_mode, value=label,
                           bg=COLOR_PANEL, fg=COLOR_FG, selectcolor=COLOR_BG,
                           activebackground=COLOR_PANEL, activeforeground=COLOR_FG,
                           command=self._on_mode_change).pack(anchor="w")
        tk.Label(lf, text="internal: Access MDB / MySQL を使う社内向けモード\n"
                           "sample  : 付属サンプル CSV を使うデモ/開発モード",
                 bg=COLOR_PANEL, fg="#E5CAFF", justify="left").pack(anchor="w", pady=(6, 0))
        return p

    def _page_mdb(self) -> tk.Frame:
        p = self._page()
        tk.Label(p, text="ステップ 2 / 5  –  MDB ファイルパス", bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        lf = self._lf(p, "MDB ベースディレクトリ（UNCパス可）")
        self._entry(lf, self.v_mdb_base).pack(fill="x", pady=2)
        tk.Label(lf, text="※ 3 つの MDB を同一フォルダに置いている場合はここだけ設定してください。",
                 bg=COLOR_PANEL, fg="#E5CAFF").pack(anchor="w")

        lf2 = self._lf(p, "個別パス（ベースと異なる場合のみ入力）")
        for label, var in [
            ("簡易受注管理.mdb", self.v_shipment_mdb),
            ("出荷管理.mdb",     self.v_post_ship_mdb),
            ("製造管理.mdb",     self.v_mfg_mdb),
        ]:
            row = tk.Frame(lf2, bg=COLOR_PANEL)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, width=18, anchor="w",
                     bg=COLOR_PANEL, fg=COLOR_FG).pack(side="left")
            self._entry(row, var).pack(side="left", fill="x", expand=True, padx=4)
            tk.Button(row, text="参照", bg=COLOR_PANEL, fg=COLOR_FG,
                      command=lambda v=var: self._browse_file(v)).pack(side="left")
        return p

    def _page_mysql(self) -> tk.Frame:
        p = self._page()
        tk.Label(p, text="ステップ 3 / 5  –  MySQL 接続（任意）", bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        lf = self._lf(p, "MySQL 接続設定（不要な場合は空のままでOK）")
        for label, var in [
            ("ホスト",      self.v_mysql_host),
            ("ユーザー",    self.v_mysql_user),
            ("データベース", self.v_mysql_database),
        ]:
            self._row(lf, label, self._entry, textvariable=var)
        # パスワード
        f = tk.Frame(lf, bg=COLOR_PANEL)
        f.pack(fill="x", pady=2)
        tk.Label(f, text="パスワード", width=22, anchor="w",
                 bg=COLOR_PANEL, fg=COLOR_FG).pack(side="left")
        tk.Entry(f, textvariable=self.v_mysql_password, show="*",
                 bg="#1E1E2F", fg=COLOR_FG, insertbackground=COLOR_FG,
                 relief="flat").pack(side="left", fill="x", expand=True, padx=4)
        # ポート
        self._row(lf, "ポート", self._entry, textvariable=self.v_mysql_port)
        return p

    def _page_dirs(self) -> tk.Frame:
        p = self._page()
        tk.Label(p, text="ステップ 4 / 5  –  保存先ディレクトリ", bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))

        lf = self._lf(p, "Web サーバー")
        self._row(lf, "待受ポート", self._entry, textvariable=self.v_port)

        lf2 = self._lf(p, "データ保存先")
        for label, var in [
            ("データディレクトリ", self.v_data_dir),
            ("モデル保存先",       self.v_models_dir),
        ]:
            row = tk.Frame(lf2, bg=COLOR_PANEL)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, width=22, anchor="w",
                     bg=COLOR_PANEL, fg=COLOR_FG).pack(side="left")
            self._entry(row, var).pack(side="left", fill="x", expand=True, padx=4)
            tk.Button(row, text="参照", bg=COLOR_PANEL, fg=COLOR_FG,
                      command=lambda v=var: self._browse_dir(v)).pack(side="left")
        return p

    def _page_startup(self) -> tk.Frame:
        p = self._page()
        tk.Label(p, text="ステップ 5 / 5  –  自動起動設定", bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        lf = self._lf(p, "Windows 起動時に自動起動する")
        tk.Checkbutton(lf, text="タスクスケジューラに自動起動タスクを登録する（推奨）",
                       variable=self.v_auto_start,
                       bg=COLOR_PANEL, fg=COLOR_FG, selectcolor=COLOR_BG,
                       activebackground=COLOR_PANEL, activeforeground=COLOR_FG).pack(anchor="w")
        tk.Label(lf, text="SYSTEM アカウントで実行されるため、ログイン不要で起動します。\n"
                           "登録には管理者権限が必要です。",
                 bg=COLOR_PANEL, fg="#E5CAFF", justify="left").pack(anchor="w", pady=(6, 0))
        return p

    def _page_confirm(self) -> tk.Frame:
        p = self._page()
        tk.Label(p, text="設定確認", bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        self._confirm_text = tk.Text(p, height=18, bg=COLOR_PANEL, fg=COLOR_FG,
                                     relief="flat", state="disabled")
        self._confirm_text.pack(fill="both", expand=True)
        return p

    def _update_confirm_text(self) -> None:
        txt = self._build_settings_dict()
        s = json.dumps(txt, ensure_ascii=False, indent=2)
        self._confirm_text.configure(state="normal")
        self._confirm_text.delete("1.0", "end")
        self._confirm_text.insert("end", "以下の内容で settings.json を作成します:\n\n" + s)
        self._confirm_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # ナビゲーション
    # ------------------------------------------------------------------
    def _show_page(self, idx: int) -> None:
        if idx == len(self._pages) - 1:
            self._update_confirm_text()
            self._btn_next.configure(text="完了・保存", bg=COLOR_OK)
        else:
            self._btn_next.configure(text="次へ >", bg=COLOR_BUTTON)
        self._btn_back.configure(state="normal" if idx > 0 else "disabled")
        self._pages[idx].lift()
        self._current = idx

    def _next_page(self) -> None:
        if self._current == len(self._pages) - 1:
            self._finish()
        else:
            # sample モードは MDB / MySQL ページをスキップ
            nxt = self._current + 1
            mode_val = MODES.get(self.v_mode.get(), "internal")
            if mode_val == "sample" and nxt in (1, 2):
                nxt = 3
            self._show_page(nxt)

    def _prev_page(self) -> None:
        prev = self._current - 1
        mode_val = MODES.get(self.v_mode.get(), "internal")
        if mode_val == "sample" and prev in (1, 2):
            prev = 0
        if prev >= 0:
            self._show_page(prev)

    def _on_mode_change(self) -> None:
        pass  # 将来: モードに応じて項目を動的に表示/非表示

    # ------------------------------------------------------------------
    # 設定生成 / 保存
    # ------------------------------------------------------------------
    def _build_settings_dict(self) -> dict[str, Any]:
        mode_val = MODES.get(self.v_mode.get(), "internal")
        s: dict[str, Any] = {
            "data_mode": mode_val,
            "port": self.v_port.get(),
            "data_dir":   self.v_data_dir.get(),
            "models_dir": self.v_models_dir.get(),
        }
        if mode_val == "internal":
            base = self.v_mdb_base.get().strip()
            s["mdb_base_dir"]      = base
            s["shipment_mdb"]      = self.v_shipment_mdb.get().strip()   or f"{base}\\簡易受注管理.mdb"
            s["post_shipment_mdb"] = self.v_post_ship_mdb.get().strip()  or f"{base}\\出荷管理.mdb"
            s["manufacture_mdb"]   = self.v_mfg_mdb.get().strip()        or f"{base}\\製造管理.mdb"
        return s

    def _build_mysql_dict(self) -> dict[str, Any]:
        return {
            "host":     self.v_mysql_host.get().strip(),
            "port":     self.v_mysql_port.get(),
            "user":     self.v_mysql_user.get().strip(),
            "password": self.v_mysql_password.get(),
            "database": self.v_mysql_database.get().strip(),
        }

    def _finish(self) -> None:
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

            # settings.json
            cfg = self._build_settings_dict()
            with SETTINGS_FILE.open("w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

            # mysql_config.json（パスワード入力がある場合のみ）
            mysql = self._build_mysql_dict()
            if any(mysql.get(k) for k in ("host", "user", "database")):
                mysql_path = SETTINGS_DIR / "data" / "config" / "mysql_config.json"
                mysql_path.parent.mkdir(parents=True, exist_ok=True)
                with mysql_path.open("w", encoding="utf-8") as f:
                    json.dump(mysql, f, ensure_ascii=False, indent=2)

            # タスクスケジューラ登録
            if self.v_auto_start.get():
                self._register_task()

            messagebox.showinfo("完了", f"設定を保存しました:\n{SETTINGS_FILE}\n\nTW_Prophet を起動してください。")
            self.destroy()

        except PermissionError:
            messagebox.showerror("エラー", f"{SETTINGS_FILE} への書き込み権限がありません。\n管理者として実行してください。")
        except Exception as e:
            messagebox.showerror("エラー", f"保存中にエラーが発生しました:\n{e}")

    def _register_task(self) -> None:
        """scripts\\register_startup.ps1 を管理者権限で実行する。"""
        script = Path(__file__).parent / "scripts" / "register_startup.ps1"
        if not script.exists():
            messagebox.showwarning("警告", "register_startup.ps1 が見つかりません。手動で登録してください。")
            return
        try:
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass",
                 "-File", str(script),
                 f"-Port", str(self.v_port.get()),
                 f"-InstallDir", str(Path(__file__).parent)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                messagebox.showwarning(
                    "自動起動登録の警告",
                    "タスクスケジューラへの登録に失敗しました（管理者権限が必要な場合があります）。\n\n"
                    + result.stderr[:500]
                )
            else:
                messagebox.showinfo("自動起動", "タスクスケジューラへの登録が完了しました。")
        except Exception as e:
            messagebox.showwarning("自動起動登録の警告", f"登録スクリプトの実行に失敗しました:\n{e}")


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    app = SetupWizard()
    app.mainloop()


if __name__ == "__main__":
    main()
