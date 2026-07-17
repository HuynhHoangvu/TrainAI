"""
Chay CUNG LUC ca proxy local (pproxy) va ngrok tunnel bang 1 lenh duy nhat,
roi tu in ra dia chi socks5://... de dan vao bien YOUTUBE_PROXY_URL tren Railway.

Yeu cau: da cai ngrok (ngrok.exe phai co trong PATH) va da chay
"ngrok config add-authtoken <token>" it nhat 1 lan truoc do.

Chay:
    py start_youtube_proxy.py

De 2 tien trinh nay chay nen (dung cua so nay). Nhan Ctrl+C de dung ca hai.
"""

import subprocess
import sys
import time
import urllib.request
import json

PROXY_PORT = 1080


def main():
    print("Dang khoi dong proxy local (socks5://0.0.0.0:%d)..." % PROXY_PORT, flush=True)
    proxy_proc = subprocess.Popen(
        [sys.executable, "run_proxy.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(1.5)

    print("Dang khoi dong ngrok tunnel...", flush=True)
    ngrok_proc = subprocess.Popen(
        ["ngrok", "tcp", str(PROXY_PORT), "--log=stdout"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("Dang cho ngrok cap dia chi cong khai...", flush=True)
    public_url = None
    for _ in range(30):
        time.sleep(1)
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=2) as r:
                data = json.load(r)
            tunnels = data.get("tunnels", [])
            if tunnels:
                public_url = tunnels[0]["public_url"]
                break
        except Exception:
            continue

    if not public_url:
        print(
            "Khong lay duoc dia chi ngrok sau 30s. Kiem tra ngrok da dang nhap "
            "(ngrok config add-authtoken ...) va thu lai.",
            flush=True,
        )
        proxy_proc.terminate()
        ngrok_proc.terminate()
        return

    proxy_url = public_url.replace("tcp://", "socks5://")

    print("\n" + "=" * 60, flush=True)
    print("DA SAN SANG! Dan dong nay vao bien YOUTUBE_PROXY_URL tren Railway:", flush=True)
    print(f"\n  YOUTUBE_PROXY_URL={proxy_url}\n", flush=True)
    print("=" * 60, flush=True)
    print("\nDang chay... giu cua so nay mo. Nhan Ctrl+C de dung ca proxy va tunnel.\n", flush=True)

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nDang dung...", flush=True)
    finally:
        proxy_proc.terminate()
        ngrok_proc.terminate()


if __name__ == "__main__":
    main()
