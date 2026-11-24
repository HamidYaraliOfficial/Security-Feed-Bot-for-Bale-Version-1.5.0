# -*- coding: utf-8 -*-
"""Minimal client for the Bale Bot API (https://tapi.bale.ai/bot<TOKEN>/<method>)."""
import re
import time

import requests


class BaleError(Exception):
    def __init__(self, description, code=None, retry_after=None, network=False):
        super().__init__(description)
        self.description = description
        self.code = code
        self.retry_after = retry_after
        self.network = network          # transient problem (connection / 5xx): try again later


_FATAL_RE = re.compile(
    r"chat not found|not found|forbidden|unauthorized|not enough rights|administrator|kicked|not a member|rights",
    re.I,
)


def is_fatal(e):
    """Errors that mean 'configuration is wrong' (bad token / channel / permissions)."""
    if e.network:
        return False
    if e.code in (401, 403, 404):
        return True
    return e.code == 400 and bool(_FATAL_RE.search(e.description or ""))


def explain(e):
    """Human friendly (Persian) explanation of a BaleError."""
    d = (e.description or "").lower()
    if e.network:
        return ("اتصال به سرور بله برقرار نشد. اینترنت را بررسی کنید؛ اگر برنامه خارج از ایران اجرا می‌شود "
                "و بله باز نمی‌شود، در بخش «پیشرفته» پروکسی بله را تنظیم کنید.")
    if e.code == 401:
        return "توکن نامعتبر است. توکن را دقیقاً از @botfather کپی کنید (بدون فاصله اضافه)."
    if e.code == 403 or "rights" in d or "administrator" in d:
        return "ربات اجازهٔ ارسال در این کانال را ندارد. ربات را ادمین کانال کنید و دسترسی «ارسال پیام» بدهید."
    if e.code in (400, 404):
        return ("کانال پیدا نشد. آیدی کانال را بررسی کنید (مثل @mychannel یا عدد) و مطمئن شوید ربات "
                "در کانال ادمین است.")
    if e.code == 429:
        return "بله موقتاً محدودیت نرخ اعمال کرده؛ چند دقیقه بعد دوباره امتحان کنید."
    return f"خطای بله: {e.description} (کد {e.code})"


class BaleClient:
    """Bale Bot API client.

    No keep-alive: a pooled connection that sat idle (e.g. while waiting for the next translation) is closed by the
    server / proxy / NAT after a while, and the next request on it fails - which looked like "Bale is down".
    Every call therefore uses a fresh connection, and a failed connect is retried once."""

    def __init__(self, token, base="https://tapi.bale.ai", proxy="", timeout=(10, 45)):
        self._url = f"{base.rstrip('/')}/bot{token}/"
        self.proxy = proxy
        self.timeout = timeout

    def _session(self):
        s = requests.Session()
        s.headers["Connection"] = "close"
        if self.proxy:
            s.proxies = {"http": self.proxy, "https": self.proxy}
        return s

    @staticmethod
    def _chat(chat_id):
        s = str(chat_id)
        return int(s) if re.fullmatch(r"-?\d+", s) else s

    def call(self, method, payload=None, files=None):
        r = None
        for attempt in (1, 2):
            sess = self._session()
            try:
                if files:
                    r = sess.post(self._url + method, data=payload or {}, files=files, timeout=self.timeout)
                else:
                    r = sess.post(self._url + method, json=payload or {}, timeout=self.timeout)
                break
            except requests.ConnectionError as e:                  # connect failed / reset: nothing was processed yet
                if attempt == 1:
                    time.sleep(0.6)
                    continue
                # never include str(e): it may contain the URL (and therefore the token)
                raise BaleError("network error: " + type(e).__name__, network=True) from None
            except requests.RequestException as e:
                raise BaleError("network error: " + type(e).__name__, network=True) from None
            finally:
                sess.close()
        try:
            data = r.json()
        except ValueError:
            raise BaleError(f"invalid response (HTTP {r.status_code})", code=r.status_code,
                            network=r.status_code >= 500) from None
        if r.ok and data.get("ok"):
            return data.get("result")
        code = data.get("error_code") or r.status_code
        params = data.get("parameters") or {}
        raise BaleError(str(data.get("description") or f"HTTP {r.status_code}"), code=code,
                        retry_after=params.get("retry_after"), network=code >= 500)

    def get_me(self):
        return self.call("getMe")

    def send_message(self, chat_id, text, reply_markup=None):
        payload = {"chat_id": self._chat(chat_id), "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.call("sendMessage", payload)

    def edit_message_text(self, chat_id, message_id, text, reply_markup=None):
        payload = {"chat_id": self._chat(chat_id), "message_id": message_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.call("editMessageText", payload)

    def answer_callback(self, callback_id, text="", alert=False):
        payload = {"callback_query_id": callback_id}
        if text:
            payload.update(text=text, show_alert=bool(alert))
        return self.call("answerCallbackQuery", payload)

    def delete_message(self, chat_id, message_id):
        return self.call("deleteMessage", {"chat_id": self._chat(chat_id), "message_id": message_id})

    def send_photo(self, chat_id, data, filename, caption):
        return self.call("sendPhoto", {"chat_id": str(chat_id), "caption": caption},
                         files={"photo": (filename, data)})

    def get_updates(self, offset=None, timeout=0, limit=100):
        payload = {"limit": limit, "timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload)


INTERNET_PROBES = ["https://www.gstatic.com/generate_204", "https://cp.cloudflare.com/generate_204",
                   "https://www.msftconnecttest.com/connecttest.txt"]


def ping_bale(token, base="https://tapi.bale.ai", proxy="", timeout=(6, 12)):
    """Cheap connectivity check (getMe on a fresh connection).
    -> {'ok': token+API fine, 'reachable': Bale answered at all, 'ms': latency, 'username', 'error'}"""
    t0 = time.time()
    try:
        me = BaleClient(token, base, proxy, timeout=timeout).get_me() or {}
        return {"ok": True, "reachable": True, "ms": int((time.time() - t0) * 1000), "username": me.get("username", "")}
    except BaleError as e:
        return {"ok": False, "reachable": not e.network, "ms": int((time.time() - t0) * 1000), "error": explain(e), "code": e.code}


def internet_ok(proxy="", timeout=6):
    """True if at least one well-known 'connectivity check' URL answers (through the given proxy, if any)."""
    proxies = {"http": proxy, "https": proxy} if proxy else None
    for url in INTERNET_PROBES:
        try:
            r = requests.get(url, proxies=proxies, timeout=timeout, headers={"Connection": "close"})
            if r.status_code < 500:
                return True
        except requests.RequestException:
            continue
    return False


def diagnose(token, base="https://tapi.bale.ai", bale_proxy="", fetch_proxy=""):
    """Ping Bale; if it does not answer, find out whether the Internet itself is the problem."""
    p = ping_bale(token, base, bale_proxy)
    if p["reachable"]:
        return {**p, "internet": True, "text": ("اتصال به بله سالم است" + (f" (@{p.get('username')}، {p['ms']} میلی‌ثانیه)" if p["ok"] else f" ولی: {p.get('error')}"))}
    net = internet_ok(bale_proxy or fetch_proxy)
    text = ("اینترنت (یا پروکسی) قطع است؛ هیچ سایتی جواب نمی‌دهد." if not net else
            "اینترنت وصل است ولی سرور بله (tapi.bale.ai) از این مسیر جواب نمی‌دهد؛ قطعی موقتِ بله یا مسدود بودن آدرس برای این شبکه/پروکسی.")
    return {**p, "internet": net, "text": text}
