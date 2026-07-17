"""
Import du lieu tu knowledge.json (file local) len MongoDB tren Railway.
Chay 1 lan de khoi tao du lieu ban dau cho database (hoac chay lai bat cu luc nao
muon ghi de toan bo du lieu Mongo bang ban trong file knowledge.json local).

Chuan bi:
    Them dong nay vao file .env (local, KHONG push len GitHub):
        MONGODB_URI=<connection string cua Mongo tren Railway>

    Luu y: lay connection string PUBLIC (co the ket noi tu ben ngoai Railway),
    khong phai URL noi bo dang "mongodb.railway.internal" (URL do chi dung duoc
    giua cac service voi nhau TREN Railway, khong dung tu may ban duoc).
    Tren Railway, vao service MongoDB -> tab "Connect" -> lay public connection URL.

Chay:
    py import_knowledge_to_mongo.py
"""

import json
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URL") or os.getenv("MONGO_PUBLIC_URL")
MONGODB_DB = os.getenv("MONGODB_DB", "trainai")


def main():
    if not MONGODB_URI:
        print("Chua co MONGODB_URI trong file .env. Them vao roi chay lai:")
        print("  MONGODB_URI=<connection string public cua Mongo tren Railway>")
        return

    if not os.path.exists("knowledge.json"):
        print("Khong tim thay knowledge.json trong thu muc hien tai.")
        return

    with open("knowledge.json", encoding="utf-8") as f:
        data = json.load(f)

    print("Dang ket noi MongoDB...")
    client = MongoClient(MONGODB_URI)
    collection = client[MONGODB_DB]["knowledge"]

    doc = dict(data)
    doc["_id"] = "singleton"
    collection.replace_one({"_id": "singleton"}, doc, upsert=True)

    print("Da import xong len MongoDB:")
    print(f"  - {len(data.get('products', []))} san pham")
    print(f"  - {len(data.get('bundles', []))} goi combo")
    print(f"  - {len(data.get('video_insights', []))} video insight")
    print(f"  - guide: {'co' if data.get('guide') else 'khong'}")
    print(f"  - mixing_guide: {'co' if data.get('mixing_guide') else 'khong'}")


if __name__ == "__main__":
    main()
