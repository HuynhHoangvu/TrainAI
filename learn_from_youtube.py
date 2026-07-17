"""
Dan link YouTube, AI se doc transcript va TU LOC ra cac thong tin huu ich (cong dung,
cach dung, lieu luong duoc nhac toi, canh bao, kinh nghiem thuc te...) roi them vao
knowledge.json (muc "video_insights"). KHONG luu nguyen transcript tho vao kho du lieu.

Chay co giao dien (mac dinh, khong can tham so):
    py learn_from_youtube.py

Chay dong lenh (khong giao dien, cho scripting):
    py learn_from_youtube.py "<link YouTube>" [<them link khac>...]
"""

import json
import os
import re
import sys
import threading
import tkinter as tk
from pathlib import Path

import yt_dlp
from dotenv import load_dotenv
from google import genai
from google.genai import types
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = "gemini-3.5-flash"
KNOWLEDGE_FILE = os.getenv("KNOWLEDGE_FILE", "knowledge.json")

_VIDEO_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|embed/|live/))([A-Za-z0-9_-]{11})"
)


def extract_video_id(link_or_id: str) -> str:
    link_or_id = link_or_id.strip()
    m = _VIDEO_ID_RE.search(link_or_id)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", link_or_id):
        return link_or_id
    raise ValueError(f"Khong nhan dien duoc video ID tu: {link_or_id}")


def fetch_metadata(video_id: str) -> dict:
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "url": url,
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
    }


def fetch_transcript(video_id: str, languages: list[str] = ["en", "vi"]) -> str:
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)
    try:
        transcript = transcript_list.find_transcript(languages)
    except Exception:
        transcript = transcript_list.find_transcript([t.language_code for t in transcript_list])
    fetched = transcript.fetch()
    return " ".join(s.text.replace("\n", " ").strip() for s in fetched)


def extract_insights(client: genai.Client, title: str, channel: str, transcript_text: str) -> str:
    prompt = f"""Ban dang xay dung kho kien thuc cho AI cham soc khach hang cua 1 shop ban peptide nghien cuu.
Duoi day la transcript cua 1 video YouTube. Hay doc va TRICH XUAT CHI nhung thong tin thuc su huu ich,
cu the, co the dung de tra loi khach hang sau nay - vi du: cong dung/co che cua mot peptide cu the duoc
nhac toi, cach dung/lieu luong/tan suat duoc de cap trong video, canh bao an toan, meo pha che/bao quan,
so sanh giua cac loai peptide, kinh nghiem/nhan xet thuc te dang chu y.

KHONG bao gom: loi chao hoi, quang cao kenh, chuyen huong khong lien quan, cau noi lap lai, thong tin
chung chung khong co gia tri tra cuu.

Neu video KHONG co thong tin gi huu ich lien quan toi peptide/nghien cuu, chi tra loi dung 1 dong:
KHONG CO THONG TIN HUU ICH.

Tieu de video: {title}
Kenh: {channel}

TRANSCRIPT:
{transcript_text[:15000]}

Return the result as a short bullet-point list (1-2 sentences per point), written in ENGLISH (even if the
transcript above is in Vietnamese or another language - always translate/output in English). Do not use
markdown bold/italics."""

    response = client.models.generate_content(
        model=MODEL, contents=prompt, config=types.GenerateContentConfig(temperature=0.2)
    )
    return (response.text or "").strip()


def load_knowledge() -> dict:
    if not Path(KNOWLEDGE_FILE).exists():
        return {}
    with open(KNOWLEDGE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_video_insight(video_id: str, title: str, channel: str, url: str, summary: str) -> None:
    knowledge = load_knowledge()
    insights = knowledge.setdefault("video_insights", [])
    insights[:] = [i for i in insights if i.get("video_id") != video_id]
    insights.append(
        {"video_id": video_id, "title": title, "channel": channel, "url": url, "summary": summary}
    )
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=2)


BG_APP = "#0f1420"
BG_HEADER = "#161d2e"
ACCENT = "#5865f2"
ACCENT_HOVER = "#4752c4"
SUBTLE = "#8790a8"
INPUT_BG = "#1c2438"
INPUT_FG = "#f0f2f7"


class LearnApp(tk.Tk):
    """Giao dien rieng cho viec hoc kien thuc tu video YouTube (doc lap voi chat_gui.py)."""

    def __init__(self):
        super().__init__()
        self.title("Hoc tu YouTube - Peptide Shop")
        self.geometry("480x420")
        self.configure(bg=BG_APP)
        self.minsize(420, 380)
        self.client = genai.Client(api_key=API_KEY) if API_KEY else None

        self._build_widgets()
        if not API_KEY:
            self.status_var.set("Chua co GEMINI_API_KEY trong file .env")
            self.learn_btn.config(state="disabled")

    def _build_widgets(self):
        header = tk.Frame(self, bg=BG_HEADER, height=56)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Label(
            header, text="📺 Hoc kien thuc tu YouTube", font=("Segoe UI", 13, "bold"),
            fg="#ffffff", bg=BG_HEADER,
        ).pack(anchor="w", padx=16, pady=14)

        body = tk.Frame(self, bg=BG_APP)
        body.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            body, text="Dan link YouTube (moi dong 1 link):", font=("Segoe UI", 10),
            fg="#ffffff", bg=BG_APP,
        ).pack(anchor="w")

        self.link_box = tk.Text(
            body, height=6, bg=INPUT_BG, fg=INPUT_FG, insertbackground=INPUT_FG,
            font=("Segoe UI", 10), relief="flat", bd=0,
        )
        self.link_box.pack(fill="x", pady=(6, 12))

        self.learn_btn = tk.Button(
            body, text="Bat dau hoc", command=self.on_learn, bg=ACCENT, fg="#ffffff",
            activebackground=ACCENT_HOVER, activeforeground="#ffffff", relief="flat", bd=0,
            font=("Segoe UI", 10, "bold"), padx=16, pady=8, cursor="hand2",
        )
        self.learn_btn.pack(anchor="w")

        self.status_var = tk.StringVar(value="San sang.")
        tk.Label(
            body, textvariable=self.status_var, font=("Segoe UI", 9), fg=SUBTLE, bg=BG_APP,
            wraplength=440, justify="left", anchor="w",
        ).pack(fill="x", pady=(12, 6))

        self.log_box = tk.Text(
            body, bg=INPUT_BG, fg=INPUT_FG, font=("Segoe UI", 9), relief="flat", bd=0,
            state="disabled", wrap="word",
        )
        self.log_box.pack(fill="both", expand=True)

    def _log(self, text: str):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def _set_status(self, text: str):
        self.after(0, lambda: self.status_var.set(text))

    def _log_async(self, text: str):
        self.after(0, lambda: self._log(text))

    def on_learn(self):
        raw = self.link_box.get("1.0", "end").strip()
        links = [l.strip() for l in raw.splitlines() if l.strip()]
        if not links:
            self.status_var.set("Ban chua dan link YouTube nao.")
            return
        self.learn_btn.config(state="disabled")
        threading.Thread(target=self._worker, args=(links,), daemon=True).start()

    def _worker(self, links: list[str]):
        ok, skipped, failed = 0, 0, 0
        for i, link in enumerate(links, 1):
            try:
                video_id = extract_video_id(link)
            except ValueError as e:
                failed += 1
                self._log_async(f"({i}/{len(links)}) Link khong hop le: {e}")
                continue

            self._set_status(f"({i}/{len(links)}) Dang lay thong tin video...")
            try:
                meta = fetch_metadata(video_id)
            except Exception:
                meta = {"title": video_id, "channel": None, "url": f"https://www.youtube.com/watch?v={video_id}"}

            self._set_status(f"({i}/{len(links)}) Dang lay transcript...")
            try:
                transcript_text = fetch_transcript(video_id)
            except Exception as e:
                failed += 1
                self._log_async(f"({i}/{len(links)}) {meta.get('title')}: khong co phu de / loi ({e})")
                continue

            if not transcript_text.strip():
                skipped += 1
                self._log_async(f"({i}/{len(links)}) {meta.get('title')}: transcript rong, bo qua.")
                continue

            self._set_status(f"({i}/{len(links)}) AI dang loc thong tin huu ich...")
            summary = extract_insights(self.client, meta.get("title"), meta.get("channel"), transcript_text)

            if summary.upper().startswith("KHONG CO THONG TIN"):
                skipped += 1
                self._log_async(f"({i}/{len(links)}) {meta.get('title')}: khong co thong tin huu ich, bo qua.")
                continue

            save_video_insight(video_id, meta.get("title"), meta.get("channel"), meta.get("url"), summary)
            ok += 1
            self._log_async(f"({i}/{len(links)}) {meta.get('title')}: da them vao knowledge.json.\n{summary}\n")

        self._set_status(f"Xong. Them moi: {ok}, bo qua: {skipped}, loi: {failed}.")
        self.after(0, lambda: self.learn_btn.config(state="normal"))


def main():
    if len(sys.argv) < 2:
        print('Dung: py learn_from_youtube.py "<link YouTube>" [<them link khac>...]')
        return
    if not API_KEY:
        print("Chua co GEMINI_API_KEY trong file .env")
        return

    client = genai.Client(api_key=API_KEY)

    for link in sys.argv[1:]:
        try:
            video_id = extract_video_id(link)
        except ValueError as e:
            print(f"Bo qua '{link}': {e}")
            continue

        print(f"\nDang xu ly video {video_id}...")
        try:
            meta = fetch_metadata(video_id)
        except Exception as e:
            print(f"  Khong lay duoc metadata: {e}")
            meta = {"title": video_id, "channel": None, "url": f"https://www.youtube.com/watch?v={video_id}"}

        try:
            transcript_text = fetch_transcript(video_id)
        except Exception as e:
            print(f"  Khong lay duoc transcript (video co the khong co phu de): {e}")
            continue

        if not transcript_text.strip():
            print("  Transcript rong, bo qua.")
            continue

        print(f"  Da lay transcript ({len(transcript_text)} ky tu). Dang loc thong tin huu ich bang AI...")
        summary = extract_insights(client, meta.get("title"), meta.get("channel"), transcript_text)

        if summary.upper().startswith("KHONG CO THONG TIN"):
            print("  AI danh gia video nay khong co thong tin huu ich cho kho du lieu, bo qua.")
            continue

        save_video_insight(video_id, meta.get("title"), meta.get("channel"), meta.get("url"), summary)
        print(f"  Da them vao knowledge.json:\n{summary}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        LearnApp().mainloop()
