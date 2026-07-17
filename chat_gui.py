"""
Cua so chat AI (Tkinter) giao dien kieu chat app hien dai - bong bong tin nhan bo goc,
theme toi, avatar - de thu hoi AI dua tren knowledge.json (san pham + combo + huong dan).

Chay:
    py chat_gui.py
"""

import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import chat

BG_APP = "#0f1420"
BG_HEADER = "#161d2e"
BG_INPUT_BAR = "#141a29"
ACCENT = "#5865f2"
ACCENT_HOVER = "#4752c4"
USER_BUBBLE = ACCENT
USER_TEXT = "#ffffff"
BOT_BUBBLE = "#212a3d"
BOT_TEXT = "#e7eaf3"
ERROR_BUBBLE = "#42232b"
ERROR_TEXT = "#ff9ea8"
SUBTLE = "#8790a8"
INPUT_BG = "#1c2438"
INPUT_FG = "#f0f2f7"
PLACEHOLDER_FG = "#5c6784"

BUBBLE_MAX_WIDTH = 300
PLACEHOLDER = "Nhap cau hoi cho tro ly..."


def _rounded_rect_points(x1, y1, x2, y2, radius):
    return [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]


class Bubble(tk.Frame):
    """Mot bong bong tin nhan bo goc, tu can chinh trai/phai theo nguoi gui."""

    def __init__(self, parent, text, sender, kind, msg_font):
        super().__init__(parent, bg=BG_APP)
        is_user = kind == "user"
        bubble_bg = {"user": USER_BUBBLE, "bot": BOT_BUBBLE, "err": ERROR_BUBBLE}[kind]
        text_fg = {"user": USER_TEXT, "bot": BOT_TEXT, "err": ERROR_TEXT}[kind]
        avatar = "🧑" if is_user else "🤖"
        pad = 14

        sender_row = tk.Frame(self, bg=BG_APP)
        sender_row.pack(fill="x")
        sender_lbl = tk.Label(sender_row, text=sender, font=("Segoe UI", 8), fg=SUBTLE, bg=BG_APP)
        sender_lbl.pack(side="right" if is_user else "left", padx=(0, 44) if is_user else (44, 0))

        row = tk.Frame(self, bg=BG_APP)
        row.pack(fill="x", expand=True)

        canvas = tk.Canvas(row, bg=BG_APP, highlightthickness=0, bd=0)
        text_id = canvas.create_text(
            pad, pad, text=text, anchor="nw", font=msg_font, fill=text_fg, width=BUBBLE_MAX_WIDTH
        )
        x1, y1, x2, y2 = canvas.bbox(text_id)
        w, h = x2 + pad, y2 + pad
        canvas.configure(width=w, height=h)
        rect = canvas.create_polygon(
            _rounded_rect_points(1, 1, w - 1, h - 1, 16),
            smooth=True, fill=bubble_bg, outline=bubble_bg,
        )
        canvas.tag_lower(rect, text_id)
        avatar_lbl = tk.Label(row, text=avatar, font=("Segoe UI Emoji", 13), bg=BG_APP, fg=SUBTLE)

        if is_user:
            canvas.pack(side="right", padx=(40, 8))
            avatar_lbl.pack(side="right")
        else:
            canvas.pack(side="left", padx=(8, 40))
            avatar_lbl.pack(side="left")

        self.pack(fill="x", pady=(10, 0), anchor="e" if is_user else "w")


class TypingBubble(tk.Frame):
    """Bong bong 'dang tra loi...' hien thi tam thoi khi cho phan hoi AI."""

    def __init__(self, parent, msg_font):
        super().__init__(parent, bg=BG_APP)
        row = tk.Frame(self, bg=BG_APP)
        row.pack(fill="x")
        avatar_lbl = tk.Label(row, text="🤖", font=("Segoe UI Emoji", 13), bg=BG_APP, fg=SUBTLE)
        avatar_lbl.pack(side="left")

        canvas = tk.Canvas(row, bg=BG_APP, highlightthickness=0, bd=0)
        pad = 14
        text_id = canvas.create_text(pad, pad, text="...", anchor="nw", font=msg_font, fill=SUBTLE)
        x1, y1, x2, y2 = canvas.bbox(text_id)
        w, h = x2 + pad, y2 + pad
        canvas.configure(width=w, height=h)
        rect = canvas.create_polygon(
            _rounded_rect_points(1, 1, w - 1, h - 1, 16), smooth=True, fill=BOT_BUBBLE, outline=BOT_BUBBLE
        )
        canvas.tag_lower(rect, text_id)
        canvas.pack(side="left", padx=(8, 40))
        self.pack(fill="x", pady=(10, 0), anchor="w")
        self._canvas, self._text_id, self._dots = canvas, text_id, 0
        self._animating = True
        self._animate()

    def _animate(self):
        if not self._animating:
            return
        self._dots = (self._dots + 1) % 4
        self._canvas.itemconfig(self._text_id, text="." * (self._dots + 1))
        self.after(400, self._animate)

    def stop(self):
        self._animating = False


class ChatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Peptide Shop - Tro ly AI")
        self.geometry("460x720")
        self.configure(bg=BG_APP)
        self.minsize(380, 520)

        self.history: list[dict] = []
        self.chunks: list[dict] = []
        self.chunk_embeddings: list[list[float]] = []
        self.client = None
        self._typing_bubble = None

        self.msg_font = tkfont.Font(family="Segoe UI", size=10)

        self._build_widgets()
        self.after(100, self._load_backend)

    def _build_widgets(self):
        header = tk.Frame(self, bg=BG_HEADER, height=64)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header, text="Tro ly Peptide Shop", font=("Segoe UI", 13, "bold"), fg="#ffffff", bg=BG_HEADER
        ).pack(anchor="w", padx=16, pady=(10, 0))

        self.status_var = tk.StringVar(value="Dang khoi dong...")
        tk.Label(
            header, textvariable=self.status_var, font=("Segoe UI", 9), fg=SUBTLE, bg=BG_HEADER
        ).pack(anchor="w", padx=16, pady=(0, 10))

        body = tk.Frame(self, bg=BG_APP)
        body.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(body, bg=BG_APP, highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.scroll_frame = tk.Frame(self.canvas, bg=BG_APP)
        self._window_id = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.scroll_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._window_id, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        tk.Frame(self.scroll_frame, bg=BG_APP, height=10).pack()

        bottom = tk.Frame(self, bg=BG_INPUT_BAR, height=64)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        input_wrap = tk.Frame(bottom, bg=BG_INPUT_BAR)
        input_wrap.pack(fill="both", expand=True, padx=12, pady=12)

        self.entry = tk.Entry(
            input_wrap, bg=INPUT_BG, fg=PLACEHOLDER_FG, insertbackground=INPUT_FG,
            font=("Segoe UI", 10), relief="flat", bd=0,
        )
        self.entry.insert(0, PLACEHOLDER)
        self.entry.pack(side="left", fill="both", expand=True, ipady=8, padx=(4, 8))
        self.entry.bind("<FocusIn>", self._clear_placeholder)
        self.entry.bind("<FocusOut>", self._restore_placeholder)
        self.entry.bind("<Return>", lambda e: self.on_send())
        self.entry.config(state="disabled")

        self.send_btn = tk.Button(
            input_wrap, text="Gui", command=self.on_send, bg=ACCENT, fg="#ffffff",
            activebackground=ACCENT_HOVER, activeforeground="#ffffff", relief="flat", bd=0,
            font=("Segoe UI", 10, "bold"), padx=18, cursor="hand2", state="disabled",
        )
        self.send_btn.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _clear_placeholder(self, _event=None):
        if self.entry.get() == PLACEHOLDER:
            self.entry.delete(0, "end")
            self.entry.config(fg=INPUT_FG)

    def _restore_placeholder(self, _event=None):
        if not self.entry.get().strip():
            self.entry.insert(0, PLACEHOLDER)
            self.entry.config(fg=PLACEHOLDER_FG)

    def _add_bubble(self, text: str, sender: str, kind: str):
        Bubble(self.scroll_frame, text, sender, kind, self.msg_font)
        self.after(50, lambda: self.canvas.yview_moveto(1.0))

    def _load_backend(self):
        def worker():
            if not chat.API_KEY:
                self.after(0, lambda: self.status_var.set("Chua co GEMINI_API_KEY trong file .env"))
                return
            chunks = chat.load_all_chunks()
            from google import genai

            client = genai.Client(api_key=chat.API_KEY)
            self.after(0, lambda: self.status_var.set("Dang tinh embedding tim kiem ngu nghia..."))
            chunk_embeddings = chat.build_chunk_embeddings(client, chunks)

            def done():
                self.chunks = chunks
                self.chunk_embeddings = chunk_embeddings
                self.client = client
                self.status_var.set("San sang tra loi")
                self.entry.config(state="normal")
                self.send_btn.config(state="normal")
                self._add_bubble(
                    "Xin chao! Ban muon hoi gi ve san pham, cach dung, hay gia ca khong?",
                    "Tro ly", "bot",
                )

            self.after(0, done)

    def on_send(self):
        question = self.entry.get().strip()
        if not question or question == PLACEHOLDER or self.client is None:
            return
        self.entry.delete(0, "end")
        self._add_bubble(question, "Ban", "user")
        self.send_btn.config(state="disabled")
        self._typing_bubble = TypingBubble(self.scroll_frame, self.msg_font)
        self.after(50, lambda: self.canvas.yview_moveto(1.0))
        threading.Thread(target=self._ask_worker, args=(question,), daemon=True).start()

    def _ask_worker(self, question: str):
        top_chunks = chat.retrieve_combined(
            self.chunks, question, history=self.history,
            client=self.client, chunk_embeddings=self.chunk_embeddings,
        )
        prompt = chat.build_prompt(question, top_chunks, self.history)
        try:
            answer = chat.ask_gemini(self.client, prompt)
            kind = "bot"
        except Exception as e:
            answer = f"Loi goi Gemini: {e}"
            kind = "err"

        def done():
            if self._typing_bubble is not None:
                self._typing_bubble.stop()
                self._typing_bubble.destroy()
                self._typing_bubble = None
            self._add_bubble(answer, "Tro ly", kind)
            self.history.append({"role": "Khach hang", "text": question})
            self.history.append({"role": "Tro ly", "text": answer})
            self.send_btn.config(state="normal")
            self.entry.focus_set()

        self.after(0, done)


if __name__ == "__main__":
    ChatApp().mainloop()
