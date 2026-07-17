"""
Chat AI don gian: tra loi khach hang dua tren du lieu san pham/combo/huong dan pha che.

Cach hoat dong:
1. Nap knowledge.json (gom san pham, combo, huong dan pha che trong 1 file).
2. Cat cac muc thanh doan, tim cac doan lien quan nhat toi cau hoi (theo tu khoa).
3. Gui cau hoi + cac doan lien quan cho Gemini (gemini-3.5-flash) de tra loi.

Chay:
    py chat.py
"""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = "gemini-3.5-flash"
GENERATE_CONFIG = types.GenerateContentConfig(temperature=0.2)


def ask_gemini(client: genai.Client, prompt: str) -> str:
    """Goi Gemini voi temperature thap de tra loi bam sat du lieu, giam kha nang
    tra loi sai/tu choi ngau nhien du da co du du lieu trong ngu canh."""
    response = client.models.generate_content(model=MODEL, contents=prompt, config=GENERATE_CONFIG)
    return response.text


KNOWLEDGE_FILE = os.getenv("KNOWLEDGE_FILE", "knowledge.json")
MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URL") or os.getenv("MONGO_PUBLIC_URL")
MONGODB_DB = os.getenv("MONGODB_DB", "trainai")
_mongo_collection = None

_WORD_RE = re.compile(r"\w+", re.UNICODE)

_STOPWORDS = {
    "how", "much", "many", "should", "would", "could", "take", "and", "the", "for",
    "per", "week", "weeks", "day", "days", "month", "months", "does", "this", "that",
    "with", "from", "into", "about", "what", "when", "where", "why", "who", "which",
    "can", "will", "shall", "may", "might", "must", "than", "then", "also", "more",
    "most", "some", "any", "all", "each", "every", "both", "few", "other", "such",
    "only", "own", "same", "too", "very", "just", "now", "are", "was", "were", "you",
    "your", "have", "has", "had", "not", "but", "use", "used", "using", "often",
    "product", "products",
    "va", "cho", "cua", "khi", "nhu", "thi", "hay", "hoac", "voi", "den", "trong",
    "ngoai", "tren", "duoi", "nay", "mot", "hai", "rat", "cung", "duoc", "khong",
    "nen", "neu", "nhung", "vay", "the", "sao", "gio", "lan", "tuan", "ngay",
}


def _get_mongo_collection():
    global _mongo_collection
    if _mongo_collection is None:
        from pymongo import MongoClient

        client = MongoClient(MONGODB_URI)
        _mongo_collection = client[MONGODB_DB]["knowledge"]
    return _mongo_collection


def load_knowledge(path: str = KNOWLEDGE_FILE) -> dict:
    if MONGODB_URI:
        doc = _get_mongo_collection().find_one({"_id": "singleton"})
        if not doc:
            return {"products": [], "bundles": [], "guide": None}
        doc.pop("_id", None)
        return doc

    if not Path(path).exists():
        return {"products": [], "bundles": [], "guide": None}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_knowledge(data: dict, path: str = KNOWLEDGE_FILE) -> None:
    if MONGODB_URI:
        doc = dict(data)
        doc["_id"] = "singleton"
        _get_mongo_collection().replace_one({"_id": "singleton"}, doc, upsert=True)
        return

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_products(path: str = KNOWLEDGE_FILE) -> list[dict]:
    return load_knowledge(path).get("products", [])


def load_guide(path: str = KNOWLEDGE_FILE) -> dict | None:
    return load_knowledge(path).get("guide")


def load_bundles(path: str = KNOWLEDGE_FILE) -> list[dict]:
    return load_knowledge(path).get("bundles", [])


def build_bundle_chunks(bundles: list[dict]) -> list[dict]:
    chunks = []
    for b in bundles:
        components = ", ".join(b.get("components", []))
        text = (
            f"Goi combo: {b.get('name')}\n"
            f"Gom cac san pham: {components}\n"
            f"Gia goi: {b.get('bundle_price')} USD (gia goc {b.get('original_price')} USD, "
            f"tiet kiem {b.get('savings')} USD, giam {b.get('discount_percent')}%)"
        )
        if b.get("synergy_vi"):
            text += f"\nLy do phoi hop: {b['synergy_vi']}"
        if b.get("synergy_en"):
            text += f"\nWhy this combo works: {b['synergy_en']}"
        if b.get("order_url"):
            text += f"\nLink dat hang goi combo: {b['order_url']}"
        chunks.append({"type": "bundle", "title": b.get("name"), "url": b.get("order_url"), "text": text})
    return chunks


def build_guide_chunk(guide: dict | None) -> list[dict]:
    if guide is None:
        return []
    text = "\n".join(
        [
            guide["title_en"],
            *guide["steps_en"],
            *guide["notes_en"],
            guide.get("safety_note_en", ""),
            guide.get("cycling_note_en", ""),
            guide["title_vi"],
            *guide["steps_vi"],
            *guide["notes_vi"],
            guide.get("safety_note_vi", ""),
            guide.get("cycling_note_vi", ""),
        ]
    )
    return [{"type": "guide", "title": guide["title_en"], "url": None, "text": text}]


def build_mixing_chunk(mixing: dict | None) -> list[dict]:
    if mixing is None:
        return []
    text = "\n".join(
        [
            mixing["title_en"],
            mixing["general_rule_en"],
            *mixing["notes_en"],
            mixing["title_vi"],
            mixing["general_rule_vi"],
            *mixing["notes_vi"],
        ]
    )
    return [{"type": "guide", "title": mixing["title_en"], "url": None, "text": text}]


def build_video_insight_chunks(video_insights: list[dict]) -> list[dict]:
    chunks = []
    for v in video_insights or []:
        text = (
            f"[KINH NGHIEM CHIA SE - khong phai thong tin chinh thuc cua shop] "
            f"Nguon: video YouTube \"{v.get('title')}\" - kenh {v.get('channel')}\n"
            f"Noi dung duoc chia se trong video (quan diem/kinh nghiem ca nhan cua nguoi lam video, "
            f"CHUA duoc shop xac thuc):\n{v.get('summary', '')}"
        )
        chunks.append(
            {"type": "video", "title": v.get("title"), "url": v.get("url"), "text": text}
        )
    return chunks


CATEGORY_ALIASES = {
    "Lose Fat": "giam can, giam mo, dot mo, giam beo",
    "Recovery": "phuc hoi, tai tao mo, lanh vet thuong, chong viem",
    "Build Muscle": "tang co, phat trien co bap, tang suc manh",
    "Longevity": "chong lao hoa, song lau, tuoi tho, chong oxy hoa",
    "Wellness": "suc khoe tong quat, cai thien suc khoe, sinh ly",
    "Supplies": "vat tu ho tro, dung cu pha thuoc",
}


def build_product_chunks(products: list[dict]) -> list[dict]:
    chunks = []
    for p in products:
        variant_lines = "\n".join(
            f"  - Lieu {v.get('dose')}: gia {v.get('price')} USD, "
            f"con {v.get('stock')} trong kho (SKU {v.get('sku')})"
            for v in p.get("variants", [])
        )
        category = p.get("category") or ""
        aliases = CATEGORY_ALIASES.get(category, "")
        benefits_lines = "\n".join(f"  - {b}" for b in p.get("benefits_vi", []))
        text_parts = [
            f"San pham: {p.get('name')}",
            f"Danh muc: {category} ({aliases})",
            f"Link dat hang: {p.get('order_url') or p.get('slug')}",
            f"Trang thai: {'Dang ban' if p.get('active') else 'Ngung ban'}"
            f"{', noi bat' if p.get('featured') else ''}",
        ]
        if p.get("tagline_en"):
            text_parts.append(f"Tagline: {p['tagline_en']}")
        if p.get("description_vi"):
            text_parts.append(f"Mo ta: {p['description_vi']}")
        if p.get("official_long_en"):
            text_parts.append(f"Official description (EN): {p['official_long_en']}")
        if p.get("mechanism_en"):
            text_parts.append(f"Mechanism (EN): {p['mechanism_en']}")
        if benefits_lines:
            text_parts.append(f"Cong dung thuong duoc nghien cuu:\n{benefits_lines}")
        if p.get("usage_frequency_vi"):
            text_parts.append(f"Tan suat su dung thuong gap: {p['usage_frequency_vi']}")
        if p.get("cycling_vi"):
            text_parts.append(f"Chu ky dung dai han (on/off): {p['cycling_vi']}")
        if p.get("protocol_en"):
            protocol_lines = "\n".join(f"  - {line}" for line in p["protocol_en"])
            text_parts.append(f"Official protocol (EN, tu website chinh thuc cua shop):\n{protocol_lines}")
        if p.get("half_life"):
            text_parts.append(f"Half-life: {p['half_life']}")
        if p.get("reconstitution_vi"):
            text_parts.append(f"Cach pha che: {p['reconstitution_vi']}")
        if p.get("official_reconstitution_en"):
            text_parts.append(f"Official reconstitution (EN): {p['official_reconstitution_en']}")
        if p.get("official_storage_en"):
            text_parts.append(f"Official storage (EN): {p['official_storage_en']}")
        if p.get("specs"):
            specs_lines = "\n".join(f"  - {s.get('label')}: {s.get('value')}" for s in p["specs"])
            text_parts.append(f"Specs:\n{specs_lines}")
        text_parts.append(f"Cac lieu dung:\n{variant_lines}")
        text = "\n".join(text_parts)
        chunks.append({"type": "product", "title": p.get("name"), "url": p.get("order_url"), "text": text})
    return chunks


def _normalize(text: str) -> str:
    return text.lower().replace("-", "").replace("_", "").replace("/", "")


def retrieve(chunks: list[dict], question: str, top_k: int = 5) -> list[dict]:
    query_words = [w for w in _WORD_RE.findall(question.lower()) if len(w) > 2 and w not in _STOPWORDS]
    if not query_words:
        return chunks[:top_k]

    scored = []
    for c in chunks:
        text_lower = c["text"].lower()
        text_norm = _normalize(text_lower)
        s = 0
        for w in query_words:
            s += text_lower.count(w)
            s += text_norm.count(w)
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:top_k]]


def expand_query_with_history(question: str, history: list[dict], turns: int = 4) -> str:
    """Cong them vai luot hoi thoai gan nhat de cau hoi ngan gon (vd 'lieu dung the nao')
    van tim dung san pham dang duoc nhac toi tu ngu canh truoc do."""
    recent = history[-turns:] if history else []
    recent_text = " ".join(t.get("text", "") for t in recent)
    return f"{recent_text} {question}".strip()


EMBED_MODEL = "gemini-embedding-001"


def embed_texts(client: genai.Client, texts: list[str]) -> list[list[float]]:
    result = client.models.embed_content(model=EMBED_MODEL, contents=texts)
    return [e.values for e in result.embeddings]


def build_chunk_embeddings(client: genai.Client, chunks: list[dict]) -> list[list[float]]:
    """Tinh truoc vector embedding cho tung doan (1 lan luc khoi dong), de sau nay
    so sanh voi cau hoi cua khach theo ngu nghia thay vi chi so tung chu."""
    texts = [f"{c.get('title', '')}\n{c['text'][:1500]}" for c in chunks]
    return embed_texts(client, texts)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def semantic_retrieve(
    client: genai.Client,
    chunks: list[dict],
    chunk_embeddings: list[list[float]],
    question: str,
    top_k: int = 5,
    min_score: float = 0.45,
) -> list[dict]:
    """Tim theo ngu nghia (embedding) - hieu duoc tu viet tat, go sai, tu dong nghia
    ma tim theo tu khoa thuong bo sot."""
    if not chunks or not chunk_embeddings:
        return []
    try:
        query_vec = embed_texts(client, [question])[0]
    except Exception:
        return []
    scored = [(_cosine(query_vec, emb), c) for c, emb in zip(chunks, chunk_embeddings)]
    scored.sort(key=lambda x: -x[0])
    return [c for score, c in scored[:top_k] if score >= min_score]


def retrieve_combined(
    chunks: list[dict],
    question: str,
    top_k_products: int = 5,
    top_k_bundles: int = 3,
    top_k_videos: int = 2,
    history: list[dict] | None = None,
    client: genai.Client | None = None,
    chunk_embeddings: list[list[float]] | None = None,
) -> list[dict]:
    search_text = expand_query_with_history(question, history or [])
    product_chunks = [c for c in chunks if c.get("type") == "product"]
    guide_chunks = [c for c in chunks if c.get("type") == "guide"]
    bundle_chunks = [c for c in chunks if c.get("type") == "bundle"]
    video_chunks = [c for c in chunks if c.get("type") == "video"]

    results = (
        retrieve(product_chunks, search_text, top_k_products)
        + retrieve(bundle_chunks, search_text, top_k_bundles)
        + retrieve(video_chunks, search_text, top_k_videos)
    )

    if client is not None and chunk_embeddings is not None:
        semantic_hits = semantic_retrieve(client, chunks, chunk_embeddings, search_text, top_k=5)
        seen = {id(c) for c in results}
        for c in semantic_hits:
            if c.get("type") in ("product", "bundle", "video") and id(c) not in seen:
                results.append(c)
                seen.add(id(c))

    return results + guide_chunks


def _format_chunk(c: dict) -> str:
    if c.get("type") == "product":
        return f"[San pham: {c['title']}]\n{c['text']}"
    if c.get("type") == "bundle":
        return f"[Goi combo: {c['title']}]\n{c['text']}"
    if c.get("type") == "video":
        return c["text"]
    return f"[Huong dan pha che chung]\n{c['text']}"


def build_prompt(question: str, context_chunks: list[dict], history: list[dict]) -> str:
    if context_chunks:
        context_text = "\n\n".join(_format_chunk(c) for c in context_chunks)
    else:
        context_text = "(khong tim thay noi dung lien quan trong kho du lieu)"

    history_text = "\n".join(f"{turn['role']}: {turn['text']}" for turn in history[-6:])

    return f"""Ban la tro ly cham soc khach hang cho mot shop ban peptide. Chi duoc tra loi dua tren THONG TIN THAM KHAO ben duoi.
Neu THONG TIN THAM KHAO khong du de tra loi, hay noi that la chua co du lieu ve van de nay va de nghi khach lien he them, TUYET DOI KHONG bia dat thong tin (gia, ton kho, cong dung...).

THONG TIN THAM KHAO co the bao gom: mo ta san pham, cong dung thuong duoc nghien cuu, tan suat su dung thuong gap, "Official protocol" (giao thuc lieu dung chinh thuc lay truc tiep tu website cua shop - vi du "250 mcg subcutaneous, 1-2x daily"), cach pha che (bao gom ca "Official reconstitution" ghi chinh xac ty le mg/ml tu website), cac goi combo (bundle) san pham co san cua shop, va luu y an toan chung. Khi trong THONG TIN THAM KHAO co "Official protocol" hoac "Official reconstitution", day la thong tin CHINH THUC da duoc shop cong bo cong khai tren website san pham - ban DUOC PHEP va NEN trich dan truc tiep cac con so cu the (mg, mcg, ml, so lan/tuan...) tu do khi khach hoi ve lieu dung, vi day khong phai ban tu bia ra hay tu van y te ca nhan hoa, ma chi la nhac lai thong tin san pham da duoc cong bo. Neu chi co "tan suat su dung thuong gap" (khong co Official protocol cu the), thi trinh bay o dang "thuong duoc nghien cuu/su dung o...". Chi khi KHONG co bat ky thong tin lieu dung nao (ca protocol chinh thuc lan tan suat chung) trong THONG TIN THAM KHAO thi moi noi that la chua co du lieu.

QUAN TRONG: Cac nhan nhu "Official protocol", "Official reconstitution", "tu website chinh thuc" chi la ten truong du lieu noi bo de BAN hieu do la thong tin dang tin cay - KHONG duoc lap lai cac cum tu nay hay nhac den "theo protocol chinh thuc/website chinh thuc cua chung toi" trong cau tra loi. Chi noi thang cac con so (vi du "BPC-157 thuong dung 250 mcg, 1-2 lan/ngay") nhu the do la kien thuc ban dang co san, tu nhien nhu dang tu van chu khong phai dang trich dan tai lieu.

THU TU UU TIEN KHI CAC NGUON MAU THUAN NHAU (quan trong): THONG TIN THAM KHAO co the gom nhieu loai nguon voi do tin cay khac nhau - (1) thong tin san pham/"Official protocol"/"Official reconstitution" cua shop la nguon dang tin cay nhat, luon uu tien dung nguon nay truoc; (2) cac doan danh dau "[KINH NGHIEM CHIA SE - khong phai thong tin chinh thuc cua shop]" la quan diem/kinh nghiem ca nhan tu video YouTube cua nguoi khac, CHUA duoc xac thuc, do tin cay thap hon. Neu kinh nghiem chia se trong video KHAC voi thong tin chinh thuc cua shop (vi du lieu luong khac nhau), hay uu tien noi so lieu chinh thuc truoc, roi neu can co the them "mot so nguon/kinh nghiem chia se khac lai dung..." nhu mot ghi chu phu, KHONG duoc tron lan hai loai lam mot hay coi kinh nghiem chia se ngang hang voi thong tin chinh thuc. Neu nhieu video khac nhau ke kinh nghiem TRAI NGUOC nhau va khong co thong tin chinh thuc de doi chieu, hay noi that la co nhieu kinh nghiem khac nhau duoc chia se va khach nen tham khao them, KHONG tu chon 1 ben la dung.

Khi khach hoi co the dung chung/ket hop san pham nao voi nhau, hay uu tien tra loi dua tren cac GOI COMBO co san trong THONG TIN THAM KHAO (neu co goi phu hop). Neu khong co goi combo lien quan va cung khong co thong tin nao khac ve viec ket hop, hay noi that la chua co du lieu ve viec phoi hop cu the do, KHONG tu suy doan hay bia dat.

Khi khach hoi CO THE TRON/RUT CHUNG hai peptide vao 1 ong tiem hay khong (khac voi hoi ve goi combo ban san), hay dung phan "Can Different Peptides Be Mixed Together?" / "Co The Tron Chung Cac Peptide Voi Nhau Khong?" trong THONG TIN THAM KHAO (neu co) de tra loi theo nguyen tac chung (tuong thich dung moi, do pH, luu y dac biet voi GHK-Cu do co oxy hoa). Neu cap san pham khach hoi khong duoc de cap ro trong do, ap dung nguyen tac chung va noi ro day la huong dan chung, khuyen nghi an toan la tiem rieng neu khong chac chan, KHONG khang dinh chac chan "duoc" hay "khong duoc" cho 1 cap cu the chua duoc xac nhan.

Khi khach hoi ve viec dung dai han, lap lai nhieu chu ky, nghi giua cac dot, hoac gioi han so lan dung trong 1 nam: KHONG bia ra mot con so gioi han cu the neu THONG TIN THAM KHAO khong co. Thay vao do, dua vao "cycling note" (neu co trong THONG TIN THAM KHAO) de giai thich nguyen tac chung (chay het chu ky da neu trong tan suat/protocol cua san pham, roi nghi mot khoang truoc khi lap lai, tham khao chuyen gia y te truoc khi lap lai chu ky moi) va noi ro la khong co con so gioi han "X lan/nam" chinh thuc duoc cong bo, thay vi tu choi tra loi hoan toan.

Moi san pham va goi combo trong THONG TIN THAM KHAO co san "Link dat hang". Khi khach hoi cach dat hang, hoi mua o dau, hoac hoi link san pham/combo, hay dua thang link tuong ung co san trong THONG TIN THAM KHAO - KHONG noi la chua co thong tin dat hang hay bao khach lien he shop trong truong hop nay.

THONG TIN THAM KHAO:
{context_text}

LICH SU HOI THOAI GAN NHAT:
{history_text}

CAU HOI CUA KHACH HANG: {question}

Tra loi tu nhien nhu nguoi that dang nhan tin tu van (kieu chat/nhan tin, KHONG phai van ban trang trong), NGAN GON va di thang vao trong tam. Uu tien 2-4 cau hoac vai gach dau dong ngan, chi noi dai hon khi khach thuc su can huong dan tung buoc chi tiet (vi du cach pha che). Khong nhac lai nhung gi khach da biet hoac da hoi truoc do trong LICH SU HOI THOAI. Khong mo dau dai dong, di thang vao cau tra loi.

NGON NGU TRA LOI: hay tra loi bang chinh ngon ngu ma khach hang dung o CAU HOI CUA KHACH HANG ben tren (khach hoi tieng Anh thi tra loi hoan toan bang tieng Anh, khach hoi tieng Viet thi tra loi bang tieng Viet, v.v.). Khong tron ngon ngu trong cung 1 cau tra loi.

KHONG dung dinh dang markdown (khong dung **chu dam**, khong dung dau *, khong dung gach dau dong, chi viet van xuoi binh thuong thanh cac cau/doan van).
KHONG tu dong them cau khuyen nghi kieu "tham khao y kien bac si/chuyen gia y te truoc khi su dung" - bo han cau nay khoi cau tra loi."""


def load_all_chunks() -> list[dict]:
    knowledge = load_knowledge()
    products = knowledge.get("products", [])
    bundles = knowledge.get("bundles", [])
    guide = knowledge.get("guide")
    mixing = knowledge.get("mixing_guide")
    video_insights = knowledge.get("video_insights", [])
    return (
        build_product_chunks(products)
        + build_bundle_chunks(bundles)
        + build_guide_chunk(guide)
        + build_mixing_chunk(mixing)
        + build_video_insight_chunks(video_insights)
    )


def main():
    if not API_KEY:
        print("Chua co GEMINI_API_KEY trong file .env")
        return

    print("Dang nap knowledge.json...")
    chunks = load_all_chunks()
    if not chunks:
        print("Kho du lieu chua co gi ca. Hay tao knowledge.json truoc.")
        return
    print(f"Da nap {len(chunks)} doan noi dung.\n")

    client = genai.Client(api_key=API_KEY)
    print("Dang tinh embedding cho tim kiem ngu nghia...")
    chunk_embeddings = build_chunk_embeddings(client, chunks)
    history: list[dict] = []

    print("Go cau hoi de chat (go 'exit' de thoat):")
    while True:
        question = input("\nKhach hang: ").strip()
        if question.lower() in ("exit", "quit", "thoat"):
            break
        if not question:
            continue

        top_chunks = retrieve_combined(
            chunks, question, history=history, client=client, chunk_embeddings=chunk_embeddings
        )
        prompt = build_prompt(question, top_chunks, history)
        try:
            answer = ask_gemini(client, prompt)
        except Exception as e:
            answer = f"[Loi goi Gemini: {e}]"

        print(f"\nTro ly: {answer}")
        history.append({"role": "Khach hang", "text": question})
        history.append({"role": "Tro ly", "text": answer})


if __name__ == "__main__":
    main()
