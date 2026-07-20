"""
Backend web app cho chat AI + trang "Hoc tu YouTube" (dung de deploy len Railway).

- "/"            trang chat cong khai (ai co link cung vao chat duoc)
- "/admin"       trang de dan link YouTube day them kien thuc (khong can mat khau)
- "/chat"        API chat (JSON) - dung cho ChatWidget.tsx nhung tren Lovable neu muon
- "/admin/learn" API hoc tu YouTube (JSON)

Bien moi truong can co tren Railway:
    GEMINI_API_KEY   - API key Gemini
    KNOWLEDGE_FILE    - (tuy chon) duong dan file knowledge.json, vd /data/knowledge.json neu
                        gan Railway Volume de du lieu khong mat khi redeploy

Chay local de test:
    py server.py
"""

import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google import genai

import chat
import learn_from_youtube as lfy

_chunks: list[dict] = []
_chunk_embeddings: list[list[float]] = []
_client: genai.Client | None = None
_lock = threading.Lock()


def _reload_chunks():
    global _chunks, _chunk_embeddings
    chunks = chat.load_all_chunks()
    embeddings = chat.build_chunk_embeddings(_client, chunks) if _client else []
    with _lock:
        _chunks = chunks
        _chunk_embeddings = embeddings


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    if chat.API_KEY:
        _client = genai.Client(api_key=chat.API_KEY)
    _reload_chunks()
    print(f"Loaded {len(_chunks)} context chunks, {len(_chunk_embeddings)} embeddings.")
    yield


app = FastAPI(title="Peptide Shop Chat API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatTurn(BaseModel):
    role: str
    text: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = []


class ChatResponse(BaseModel):
    reply: str


class LearnRequest(BaseModel):
    links: list[str]


class LearnResultItem(BaseModel):
    link: str
    status: str
    detail: str


class LearnResponse(BaseModel):
    results: list[LearnResultItem]


@app.get("/health")
def health():
    with _lock:
        return {"status": "ok", "chunks_loaded": len(_chunks)}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    if _client is None:
        return ChatResponse(reply="Server chua cau hinh GEMINI_API_KEY.")

    with _lock:
        chunks, embeddings = _chunks, _chunk_embeddings

    history = [{"role": t.role, "text": t.text} for t in req.history]
    top_chunks = chat.retrieve_combined(
        chunks, req.message, history=history, client=_client, chunk_embeddings=embeddings
    )
    prompt = chat.build_prompt(req.message, top_chunks, history)
    try:
        return ChatResponse(reply=chat.ask_gemini(_client, prompt))
    except Exception as e:
        return ChatResponse(reply=f"Xin loi, dang co loi ket noi AI ({e}). Vui long thu lai sau.")


@app.post("/admin/learn", response_model=LearnResponse)
def admin_learn(req: LearnRequest):
    if _client is None:
        raise HTTPException(status_code=503, detail="Server chua cau hinh GEMINI_API_KEY.")

    results: list[LearnResultItem] = []
    for link in req.links:
        try:
            video_id = lfy.extract_video_id(link)
        except ValueError as e:
            results.append(LearnResultItem(link=link, status="loi", detail=str(e)))
            continue

        if lfy.is_already_learned(video_id):
            results.append(
                LearnResultItem(link=link, status="trung", detail=f"Video {video_id} da hoc truoc do, bo qua.")
            )
            continue

        try:
            meta = lfy.fetch_metadata(video_id)
        except Exception:
            meta = {"title": video_id, "channel": None, "url": f"https://www.youtube.com/watch?v={video_id}"}

        try:
            transcript_text = lfy.fetch_transcript(video_id)
        except Exception as e:
            results.append(LearnResultItem(link=link, status="loi", detail=f"Khong lay duoc transcript: {e}"))
            continue

        if not transcript_text.strip():
            results.append(LearnResultItem(link=link, status="bo_qua", detail="Transcript rong."))
            continue

        summary = lfy.extract_insights(_client, meta.get("title"), meta.get("channel"), transcript_text)
        if summary.upper().startswith("KHONG CO THONG TIN"):
            results.append(LearnResultItem(link=link, status="bo_qua", detail="Khong co thong tin huu ich."))
            continue

        lfy.save_video_insight(video_id, meta.get("title"), meta.get("channel"), meta.get("url"), summary)
        results.append(LearnResultItem(link=link, status="da_them", detail=summary))

    _reload_chunks()
    return LearnResponse(results=results)


CHAT_PAGE = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">
<title>Trợ lý Peptide Shop</title>
<style>
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html{-webkit-text-size-adjust:100%}
  body{margin:0;font-family:'Segoe UI',sans-serif;background:#0f1420;color:#e7eaf3;height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden}
  header{background:#161d2e;padding:14px 16px;padding-top:max(14px,env(safe-area-inset-top));font-weight:700;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
  header span{font-size:15px}
  header a{color:#8790a8;font-size:12px;font-weight:400;text-decoration:none;border:1px solid #2a334a;padding:6px 12px;border-radius:14px;touch-action:manipulation}
  header a:hover{color:#fff;border-color:#5865f2}
  #log{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:16px;display:flex;flex-direction:column;gap:10px}
  .msg{max-width:85%;padding:10px 14px;border-radius:14px;line-height:1.4;font-size:15px;word-break:break-word;overflow-wrap:anywhere}
  .user{align-self:flex-end;background:#5865f2;color:#fff}
  .bot{align-self:flex-start;background:#212a3d;color:#e7eaf3}
  form{display:flex;gap:8px;padding:12px;padding-bottom:max(12px,env(safe-area-inset-bottom));background:#141a29;flex-shrink:0}
  input{flex:1;min-width:0;padding:12px 14px;border-radius:20px;border:none;background:#1c2438;color:#f0f2f7;font-size:16px;touch-action:manipulation}
  input:focus{outline:2px solid #5865f2}
  button{padding:10px 18px;border-radius:20px;border:none;background:#5865f2;color:#fff;font-weight:700;cursor:pointer;touch-action:manipulation;flex-shrink:0}
  button:disabled{opacity:.5;cursor:default}
  @media (max-width:480px){
    .msg{max-width:90%;font-size:14px}
    header span{font-size:14px}
  }
</style></head>
<body>
<header><span>Trợ lý Peptide Shop</span><a href="/admin">⚙ Admin</a></header>
<div id="log"></div>
<form id="f"><input id="q" placeholder="Nhập câu hỏi..." autocomplete="off" enterkeyhint="send"><button id="send">Gửi</button></form>
<script>
const log=document.getElementById('log'), q=document.getElementById('q'), f=document.getElementById('f'), send=document.getElementById('send');
let history=[];
function add(text, cls){const d=document.createElement('div');d.className='msg '+cls;d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;}
f.onsubmit=async(e)=>{
  e.preventDefault();
  const text=q.value.trim(); if(!text) return;
  add(text,'user'); q.value=''; send.disabled=true;
  try{
    const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,history})});
    const data=await res.json();
    add(data.reply,'bot');
    history.push({role:'Khach hang',text:text},{role:'Tro ly',text:data.reply});
  }catch(err){ add('Lỗi kết nối, thử lại sau.','bot'); }
  send.disabled=false; q.focus();
};
add('Xin chào! Bạn muốn hỏi gì về sản phẩm, cách dùng, hay giá cả không?','bot');
</script>
</body></html>"""

ADMIN_PAGE = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">
<title>Hoc tu YouTube - Admin</title>
<style>
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html{-webkit-text-size-adjust:100%}
  body{margin:0;font-family:'Segoe UI',sans-serif;background:#0f1420;color:#e7eaf3;padding:16px;padding-top:max(16px,env(safe-area-inset-top));padding-bottom:max(16px,env(safe-area-inset-bottom))}
  h1{font-size:17px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
  h1 a{color:#8790a8;font-size:12px;font-weight:400;text-decoration:none;border:1px solid #2a334a;padding:6px 12px;border-radius:14px;touch-action:manipulation}
  h1 a:hover{color:#fff;border-color:#5865f2}
  textarea{width:100%;padding:10px;border-radius:8px;border:none;background:#1c2438;color:#f0f2f7;font-size:16px;margin-bottom:10px}
  textarea{height:120px;resize:vertical;font-family:inherit}
  button{width:100%;padding:12px 20px;border-radius:8px;border:none;background:#5865f2;color:#fff;font-weight:700;font-size:15px;cursor:pointer;touch-action:manipulation}
  button:disabled{opacity:.5;cursor:default}
  #out{margin-top:16px;white-space:pre-wrap;word-break:break-word;font-size:13px;background:#1c2438;padding:12px;border-radius:8px;max-height:400px;overflow-y:auto}
  @media (min-width:480px){ button{width:auto} }
</style></head>
<body>
<h1><span>Learn from YouTube</span><a href="/">💬 Chat</a></h1>
<textarea id="links" placeholder="Paste link YouTube"></textarea>
<button id="btn">Start</button>
<div id="out"></div>
<script>
const btn=document.getElementById('btn'), out=document.getElementById('out');
btn.onclick=async()=>{
  const links=document.getElementById('links').value.split('\\n').map(s=>s.trim()).filter(Boolean);
  if(!links.length){ out.textContent='Missing link.'; return; }
  btn.disabled=true; out.textContent='Processing...';
  try{
    const res=await fetch('/admin/learn',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({links})});
    const data=await res.json();
    out.textContent=data.results.map(r=>`[${r.status}] ${r.link}\\n${r.detail}`).join('\\n\\n');
  }catch(e){ out.textContent='Error: '+e; }
  btn.disabled=false;
};
</script>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def chat_page():
    return CHAT_PAGE


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return ADMIN_PAGE


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
