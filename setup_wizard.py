"""
setup_wizard.py  –  TW_Prophet セットアップウィザード（Tkinter GUI）

初回インストール後またはインストーラから呼び出す。
設定内容を %ProgramData%\TW_Prophet\data\config\settings.json に書き込む。
必要に応じてタスクスケジューラへの登録も行う。

使い方:
    python setup_wizard.py
"""
from __future__ import annotations

import ctypes
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
PROGRAMDATA   = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
SETTINGS_DIR  = PROGRAMDATA / "TW_Prophet" / "data" / "config"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# インストールディレクトリの解決
# PyInstaller onefile 実行時: __file__ は一時展開フォルダ (_MEI*) を指すため使えない。
# sys.executable が実際の .exe の場所（インストールディレクトリ）を指す。
if getattr(sys, 'frozen', False):
    # PyInstaller バンドル実行
    INSTALL_DIR = Path(sys.executable).parent
else:
    # 通常の python 実行 (env var > __file__ の親)
    INSTALL_DIR = Path(os.environ.get("TW_PROPHET_DIR", str(Path(__file__).parent)))

MODES = {"internal (MDB/MySQL)": "internal", "sample (サンプルCSV)": "sample"}

COLOR_BG     = "#221B44"
COLOR_FG     = "#80FFEA"
COLOR_PANEL  = "#2E2E3E"
COLOR_BUTTON = "#1565C0"
COLOR_OK     = "#388E3C"


def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _default_python_exe() -> str:
    """サービス起動に使う実行ファイルパスを返す。
    PyInstaller バンドル実行時は TW_Prophet_Web.exe を優先する。
    """
    # PyInstaller バンドル実行時: 同じフォルダの TW_Prophet_Web.exe を使う
    if getattr(sys, 'frozen', False):
        web_exe = INSTALL_DIR / "TW_Prophet_Web.exe"
        if web_exe.exists():
            return str(web_exe)

    # 1. settings.json に保存済みパス
    if SETTINGS_FILE.exists():
        try:
            s = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            p = s.get("python_exe", "")
            if p and Path(p).exists():
                return p
        except Exception:
            pass
    # 2. インストールディレクトリの仮想環境
    for rel in (".venv/Scripts/pythonw.exe", ".venv/Scripts/python.exe",
                "venv/Scripts/pythonw.exe",  "venv/Scripts/python.exe"):
        c = INSTALL_DIR / rel
        if c.exists():
            return str(c)
    # 3. 現在の Python 実行ファイル（pythonw.exe があれば）
    exe = Path(sys.executable)
    pw = exe.parent / "pythonw.exe"
    if pw.exists():
        return str(pw)
    return str(exe)


# ---------------------------------------------------------------------------
# ウィザード
# ---------------------------------------------------------------------------

class SetupWizard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("720x640")
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
        self.v_data_dir       = tk.StringVar(value=str(PROGRAMDATA / "TW_Prophet" / "data"))
        self.v_models_dir     = tk.StringVar(value=str(PROGRAMDATA / "TW_Prophet" / "data" / "models"))
        self.v_python_exe     = tk.StringVar(value=_default_python_exe())
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
        hdr = tk.Frame(self, bg=COLOR_BG, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text=APP_TITLE, bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 14, "bold")).pack()

        self._content = tk.Frame(self, bg=COLOR_BG, padx=20, pady=10)
        self._content.pack(fill="both", expand=True)

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

    def _lf(self, parent: tk.Widget, text: str) -> tk.LabelFrame:
        lf = tk.LabelFrame(parent, text=text, bg=COLOR_PANEL, fg=COLOR_FG,
                           font=("Segoe UI", 10, "bold"), relief="groove",
                           padx=10, pady=8)
        lf.pack(fill="x", pady=6)
        return lf

    def _row(self, parent: tk.Widget, label: str,
             widget_factory, **kw) -> tk.Widget:
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

    def _browse_file(self, var: tk.StringVar,
                     filetypes=(("MDB", "*.mdb *.accdb"), ("All", "*"))) -> None:
        f = filedialog.askopenfilename(initialdir="/", filetypes=filetypes)
        if f:
            var.set(f)

    def _browse_exe(self, var: tk.StringVar) -> None:
        f = filedialog.askopenfilename(
            initialdir=str(Path(var.get()).parent) if var.get() else "/",
            filetypes=(("Python実行ファイル", "python*.exe pythonw*.exe"), ("All", "*")),
        )
        if f:
            var.set(f)

    # ------------------------------------------------------------------
    # ページ定義
    # ------------------------------------------------------------------
    def _page(self) -> tk.Frame:
        return tk.Frame(self._content, bg=COLOR_BG)

    def _page_mode(self) -> tk.Frame:
        p = self._page()
        tk.Label(p, text="ステップ 1 / 5  –  動作モード", bg=COLOR_BG, fg=COLOR_FG,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
        lf = self._lf(p, "データ取得方法")
        for label in MODES:
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
        f = tk.Frame(lf, bg=COLOR_PANEL)
        f.pack(fill="x", pady=2)
        tk.Label(f, text="パスワード", width=22, anchor="w",
                 bg=COLOR_PANEL, fg=COLOR_FG).pack(side="left")
        tk.Entry(f, textvariable=self.v_mysql_password, show="*",
                 bg="#1E1E2F", fg=COLOR_FG, insertbackground=COLOR_FG,
                 relief="flat").pack(side="left", fill="x", expand=True, padx=4)
        self._row(lf, "ポート", self._entry, textvariable=self.v_mysql_port)
        return p

    def _page_dirs(self) -> tk.Frame:
        p = self._page()
        tk.Label(p, text="ステップ 4 / 5  –  保存先・Python", bg=COLOR_BG, fg=COLOR_FG,
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

        lf3 = self._lf(p, "Python 実行ファイル（自動起動に使用）")
        row3 = tk.Frame(lf3, bg=COLOR_PANEL)
        row3.pack(fill="x", pady=2)
        self._entry(row3, self.v_python_exe).pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Button(row3, text="参照", bg=COLOR_PANEL, fg=COLOR_FG,
                  command=lambda: self._browse_exe(self.v_python_exe)).pack(side="left")
        tk.Label(lf3,
                 text="pythonw.exe を選ぶとウィンドウが非表示になります（推奨）。\n"
                      "conda env の場合: Anaconda3\\envs\\<env>\\pythonw.exe",
                 bg=COLOR_PANEL, fg="#E5CAFF", justify="left").pack(anchor="w", pady=(4, 0))
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
        tk.Label(lf,
                 text="・SYSTEM アカウントで実行されるため、ログイン不要で起動します。\n"
                      "・pythonw.exe を使うのでコンソールウィンドウは表示されません。\n"
                      "・ログは %ProgramData%\\TW_Prophet\\logs\\service.log に出力されます。\n"
                      "・登録には管理者権限が必要です（必要な場合は昇格ダイアログが表示されます）。",
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
        pass

    # ------------------------------------------------------------------
    # 設定生成 / 保存
    # ------------------------------------------------------------------
    def _build_settings_dict(self) -> dict[str, Any]:
        mode_val = MODES.get(self.v_mode.get(), "internal")
        s: dict[str, Any] = {
            "data_mode":  mode_val,
            "port":       self.v_port.get(),
            "data_dir":   self.v_data_dir.get(),
            "models_dir": self.v_models_dir.get(),
            "python_exe": self.v_python_exe.get(),
        }
        if mode_val == "internal":
            base = self.v_mdb_base.get().strip()
            s["mdb_base_dir"]      = base
            s["shipment_mdb"]      = self.v_shipment_mdb.get().strip()  or f"{base}\\簡易受注管理.mdb"
            s["post_shipment_mdb"] = self.v_post_ship_mdb.get().strip() or f"{base}\\出荷管理.mdb"
            s["manufacture_mdb"]   = self.v_mfg_mdb.get().strip()       or f"{base}\\製造管理.mdb"
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

            cfg = self._build_settings_dict()
            with SETTINGS_FILE.open("w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

            mysql = self._build_mysql_dict()
            if any(mysql.get(k) for k in ("host", "user", "database")):
                mysql_path = SETTINGS_DIR / "mysql_config.json"
                with mysql_path.open("w", encoding="utf-8") as f:
                    json.dump(mysql, f, ensure_ascii=False, indent=2)

            if self.v_auto_start.get():
                self._register_task()

            messagebox.showinfo(
                "完了",
                f"設定を保存しました:\n{SETTINGS_FILE}\n\n"
                "Windows 再起動後、TW_Prophet が自動起動します。\n"
                "今すぐ起動する場合はタスクスケジューラから手動で開始してください。",
            )
            self.destroy()

        except PermissionError:
            messagebox.showerror(
                "エラー",
                f"{SETTINGS_FILE} への書き込み権限がありません。\n管理者として実行してください。",
            )
        except Exception as e:
            messagebox.showerror("エラー", f"保存中にエラーが発生しました:\n{e}")

    def _register_task(self) -> None:
        """register_startup.ps1 を管理者権限で実行する。
        管理者権限がない場合は ShellExecute runas で UAC 昇格ダイアログを表示する。
        """
        script = INSTALL_DIR / "scripts" / "register_startup.ps1"
        if not script.exists():
            messagebox.showwarning("警告", f"register_startup.ps1 が見つかりません:\n{script}")
            return

        python_exe = self.v_python_exe.get().strip()
        ps_args = (
            f'-ExecutionPolicy Bypass -File "{script}" '
            f'-Port {self.v_port.get()} '
            f'-InstallDir "{INSTALL_DIR}" '
            f'-PythonExe "{python_exe}"'
        )

        if _is_admin():
            # 既に管理者 → 直接実行（-File 形式で引数を確実に渡す）
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(script),
                 "-Port", str(self.v_port.get()),
                 "-InstallDir", str(INSTALL_DIR),
                 "-PythonExe", python_exe],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # 日本語 Windows のコンソールは cp932。UTF-8 で失敗したら cp932 で再試行
            def _decode(b: bytes) -> str:
                for enc in ("utf-8", "cp932", "utf-16"):
                    try:
                        return b.decode(enc)
                    except Exception:
                        pass
                return b.decode("utf-8", errors="replace")

            if result.returncode != 0:
                err = (_decode(result.stderr) or _decode(result.stdout) or "不明なエラー")[:800]
                messagebox.showwarning(
                    "自動起動登録の警告",
                    "タスクスケジューラへの登録に失敗しました。\n\n" + err,
                )
            else:
                messagebox.showinfo("自動起動", "タスクスケジューラへの登録が完了しました。")
        else:
            # UAC 昇格 → 結果は非同期なので成功/失敗の確認は省略
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", "powershell.exe", ps_args, None, 1
            )
            if ret <= 32:
                messagebox.showwarning(
                    "自動起動登録の警告",
                    "管理者昇格がキャンセルされたか失敗しました。\n"
                    "後から手動で register_startup.ps1 を管理者として実行してください。",
                )
            else:
                messagebox.showinfo(
                    "自動起動",
                    "管理者権限でタスク登録を実行しています。\n"
                    "しばらく待ってから Windows を再起動してください。",
                )


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    app = SetupWizard()
    app.mainloop()


if __name__ == "__main__":
    main()
