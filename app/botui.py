# -*- coding: utf-8 -*-
"""Control the bot from inside Bale (inline-keyboard menus). Everything the web dashboard can do, except themes.

Security: only users who logged in with the one-time admin code (shown in the dashboard) are obeyed:
    /login CODE
Everything else is ignored (non-admins only get a short login hint).
"""
import hmac
import re
import threading
import time
from collections import deque
from datetime import datetime

from . import article, config, fetcher
from .bale import BaleClient, BaleError, diagnose, explain
from .sources import CATEGORIES, CATEGORY_EMOJI, SOURCES, SOURCES_BY_ID
from .translate import Translator

PAGE = 8
PROVIDERS = [("edge", "Microsoft Edge ⭐"), ("google", "Google"), ("lingva", "Lingva"), ("mymemory", "MyMemory"),
             ("libretranslate", "LibreTranslate"), ("google_cloud", "Google Cloud")]
# (kind, key, label, presets)
SEND_ITEMS = [
    ("bool", "full_text", "متن کامل خبر", None),
    ("bool", "send_images", "ارسال عکس‌ها", None),
    ("bool", "skip_backlog_first_run", "اولین اجرا: مطالب قدیمی ارسال نشود", None),
    ("bool", "auto_start", "شروع خودکار با اجرای برنامه", None),
    ("num", "interval_minutes", "صبر تا دورهٔ بعد، بعد از خالی شدن صف (دقیقه)", [3, 5, 10, 15, 30, 60]),
    ("num", "delay_between_posts_sec", "فاصلهٔ بین دو خبر (ثانیه)", [1, 3, 5, 10, 20]),
    ("num", "max_age_hours", "حداکثر سن خبر (ساعت)", [3, 6, 12, 24, 48]),
    ("num", "max_images", "حداکثر عکس در هر خبر (۰ = نامحدود)", [0, 3, 5, 10, 20]),
    ("num", "summary_chars", "طول خلاصه، فقط بدون «متن کامل» (کاراکتر)", [0, 200, 350, 600, 800]),
]
TR_ITEMS = [
    ("bool", "translate_enabled", "ترجمه فعال باشد", None),
    ("bool", "translate_body", "متن کامل هم ترجمه شود", None),
    ("bool", "translate_show_original", "عنوان اصلی زیر عنوان فارسی", None),
    ("bool", "translate_original_body", "اول متن اصلی کامل، بعد ترجمه", None),
    ("num", "translate_chunk_chars", "اندازهٔ هر تکهٔ ترجمه (کاراکتر)", [1000, 1500, 2000, 2500, 3000]),
    ("num", "translate_delay_sec", "فاصلهٔ بین ترجمه‌ها (ثانیه)", [0, 30, 60, 120, 300]),
    ("num", "translate_give_up_min", "انصراف از ترجمه بعد از (دقیقه، ۰ = هرگز)", [0, 10, 30, 60, 120]),
]
NUM_TYPES = {"translate_delay_sec": float}          # everything else numeric is int
TEXT_ITEMS = {                                       # key -> (label, secret, hint)
    "channel_id": ("آیدی کانال", False, "مثل @my_sec_feed یا لینک ble.ir/my_sec_feed یا شناسهٔ عددی"),
    "include_keywords": ("کلمات «فقط شامل»", False, "هر خط یا هر بخشِ جداشده با ویرگول یک کلمه (انگلیسی)"),
    "exclude_keywords": ("کلمات «ارسال نشود اگر شامل»", False, "هر خط یا هر بخشِ جداشده با ویرگول یک کلمه (انگلیسی)"),
    "fetch_proxy": ("پروکسی دریافت منابع و ترجمه", False, "مثل http://127.0.0.1:10809 یا socks5://127.0.0.1:10808"),
    "bale_proxy": ("پروکسی ارتباط با بله", False, "فقط اگر اتصال به بله برقرار نمی‌شود"),
    "bale_api_base": ("آدرس API بله", False, "پیش‌فرض: https://tapi.bale.ai"),
    "mymemory_email": ("ایمیل MyMemory", False, "اختیاری؛ برای بالا رفتن سهمیهٔ رایگان"),
    "lingva_url": ("آدرس سرورهای Lingva", False, "یک یا چند آدرس با ویرگول"),
    "libretranslate_url": ("آدرس LibreTranslate", False, "مثل http://127.0.0.1:5000"),
    "libretranslate_key": ("کلید LibreTranslate", True, "کلید API"),
    "google_api_key": ("کلید Google Cloud Translation", True, "کلید API"),
}
LIST_KEYS = {"include_keywords", "exclude_keywords"}
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _clock(ts):
    return datetime.fromtimestamp(ts, fetcher.TEHRAN).strftime("%H:%M:%S")


def _rel(sec):
    sec = max(0, int(sec))
    return f"{sec // 60} دقیقه و {sec % 60} ثانیه" if sec >= 60 else f"{sec} ثانیه"


def _n(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def kb(*rows):
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows if row]}


class Ctx:
    def __init__(self, client, uid, chat_id, msg_id=None, cb_id=None):
        self.client, self.uid, self.chat_id, self.msg_id, self.cb_id = client, uid, chat_id, msg_id, cb_id


class BotUI:
    def __init__(self, engine):
        self.engine = engine
        self.stop_evt = threading.Event()
        self.thread = None
        self.state = {}                 # admin user id -> pending input / view state
        self.bad = {}                   # user id -> timestamps of failed /login
        self.info = {"running": False, "username": "", "error": "", "last_poll": None, "polls": 0, "updates": 0,
                     "last_update": None, "mode": "long-poll"}
        self.events = deque(maxlen=30)          # what the bot saw / did (shown in the dashboard to debug the connection)
        self.use_timeout = True
        self._client_key = None
        self._client = None

    # ------------------------------------------------------------ lifecycle
    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_evt.clear()
        self.thread = threading.Thread(target=self._loop, name="botui", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_evt.set()
        if self.thread:
            self.thread.join(timeout=3)
        self.info["running"] = False

    def event(self, msg, level="info", log=False):
        self.events.append({"t": datetime.now().strftime("%H:%M:%S"), "msg": msg, "level": level})
        if log:
            self.engine.log("کنترل از بله: " + msg, level)

    def _get_client(self, cfg):
        key = (cfg["bale_token"], cfg["bale_api_base"], cfg["bale_proxy"])
        if key != self._client_key:
            self._client = BaleClient(cfg["bale_token"], cfg["bale_api_base"], cfg["bale_proxy"], timeout=(10, 45))
            self._client_key = key
            self.info["username"] = ""
        return self._client

    def _loop(self):
        offset, backlog, backoff, hook_cleared = None, True, 5, False
        last_err = ""
        while not self.stop_evt.is_set():
            cfg = config.load()
            if not cfg["bale_token"] or not cfg["bot_control"]:
                self.info.update(running=False, error="" if not cfg["bot_control"] else "توکن هنوز وارد نشده")
                self.stop_evt.wait(5)
                continue
            client = self._get_client(cfg)
            if not self.info["username"]:
                try:
                    self.info["username"] = (client.get_me() or {}).get("username", "")
                    self.event(f"به بله وصل شد: @{self.info['username']}", log=True)
                except BaleError as e:
                    self.info.update(running=False, error=explain(e))
                    if explain(e) != last_err:
                        self.event("اتصال به بله ناموفق: " + explain(e), "error", log=True)
                        last_err = explain(e)
                    self.stop_evt.wait(min(backoff, 60))
                    backoff = min(backoff * 2, 60)
                    continue
            if not hook_cleared:                        # a leftover webhook would stop getUpdates from delivering
                try:
                    client.call("deleteWebhook", {})
                except BaleError:
                    pass
                hook_cleared = True
            t0 = time.time()
            try:
                updates = client.get_updates(offset=offset, timeout=20 if self.use_timeout else 0, limit=50) or []
                self.info.update(running=True, error="", last_poll=time.time(), mode="long-poll" if self.use_timeout else "polling")
                self.info["polls"] += 1
                backoff, last_err = 5, ""
            except BaleError as e:
                if not e.network and self.use_timeout and e.code in (400, 404, 405, 409, 422):
                    self.use_timeout = False            # this Bale server does not like the 'timeout' parameter
                    self.event("long-polling پذیرفته نشد؛ به حالت polling ساده رفتم.", "warn", log=True)
                    continue
                self.info.update(running=False, error=explain(e))
                if explain(e) != last_err:
                    self.event("خطا در دریافت دستورها: " + explain(e), "error", log=True)
                    last_err = explain(e)
                self.stop_evt.wait(min(backoff, 60) if e.network else 30)
                backoff = min(backoff * 2, 60)
                continue
            if updates:
                self.info["last_update"] = time.time()
            for u in updates:
                offset = max(offset or 0, int(u.get("update_id", 0)) + 1)
                self.info["updates"] += 1
                try:
                    self.handle_update(client, u, backlog)
                except BaleError as e:
                    self.event("خطا در پاسخ‌دادن: " + explain(e), "error", log=True)
                except Exception as e:                           # never let one bad update kill the loop
                    self.event(f"خطای داخلی: {type(e).__name__}: {e}", "error", log=True)
            backlog = False
            if not updates and time.time() - t0 < 1.5:           # server answered instantly: avoid hammering it
                self.stop_evt.wait(2)

    # ------------------------------------------------------------ helpers
    def is_admin(self, uid):
        return any(a["id"] == uid for a in config.load()["admins"])

    def st(self, uid):
        return self.state.setdefault(uid, {"await": None})

    def _reply(self, ctx, text, markup=None, edit=True):
        """Edit the menu message in place when possible, otherwise send a new one."""
        if edit and ctx.msg_id:
            try:
                ctx.client.edit_message_text(ctx.chat_id, ctx.msg_id, text, markup)
                return
            except BaleError as e:
                if e.network:
                    raise
        r = ctx.client.send_message(ctx.chat_id, text, markup) or {}
        ctx.msg_id = r.get("message_id", ctx.msg_id)

    def _bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def cfg_set(self, key, value):
        cfg = config.update(lambda c: c.__setitem__(key, value))
        if key in ("include_keywords", "exclude_keywords", "max_age_hours", "selected_sources", "custom_feeds"):
            self.engine.cache.clear()
        return cfg

    # ------------------------------------------------------------ update routing
    def handle_update(self, client, u, backlog=False):
        if "callback_query" in u:
            if backlog:                                          # old button presses from before this run: ignore
                return
            return self.on_callback(client, u["callback_query"])
        m = u.get("message")
        if not m or not m.get("text"):
            return
        frm = m.get("from") or {}
        try:
            uid = int(frm.get("id"))
        except (TypeError, ValueError):
            return
        chat = m.get("chat") or {}
        ctype = str(chat.get("type") or "").lower()
        if ctype not in ("", "private") and chat.get("id") != uid:
            return
        ctx = Ctx(client, uid, chat.get("id", uid))
        text = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", m["text"]).strip()
        low = text.lower()
        shown = "/login ***" if re.match(r"^/?(login|start)\b.+", low) else text[:40]
        self.event(f"پیام از {frm.get('first_name') or uid} ({uid}): {shown}")
        code = None
        mt = re.match(r"^/?(?:login|start)(?:@\w+)?\s*[:：=-]?\s*(\S+)?\s*$", text, re.I)
        if mt and mt.group(1) and (low.startswith("/login") or low.startswith("login") or low.startswith("/start")):
            code = mt.group(1)
        elif not self.is_admin(uid) and re.fullmatch(r"[A-Za-z0-9]{6,12}", text.translate(DIGITS)) and \
                hmac.compare_digest(text.translate(DIGITS).upper(), config.ensure_admin_code().upper()):
            code = text                                          # just the code, without /login
        if low.startswith("/login") or code:
            return self.login(ctx, m, code)
        if backlog:
            return
        if not self.is_admin(uid):
            return client.send_message(ctx.chat_id, "🔒 این ربات خصوصی است.\nبرای دسترسی کد ادمین را (از داشبورد، تب «کنترل از بله») بفرستید:\n/login کد")
        if low.startswith("/cancel"):
            self.st(uid)["await"] = None
            return self.show_home(ctx, "لغو شد.", edit=False)
        if re.match(r"^/(start|menu|help)\b", low):
            self.st(uid)["await"] = None
            return self.show_home(ctx, edit=False)
        cmd = {"/status": "st", "/logs": "lg", "/start_bot": "run:start", "/stop_bot": "run:stop", "/run": "run:now"}.get(low.split()[0])
        if cmd and not self.st(uid)["await"]:                    # text shortcuts (work even if inline buttons are unavailable)
            return self.route(ctx, cmd)
        pending = self.st(uid)["await"]
        if pending:
            return self.on_input(ctx, m, text, pending)
        self.show_home(ctx, edit=False)

    def login(self, ctx, m, code):
        uid = ctx.uid
        now = time.time()
        fails = [t for t in self.bad.get(uid, []) if now - t < 600]
        if len(fails) >= 5:
            self.event("ورود: تلاش‌های ناموفق زیاد؛ موقتاً مسدود", "warn")
            return ctx.client.send_message(ctx.chat_id, "⛔ تلاش‌های ناموفق زیاد بود؛ ۱۰ دقیقه بعد دوباره امتحان کنید.")
        real = config.ensure_admin_code()
        given = (code or "").translate(DIGITS)
        if not given or not hmac.compare_digest(given.upper(), real.upper()):
            self.bad[uid] = fails + [now]
            self.event(f"ورود ناموفق: کد نادرست از {uid}", "warn", log=True)
            return ctx.client.send_message(ctx.chat_id, "❌ کد نادرست است.\nکد را از داشبورد (تب «کنترل از بله») بردارید و به‌شکل /login کد بفرستید.")
        frm = m.get("from") or {}
        name = " ".join(filter(None, [frm.get("first_name"), frm.get("last_name")])) or frm.get("username", "")

        def add(c):
            if not any(a["id"] == uid for a in c["admins"]):
                c["admins"].append({"id": uid, "name": name})
        config.update(add)
        try:
            ctx.client.delete_message(ctx.chat_id, m.get("message_id"))     # do not leave the code in the chat
        except BaleError:
            pass
        self.event(f"ورود موفق: {name or uid}", log=True)
        self.show_home(ctx, "✅ وارد شدید. شما ادمین ربات هستید.", edit=False)

    def on_callback(self, client, cq):
        uid = (cq.get("from") or {}).get("id")
        msg = cq.get("message") or {}
        ctx = Ctx(client, uid, (msg.get("chat") or {}).get("id", uid), msg.get("message_id"), cq.get("id"))
        if not self.is_admin(uid):
            return client.answer_callback(cq.get("id"), "دسترسی ندارید. /login کد", True)
        data = cq.get("data") or ""
        self.event(f"دکمه: {data}")
        try:
            toast = self.route(ctx, data)
        except BaleError as e:
            toast = explain(e)[:150]
        try:
            client.answer_callback(cq.get("id"), toast or "")
        except BaleError:
            pass

    # ------------------------------------------------------------ screens
    def show_home(self, ctx, note="", edit=True):
        snap = self.engine.snapshot()
        run = "▶ در حال اجرا" if snap["running"] else "■ متوقف"
        text = (f"{note}\n\n" if note else "") + f"🛡️ منوی کنترل ربات رصد امنیتی\n\nوضعیت: {run} | صف: {snap['queue']} خبر\nاز دکمه‌ها استفاده کنید. (/menu منو، /cancel لغو)"
        self._reply(ctx, text, kb(
            [("📊 وضعیت", "st"), ("📜 گزارش", "lg")],
            [("▶ شروع", "run:start"), ("■ توقف", "run:stop"), ("⟳ اجرای فوری", "run:now")],
            [("🔌 اتصال", "sec:conn"), ("📨 ارسال", "sec:send")],
            [("📡 منابع و دسته‌بندی", "sec:src"), ("🌐 ترجمه", "sec:tr")],
            [("🔎 فیلتر", "sec:flt"), ("⚙️ پیشرفته", "sec:adv")]), edit)

    def show_status(self, ctx):
        s = self.engine.snapshot()
        cfg = config.load()
        lines = ["📊 وضعیت ربات", ""]
        lines.append("وضعیت: " + ("▶ در حال اجرا" if s["running"] else "■ متوقف"))
        if s["running"]:
            if s.get("phase") == "waiting" and s.get("next_cycle"):
                lines.append(f"مرحله: صف خالی؛ دورهٔ بعد ساعت {_clock(s['next_cycle'])} (تهران)، {_rel(s['next_cycle'] - time.time())} دیگر")
            else:
                lines.append(f"مرحله: پردازش صف — دورهٔ {s['cycle_no']}: {s['cycle_sent']} از {s['cycle_total']} ارسال شد")
        lines.append(f"در صف: {s['queue']} خبر | کل ارسال‌شده: {s['sent_total']}")
        if s.get("last_cycle"):
            lines.append(f"آخرین شروع دوره: {_clock(s['last_cycle'])}")
        t = s.get("tr") or {}
        if not t.get("enabled"):
            lines.append("ترجمه: خاموش")
        elif t.get("blocked_until"):
            lines.append(("⏳ نوبت بعدی ترجمه: " if t.get("gate") == "spacing" else "⚠️ ترجمه محدود تا: ") + _clock(t["blocked_until"]))
        else:
            lines.append("ترجمه: آماده" + (f" (آخرین سرویس: {t['provider']})" if t.get("provider") else ""))
        for x in (t.get("providers") or []):
            mark = "✅" if x["state"] == "ok" else ("⏸" if x["state"] == "cooling" else "•")
            until = f" تا {_clock(x['until'])}" if x.get("until") else ""
            lines.append(f"   {mark} {x['name']}{until}" + (f" — {x['error'][:70]}" if x["state"] == "cooling" and x.get("error") else ""))
        n = s.get("net") or {}
        if n:
            lines.append(("🟢 اتصال به بله: سالم" if n.get("bale") == "ok" else "🔴 اتصال به بله: قطع") + (f" — {n['text']}" if n.get("bale") != "ok" else "") + f" (بررسی {_clock(n['checked'])})")
        f = s.get("feeds") or {"total": 0, "failed": []}
        lines.append(f"منابع: {f['total'] - len(f['failed'])} سالم، {len(f['failed'])} ناموفق")
        for x in f["failed"][:6]:
            lines.append(f"  ✖ {x['name']}: {x['error']}")
        if s.get("last_error"):
            lines.append(f"⚠️ {s['last_error']}")
        lines.append(f"کانال: {cfg['channel_id'] or '—'} | سرویس ترجمه: {cfg['translate_provider']}")
        self._reply(ctx, "\n".join(lines)[:3900], kb([("🔄 تازه‌سازی", "st"), ("🔙 منو", "home")]))

    def show_logs(self, ctx):
        logs = list(self.engine.logs)[-14:]
        icon = {"warn": "⚠️", "error": "❌"}
        text = "📜 آخرین گزارش‌ها\n\n" + "\n".join(f"{l['t']} {icon.get(l['level'], '•')} {l['msg'][:230]}" for l in logs)
        self._reply(ctx, (text if logs else "📜 هنوز گزارشی نیست.")[:3900], kb([("🔄 تازه‌سازی", "lg"), ("🔙 منو", "home")]))

    def _val(self, cfg, key):
        v = cfg[key]
        if key in LIST_KEYS:
            return ("، ".join(v) if v else "—")
        if TEXT_ITEMS.get(key, ("", False))[1]:
            return config.mask_token(v) or "—"
        return v if v not in ("", None) else "—"

    def show_section(self, ctx, name):
        cfg = config.load()
        if name == "conn":
            text = (f"🔌 اتصال به بله\n\nربات: @{self.info['username'] or '?'}\nکانال: {cfg['channel_id'] or '— (تنظیم نشده)'}\n"
                    "توکن: فقط از داشبورد تغییر می‌کند (تغییر توکن یعنی ربات دیگر).")
            return self._reply(ctx, text, kb([("✏️ تغییر آیدی کانال", "tx:channel_id")], [("✅ تست ارسال به کانال", "ts:bale"), ("🏓 پینگ بله", "ts:ping")], [("🔙 منو", "home")]))
        if name in ("send", "tr"):
            items = SEND_ITEMS if name == "send" else TR_ITEMS
            title = "📨 نحوهٔ ارسال" if name == "send" else "🌐 ترجمهٔ خودکار"
            lines = [title, ""]
            rows = []
            for kind, key, label, presets in items:
                if kind == "bool":
                    lines.append(f"{'✅' if cfg[key] else '⬜'} {label}")
                    rows.append([(("✅ " if cfg[key] else "⬜ ") + label, f"tg:{key}")])
                else:
                    lines.append(f"🔢 {label}: {_n(cfg[key])}")
                    rows.append([(f"🔢 {label.split(' (')[0]}: {_n(cfg[key])}", f"nm:{key}")])
            if name == "send":
                lines += ["", "⚡ ارسال پیوسته: تا خالی شدن کامل صف ارسال می‌شود؛ «صبر تا دورهٔ بعد» از لحظهٔ خالی شدن صف حساب می‌شود."]
            else:
                lines += ["", f"سرویس ترجمه: {cfg['translate_provider']}"]
                prow = [(("🔘 " if cfg["translate_provider"] == k else "") + n, f"pv:{k}") for k, n in PROVIDERS]
                rows += [prow[:2], prow[2:4], prow[4:]]
                rows.append([("✉️ ایمیل MyMemory", "tx:mymemory_email"), ("🌍 سرورهای Lingva", "tx:lingva_url")])
                rows.append([("🔗 آدرس LibreTranslate", "tx:libretranslate_url"), ("🔑 کلید LibreTranslate", "tx:libretranslate_key")])
                rows.append([("🔑 کلید Google Cloud", "tx:google_api_key"), ("🧪 تست ترجمه", "ts:tr")])
            rows.append([("🔙 منو", "home")])
            return self._reply(ctx, "\n".join(lines), kb(*rows))
        if name == "flt":
            text = (f"🔎 فیلتر کلمات کلیدی\n\n«فقط شامل»: {self._val(cfg, 'include_keywords')}\n«ارسال نشود اگر شامل»: {self._val(cfg, 'exclude_keywords')}\n\n"
                    "فیلتر روی عنوان و خلاصهٔ خبر (زبان اصلی) اعمال می‌شود. خالی = بدون فیلتر.")
            return self._reply(ctx, text, kb([("✏️ فقط شامل…", "tx:include_keywords"), ("🧹 پاک", "tc:include_keywords")],
                                              [("✏️ ارسال نشود اگر…", "tx:exclude_keywords"), ("🧹 پاک", "tc:exclude_keywords")], [("🔙 منو", "home")]))
        if name == "adv":
            lines = ["⚙️ تنظیمات پیشرفته", ""]
            for k in ("fetch_proxy", "bale_proxy", "bale_api_base"):
                lines.append(f"{TEXT_ITEMS[k][0]}: {self._val(cfg, k)}")
            lines.append(f"نگه‌داشتن اثرانگشت‌ها: {cfg['seen_retention_days']} روز")
            lines.append(f"کنترل از بله: {'✅ فعال' if cfg['bot_control'] else '⬜ غیرفعال'} | ادمین‌ها: {len(cfg['admins'])}")
            return self._reply(ctx, "\n".join(lines), kb(
                [("🌍 پروکسی دریافت منابع", "tx:fetch_proxy"), ("🌍 پروکسی بله", "tx:bale_proxy")],
                [("🔗 آدرس API بله", "tx:bale_api_base"), ("🗓 روز نگه‌داری", "nm:seen_retention_days")],
                [("🧹 خالی کردن صف", "db:q"), ("🗑 پاک‌سازی کامل دیتابیس", "db:a")],
                [("🚪 خروج من از ادمینی", "ad:out")], [("🔙 منو", "home")]))
        if name == "src":
            n_sel = len(cfg["selected_sources"])
            text = (f"📡 منابع و دسته‌بندی\n\nمنابع آماده: {n_sel} از {len(SOURCES)} انتخاب شده\n"
                    f"دسته‌های من: {len(cfg['custom_categories'])} | منابع دستی من: {len(cfg['custom_feeds'])}")
            rows = []
            for key, label in CATEGORIES.items():
                if key == "custom":
                    continue
                ids = [s["id"] for s in SOURCES if s["category"] == key]
                on = sum(1 for i in ids if i in cfg["selected_sources"])
                rows.append([(f"{CATEGORY_EMOJI[key]} {label} ({on}/{len(ids)})", f"sc:{key}:0")])
            rows += [[("🗂 دسته‌بندی‌های من", "cc:list"), ("➕ دستهٔ جدید", "cc:new")],
                     [("📃 منابع دستی من", "cf:list"), ("➕ منبع دستی", "cf:new")],
                     [("🧪 تست منابع", "ts:src"), ("🔙 منو", "home")]]
            return self._reply(ctx, text, kb(*rows))

    def show_num(self, ctx, key):
        cfg = config.load()
        item = next((i for i in SEND_ITEMS + TR_ITEMS if i[1] == key), None)
        presets = item[3] if item else [7, 14, 30, 60, 90]
        label = item[2] if item else "نگه‌داشتن اثرانگشت‌ها (روز)"
        back = "sec:tr" if item and item in TR_ITEMS else ("sec:send" if item else "sec:adv")
        rows = [[(str(v), f"nv:{key}:{v}") for v in presets[i:i + 3]] for i in range(0, len(presets), 3)]
        rows.append([("✏️ مقدار دلخواه", f"ni:{key}"), ("🔙 بازگشت", back)])
        self._reply(ctx, f"🔢 {label}\n\nمقدار فعلی: {_n(cfg[key])}\nیکی را انتخاب کنید یا مقدار دلخواه بفرستید.", kb(*rows))

    def show_sources(self, ctx, cat, page):
        cfg = config.load()
        items = [s for s in SOURCES if s["category"] == cat]
        pages = max(1, (len(items) + PAGE - 1) // PAGE)
        page = max(0, min(page, pages - 1))
        rows = [[(("✅ " if s["id"] in cfg["selected_sources"] else "⬜ ") + s["name"], f"ss:{s['id']}:{cat}:{page}")]
                for s in items[page * PAGE:(page + 1) * PAGE]]
        nav = []
        if page > 0:
            nav.append(("⏪ قبلی", f"sc:{cat}:{page - 1}"))
        if page < pages - 1:
            nav.append(("بعدی ⏩", f"sc:{cat}:{page + 1}"))
        rows += [nav] if nav else []
        rows.append([("✅ همه", f"sa:{cat}:1"), ("⬜ هیچ", f"sa:{cat}:0"), ("🔙 بازگشت", "sec:src")])
        self._reply(ctx, f"{CATEGORY_EMOJI[cat]} {CATEGORIES[cat]}\nصفحهٔ {page + 1} از {pages} — برای فعال/غیرفعال کردن بزنید.", kb(*rows))

    def show_cats(self, ctx):
        cfg = config.load()
        rows = [[(f"🗑 {c['emoji']} {c['name']}", f"cc:del:{c['id']}")] for c in cfg["custom_categories"]]
        rows.append([("➕ دستهٔ جدید", "cc:new"), ("🔙 بازگشت", "sec:src")])
        text = "🗂 دسته‌بندی‌های من\n\n" + ("برای حذف هر دسته روی آن بزنید (منابعِ آن دسته به «سایر» می‌روند)." if cfg["custom_categories"] else "هنوز دسته‌ای نساخته‌اید.")
        self._reply(ctx, text, kb(*rows))

    def show_feeds(self, ctx):
        cfg = config.load()
        info = config.category_info(cfg)
        lines = ["📃 منابع دستی من", ""]
        rows = []
        for i, f in enumerate(cfg["custom_feeds"]):
            c = info.get(f["category"], {"emoji": "📌", "name": "سایر"})
            lines.append(f"{i + 1}. {f['name']} — {c['emoji']} {c['name']}")
            rows.append([(f"🗑 {f['name'][:22]}", f"cf:del:{i}"), (f"🗂 دسته", f"cf:mv:{i}")])
        if not cfg["custom_feeds"]:
            lines.append("هنوز منبع دستی اضافه نکرده‌اید.")
        rows.append([("➕ منبع دستی", "cf:new"), ("🔙 بازگشت", "sec:src")])
        self._reply(ctx, "\n".join(lines)[:3800], kb(*rows))

    def pick_category(self, ctx, prefix, title):
        cfg = config.load()
        cats = [(k, f"{CATEGORY_EMOJI[k]} {v}") for k, v in CATEGORIES.items()] + [(c["id"], f"{c['emoji']} {c['name']}") for c in cfg["custom_categories"]]
        rows = [[(label, f"{prefix}:{cid}")] for cid, label in cats]
        rows.append([("🔙 لغو", "sec:src")])
        self._reply(ctx, title, kb(*rows))

    def prompt(self, ctx, await_state, text):
        self.st(ctx.uid)["await"] = await_state
        self._reply(ctx, text + "\n\n(برای لغو: /cancel)", kb([("🔙 لغو", "cancel")]))

    # ------------------------------------------------------------ callback router
    def route(self, ctx, data):
        a = data.split(":")
        cmd = a[0]
        S = self.st(ctx.uid)
        if cmd == "cancel":
            S["await"] = None
            return self.show_home(ctx)
        if cmd == "home":
            S["await"] = None
            return self.show_home(ctx)
        if cmd == "st":
            return self.show_status(ctx)
        if cmd == "lg":
            return self.show_logs(ctx)
        if cmd == "sec":
            S["await"] = None
            return self.show_section(ctx, a[1])
        if cmd == "run":
            return self.control(ctx, a[1])
        if cmd == "tg":                                             # toggle a bool
            key = a[1]
            if key not in {i[1] for i in SEND_ITEMS + TR_ITEMS if i[0] == "bool"}:
                return
            cur = config.load()[key]
            self.cfg_set(key, not cur)
            self.show_section(ctx, "tr" if key.startswith("translate_") else "send")
            return "روشن شد" if not cur else "خاموش شد"
        if cmd == "nm":
            return self.show_num(ctx, a[1])
        if cmd == "nv":
            return self.set_number(ctx, a[1], a[2])
        if cmd == "ni":
            return self.prompt(ctx, {"type": "num", "key": a[1]}, "✏️ مقدار عددی را بفرستید (مثلاً 15).")
        if cmd == "pv":
            if a[1] in dict(PROVIDERS):
                self.cfg_set("translate_provider", a[1])
                self.show_section(ctx, "tr")
                return "سرویس ترجمه عوض شد"
            return
        if cmd == "tx":
            label, secret, hint = TEXT_ITEMS[a[1]]
            extra = "\n⚠️ برای پاک کردن مقدار، «-» بفرستید. پیام شما بعد از خواندن حذف می‌شود." if secret else "\nبرای پاک کردن مقدار، «-» بفرستید."
            return self.prompt(ctx, {"type": "text", "key": a[1]}, f"✏️ {label}\n{hint}{extra}")
        if cmd == "tc":
            self.cfg_set(a[1], [] if a[1] in LIST_KEYS else "")
            self.show_section(ctx, "flt")
            return "پاک شد"
        if cmd == "sc":
            return self.show_sources(ctx, a[1], int(a[2]))
        if cmd == "ss":
            sid = a[1]
            cur = list(config.load()["selected_sources"])
            self.cfg_set("selected_sources", [x for x in cur if x != sid] if sid in cur else cur + [sid])
            return self.show_sources(ctx, a[2], int(a[3]))
        if cmd == "sa":
            ids = {s["id"] for s in SOURCES if s["category"] == a[1]}
            cur = [x for x in config.load()["selected_sources"] if x not in ids]
            self.cfg_set("selected_sources", cur + (sorted(ids) if a[2] == "1" else []))
            return self.show_sources(ctx, a[1], 0)
        if cmd == "cc":
            if a[1] == "list":
                return self.show_cats(ctx)
            if a[1] == "new":
                return self.prompt(ctx, {"type": "cat_name"}, "🗂 نام دستهٔ جدید را بفرستید (مثلاً: تهدیدات ایران).")
            if a[1] == "del":
                self.cfg_set("custom_categories", [c for c in config.load()["custom_categories"] if c["id"] != a[2]])
                self.show_cats(ctx)
                return "دسته حذف شد"
        if cmd == "cf":
            if a[1] == "list":
                return self.show_feeds(ctx)
            if a[1] == "new":
                return self.prompt(ctx, {"type": "feed_url"}, "➕ آدرس سایت یا فید RSS/Atom را بفرستید.\nاگر آدرس خودِ سایت را بدهید، فید آن خودکار پیدا می‌شود.")
            if a[1] == "del":
                feeds = list(config.load()["custom_feeds"])
                if 0 <= int(a[2]) < len(feeds):
                    feeds.pop(int(a[2]))
                    self.cfg_set("custom_feeds", feeds)
                self.show_feeds(ctx)
                return "منبع حذف شد"
            if a[1] == "mv":
                S["mv"] = int(a[2])
                return self.pick_category(ctx, "cf:mc", "🗂 دستهٔ این منبع را انتخاب کنید:")
            if a[1] == "mc":
                feeds = [dict(f) for f in config.load()["custom_feeds"]]
                if 0 <= S.get("mv", -1) < len(feeds):
                    feeds[S["mv"]]["category"] = ":".join(a[2:])
                    self.cfg_set("custom_feeds", feeds)
                self.show_feeds(ctx)
                return "دسته تغییر کرد"
            if a[1] == "nc":                                       # category chosen for the NEW feed
                p = S.pop("pending_feed", None)
                if p:
                    p["category"] = ":".join(a[2:])
                    feeds = [dict(f) for f in config.load()["custom_feeds"]] + [p]
                    self.cfg_set("custom_feeds", feeds)
                self.show_feeds(ctx)
                return "منبع افزوده شد"
        if cmd == "db":
            return self.db_action(ctx, a[1])
        if cmd == "ts":
            return self.test(ctx, a[1])
        if cmd == "ad" and a[1] == "out":
            config.update(lambda c: c.__setitem__("admins", [x for x in c["admins"] if x["id"] != ctx.uid]))
            return self._reply(ctx, "🚪 از ادمینی خارج شدید. برای ورود دوباره: /login کد", None)

    # ------------------------------------------------------------ actions
    def control(self, ctx, what):
        cfg = config.load()
        if what == "start":
            if not cfg["channel_id"]:
                return "ابتدا آیدی کانال را تنظیم کنید (منو ← اتصال)"
            self.engine.start()
            msg = "▶ ربات شروع شد"
        elif what == "stop":
            threading.Thread(target=self.engine.stop, daemon=True).start()
            msg = "■ در حال توقف…"
        else:
            if not self.engine.running:
                return "ابتدا «شروع» را بزنید"
            self.engine.run_now()
            msg = "⟳ دورهٔ فوری شروع شد"
        time.sleep(0.3)
        self.show_home(ctx)
        return msg

    def set_number(self, ctx, key, raw):
        t = NUM_TYPES.get(key, int)
        try:
            val = t(float(str(raw).translate(DIGITS).replace(",", ".")))
        except ValueError:
            return "عدد نامعتبر است"
        cfg = self.cfg_set(key, val)
        if any(i[1] == key for i in TR_ITEMS):
            self.show_section(ctx, "tr")
        elif key == "seen_retention_days":
            self.show_section(ctx, "adv")
        else:
            self.show_section(ctx, "send")
        return f"ذخیره شد: {_n(cfg[key])}"

    def db_action(self, ctx, what):
        if what == "q":
            return self._reply(ctx, "🧹 صف ارسال خالی شود؟ خبرهای در انتظار ارسال از بین می‌روند.", kb([("✅ بله، خالی کن", "db:q!"), ("🔙 نه", "sec:adv")]))
        if what == "a":
            return self._reply(ctx, "🗑 کل دیتابیس پاک شود؟ ممکن است خبرهای اخیر دوباره ارسال شوند.", kb([("✅ بله، پاک کن", "db:a!"), ("🔙 نه", "sec:adv")]))
        if what == "q!":
            self.engine.store.clear_queue()
        else:
            self.engine.store.clear_all()
        self.engine.cache.clear()
        self.engine.skip_until.clear()
        self.show_section(ctx, "adv")
        return "انجام شد"

    def test(self, ctx, what):
        cfg = config.load()
        if what == "bale":
            try:
                ctx.client.send_message(cfg["channel_id"], "✅ تست اتصال از داخل بله: پیام آزمایشی.")
                return "پیام آزمایشی در کانال ارسال شد ✅"
            except BaleError as e:
                return explain(e)[:190]
        self._reply(ctx, "⏳ در حال تست… (چند ثانیه)", None)

        def work():
            try:
                if what == "ping":
                    d = diagnose(cfg["bale_token"], cfg["bale_api_base"], cfg["bale_proxy"], cfg["fetch_proxy"])
                    text = ("🏓 پینگ بله\n\n" + ("🟢 " if d["reachable"] else "🔴 ") + d["text"] +
                            (f"\nتأخیر: {d['ms']} میلی‌ثانیه" if d.get("ms") and d["reachable"] else ""))
                    back = "sec:conn"
                elif what == "tr":
                    tr = Translator(cfg)
                    t0 = time.time()
                    out, st = tr.translate("Critical vulnerability exploited in the wild. Administrators should patch immediately.", patient=False, ignore_cooldown=True)
                    text = (f"🧪 تست ترجمه\n\n✅ کار می‌کند — سرویس: {tr.last_provider} ({round(time.time() - t0, 1)} ثانیه)\n{out}" if st == "ok"
                            else "🧪 تست ترجمه\n\n❌ ناموفق:\n" + "\n".join(tr.errors.values() or ["پاسخی نیامد"]))
                    back = "sec:tr"
                else:
                    srcs = config.active_sources(cfg)
                    bad = []
                    for s in srcs:
                        try:
                            fetcher.parse_feed(fetcher.fetch_feed(fetcher.new_session(cfg["fetch_proxy"]), s["url"], tries=1), s)
                        except Exception as e:
                            bad.append(f"✖ {s['name']}: {fetcher.describe_error(e)}")
                    text = f"🧪 تست منابع\n\n{len(srcs) - len(bad)} سالم، {len(bad)} ناموفق (از {len(srcs)})\n" + "\n".join(bad[:25])
                    back = "sec:src"
                self._reply(ctx, text[:3900], kb([("🔙 بازگشت", back)]))
            except Exception as e:
                self._reply(ctx, f"خطا در تست: {type(e).__name__}", kb([("🔙 منو", "home")]))
        self._bg(work)

    # ------------------------------------------------------------ typed input
    def on_input(self, ctx, m, text, pending):
        S = self.st(ctx.uid)
        kind = pending["type"]
        if kind == "num":
            if self.set_number(Ctx(ctx.client, ctx.uid, ctx.chat_id), pending["key"], text) == "عدد نامعتبر است":
                return ctx.client.send_message(ctx.chat_id, "❌ عدد نامعتبر است؛ دوباره بفرستید یا /cancel.")
            S["await"] = None
            return
        if kind == "text":
            key = pending["key"]
            S["await"] = None
            secret = TEXT_ITEMS[key][1]
            val = "" if text == "-" else text
            if key in LIST_KEYS:
                val = [x for x in re.split(r"[\n,،;]+", val) if x.strip()]
            cfg = self.cfg_set(key, val)
            if secret:
                try:
                    ctx.client.delete_message(ctx.chat_id, m.get("message_id"))
                except BaleError:
                    pass
            ok = bool(cfg[key]) == bool(val) if key not in ("bale_api_base", "lingva_url") else True
            back = "tr" if key in ("mymemory_email", "lingva_url", "libretranslate_url", "libretranslate_key", "google_api_key") else (
                "flt" if key in LIST_KEYS else ("conn" if key == "channel_id" else "adv"))
            note = ("✅ ذخیره شد." if ok else "⚠️ مقدار نامعتبر بود و ذخیره نشد.")
            if key == "channel_id" and val:
                note += f"\nمقدار: {cfg['channel_id']}"
            ctx.client.send_message(ctx.chat_id, note)
            return self._after_input(ctx, back)
        if kind == "cat_name":
            S["await"] = {"type": "cat_emoji", "name": text[:40]}
            return ctx.client.send_message(ctx.chat_id, "😀 یک ایموجی برای دسته بفرستید (یا «-» برای 📌).\n(لغو: /cancel)")
        if kind == "cat_emoji":
            S["await"] = None
            emoji = "📌" if text == "-" else text[:8]
            self.cfg_set("custom_categories", config.load()["custom_categories"] + [{"id": "", "name": pending["name"], "emoji": emoji}])
            ctx.client.send_message(ctx.chat_id, f"✅ دستهٔ «{emoji} {pending['name']}» ساخته شد.")
            return self._after_input(ctx, "srcl")
        if kind == "feed_url":
            S["await"] = None
            url = text if re.match(r"^https?://", text, re.I) else "https://" + text
            ctx.client.send_message(ctx.chat_id, "🔎 در حال پیدا کردن فید…")

            def work():
                try:
                    res = article.discover_feed(fetcher.new_session(config.load()["fetch_proxy"]), url)
                except Exception as e:
                    ctx.client.send_message(ctx.chat_id, f"❌ {fetcher.describe_error(e)}\nدوباره از منو امتحان کنید.")
                    return self._after_input(ctx, "srcl")
                S["pending_feed"] = {"name": res["title"] or re.sub(r"^https?://", "", res["feed_url"]).split("/")[0], "url": res["feed_url"], "category": "custom"}
                S["await"] = {"type": "feed_name"}
                ctx.client.send_message(ctx.chat_id, f"✅ فید پیدا شد: {res['title'] or res['feed_url']}\n({res['count']} مطلب)\n\nنام دلخواه را بفرستید، یا «-» برای همین نام.\n(لغو: /cancel)")
            return self._bg(work)
        if kind == "feed_name":
            S["await"] = None
            if text != "-" and S.get("pending_feed"):
                S["pending_feed"]["name"] = text[:80]
            return self.pick_category(Ctx(ctx.client, ctx.uid, ctx.chat_id), "cf:nc", "🗂 دستهٔ این منبع را انتخاب کنید:")

    def _after_input(self, ctx, where):
        c2 = Ctx(ctx.client, ctx.uid, ctx.chat_id)
        if where == "srcl":
            return self.show_cats(c2)
        return self.show_section(c2, where)
