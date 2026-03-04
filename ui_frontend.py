"""
#################################################
2025/02
-TW_Prophet-
ui_frontend.py
#################################################
"""
import tkinter as tk

class ParallelogramButton(tk.Canvas):
    """
    平行四辺形の形をしたカスタムボタン風ウィジェット。
    近未来/占い師っぽい配色やフォントを採用。
    """
    def __init__(self, parent, text, command=None,
                 width=150, height=50,
                 bg_normal="#5C2EBE",  
                 bg_hover="#9C5FFF",   
                 outline_color="#E5CAFF", 
                 text_color="#FFFFFF",
                 font=("Consolas", 11, "bold"),
                 **kwargs):
        """
        - bg_normal : 通常時の塗り色
        - bg_hover  : ホバー時の塗り色
        - outline_color : 外枠線の色
        - text_color : テキスト色
        - font       : ボタン上のテキストフォント
        """
        super().__init__(parent, width=width, height=height,
                         bg="#221B44", 
                         highlightthickness=0, **kwargs)
        self.command = command
        self.bg_normal = bg_normal
        self.bg_hover = bg_hover
        self.outline_color = outline_color
        self.text_color = text_color
        self.font = font
        self.text_value = text

        self.parallelogram_id = None
        self.text_id = None

        # イベントバインド
        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

        # 初期描画
        self.draw_button(self.bg_normal)

    def draw_button(self, fill_color):
        """ 平行四辺形とテキストを描画 """
        self.delete("all")

        w = int(self["width"])
        h = int(self["height"])

        # 少し右にずれた平行四辺形
        x_offset = 20
        points = [
            (0, 0),
            (x_offset, h),
            (w, h),
            (w - x_offset, 0)
        ]
        self.parallelogram_id = self.create_polygon(
            points,
            fill=fill_color,
            outline=self.outline_color,
            width=2
        )
        # テキスト中央
        self.text_id = self.create_text(
            w // 2,
            h // 2,
            text=self.text_value,
            fill=self.text_color,
            font=self.font
        )

    def on_click(self, event):
        if self.command:
            self.command()

    def on_enter(self, event):
        # ホバー時に色を切り替え
        self.draw_button(self.bg_hover)

    def on_leave(self, event):
        # ホバーが外れたら元に戻す
        self.draw_button(self.bg_normal)