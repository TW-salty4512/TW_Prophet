"""
#################################################
2025/02
-TW_Prophet-
app.py
#################################################
"""
import tkinter as tk
import pandas as pd
from tkinter import Listbox, Button, Label, messagebox, Toplevel, SINGLE, MULTIPLE, ttk
import os
import json
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

COLOR_BG_MAIN   = "#221B44"  # メイン背景色
COLOR_BG_SUB    = "#2E2E3E"  # サブ背景色 (listboxなど)
COLOR_FG_TEXT   = "#80FFEA"  # テキスト用の明るい色
COLOR_FG_ACCENT = "#E5CAFF"  # 見出しや強調用
COLOR_HIGHLIGHT = "#3A3A4E"  # 選択時の背景など

DEFAULT_FONT    = ("M PLUS 1p", 12)
TITLE_FONT      = ("M PLUS 1p", 12, "bold")

# 他ファイルからのクラスをインポート
from ui_frontend import ParallelogramButton
from access_handler import AccessHandler
from model_handler import ModelHandler
from email_notifier import EmailNotifier

class TW_prophet:
    def __init__(self):
        self.root = tk.Tk()
        # タイトルやウィンドウサイズ
        self.root.title("TW_Prophet")
        self.root.configure(bg=COLOR_BG_MAIN)
        self.root.geometry("1200x800")

        iconfile = "icon.ico"
        if os.path.exists(iconfile):
            self.root.iconbitmap(default=iconfile)

        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure(
            "TLabel",
            background=COLOR_BG_MAIN,
            foreground=COLOR_FG_TEXT,
            font=DEFAULT_FONT
        )
        style.configure(
            "TFrame",
            background=COLOR_BG_MAIN
        )
        
        # 左フレーム
        self.left_frame = tk.Frame(
            self.root,
            bg=COLOR_BG_MAIN,
            bd=2,
            width=250
        )
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)

        Label(
            self.left_frame,
            text="製品リスト (検索可)",
            bg=COLOR_BG_MAIN,
            fg=COLOR_FG_ACCENT,
            font=TITLE_FONT
        ).pack(pady=(10, 5))

        # 検索用フレーム
        search_frame = tk.Frame(self.left_frame, bg=COLOR_BG_MAIN)
        search_frame.pack(pady=5)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=DEFAULT_FONT,
            width=20,
            bg=COLOR_BG_SUB,      # 背景を統一
            fg=COLOR_FG_TEXT,
            highlightthickness=0
        )
        self.search_entry.pack(side=tk.LEFT, padx=(0, 5))

        self.search_button = Button(
            search_frame,
            text="検索",
            font=DEFAULT_FONT,
            command=self.update_filter,
            bg="#3A0CA3",  # ボタン色は ParallelogramButton ではないため別指定
            fg="white",
            relief=tk.RAISED
        )
        self.search_button.pack(side=tk.LEFT)

        # リストボックス
        self.listbox = tk.Listbox(
            self.left_frame,
            selectmode=SINGLE,
            width=30, height=25,
            bg=COLOR_BG_SUB,
            fg=COLOR_FG_TEXT,
            highlightthickness=0,
            selectbackground=COLOR_HIGHLIGHT,
            selectforeground="#FFFFFF",
            font=DEFAULT_FONT
        )
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self._auto_plot_job = None
        self._last_auto_plot_barcode = None
        self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select_auto_plot)

        # 中央フレーム
        self.center_frame = tk.LabelFrame(
            self.root,
            text="ディスプレイ",
            fg=COLOR_FG_ACCENT,
            bg=COLOR_BG_MAIN,
            bd=2,
            font=TITLE_FONT
        )
        self.center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.plot_frame = tk.Frame(self.center_frame, bg="#444444")
        self.plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._plot_convas = None

        # 右フレーム
        self.right_frame = tk.Frame(
            self.root,
            bg=COLOR_BG_MAIN
        )
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=20, pady=20)

        # 学習系ラベルフレーム
        self.frame_train = tk.LabelFrame(
            self.right_frame,
            text="学習系",
            fg=COLOR_FG_TEXT,
            bg=COLOR_BG_MAIN,
            bd=2,
            font=TITLE_FONT
        )
        self.frame_train.pack(fill=tk.X, pady=10)

        # 予測系ラベルフレーム
        self.frame_predict = tk.LabelFrame(
            self.right_frame,
            text="予測系",
            fg=COLOR_FG_TEXT,
            bg=COLOR_BG_MAIN,
            bd=2,
            font=TITLE_FONT
        )
        self.frame_predict.pack(fill=tk.X, pady=10)

        # 学習系ボタン
        btn_db = ParallelogramButton(
            self.frame_train, text="DBから取得",
            command=self.load_data_from_db, width=180, height=50,
            bg_normal="#388E3C", bg_hover="#66BB6A",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_db.pack(pady=5)

        # 学習(選択製品)
        btn_train1 = ParallelogramButton(
            self.frame_train, text="学習(選択製品)",
            command=self.train_product, width=180, height=50,
            bg_normal="#F57C00", bg_hover="#FFA726",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_train1.pack(pady=5)

        # 一斉学習
        btn_trainAll = ParallelogramButton(
            self.frame_train, text="一斉学習",
            command=self.train_all_products, width=180, height=50,
            bg_normal="#E65100", bg_hover="#FF7043",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_trainAll.pack(pady=5)

        # 予測実行
        btn_predictOne = ParallelogramButton(
            self.frame_predict, text="予測実行",
            command=self.run_prediction, width=180, height=50,
            bg_normal="#1976D2", bg_hover="#42A5F5",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_predictOne.pack(pady=5)

        # 一斉予測
        btn_predictAll = ParallelogramButton(
            self.frame_predict, text="一斉予測",
            command=self.predict_all_without_mail, width=180, height=50,
            bg_normal="#1565C0", bg_hover="#1E88E5",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_predictAll.pack(pady=5)

        # 一斉予測＆通知
        btn_predictAndMail = ParallelogramButton(
            self.frame_predict, text="一斉予測＆通知",
            command=self.predict_and_notify_all, width=180, height=50,
            bg_normal="#C62828", bg_hover="#EF5350",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_predictAndMail.pack(pady=5)

        # 除外対象を選択
        btn_exclusion = ParallelogramButton(
            self.frame_predict, text="除外対象を選択",
            command=self.open_exclusion_window, width=180, height=50,
            bg_normal="#6A1B9A", bg_hover="#AB47BC",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_exclusion.pack(pady=5)

        # 除外解除（管理）
        btn_exclusion_manage = ParallelogramButton(
            self.frame_predict, text="除外解除（管理）",
            command=self.open_exclusion_management_window, width=180, height=50,
            bg_normal="#4A148C", bg_hover="#9C27B0",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_exclusion_manage.pack(pady=5)

        # 週次リスト管理
        btn_weekly_list = ParallelogramButton(
            self.frame_predict, text="週次リスト管理",
            command=self.open_weekly_list_management_window, width=180, height=50,
            bg_normal="#006064", bg_hover="#00838F",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_weekly_list.pack(pady=5)

        # メール設定ボタン
        btn_email_config = ParallelogramButton(
            self.frame_predict, text = "メール設定",
            command=self.open_email_setting_window, width=180, height=50,
            bg_normal="#00897B", bg_hover="#26A69A",
            outline_color="#FFFFFF", text_color="#FFFFFF"
        )
        btn_email_config.pack(pady=5)
        
        self.access_handler = AccessHandler()
        self.model_handler = ModelHandler()
        self.email_notifier = EmailNotifier()

        # DBから取得したデータ保持用
        self.data = None
        self.inventory_data = None
        self.all_barcodes = []

        self.email_list=[]
        self.load_email_list()
        self.email_notifier.set_to_addrs(self.email_list)

        # 除外リスト
        self.excluded_products = set()
        self.load_exclusion_list()

        # 週次データ学習リスト
        self.weekly_data_products = set()
        self.load_weekly_list()
        self.loading_label = None
        self.auto_connect_db()

    def show_loading(self, message="処理中...しばらくお待ちください"):
        """
        重い処理中に「実行中...」ラベルを画面中央に表示し、ユーザーに処理中であることを伝える
        """
        if self.loading_label is not None:
            return

        self.loading_label = tk.Label(
            self.root,
            text=message,
            bg="#221B44",
            fg="#FFA",  # 少し目立つよう薄い黄色
            font=("Consolas", 16, "bold")
        )
        self.loading_label.place(relx=0.5, rely=0.5, anchor="center")
        self.root.update()

    def hide_loading(self):
        """
        ローディングラベルを削除
        """
        if self.loading_label is not None:
            self.loading_label.destroy()
            self.loading_label = None
        self.root.update()
    
    # ---------------------
    # データ取得・画面表示
    # ---------------------
    def auto_connect_db(self):
        try:
            self.load_data_from_db()
        except Exception as e:
            messagebox.showerror("エラー", f"起動時のDB接続に失敗: {e}")

    def load_data_from_db(self):
        """DBから出荷データ・在庫データを取得してListboxにバーコード一覧を表示"""
        self.show_loading("DBからデータ取得中...")
        try:
            self.data = self.access_handler.get_shipment_data()
            self.data = self.data[self.data['バーコード'].notnull()]

            self.inventory_data = self.access_handler.get_inventory_data()
            self.inventory_data = self.inventory_data[self.inventory_data['バーコード'].notnull()]

            self.all_barcodes = list(self.data['バーコード'].unique())
            self.populate_barcodes()
            messagebox.showinfo("成功", "データベースからデータの取得が完了しました！")
        except Exception as e:
            messagebox.showerror("エラー", f"データ取得中にエラーが発生しました: {e}")
        finally:
            self.hide_loading()

    def populate_barcodes(self):
        """Listboxにバーコード一覧を表示（除外対象を除く）"""
        if self.data is None:
            return

        self.listbox.delete(0, tk.END)
        search_word = self.search_var.get().strip().lower()
        for bc in self.all_barcodes:
            if bc is None:
                continue
            if bc not in self.excluded_products:
                bc_lower = bc.lower()
                if search_word == "" or search_word in bc_lower:
                    self.listbox.insert(tk.END, bc)
    
    def update_filter(self, *args):
        self.populate_barcodes()

    def on_listbox_select_auto_plot(self, event=None):
        """
        製品リストで選択が変わったら、すぐにバックテストプロットを表示します。
        ※「予測実行」ボタンは、部品アラート等も含むフル処理用として残します。
        """
        selection = self.listbox.curselection()
        if not selection:
            return

        barcode = self.listbox.get(selection[0])

        # 除外中は何もしない
        if barcode in self.excluded_products:
            return

        # 同じバーコードを何度も描画しない
        if barcode == self._last_auto_plot_barcode:
            return

        # ★変更点★ 実際に描画できたタイミングで _last_auto_plot_barcode を更新します
        # （処理中などで描画がスキップされても、次回の選択で表示できるように）

        # 直前の予約があればキャンセル（連打対策）
        if self._auto_plot_job is not None:
            try:
                self.root.after_cancel(self._auto_plot_job)
            except Exception:
                pass
            self._auto_plot_job = None

        # 少し遅延して実行（選択移動中のムダ描画を抑制）
        self._auto_plot_job = self.root.after(
            250,
            lambda bc=barcode: self._auto_plot_selected_product(bc)
        )
    
    def _auto_plot_selected_product(self, barcode: str):
        """
        選択された製品のバックテスト図だけを生成して中央に表示します。
        """
        # 選択が変わっていたらキャンセル
        selection = self.listbox.curselection()
        if not selection:
            return
        current_bc = self.listbox.get(selection[0])
        if current_bc != barcode:
            return

        if self.data is None:
            self.show_message_on_plot_screen("DB未接続です。先に「DBから取得」を実行してください。")
            return

        is_weekly = (barcode in self.weekly_data_products)

        # ★変更点★ 他の重い処理中は割り込み表示しない（ローディングラベル破壊を防ぐ）
        if self.loading_label is not None:
            return

        # ★変更点★ 最後に描画したバーコードとして記録（同一の連続描画を抑制）
        self._last_auto_plot_barcode = barcode

        self.show_loading("グラフ生成中...")

        try:
            if is_weekly:
                fig = self.model_handler.backtest_weekly_1month(self.data, barcode)
            else:
                fig = self.model_handler.backtest_monthly_1year(self.data, barcode)

            if fig is not None:
                self.show_plot_on_main_screen(fig)
            else:
                self.show_message_on_plot_screen("プロット生成に失敗しました。")

        except ValueError as ve:
            # モデル未学習/データ不足など（自動プレビューではポップアップ乱発を避けたい）
            self.show_message_on_plot_screen(
                f"{barcode}\n\n{ve}\n\n学習が必要なら「学習(選択製品)」を実行してください。"
            )
        except Exception as ex:
            self.show_message_on_plot_screen(f"{barcode}\n\nプロット中にエラー: {ex}")
        finally:
            self.hide_loading()

    def show_message_on_plot_screen(self, message: str):
        """
        中央のプロット領域にメッセージを表示します（ポップアップを出さない）。
        """
        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        lbl = tk.Label(
            self.plot_frame,
            text=message,
            bg="#444444",
            fg="#FFFFFF",
            font=("Consolas", 14),
            justify="left",
            anchor="nw"
        )
        lbl.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # ---------------------
    # 学習・予測
    # ---------------------
    def train_product(self):
        selected_index = self.listbox.curselection()
        if not selected_index:
            messagebox.showwarning("警告", "バーコードを選択してください。")
            return
        selected_barcode = self.listbox.get(selected_index)
        if selected_barcode in self.excluded_products:
            messagebox.showinfo("除外中", f"{selected_barcode} は除外対象です。")
            return
        if self.data is None:
            self.data = self.access_handler.get_shipment_data()

        self.show_loading("学習中...")
        try:
            # weekly_data_products に含まれていれば週次、そうでなければ月次
            if selected_barcode in self.weekly_data_products:
                self.model_handler.train_product_model_weekly(self.data, selected_barcode)
                msg = f"{selected_barcode} は週次モデルで学習しました。"
            else:
                self.model_handler.train_product_model_monthly(self.data, selected_barcode)
                msg = f"{selected_barcode} は月次モデルで学習しました。"
            messagebox.showinfo("完了", msg)
        except Exception as e:
            messagebox.showerror("エラー", f"学習中にエラー発生: {e}")
        finally:
            self.hide_loading()

    def run_prediction(self):
        selected_index = self.listbox.curselection()
        if not selected_index:
            messagebox.showwarning("警告", "バーコードを選択してください。")
            return
        selected_barcode = self.listbox.get(selected_index)
        if selected_barcode in self.excluded_products:
            messagebox.showinfo("除外中", f"{selected_barcode} は除外対象です。")
            return
        
        is_weekly = (selected_barcode in self.weekly_data_products)

        if self.data is None or self.inventory_data is None:
            try:
                self.data = self.access_handler.get_shipment_data()
                self.inventory_data = self.access_handler.get_inventory_data()
            except Exception as e:
                messagebox.showerror("エラー", f"データ再取得中にエラー: {e}")
                return

        product_inv_row = self.inventory_data[self.inventory_data['バーコード'] == selected_barcode]
        product_inventory = product_inv_row.iloc[0]['在庫数'] if not product_inv_row.empty else 0

        self.show_loading("バックテスト＆予測中...")

        try:
            if is_weekly:
                # 週次モデルの場合は 直近1か月バックテスト
                fig = self.model_handler.backtest_weekly_1month(self.data, selected_barcode)
            else:
                # 月次モデルの場合は 直近1年バックテスト
                fig = self.model_handler.backtest_monthly_1year(self.data, selected_barcode)

        except ValueError as ve:
            messagebox.showwarning("警告", f"バックテスト不可: {ve}")
            self.hide_loading()
            return
        except Exception as ex:
            messagebox.showerror("エラー", f"バックテスト中にエラー: {ex}")
            self.hide_loading()
            return

        # バックテスト結果を中央画面に表示
        if fig is not None:
            self.show_plot_on_main_screen(fig)

        # ---------------------
        # 部品在庫チェック
        # ---------------------
        try:
            df_parts = self.access_handler.get_parts_info(selected_barcode)
            if df_parts.empty:
                messagebox.showinfo("部品情報なし", f"{selected_barcode} に部品情報がありません。")
                self.hide_loading()
                return

            part_alerts = self.model_handler.predict_parts_depletion(
                product_barcode=selected_barcode,
                product_inventory=product_inventory,
                shipment_data=self.data,
                df_parts=df_parts,
                is_monthly=(not is_weekly)  # 週次でなければ月次扱い
            )

            if part_alerts:
                alert_text = "\n".join(part_alerts)
                messagebox.showwarning("部品在庫アラート", alert_text)
            else:
                messagebox.showinfo("部品OK", "半年前 & 1か月前アラートはありません。")

            six_months_days = (pd.Timestamp.now() + pd.DateOffset(months=6) -pd.Timestamp.now()).days
            one_month_days = (pd.Timestamp.now() + pd.DateOffset(months=1) -pd.Timestamp.now()).days

            if is_weekly:
                c_6mo = self.model_handler.predict_consumption_for_n_months_weekly(self.data, selected_barcode, n=6)
                c_1mo = self.model_handler.predict_consumption_for_n_months_weekly(self.data, selected_barcode, n=1)
            else:
                c_6mo = self.model_handler.predict_consumption_for_n_months_monthly(self.data, selected_barcode, n=6)
                c_1mo = self.model_handler.predict_consumption_for_n_months_monthly(self.data, selected_barcode, n=1)

            parts_info_list = []
            for idx, row in df_parts.iterrows():
                part_name = row['部品名']
                part_inv  = row['在庫数']

                if c_6mo > 0:
                    days_6mo = (product_inventory + part_inv) / c_6mo * six_months_days
                else:
                    days_6mo = None
                if c_1mo > 0:
                    days_1mo = (product_inventory + part_inv) / c_1mo * one_month_days
                else:
                    days_1mo = None

                parts_info_list.append((part_name, part_inv, days_6mo, days_1mo))
            
            self.show_parts_prediction_window(selected_barcode, product_inventory, parts_info_list)
        except Exception as ex2:
            messagebox.showerror("エラー", f"部品在庫チェックでエラー: {ex2}")
        finally:
            self.hide_loading()

    def show_plot_on_main_screen(self, fig):
        """取得したfigureを画面中央に表示"""
        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        self._plot_canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        self._plot_canvas.draw()
        self._plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def show_parts_prediction_window(self, barcode, product_inv, parts_info_list):
        """
        部品在庫残日数を一覧表示するためのウィンドウ
        """
        wnd = tk.Toplevel(self.root)
        wnd.title(f"{barcode} - 部品在庫予測")
        wnd.configure(bg="#1E1E2F")
        wnd.geometry("600x400")
        label_title = tk.Label(wnd, text=f"製品: {barcode}, 製品在庫={product_inv}", font=("Consolas", 14), bg="#1E1E2F", fg="#80FFEA")
        label_title.pack(pady=5)
        
        frame_tv = tk.Frame(wnd, bg ="#1E1E2F")
        frame_tv.pack(fill="both", expand=True, padx=10, pady=10)

        vsb = tk.Scrollbar(frame_tv, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        tree = ttk.Treeview(frame_tv,
                            columns=("part_name", "inventory", "days_6mo", "days_1mo"),
                            show="headings",
                            yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill="both", expand=True)
        vsb.config(command=tree.yview)

        tree.heading("part_name", text="部品名")
        tree.heading("inventory", text="部品在庫")
        tree.heading("days_6mo", text="半年残日数")
        tree.heading("days_1mo", text="1ヶ月残日数")

        tree.column("part_name", anchor=tk.W, width=150, stretch=True)
        tree.column("inventory", anchor=tk.E, width=70, stretch=False)
        tree.column("days_6mo", anchor=tk.E, width=100, stretch=False)
        tree.column("days_1mo", anchor=tk.E, width=100, stretch=False)

        for (pname, pinv, d6, d1) in parts_info_list:
            tree.insert("", "end",
                        values=(pname,
                                pinv,
                                f"{d6:.1f}日" if d6 is not None else "予測低下注意",
                                f"{d1:.1f}日" if d1 is not None else "予測低下注意"))
        
        style = ttk.Style()
        style.configure("Treeview", 
                        background="#1E1E2F", 
                        foreground="#80FFEA", 
                        fieldbackground="#1E1E2F")
        tree.configure(style="Treeview")

    def train_all_products(self):
        """除外対象以外のバーコードを一括学習（週次or月次を振り分け）"""
        if self.data is None:
            self.data = self.access_handler.get_shipment_data()

        self.show_loading("一斉学習を実行中...")
        try:
            barcodes = self.data['バーコード'].unique()
            for barcode in barcodes:
                if barcode in self.excluded_products:
                    continue
                try:
                    if barcode in self.weekly_data_products:
                        self.model_handler.train_product_model_weekly(self.data, barcode)
                    else:
                        self.model_handler.train_product_model_monthly(self.data, barcode)
                except Exception as e:
                    print(f"学習失敗: {barcode} -> {e}")
        finally:
            self.hide_loading()

        messagebox.showinfo("完了", "一斉学習が完了しました。")

    def predict_and_notify_all(self):
        """
        除外対象以外の全バーコードについて1か月分の消費予測を行い、
        1か月以内に在庫切れになりそうな製品と部品を HTMLメールで通知
        """
        if self.data is None:
            self.data = self.access_handler.get_shipment_data()
        if self.inventory_data is None:
            self.inventory_data = self.access_handler.get_inventory_data()

        self.show_loading("一斉予測＆メール通知を実行中...")
        product_alert_list = []
        parts_alert_details = []
        no_parts_list = []
        try:
            barcodes = self.data['バーコード'].unique()
            for barcode in barcodes:
                if barcode in self.excluded_products:
                    continue
                six_months_days = (pd.Timestamp.now() + pd.DateOffset(months=6) - pd.Timestamp.now()).days
                one_month_days = (pd.Timestamp.now() + pd.DateOffset(months=1) - pd.Timestamp.now()).days
                # --- 週次 or 月次 を判定 ---
                if barcode in self.weekly_data_products:
                    c_1mo = self.model_handler.predict_consumption_for_n_months_weekly(self.data, barcode, n=1)
                    c_6mo = self.model_handler.predict_consumption_for_n_months_weekly(self.data, barcode, n=6)
                else:
                    c_1mo = self.model_handler.predict_consumption_for_n_months_monthly(self.data, barcode, n=1)
                    c_6mo = self.model_handler.predict_consumption_for_n_months_monthly(self.data, barcode, n=6)

                row_inv = self.inventory_data[self.inventory_data['バーコード'] == barcode]
                product_inv = row_inv.iloc[0]['在庫数'] if not row_inv.empty else 0

                df_parts = self.access_handler.get_parts_info(barcode)
                if df_parts.empty:
                    no_parts_list.append(barcode)
                    continue

                # 部品ごとの 半年/1か月残日数
                for idx, row in df_parts.iterrows():
                    part_name = row['部品名']
                    part_inv  = row['在庫数']

                    if c_6mo > 0:
                        days_6mo = (product_inv + part_inv) / c_6mo * six_months_days
                    else:
                        days_6mo = None
                    if c_1mo > 0:
                        days_1mo = (product_inv + part_inv) / c_1mo * one_month_days
                    else:
                        days_1mo = None

                    # 表示用ステータス文字列
                    halfyear_status = f"OK({days_6mo:.1f}日)"
                    if days_6mo <= 180:
                        halfyear_status = f"危険(残{days_6mo:.1f}日)"

                    onemonth_status = f"OK({days_1mo:.1f}日)"
                    if days_1mo <= 30:
                        onemonth_status = f"危険(残{days_1mo:.1f}日)"

                    parts_alert_details.append((barcode, part_name, part_inv,
                                                halfyear_status, onemonth_status))

                months_left = None
                days_left   = None
                if barcode in self.weekly_data_products:
                    try:
                        months_left, days_left = self.model_handler.predict_months_left_weekly(
                            shipment_data=self.data,
                            inventory_data=self.inventory_data,
                            barcode=barcode
                        )
                    except:
                        pass
                else:
                    try:
                        months_left, days_left = self.model_handler.predict_months_left_monthly(
                            shipment_data=self.data,
                            inventory_data=self.inventory_data,
                            barcode=barcode
                        )
                    except:
                        pass

                if (months_left is not None) and (days_left is not None):
                    if months_left < 1.0:
                        product_alert_list.append((barcode, months_left, days_left))

        finally:
            self.hide_loading()

        # HTML整形
        if not (product_alert_list or parts_alert_details):
            messagebox.showinfo("在庫OK", "部品・製品とも警告アラートはありませんでした。")
            return

        html_body = []
        html_body.append("<html><head><meta charset='utf-8'></head><body>")
        html_body.append("<h2>在庫警告レポート</h2>")

        if parts_alert_details:
            html_body.append("<h3>部品 在庫アラート一覧(半年/1か月)</h3>")
            html_body.append("<table border='1' cellspacing='0' cellpadding='4' style='border-collapse: collapse;'>")
            html_body.append("<tr><th>製品バーコード</th><th>部品名</th><th>部品在庫</th><th>半年状況</th><th>1か月状況</th></tr>")
            for (bc, p_name, p_inv, half_stat, one_stat) in parts_alert_details:
                html_body.append(f"<tr><td>{bc}</td><td>{p_name}</td><td>{p_inv}</td><td>{half_stat}</td><td>{one_stat}</td></tr>")
            html_body.append("</table>")
        else:
            html_body.append("<p>部品在庫のアラートはありません。</p>")

        html_body.append("</body></html>")
        body_final = "\n".join(html_body)

        subject = "【在庫警告】部品＆製品の在庫減少報告"
        try:
            self.email_notifier.send_notification(subject, body_final, html_mode=True)
            messagebox.showinfo("完了", "部品および製品の在庫アラート(HTML)メールを送信しました。")
        except Exception as e:
            messagebox.showerror("エラー", f"メール送信中にエラーが発生しました: {e}")

    def predict_all_without_mail(self):
        """
        週次・月次に分けて一斉に予測を実行（メール送信しない）。
        ここでは結果をGUIテーブルで見れるようにしている例。
        """
        if self.data is None:
            self.data = self.access_handler.get_shipment_data()
        if self.inventory_data is None:
            self.inventory_data = self.access_handler.get_inventory_data()

        self.show_loading("一斉予測を実行中...")
        parts_table_data = []
        no_parts_list = []
        try:
            barcodes = self.data['バーコード'].unique()
            for barcode in barcodes:
                if barcode in self.excluded_products:
                    continue
                
                six_months_days = (pd.Timestamp.now() + pd.DateOffset(months=6) - pd.Timestamp.now()).days
                one_month_days = (pd.Timestamp.now() + pd.DateOffset(months=1) - pd.Timestamp.now()).days

                # --- 週次 or 月次 の判定 ---
                if barcode in self.weekly_data_products:
                    # 週次
                    c_6mo = self.model_handler.predict_consumption_for_n_months_weekly(self.data, barcode, n=6)
                    c_1mo = self.model_handler.predict_consumption_for_n_months_weekly(self.data, barcode, n=1)
                else:
                    # 月次
                    c_6mo = self.model_handler.predict_consumption_for_n_months_monthly(self.data, barcode, n=6)
                    c_1mo = self.model_handler.predict_consumption_for_n_months_monthly(self.data, barcode, n=1)

                row_inv = self.inventory_data[self.inventory_data['バーコード'] == barcode]
                product_inv = row_inv.iloc[0]['在庫数'] if not row_inv.empty else 0

                df_parts = self.access_handler.get_parts_info(barcode)
                if df_parts.empty:
                    no_parts_list.append(barcode)
                    continue

                # 部品ごとの在庫残日数を計算
                for idx, row in df_parts.iterrows():
                    part_name = row['部品名']
                    part_inv = row['在庫数']

                    # 6ヶ月分（=6×30日）と 1ヶ月分（=30日）の残日数
                    days_6mo = 999999
                    if c_6mo > 0:
                        days_6mo = (product_inv + part_inv) / c_6mo * six_months_days
                    days_1mo = 999999
                    if c_1mo > 0:
                        days_1mo = (product_inv + part_inv) / c_1mo * one_month_days

                    parts_table_data.append((barcode, part_name, part_inv, days_6mo, days_1mo))

                if barcode in self.weekly_data_products:
                    try:
                        self.model_handler.predict_months_left_weekly(
                            shipment_data=self.data,
                            inventory_data=self.inventory_data,
                            barcode=barcode
                        )
                    except ValueError:
                        continue
                    except Exception:
                        continue
                else:
                    try:
                        months_left, days_left = self.model_handler.predict_months_left_monthly(
                            shipment_data=self.data,
                            inventory_data=self.inventory_data,
                            barcode=barcode
                        )
                    except Exception:
                        pass

        finally:
            self.hide_loading()

        if no_parts_list:
            self.show_no_parts_table(no_parts_list)

        # 計算結果をテーブル表示
        self.show_all_parts_prediction_window(parts_table_data)

    def show_no_parts_table(self, no_parts_list):
        """
        部品が見つからなかった製品のリストをTreeViewで表示
        """
        wnd = tk.Toplevel(self.root)
        wnd.title("部品が見つからなかった製品一覧")
        wnd.configure(bg = "#1E1E2F")
        wnd.geometry("350x200")
        tree = ttk.Treeview(wnd, columns=("barcode",), show="headings")
        tree.heading("barcode", text="バーコード")
        tree.pack(fill="both", expand=True)
        for bc in no_parts_list:
            tree.insert("", "end", values=(bc,))

    def show_all_parts_prediction_window(self, parts_table_data):
        """
        全製品の部品在庫予測結果を一覧表示するためのウィンドウ。
        """
        wnd = Toplevel(self.root)
        wnd.title("全製品 部品在庫予測一覧")
        wnd.configure(bg="#1E1E2F")
        wnd.geometry("700x500")
        
        frame_tv = tk.Frame(wnd, bg="#1E1E2F")
        frame_tv.pack(fill="both", expand=True, padx=10, pady=10)

        vsb = tk.Scrollbar(frame_tv, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        tree = ttk.Treeview(frame_tv,
                            columns=("barcode", "part_name", "part_inv", "days_6mo", "days_1mo"),
                            show="headings",
                            yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill="both", expand=True)
        vsb.config(command=tree.yview)

        tree.heading("barcode", text="製品バーコード")
        tree.heading("part_name", text="部品名")
        tree.heading("part_inv", text="部品在庫")
        tree.heading("days_6mo", text="半年残日数")
        tree.heading("days_1mo", text="1ヶ月残日数")

        tree.column("barcode", anchor=tk.W, width=150, stretch=True)
        tree.column("part_name", anchor=tk.W, width=150, stretch=True)
        tree.column("part_inv", anchor=tk.E, width=80, stretch=False)
        tree.column("days_6mo", anchor=tk.E, width=100, stretch=False)
        tree.column("days_1mo", anchor=tk.E, width=100, stretch=False)

        for (barcode, part_name, part_inv, d6, d1) in parts_table_data:
            tree.insert("", "end",
                        values=(barcode,
                                part_name,
                                part_inv,
                                f"{d6:.1f}",
                                f"{d1:.1f}"))
        
        style = ttk.Style()
        style.configure("Treeview", 
                        background="#1E1E2F", 
                        foreground="#80FFEA", 
                        fieldbackground="#1E1E2F")
        tree.configure(style="Treeview")

    # ---------------------
    # 除外対象選択ウィンドウ
    # ---------------------
    def open_exclusion_window(self):
        """
        新たに表示するウィンドウで、複数のバーコードを選択し、
        「完了」押下で除外対象に登録する。
        """
        if self.data is None:
            messagebox.showwarning("警告", "まずはデータベースから取得してください。")
            return

        excl_window = Toplevel(self.root)
        excl_window.title("除外対象を選択")
        excl_window.configure(bg="#1E1E2F")
        excl_window.geometry("400x400")
        Label(excl_window, text="除外したい製品を選択してください", font=("Consolas", 12),
              bg="#1E1E2F", fg="#80FFEA").pack(pady=5)

        listbox_excl = Listbox(excl_window, selectmode=MULTIPLE, width=40, height=15,
                               bg="#2E2E3E", fg="#80FFEA")
        listbox_excl.pack(pady=10)

        # すべてのバーコードをリストに表示（既に除外中は除外）
        all_barcodes = self.data['バーコード'].unique()
        for barcode in all_barcodes:
            if barcode not in self.excluded_products:
                listbox_excl.insert(tk.END, barcode)

        def apply_exclusion():
            selected_indices = listbox_excl.curselection()
            for idx in selected_indices:
                bc = listbox_excl.get(idx)
                self.excluded_products.add(bc)
            self.save_exclusion_list()
            messagebox.showinfo("除外設定", "選択されたものを除外します")
            self.populate_barcodes()
            excl_window.destroy()

        Button(excl_window, text="完了", command=apply_exclusion, bg="#4361EE",
               fg="#FFFFFF").pack(pady=5)

    # ---------------------
    # 除外リストの保存・読込
    # ---------------------
    def load_exclusion_list(self):
        """除外リストをファイルから読み込む。"""
        if os.path.exists("excluded_products.json"):
            with open("excluded_products.json", "r", encoding="utf-8") as f:
                self.excluded_products = set(json.load(f))
        else:
            self.excluded_products = set()

    def save_exclusion_list(self):
        """除外リストをファイルに保存する。"""
        with open("excluded_products.json", "w", encoding="utf-8") as f:
            json.dump(list(self.excluded_products), f, ensure_ascii=False, indent=2)

    # -------------------------
    # 除外管理ウィンドウ (除外解除用)
    # -------------------------
    def open_exclusion_management_window(self):
        """
        除外リストに入っているアイテムを表示。
        ユーザーが複数選択し、「除外解除」ボタン押下でexcluded_productsから削除。
        """
        if not self.excluded_products:
            messagebox.showinfo("除外リスト", "現在、除外されている製品はありません。")
            return

        manage_window = Toplevel(self.root)
        manage_window.title("除外管理 - 解除")
        manage_window.configure(bg="#1E1E2F")
        manage_window.geometry("400x400")
        Label(manage_window, text="除外中の製品一覧", font=("Consolas", 12),
              bg="#1E1E2F", fg="#80FFEA").pack(pady=5)

        listbox_excl = Listbox(manage_window, selectmode=MULTIPLE, width=40, height=15, 
                               bg="#2E2E3E", fg="#80FFEA")
        listbox_excl.pack(pady=10)

        for bc in sorted(self.excluded_products):
            listbox_excl.insert(tk.END, bc)

        def remove_exclusion():
            selected_indices = listbox_excl.curselection()
            if not selected_indices:
                messagebox.showwarning("警告", "除外解除したい製品を選択してください。")
                return

            removed_list = []
            for idx in reversed(selected_indices):
                bc = listbox_excl.get(idx)
                if bc in self.excluded_products:
                    self.excluded_products.remove(bc)
                    removed_list.append(bc)
                listbox_excl.delete(idx)
            if removed_list:
                messagebox.showinfo("除外解除", "以下の製品を除外解除しました:\n" + "\n".join(removed_list))
            self.populate_barcodes()

        def done():
            self.save_exclusion_list()
            messagebox.showinfo("除外管理", "除外リストを更新しました。")
            self.populate_barcodes()
            manage_window.destroy()

        btn_frame = tk.Frame(manage_window, bg="#1E1E2F")
        btn_frame.pack(pady=10)

        Button(btn_frame, text="除外解除", command=remove_exclusion, bg="#4361EE",
               fg="#FFFFFF").pack(side=tk.LEFT, padx=5)
        Button(btn_frame, text="完了", command=done, bg="#80FFEA", fg="#1E1E2F").pack(side=tk.LEFT, padx=5)

    # ---------------------
    # 週次リスト管理
    # ---------------------
    def open_weekly_list_management_window(self):
        """
        左クリックで選択・解除のトグルを行い、完了ボタンで保存
        """
        if self.data is None:
            messagebox.showwarning("警告", "まずはDBからデータを取得してください。")
            return

        wnd = Toplevel(self.root)
        wnd.title("週次データ学習リスト管理")
        wnd.configure(bg="#1E1E2F")
        wnd.geometry("400x450")

        Label(wnd, text="週次データ学習リスト(除外対象を除く)\n左クリックで選択/解除できます",
              font=("Consolas", 12), bg="#1E1E2F", fg="#80FFEA").pack(pady=5)

        frame_list = tk.Frame(wnd, bg="#1E1E2F")
        frame_list.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(frame_list, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox_weekly = Listbox(frame_list,
                                      selectmode=SINGLE,
                                      width=40, height=15,
                                      bg="#2E2E3E", fg="#80FFEA",
                                      yscrollcommand=scrollbar.set)
        self.listbox_weekly.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.config(command=self.listbox_weekly.yview)

        # 表示用データ
        display_barcodes = []
        for bc in self.all_barcodes:
            if bc is not None and bc not in self.excluded_products:
                display_barcodes.append(bc)
        display_barcodes = sorted(display_barcodes)

        # リストボックスへ追加
        for bc in display_barcodes:
            self.listbox_weekly.insert(tk.END, bc)

        def update_item_colors():
            for i, bc in enumerate(display_barcodes):
                if bc in self.weekly_data_products:
                    # 週次に入っているならハイライト
                    self.listbox_weekly.itemconfig(i, {'bg': '#444466', 'fg': '#FFFFFF'})
                else:
                    # そうでなければデフォルト色
                    self.listbox_weekly.itemconfig(i, {'bg': '#2E2E3E', 'fg': '#80FFEA'})

        def on_click(event):
            selection = self.listbox_weekly.curselection()
            if not selection:
                return
            idx = selection[0]
            bc = display_barcodes[idx]
            if bc in self.weekly_data_products:
                self.weekly_data_products.remove(bc)
            else:
                self.weekly_data_products.add(bc)
            update_item_colors()

        self.listbox_weekly.bind("<Button-1>", on_click)
        update_item_colors()

        def apply_changes():
            self.save_weekly_list()
            messagebox.showinfo("週次リスト更新", "週次データ学習リストを更新しました。")
            wnd.destroy()

        Button(wnd, text="完了", command=apply_changes,
               bg="#80FFEA", fg="#1E1E2F").pack(pady=10)

    # ---------------------
    # 週次リスト 読込・保存
    # ---------------------
    def load_weekly_list(self):
        fname = "weekly_data_list.json"
        if os.path.exists(fname):
            with open(fname, "r", encoding="utf-8") as f:
                self.weekly_data_products = set(json.load(f))
        else:
            # デフォルト例
            self.weekly_data_products = set(["KB-IT4", "KB-IOPAD4"])
            self.save_weekly_list()

    def save_weekly_list(self):
        with open("weekly_data_list.json", "w", encoding="utf-8") as f:
            json.dump(list(self.weekly_data_products), f, ensure_ascii=False, indent=2)

    # ---------------------
    # メール設定ウィンドウ
    # ---------------------
    def open_email_setting_window(self):
        """
        メールアドレスのリストを管理するウィンドウを開く
        """
        wnd = tk.Toplevel(self.root)
        wnd.title("メールアドレス設定")
        wnd.configure(bg="#1E1E2F")
        wnd.geometry("400x400")

        lbl = tk.Label(wnd, text="送信先メールアドレスを管理します", bg="#1E1E2F", fg="#80FFEA",
                       font=("Consolas", 12))
        lbl.pack(pady=5)

        frame_list = tk.Frame(wnd, bg="#1E1E2F")
        frame_list.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(frame_list, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox_mail = tk.Listbox(frame_list, selectmode=tk.SINGLE,
                                       bg="#2E2E3E", fg="#80FFEA",
                                       yscrollcommand=scrollbar.set, width=40, height=10)
        self.listbox_mail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox_mail.yview)
        
        for addr in self.email_list:
            self.listbox_mail.insert(tk.END, addr)

        add_frame = tk.Frame(wnd, bg="#1E1E2F")
        add_frame.pack(pady=5)
        tk.Label(add_frame, text="メールアドレス: ", bg="#1E1E2F", fg="#80FFEA",
                 font=("Consolas", 10)).pack(side=tk.LEFT)

        new_addr_var = tk.StringVar()
        entry_addr = tk.Entry(add_frame, textvariable=new_addr_var, width=25,
                              bg="#2E2E3E", fg="#80FFEA")
        entry_addr.pack(side=tk.LEFT, padx=5)

        def add_address():
            addr = new_addr_var.get().strip()
            if addr and addr not in self.email_list:
                self.email_list.append(addr)
                self.listbox_mail.insert(tk.END, addr)
                new_addr_var.set("")  # 入力欄をクリア

        btn_add = tk.Button(add_frame, text="追加", bg="#4CAF50", fg="#FFFFFF",
                            command=add_address)
        btn_add.pack(side=tk.LEFT)

        def remove_address():
            sel = self.listbox_mail.curselection()
            if not sel:
                messagebox.showinfo("情報", "削除するアドレスを選択してください")
                return
            idx = sel[0]
            addr = self.listbox_mail.get(idx)
            if addr in self.email_list:
                self.email_list.remove(addr)
            self.listbox_mail.delete(idx)

        btn_remove = tk.Button(wnd, text="削除", bg="#F44336", fg="#FFFFFF",
                               command=remove_address)
        btn_remove.pack(pady=5)

        def save_addresses():
            self.email_notifier.set_to_addrs(self.email_list)
            self.save_email_list()
            messagebox.showinfo("保存", "メールアドレス設定を保存しました。")
            wnd.destroy()

        btn_save = tk.Button(wnd, text="保存して閉じる", bg="#80FFEA", fg="#1E1E2F",
                             command=save_addresses)
        btn_save.pack(pady=10)

    def load_email_list(self):
        """ email_list.json から読み込み、self.email_listへ格納 """
        if os.path.exists("email_list.json"):
            with open("email_list.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.email_list = data
            else:
                self.email_list = []
        else:
            self.email_list = []

    def save_email_list(self):
        with open("email_list.json", "w", encoding="utf-8") as f:
            json.dump(self.email_list, f, ensure_ascii=False, indent=2)

    def run(self):
        self.root.mainloop()