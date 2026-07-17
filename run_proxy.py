"""
Chay 1 SOCKS5 proxy nho tren may ban (dung de "Learn from YouTube" tren Railway
di qua IP nha ban, tranh bi YouTube chan IP cua Railway).

File nay chi la wrapper vong qua 1 loi tuong thich cua thu vien pproxy voi
Python 3.14 (asyncio.get_event_loop() bi that bai khi chua co event loop san).

Chay:
    py run_proxy.py

Se lang nghe tai socks5://0.0.0.0:1080 - de cua so nay chay, roi dung ngrok
de mo duong ra ngoai (xem huong dan da gui).
"""

import asyncio
import sys

asyncio.set_event_loop(asyncio.new_event_loop())
sys.argv = ["pproxy", "-l", "socks5://0.0.0.0:1080", "-v"]

from pproxy.server import main

print("Dang chay SOCKS5 proxy tai 0.0.0.0:1080 ... (dung Ctrl+C de dung)")
main()
