/**
 * Widget chat noi (floating chat bubble) cho website Lovable (React + Tailwind).
 *
 * Cach dung:
 * 1. Copy file nay vao thu muc src/components/ trong project Lovable cua ban
 *    (doi ten neu muon, vi du ChatWidget.tsx).
 * 2. Sua API_URL ben duoi thanh URL that cua backend sau khi deploy len Railway
 *    (vi du "https://ten-du-an-cua-ban.up.railway.app").
 * 3. Import va dat <ChatWidget /> vao App.tsx (hoac layout chinh) de no hien o moi trang:
 *
 *      import ChatWidget from "@/components/ChatWidget";
 *      ...
 *      <ChatWidget />
 */

import { useState, useRef, useEffect } from "react";

const API_URL = "https://YOUR-RAILWAY-APP.up.railway.app";

type Message = { role: "user" | "assistant"; text: string };

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, open]);

  async function sendMessage() {
    const text = input.trim();
    if (!text || loading) return;

    const history = messages.map((m) => ({
      role: m.role === "user" ? "Khach hang" : "Tro ly",
      text: m.text,
    }));

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", text: data.reply }]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Xin loi, khong ket noi duoc voi tro ly. Vui long thu lai." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end">
      {open && (
        <div className="mb-3 flex h-[500px] w-[340px] flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-xl">
          <div className="flex items-center justify-between border-b border-border bg-primary px-4 py-3">
            <span className="font-semibold text-primary-foreground">Tro ly san pham</span>
            <button
              onClick={() => setOpen(false)}
              className="text-primary-foreground/80 hover:text-primary-foreground"
              aria-label="Dong chat"
            >
              ✕
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {messages.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Xin chao! Ban muon hoi gi ve san pham, cach dung, hay gia ca khong?
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                  m.role === "user"
                    ? "ml-auto bg-primary text-primary-foreground"
                    : "bg-muted text-foreground"
                }`}
              >
                {m.text}
              </div>
            ))}
            {loading && (
              <div className="max-w-[85%] rounded-xl bg-muted px-3 py-2 text-sm text-muted-foreground">
                Dang tra loi...
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 border-t border-border p-3">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Nhap cau hoi..."
              className="flex-1 rounded-full border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
            />
            <button
              onClick={sendMessage}
              disabled={loading}
              className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              Gui
            </button>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-14 w-14 items-center justify-center rounded-full bg-primary text-2xl text-primary-foreground shadow-lg transition-transform hover:scale-105"
        aria-label="Mo chat"
      >
        {open ? "✕" : "💬"}
      </button>
    </div>
  );
}
