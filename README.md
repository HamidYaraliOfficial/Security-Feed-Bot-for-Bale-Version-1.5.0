# Security Feed Bot for Bale · ربات رصد امنیتی برای بله

**[English](#english) · [فارسی](#persian)**

---

<a id="english"></a>

# Security Feed Bot for Bale — English

Version 1.5.0 · [فارسی](#persian)

A self-hosted bot that watches well-known security, vulnerability, threat-research and Internet-observation feeds and posts **every new item — full text, all images, translated to Persian when needed — into your own Bale channel**, always with the source and a link. It has a local web **dashboard** and can be **fully controlled from inside Bale with buttons**.

## Contents
1. [Features](#en-features) · 2. [How a cycle works](#en-cycle) · 3. [Quick start](#en-start) · 4. [Create the bot and the channel](#en-bale) · 5. [Dashboard](#en-dash) · 6. [Control from Bale](#en-botui) · 7. [Translation](#en-translate) · 8. [Sources & categories](#en-sources) · 9. [Configuration reference](#en-config) · 10. [Data, privacy, copyright](#en-data) · 11. [Running 24/7](#en-247) · 12. [Troubleshooting](#en-trouble) · 13. [Project layout & tests](#en-dev)

<a id="en-features"></a>
## 1. Features
- **Full articles**: the whole text (split into several messages when long) and **every image**, in reading order. Feed content is used when complete, otherwise the article page is downloaded and the body extracted (menus, ads, comments, related posts are dropped).
- **Translation to Persian**, piece by piece, with six providers and automatic fall-back. **Order in the channel: header → full original text (with photos) → full Persian translation.**
- **Rate-limit friendly**: by default **one translation request per minute per provider**; after an HTTP 429 the spacing grows automatically and `Retry-After` is honoured; the title is translated together with the first piece (saves one request per article).
- **A cycle ends only when the queue is empty**: nothing stays in the queue; the next-cycle clock starts only after the queue became empty.
- **Resumable**: every translated piece and every sent message is stored, so interruptions never duplicate or lose anything.
- **Categories & sources of your own**: give a site URL and the RSS/Atom feed is discovered and verified automatically.
- **Control from Bale**: inline-keyboard menus for everything in the dashboard (start/stop, send, sources, categories, manual sources, translation, filters, proxies, database, tests, logs).
- **Dashboard**: tabs, live status and logs, failing-source health, 12 colour themes (pink, red, blue, … and dark), Persian RTL UI.
- **Small database**: a post is deleted from the database as soon as it is fully sent; only a 20-char fingerprint remains (pruned automatically).
- **Self-healing Bale connection**: every request uses a fresh connection (no stale keep-alive), and when Bale does not answer the bot **pings it** (3, 5, 10, 15, 20, 30 s …), tells you whether Bale or the Internet is the problem, and **continues the same post** the moment Bale answers — nothing is duplicated or lost.
- **Translation servers switch automatically**: a failing/limited provider is paused with back-off, the next one takes over and **stays in charge** while it works; every switch is shown in the live log and in a live provider-health strip.
- **Robust feed fetching**: 3 attempts with different User-Agents, retries on broken connections, failing feeds are retried later and later, proxy support (HTTP/SOCKS) separately for sources/translation and for Bale.

<a id="en-cycle"></a>
## 2. How a cycle works
```
cycle N starts ──► check all feeds ──► new items go into the queue
                                          │
                  ┌───────────────────────┘
                  ▼
        take every post in the queue (no per-cycle limit)
          1. build the post (full text, images)
          2. if it needs translation: translate piece by piece (1 piece / delay), results are saved
          3. send: header → FULL original text (+photos) → FULL Persian translation → link
          4. delete the post from the database
        a post whose translation is temporarily blocked is put aside and the others continue
                  │
                  ▼
        queue EMPTY?  ──no──► keep working (no new cycle starts)
                  │yes
                  ▼
        wait `interval_minutes` (clock shown in the dashboard) ──► cycle N+1
```
If translation stays impossible for `translate_give_up_min` minutes (default 30), the original text is sent with a "translation failed" marker so the queue can finish (set 0 to wait forever).

<a id="en-start"></a>
## 3. Quick start
Requirements: Python 3.9+ and Internet. No other software.

| System | Run |
|---|---|
| Windows | double-click `start_windows.bat` |
| Linux / macOS | `chmod +x start_linux_mac.sh && ./start_linux_mac.sh` |
| Manual | `python -m venv .venv` → `.venv/bin/pip install -r requirements.txt` → `.venv/bin/python run.py` |
| Server (no dashboard) | `python run.py --headless` |

The dashboard opens at `http://127.0.0.1:8765` (local only). Options: `--port 9000`, `--no-browser`, `--headless`.

<a id="en-bale"></a>
## 4. Create the bot and the channel
1. In Bale (or `web.bale.ai`) open **@botfather**, send `/newbot`, choose a name and a username (usually ending with `bot`). Copy the **token**.
2. Create a **public channel** with an id such as `my_sec_feed` (link `ble.ir/my_sec_feed`).
3. Channel → Administrators → add your bot → allow **sending messages**.
4. In the dashboard (tab *Connection*) enter the token and `@my_sec_feed`, press **Test**, then **Start**.

Private channel? Use its numeric id (the *Find numeric id* button may or may not work depending on Bale).

<a id="en-dash"></a>
## 5. Dashboard
Tabs: **Connection · Sending · Sources & categories · Translation · Filter · Advanced · Control from Bale · Live log**. Top bar: status, 🎨 theme, Save, Start, Stop, Run now. Cards: state, last cycle, **next cycle (clock time)**, queue, translation state, total sent, database size. Every input has a "what to type / where to get it" hint.

<a id="en-botui"></a>
## 6. Control from Bale
Everything in the dashboard (except colour themes) is available in Bale as buttons.

1. Dashboard → tab *Control from Bale* → copy the **admin code**.
2. In Bale open **your bot**, press **Start**, send `/login CODE`. The message with the code is deleted and the menu appears.
3. Use the buttons. Commands: `/menu` (menu), `/cancel` (cancel an input), `/login CODE`. Text shortcuts that work even without inline buttons: `/status`, `/logs`, `/start_bot`, `/stop_bot`, `/run`. Sending just the code also logs you in.

The control thread always runs (it starts waiting for the token if you save it later in the dashboard). The dashboard tab *Control from Bale* shows how many polls/updates arrived, the last receive time and the last events — if nothing appears there after you send `/login`, the bot is not receiving Bale messages (check the ping, `bale_proxy`, and that you are chatting with the bot whose token is configured).

Menu map: **Status · Log · Start/Stop/Run now · Connection** (channel id, test) **· Sending** (full text, images, interval, delays, age, image cap, summary) **· Sources** (toggle every built-in source with paging, all/none, my categories, add a category, add a manual source from a site URL, move/delete, test sources) **· Translation** (switches, provider, chunk size, spacing, give-up time, keys/URLs, test) **· Filter · Advanced** (proxies, API base, retention, clear queue / database, log out).

Security: only logged-in admins are obeyed, only in private chats; wrong codes are rate-limited (5 tries / 10 min); API keys you type are deleted from the chat after being read; you can revoke admins or regenerate the code in the dashboard. Do not share the admin code.

<a id="en-translate"></a>
## 7. Translation
| Provider | Key | Notes |
|---|---|---|
| `edge` (default) | none | Microsoft Edge translator; token fetched automatically; unofficial. |
| `google` | none | Unofficial endpoint; often HTTP 429 on shared IPs / VPNs. |
| `lingva` | none | Open-source Google front-end; several public instances are rotated. |
| `mymemory` | optional e-mail | Small daily quota; mainly a fall-back. |
| `libretranslate` | URL (+key) | Your own server: `docker run -ti --rm -p 5000:5000 libretranslate/libretranslate`. |
| `google_cloud` | API key | Official; needs a billing-enabled Google Cloud project (free monthly quota; check Google's pricing). |

Behaviour: texts are cut into pieces (`translate_chunk_chars`, default 2500); each provider gets at most one request per `translate_delay_sec` (default 60 s); errors pause a provider with exponential back-off (30 s … 10 min) while the next provider is tried; spacing is *not* treated as an error. Translation uses `fetch_proxy`. Only the text of public articles is sent to the provider. Machine translation can be inaccurate — that is why the original text comes first.

<a id="en-sources"></a>
## 8. Sources & categories
Built-in sources (36; ✓ = enabled on first run). Feed URLs can change over time — use *Test sources* and add replacements as manual sources.

| Source | Category | Feed | Default |
|---|---|---|---|
| The Hacker News | Security news | `https://feeds.feedburner.com/TheHackersNews` | ✓ |
| BleepingComputer | Security news | `https://www.bleepingcomputer.com/feed/` | ✓ |
| Krebs on Security | Security news | `https://krebsonsecurity.com/feed/` | ✓ |
| SecurityWeek | Security news | `https://feeds.feedburner.com/securityweek` | ✓ |
| The Record (Recorded Future News) | Security news | `https://therecord.media/feed` | ✓ |
| Dark Reading | Security news | `https://www.darkreading.com/rss.xml` |  |
| Security Affairs | Security news | `https://securityaffairs.com/feed` |  |
| Help Net Security | Security news | `https://www.helpnetsecurity.com/feed/` |  |
| Ars Technica - Security | Security news | `https://arstechnica.com/security/feed/` |  |
| CyberScoop | Security news | `https://cyberscoop.com/feed/` |  |
| Schneier on Security | Security news | `https://www.schneier.com/feed/atom/` |  |
| Graham Cluley | Security news | `https://grahamcluley.com/feed/` |  |
| Troy Hunt | Security news | `https://www.troyhunt.com/rss/` |  |
| CISA - Cybersecurity Advisories | Official advisories & vulnerabilities | `https://www.cisa.gov/cybersecurity-advisories/all.xml` | ✓ |
| NCSC UK | Official advisories & vulnerabilities | `https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml` |  |
| Microsoft MSRC - Update Guide | Official advisories & vulnerabilities | `https://api.msrc.microsoft.com/update-guide/rss` |  |
| Zero Day Initiative - Published Advisories | Official advisories & vulnerabilities | `https://www.zerodayinitiative.com/rss/published/` |  |
| Exploit-DB | Official advisories & vulnerabilities | `https://www.exploit-db.com/rss.xml` |  |
| SANS Internet Storm Center | Threat research & observation | `https://isc.sans.edu/rssfeed.xml` | ✓ |
| Cisco Talos | Threat research & observation | `https://blog.talosintelligence.com/rss/` | ✓ |
| Palo Alto Unit 42 | Threat research & observation | `https://unit42.paloaltonetworks.com/feed/` | ✓ |
| Kaspersky Securelist | Threat research & observation | `https://securelist.com/feed/` | ✓ |
| ESET WeLiveSecurity | Threat research & observation | `https://www.welivesecurity.com/en/rss/feed/` |  |
| Microsoft Security Blog | Threat research & observation | `https://www.microsoft.com/en-us/security/blog/feed/` |  |
| Google Project Zero | Threat research & observation | `https://googleprojectzero.blogspot.com/feeds/posts/default` |  |
| Check Point Research | Threat research & observation | `https://research.checkpoint.com/feed/` |  |
| Sophos News | Threat research & observation | `https://news.sophos.com/en-us/feed/` |  |
| Malwarebytes Labs | Threat research & observation | `https://www.malwarebytes.com/blog/feed/index.xml` |  |
| Elastic Security Labs | Threat research & observation | `https://www.elastic.co/security-labs/rss/feed.xml` |  |
| Citizen Lab | Threat research & observation | `https://citizenlab.ca/feed/` |  |
| Cloudflare Blog | Network, Internet & anomaly observation | `https://blog.cloudflare.com/rss/` | ✓ |
| APNIC Blog | Network, Internet & anomaly observation | `https://blog.apnic.net/feed/` | ✓ |
| OONI (سنجش سانسور و اختلال) | Network, Internet & anomaly observation | `https://ooni.org/post/index.xml` | ✓ |
| Kentik Blog (تحلیل قطعی‌ها) | Network, Internet & anomaly observation | `https://www.kentik.com/blog/feed/` |  |
| Internet Society | Network, Internet & anomaly observation | `https://www.internetsociety.org/feed/` |  |
| Tor Project Blog | Network, Internet & anomaly observation | `https://blog.torproject.org/rss.xml` |  |

**Your own category**: name + emoji; posts show the name and a hashtag (e.g. `#iran_threats`). **Your own source**: paste a site or feed URL; the feed is discovered (page `<link rel=alternate>` or common paths like `/feed`, `/rss.xml`), verified and added to the category you choose. Sites without a feed can be turned into one with tools such as RSSHub or RSS-Bridge.

<a id="en-config"></a>
## 9. Configuration reference
Stored in `data/config.json` (created on first run). Normally edit it through the dashboard or Bale.

| Key | Meaning |
|---|---|
| `bale_token` | Bot token from @botfather (dashboard only). |
| `channel_id` | Target channel: `@id`, a `ble.ir/…` link, or a numeric id. |
| `bale_api_base` | Bale Bot API base URL. |
| `interval_minutes` | Minutes to wait **after the queue became empty** before the next cycle. |
| `delay_between_posts_sec` | Pause between two posts (Bale rate limits). |
| `max_age_hours` | Ignore items older than this. |
| `full_text` | Send the full article (split into several messages if long); off = summary only. |
| `summary_chars` | Summary length when `full_text` is off (0 = title + link only). |
| `send_images` | Send the lead image and every image of the article, in order. |
| `max_images` | Cap on images per article (0 = unlimited). |
| `skip_backlog_first_run` | On the very first run, mark existing items as seen instead of sending them. |
| `selected_sources` | Ids of the enabled built-in sources. |
| `custom_categories` | Your own categories (`id`, `name`, `emoji`). |
| `custom_feeds` | Your own sources (`name`, `url`, `category`). |
| `translate_enabled` | Translate non-Persian posts to Persian. |
| `translate_provider` | `edge` (default), `google`, `lingva`, `mymemory`, `libretranslate`, `google_cloud`. |
| `translate_body` | Translate the full text too (off = title only). |
| `translate_show_original` | Show the original title under the Persian title. |
| `translate_original_body` | Send the full original text first, then the full Persian translation. |
| `translate_chunk_chars` | Size of one translation piece (300–3000). |
| `translate_delay_sec` | Minimum seconds between two translation requests to the same provider (default 60 = one piece per minute). |
| `translate_give_up_min` | If a post cannot be translated for this many minutes, send the original with a marker (0 = never give up). |
| `lingva_url` | One or more Lingva instances, comma separated (tried in turn). |
| `libretranslate_url / _key` | Your LibreTranslate server and optional API key. |
| `google_api_key` | Google Cloud Translation API key (official). |
| `mymemory_email` | Optional e-mail that raises the free MyMemory quota. |
| `include_keywords / exclude_keywords` | Keyword filters on title + summary. |
| `fetch_proxy` | Proxy for downloading feeds, articles, images and for translation. |
| `bale_proxy` | Proxy for talking to Bale only. |
| `seen_retention_days` | Days to keep the tiny dedup fingerprints. |
| `auto_start` | Start the bot automatically when the app starts. |
| `bot_control` | Allow control from inside Bale (admins only). |
| `admin_code / admins` | One-time login code and logged-in Bale admins. |
| `panel_port` | Dashboard port (default 8765). |

<a id="en-data"></a>
## 10. Data, privacy, copyright
- `data/config.json` contains your **bot token and API keys** — never share or commit it. `data/bot.db` holds the queue (posts waiting to be sent, with their text) and tiny dedup fingerprints; posts are deleted right after being fully sent; images are never stored on disk.
- The dashboard listens on `127.0.0.1` only and every API call needs a per-run random token; the Bale control accepts only logged-in admins.
- Translation sends the text of public articles to the selected provider; nothing about you or your token. Turn it off or self-host LibreTranslate if that matters.
- Posting full articles into a **private channel for personal reading** is common practice; re-publishing other sites' full articles publicly may violate their copyright/terms. If your channel is public or shared, turn `full_text` off (summary + link only). The source name and link are always included.

<a id="en-247"></a>
## 11. Running 24/7
- **Windows**: keep `start_windows.bat` running; to start with Windows put a shortcut into `shell:startup`.
- **Linux (systemd)**:
```ini
[Unit]
Description=Security feed bot for Bale
After=network-online.target

[Service]
WorkingDirectory=/opt/bale_security_bot
ExecStart=/opt/bale_security_bot/.venv/bin/python run.py --headless
Restart=always
RestartSec=10
User=balebot

[Install]
WantedBy=multi-user.target
```
  Configure once with the dashboard (or copy `data/config.json`), later control the bot from Bale. For the dashboard on a server use an SSH tunnel: `ssh -L 8765:127.0.0.1:8765 user@server`.

<a id="en-trouble"></a>
## 12. Troubleshooting
| Symptom | Cause / fix |
|---|---|
| "token invalid" / "no permission" / "channel not found" | Copy the token again; make the bot an **administrator with send permission**; check the channel id. |
| Cannot reach Bale | Check the Internet; set `bale_proxy` (e.g. when running outside Iran). |
| Many sources fail (403 / timeout / connection) | Sites are blocked from your network or use bot protection: set `fetch_proxy` (VPN/proxy), disable dead sources (*Live log* tab → one click). Failing sources are retried later and later. |
| HTTP 429 in translation | Your IP is rate-limited: keep `edge` as provider, increase `translate_delay_sec`, use a proxy with another IP, or self-host LibreTranslate / use Google Cloud. |
| Posts are slow | By design: 1 translation piece per minute. Lower `translate_delay_sec` if your provider allows, enlarge the piece size, or disable body translation. |
| Next cycle does not start | It starts only when the queue is empty. Look at the *Live log* for blocked posts; `translate_give_up_min` ends them. |
| Bale menu does not answer | Open the dashboard tab *Control from Bale*: it must say "ready"; the counters/events show whether messages arrive. Check `bot_control`, press the 🏓 *ping* button (Connection tab), set `bale_proxy` if needed, make sure you chat with **the same bot** as the token, then send `/login CODE` (or `/start CODE`, or just the code). |
| "Sending paused, retry in 60 s" although Internet/proxy are fine | Fixed in 1.5: no stale keep-alive; the bot now pings Bale and resumes the same post at once. The live log says whether the problem is Bale, your proxy or the Internet. |
| Only a summary arrives | The article page is paywalled/blocked or unreachable — try `fetch_proxy`. |

<a id="en-dev"></a>
## 13. Project layout & tests
```
run.py                 entry point (dashboard + bot, or --headless)
app/worker.py          engine: cycles, queue, translation stage, sending, feed health
app/composer.py        builds posts: header, full text, images, original-then-Persian
app/article.py         article extraction, feed discovery
app/translate.py       providers, spacing, back-off, Retry-After
app/botui.py           control from Bale (inline-keyboard menus, admin login)
app/bale.py            Bale Bot API client      app/fetcher.py  feeds, images, formatting
app/db.py              SQLite queue + dedup     app/config.py   settings
app/panel.py           local dashboard server   app/web/        dashboard page + Vazirmatn font
```
The code was tested end-to-end against simulated Bale / feed / translator servers (cycle semantics, spacing, fall-backs, resume, Bale menus). It was **not** verified against the live Bale servers or live translation endpoints from the build environment — use the built-in *Test* buttons on your machine. Unofficial endpoints (Google, Edge, Lingva) may change at any time.

Credits: Vazirmatn font (SIL Open Font License, see `app/web/fonts/OFL.txt`).

---

<a id="persian"></a>

<div dir="rtl" align="right">

# ربات رصد امنیتی برای بله — فارسی

نسخهٔ 1.5.0 · [English](#english)

ربات خودمیزبان که فیدهای معتبر امنیتی، آسیب‌پذیری، رصد تهدید و رصد اینترنت را می‌خواند و **هر خبر جدید را با متن کامل، همهٔ عکس‌ها و (در صورت نیاز) ترجمهٔ فارسی در کانال بلهٔ خودتان** می‌گذارد؛ همیشه با نام منبع و لینک. یک **داشبورد** محلی دارد و می‌توان آن را **کاملاً از داخل خود بله با دکمه‌ها کنترل کرد**.

## فهرست
۱. [امکانات](#fa-features) · ۲. [چرخهٔ کار](#fa-cycle) · ۳. [شروع سریع](#fa-start) · ۴. [ساخت ربات و کانال](#fa-bale) · ۵. [داشبورد](#fa-dash) · ۶. [کنترل از داخل بله](#fa-botui) · ۷. [ترجمه](#fa-translate) · ۸. [منابع و دسته‌بندی](#fa-sources) · ۹. [مرجع تنظیمات](#fa-config) · ۱۰. [داده، حریم خصوصی، حقوق نشر](#fa-data) · ۱۱. [اجرای ۲۴ ساعته](#fa-247) · ۱۲. [عیب‌یابی](#fa-trouble) · ۱۳. [ساختار پروژه و تست](#fa-dev)

<a id="fa-features"></a>
## ۱. امکانات
- **مقالهٔ کامل**: کل متن (اگر طولانی بود در چند پیام) و **همهٔ عکس‌ها** به ترتیب مقاله. اگر فید متن کامل بدهد همان استفاده می‌شود، وگرنه صفحهٔ خبر دانلود و بدنهٔ مقاله جدا می‌شود (منو، تبلیغ، نظرات و مطالب مرتبط حذف می‌شوند).
- **ترجمه به فارسی** تکه‌تکه با شش سرویس و جایگزینی خودکار. **ترتیب در کانال: سربرگ ← کل متن اصلی (با عکس‌ها) ← کل ترجمهٔ فارسی.**
- **سازگار با محدودیت سرویس‌ها**: پیش‌فرض **هر سرویس هر یک دقیقه یک درخواست ترجمه**؛ بعد از ۴۲۹ فاصله خودکار بیشتر می‌شود و `Retry-After` رعایت می‌شود؛ عنوان همراه تکهٔ اول ترجمه می‌شود (یک درخواست کمتر برای هر خبر).
- **دوره فقط وقتی تمام می‌شود که صف کاملاً خالی باشد**؛ ساعت دورهٔ بعد بعد از خالی شدن صف شروع می‌شود و هیچ پیامی در صف نمی‌ماند.
- **قابل ازسرگیری**: هر تکهٔ ترجمه‌شده و هر پیام ارسال‌شده ذخیره می‌شود؛ قطعی نه تکرار می‌سازد نه چیزی را گم می‌کند.
- **دسته‌بندی و منبع دلخواه**: آدرس سایت را بدهید؛ فید RSS/Atom خودکار پیدا و بررسی می‌شود.
- **کنترل از بله**: منوی دکمه‌ای برای همهٔ بخش‌های داشبورد (شروع/توقف، ارسال، منابع، دسته‌ها، منبع دستی، ترجمه، فیلتر، پروکسی، دیتابیس، تست‌ها، گزارش).
- **داشبورد**: تب‌ها، وضعیت و گزارش زنده، سلامت منابع، ۱۲ تم رنگی (صورتی، قرمز، آبی، … و تیره)، رابط فارسی راست‌به‌چپ.
- **دیتابیس کوچک**: هر خبر پس از ارسال کامل حذف می‌شود؛ فقط یک اثرانگشت ۲۰ حرفی می‌ماند (خودکار پاک می‌شود).
- **اتصال خودترمیم به بله**: هر درخواست با اتصال تازه انجام می‌شود (بدون keep-alive کهنه) و وقتی بله جواب ندهد ربات **پینگ می‌گیرد** (۳، ۵، ۱۰، ۱۵، ۲۰، ۳۰ ثانیه …)، می‌گوید مشکل از بله است یا از اینترنت، و به‌محض جواب دادن بله **همان خبر را ادامه می‌دهد** — چیزی تکراری یا گم نمی‌شود.
- **سرورهای ترجمه خودکار عوض می‌شوند**: سرویس خراب یا محدود با مکث فزاینده کنار می‌رود، سرویس بعدی جایش را می‌گیرد و **تا وقتی سالم است همان می‌ماند**؛ هر تغییر در گزارش زنده و در نوار سلامت سرویس‌ها دیده می‌شود.
- **دریافت پایدار منابع**: ۳ تلاش با User-Agentهای مختلف، تلاش دوباره برای اتصال نیمه‌کاره، منابع خراب با فاصلهٔ فزاینده دوباره امتحان می‌شوند، پروکسی (HTTP/SOCKS) جداگانه برای منابع/ترجمه و برای بله.

<a id="fa-cycle"></a>
## ۲. چرخهٔ کار
```
شروع دورهٔ N ──► بررسی همهٔ منابع ──► خبرهای جدید وارد صف می‌شوند
                                          │
                  ┌───────────────────────┘
                  ▼
        همهٔ خبرهای صف (بدون سقف در هر دوره)
          ۱. ساخت خبر (متن کامل، عکس‌ها)
          ۲. اگر ترجمه لازم است: تکه‌تکه ترجمه (هر «فاصله» یک تکه)، نتیجه ذخیره می‌شود
          ۳. ارسال: سربرگ ← کل متن اصلی (+عکس‌ها) ← کل ترجمهٔ فارسی ← لینک
          ۴. حذف خبر از دیتابیس
        خبری که ترجمه‌اش موقتاً ممکن نیست کنار می‌رود و بقیه ادامه می‌یابند
                  │
                  ▼
        صف خالی است؟ ──نه──► ادامه (دورهٔ جدید شروع نمی‌شود)
                  │بله
                  ▼
        صبر «interval_minutes» دقیقه (ساعت دقیق در داشبورد) ──► دورهٔ N+1
```
اگر ترجمه تا `translate_give_up_min` دقیقه (پیش‌فرض ۳۰) ممکن نشود، متن اصلی با نشانهٔ «ترجمه ممکن نشد» ارسال می‌شود تا صف تمام شود (۰ = هرگز انصراف نده).

<a id="fa-start"></a>
## ۳. شروع سریع
پیش‌نیاز: Python 3.9 به بالا و اینترنت.

| سیستم | اجرا |
|---|---|
| ویندوز | دوبار کلیک روی `start_windows.bat` |
| لینوکس / مک | `chmod +x start_linux_mac.sh && ./start_linux_mac.sh` |
| دستی | `python -m venv .venv` ← `.venv/bin/pip install -r requirements.txt` ← `.venv/bin/python run.py` |
| سرور (بدون داشبورد) | `python run.py --headless` |

داشبورد در `http://127.0.0.1:8765` باز می‌شود (فقط روی همین کامپیوتر). گزینه‌ها: `--port 9000`، `--no-browser`، `--headless`.

<a id="fa-bale"></a>
## ۴. ساخت ربات و کانال
۱. در بله (یا `web.bale.ai`) چت **@botfather** را باز کنید، `/newbot` بفرستید، نام و نام کاربری (معمولاً به `bot` ختم می‌شود) بدهید و **توکن** را کپی کنید.
۲. یک **کانال عمومی** با آیدی مثل `my_sec_feed` بسازید (لینک `ble.ir/my_sec_feed`).
۳. کانال ← مدیران ← افزودن ربات ← اجازهٔ **ارسال پیام**.
۴. در داشبورد (تب «اتصال به بله») توکن و `@my_sec_feed` را بنویسید، **تست** و بعد **شروع** را بزنید.

کانال خصوصی؟ از شناسهٔ عددی استفاده کنید (دکمهٔ «پیدا کردن شناسهٔ عددی» بسته به بله ممکن است کار نکند).

<a id="fa-dash"></a>
## ۵. داشبورد
تب‌ها: **اتصال به بله · نحوهٔ ارسال · منابع و دسته‌بندی · ترجمه · فیلتر · پیشرفته · کنترل از بله · گزارش زنده**. نوار بالا: وضعیت، 🎨 تم، ذخیره، شروع، توقف، اجرای فوری. کارت‌ها: وضعیت، آخرین دوره، **دورهٔ بعد (ساعت دقیق)**، صف، ترجمه، کل ارسال‌شده، حجم دیتابیس. کنار هر ورودی راهنمای «چی بنویسم / از کجا بگیرم» هست.

<a id="fa-botui"></a>
## ۶. کنترل از داخل بله
همهٔ بخش‌های داشبورد (به‌جز تم رنگی) در بله با دکمه در دسترس است.

۱. داشبورد ← تب «کنترل از بله» ← **کد ادمین** را کپی کنید.
۲. در بله **ربات خودتان** را باز کنید، **Start** بزنید و `/login کد` بفرستید. پیام حاوی کد حذف می‌شود و منو می‌آید.
۳. از دکمه‌ها استفاده کنید. دستورها: `/menu` (منو)، `/cancel` (لغو ورودی)، `/login کد`. میان‌برهای متنی که بدون دکمه هم کار می‌کنند: `/status`، `/logs`، `/start_bot`، `/stop_bot`، `/run`. فرستادن فقط خودِ کد هم شما را وارد می‌کند.

ترد کنترل همیشه روشن است (اگر توکن را بعداً در داشبورد ذخیره کنید خودش شروع می‌کند). تب «کنترل از بله» در داشبورد تعداد دریافت‌ها، آخرین زمان دریافت و آخرین رویدادها را نشان می‌دهد — اگر بعد از `/login` آنجا چیزی نیامد، ربات پیام‌های بله را دریافت نمی‌کند (پینگ، `bale_proxy` و این‌که با همان رباتِ توکن تنظیم‌شده چت می‌کنید را بررسی کنید).

نقشهٔ منو: **وضعیت · گزارش · شروع/توقف/اجرای فوری · اتصال** (آیدی کانال، تست) **· ارسال** (متن کامل، عکس‌ها، بازه، مکث‌ها، سن خبر، سقف عکس، خلاصه) **· منابع** (فعال/غیرفعال کردن هر منبع آماده با صفحه‌بندی، همه/هیچ، دسته‌های من، ساخت دسته، افزودن منبع دستی از آدرس سایت، جابه‌جایی/حذف، تست منابع) **· ترجمه** (سوئیچ‌ها، سرویس، اندازهٔ تکه، فاصله، زمان انصراف، کلیدها/آدرس‌ها، تست) **· فیلتر · پیشرفته** (پروکسی‌ها، آدرس API، نگه‌داری، خالی کردن صف/دیتابیس، خروج).

امنیت: فقط ادمین‌های واردشده و فقط در چت خصوصی پذیرفته می‌شوند؛ کد اشتباه محدود می‌شود (۵ بار در ۱۰ دقیقه)؛ کلیدهای API که می‌فرستید بعد از خوانده شدن از چت حذف می‌شوند؛ در داشبورد می‌توانید ادمین‌ها را حذف یا کد را عوض کنید. کد را به کسی ندهید.

<a id="fa-translate"></a>
## ۷. ترجمه
| سرویس | کلید | نکته |
|---|---|---|
| `edge` (پیش‌فرض) | ندارد | مترجم Microsoft Edge؛ توکن را خودش می‌گیرد؛ غیررسمی. |
| `google` | ندارد | آدرس غیررسمی؛ روی IPهای مشترک/VPN اغلب HTTP 429 می‌دهد. |
| `lingva` | ندارد | رابط متن‌باز گوگل؛ چند سرور عمومی به‌نوبت. |
| `mymemory` | ایمیل اختیاری | سهمیهٔ روزانهٔ کم؛ بیشتر پشتیبان. |
| `libretranslate` | آدرس (+کلید) | سرور شخصی: `docker run -ti --rm -p 5000:5000 libretranslate/libretranslate`. |
| `google_cloud` | کلید API | رسمی؛ نیازمند پروژهٔ گوگل کلود با حساب پرداخت (سهمیهٔ رایگان ماهانه؛ قیمت را از گوگل بررسی کنید). |

رفتار: متن به تکه‌ها (`translate_chunk_chars`، پیش‌فرض ۲۵۰۰) بریده می‌شود؛ هر سرویس حداکثر هر `translate_delay_sec` (پیش‌فرض ۶۰ ثانیه) یک درخواست می‌گیرد؛ خطا باعث مکث فزایندهٔ سرویس (۳۰ ثانیه تا ۱۰ دقیقه) و امتحان سرویس بعدی می‌شود؛ رعایت فاصله «خطا» حساب نمی‌شود. ترجمه از `fetch_proxy` استفاده می‌کند. فقط متن مقاله‌های عمومی به سرویس فرستاده می‌شود. ترجمهٔ ماشینی همیشه دقیق نیست؛ برای همین متن اصلی اول می‌آید.

<a id="fa-sources"></a>
## ۸. منابع و دسته‌بندی
منابع آماده (36 مورد؛ ✓ = در اولین اجرا فعال). آدرس فیدها ممکن است تغییر کند؛ با «تست منابع» بررسی و جایگزین را به‌صورت منبع دستی اضافه کنید.

| منبع | دسته | فید | پیش‌فرض |
|---|---|---|---|
| The Hacker News | اخبار امنیتی | `https://feeds.feedburner.com/TheHackersNews` | ✓ |
| BleepingComputer | اخبار امنیتی | `https://www.bleepingcomputer.com/feed/` | ✓ |
| Krebs on Security | اخبار امنیتی | `https://krebsonsecurity.com/feed/` | ✓ |
| SecurityWeek | اخبار امنیتی | `https://feeds.feedburner.com/securityweek` | ✓ |
| The Record (Recorded Future News) | اخبار امنیتی | `https://therecord.media/feed` | ✓ |
| Dark Reading | اخبار امنیتی | `https://www.darkreading.com/rss.xml` |  |
| Security Affairs | اخبار امنیتی | `https://securityaffairs.com/feed` |  |
| Help Net Security | اخبار امنیتی | `https://www.helpnetsecurity.com/feed/` |  |
| Ars Technica - Security | اخبار امنیتی | `https://arstechnica.com/security/feed/` |  |
| CyberScoop | اخبار امنیتی | `https://cyberscoop.com/feed/` |  |
| Schneier on Security | اخبار امنیتی | `https://www.schneier.com/feed/atom/` |  |
| Graham Cluley | اخبار امنیتی | `https://grahamcluley.com/feed/` |  |
| Troy Hunt | اخبار امنیتی | `https://www.troyhunt.com/rss/` |  |
| CISA - Cybersecurity Advisories | هشدارها و آسیب‌پذیری‌های رسمی | `https://www.cisa.gov/cybersecurity-advisories/all.xml` | ✓ |
| NCSC UK | هشدارها و آسیب‌پذیری‌های رسمی | `https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml` |  |
| Microsoft MSRC - Update Guide | هشدارها و آسیب‌پذیری‌های رسمی | `https://api.msrc.microsoft.com/update-guide/rss` |  |
| Zero Day Initiative - Published Advisories | هشدارها و آسیب‌پذیری‌های رسمی | `https://www.zerodayinitiative.com/rss/published/` |  |
| Exploit-DB | هشدارها و آسیب‌پذیری‌های رسمی | `https://www.exploit-db.com/rss.xml` |  |
| SANS Internet Storm Center | گزارش‌های پژوهشی و رصد تهدید | `https://isc.sans.edu/rssfeed.xml` | ✓ |
| Cisco Talos | گزارش‌های پژوهشی و رصد تهدید | `https://blog.talosintelligence.com/rss/` | ✓ |
| Palo Alto Unit 42 | گزارش‌های پژوهشی و رصد تهدید | `https://unit42.paloaltonetworks.com/feed/` | ✓ |
| Kaspersky Securelist | گزارش‌های پژوهشی و رصد تهدید | `https://securelist.com/feed/` | ✓ |
| ESET WeLiveSecurity | گزارش‌های پژوهشی و رصد تهدید | `https://www.welivesecurity.com/en/rss/feed/` |  |
| Microsoft Security Blog | گزارش‌های پژوهشی و رصد تهدید | `https://www.microsoft.com/en-us/security/blog/feed/` |  |
| Google Project Zero | گزارش‌های پژوهشی و رصد تهدید | `https://googleprojectzero.blogspot.com/feeds/posts/default` |  |
| Check Point Research | گزارش‌های پژوهشی و رصد تهدید | `https://research.checkpoint.com/feed/` |  |
| Sophos News | گزارش‌های پژوهشی و رصد تهدید | `https://news.sophos.com/en-us/feed/` |  |
| Malwarebytes Labs | گزارش‌های پژوهشی و رصد تهدید | `https://www.malwarebytes.com/blog/feed/index.xml` |  |
| Elastic Security Labs | گزارش‌های پژوهشی و رصد تهدید | `https://www.elastic.co/security-labs/rss/feed.xml` |  |
| Citizen Lab | گزارش‌های پژوهشی و رصد تهدید | `https://citizenlab.ca/feed/` |  |
| Cloudflare Blog | شبکه، اینترنت و ناهنجاری‌های رصدی | `https://blog.cloudflare.com/rss/` | ✓ |
| APNIC Blog | شبکه، اینترنت و ناهنجاری‌های رصدی | `https://blog.apnic.net/feed/` | ✓ |
| OONI (سنجش سانسور و اختلال) | شبکه، اینترنت و ناهنجاری‌های رصدی | `https://ooni.org/post/index.xml` | ✓ |
| Kentik Blog (تحلیل قطعی‌ها) | شبکه، اینترنت و ناهنجاری‌های رصدی | `https://www.kentik.com/blog/feed/` |  |
| Internet Society | شبکه، اینترنت و ناهنجاری‌های رصدی | `https://www.internetsociety.org/feed/` |  |
| Tor Project Blog | شبکه، اینترنت و ناهنجاری‌های رصدی | `https://blog.torproject.org/rss.xml` |  |

**دستهٔ دلخواه**: نام + ایموجی؛ در پست نام دسته و هشتگ می‌آید (مثل `#تهدیدات_ایران`). **منبع دلخواه**: آدرس سایت یا فید را بدهید؛ فید (از تگ `<link rel=alternate>` یا مسیرهای رایج مثل `/feed` و `/rss.xml`) پیدا، بررسی و به دستهٔ انتخابی اضافه می‌شود. برای سایت‌های بدون فید از ابزارهایی مثل RSSHub یا RSS-Bridge کمک بگیرید.

<a id="fa-config"></a>
## ۹. مرجع تنظیمات
در `data/config.json` (بار اول ساخته می‌شود) ذخیره می‌شود؛ معمولاً از داشبورد یا بله ویرایش کنید.

| کلید | معنی |
|---|---|
| `bale_token` | توکن ربات از @botfather (فقط از داشبورد). |
| `channel_id` | کانال مقصد: `@id` یا لینک `ble.ir/…` یا شناسهٔ عددی. |
| `bale_api_base` | آدرس پایهٔ API بله. |
| `interval_minutes` | دقیقه‌ای که **بعد از خالی شدن کامل صف** تا دورهٔ بعد صبر می‌شود. |
| `delay_between_posts_sec` | مکث بین دو خبر (محدودیت نرخ بله). |
| `max_age_hours` | خبرهای قدیمی‌تر از این نادیده گرفته می‌شوند. |
| `full_text` | متن کامل مقاله (در صورت طولانی بودن چند پیام)؛ خاموش = فقط خلاصه. |
| `summary_chars` | طول خلاصه وقتی `full_text` خاموش است (۰ = فقط عنوان و لینک). |
| `send_images` | تصویر شاخص و همهٔ عکس‌های مقاله به ترتیب. |
| `max_images` | سقف عکس در هر خبر (۰ = نامحدود). |
| `skip_backlog_first_run` | در اولین اجرا مطالب موجود فقط «دیده‌شده» ثبت می‌شوند. |
| `selected_sources` | شناسهٔ منابع آمادهٔ فعال. |
| `custom_categories` | دسته‌بندی‌های خودتان (`id`، `name`، `emoji`). |
| `custom_feeds` | منابع دستی شما (`name`، `url`، `category`). |
| `translate_enabled` | ترجمهٔ خبرهای غیرفارسی به فارسی. |
| `translate_provider` | سرویس اصلی ترجمه: `edge` (پیش‌فرض)، `google`، `lingva`، `mymemory`، `libretranslate`، `google_cloud`. |
| `translate_body` | متن کامل هم ترجمه شود (خاموش = فقط عنوان). |
| `translate_show_original` | عنوان اصلی زیر عنوان فارسی نمایش داده شود. |
| `translate_original_body` | اول کل متن اصلی، سپس کل ترجمهٔ فارسی. |
| `translate_chunk_chars` | اندازهٔ هر تکهٔ ترجمه (۳۰۰ تا ۳۰۰۰). |
| `translate_delay_sec` | حداقل ثانیه بین دو درخواست ترجمه به یک سرویس (پیش‌فرض ۶۰ = هر دقیقه یک تکه). |
| `translate_give_up_min` | اگر ترجمهٔ یک خبر این‌قدر ممکن نشد، متن اصلی با نشانه ارسال می‌شود (۰ = هرگز). |
| `lingva_url` | یک یا چند سرور Lingva با ویرگول (به‌نوبت). |
| `libretranslate_url / _key` | سرور LibreTranslate و کلید اختیاری. |
| `google_api_key` | کلید API رسمی Google Cloud Translation. |
| `mymemory_email` | ایمیل اختیاری برای بالا رفتن سهمیهٔ MyMemory. |
| `include_keywords / exclude_keywords` | فیلتر کلمات کلیدی روی عنوان و خلاصه. |
| `fetch_proxy` | پروکسی دریافت منابع، مقاله‌ها، عکس‌ها و ترجمه. |
| `bale_proxy` | پروکسی فقط برای ارتباط با بله. |
| `seen_retention_days` | روزهای نگه‌داری اثرانگشت‌های ضدتکرار. |
| `auto_start` | شروع خودکار ربات با اجرای برنامه. |
| `bot_control` | اجازهٔ کنترل از داخل بله (فقط ادمین‌ها). |
| `admin_code / admins` | کد ورود و ادمین‌های واردشدهٔ بله. |
| `panel_port` | درگاه داشبورد (پیش‌فرض ۸۷۶۵). |

<a id="fa-data"></a>
## ۱۰. داده، حریم خصوصی، حقوق نشر
- فایل `data/config.json` شامل **توکن و کلیدهای API** است؛ آن را به کسی ندهید و در گیت نگذارید. `data/bot.db` صف (خبرهای در انتظار ارسال با متنشان) و اثرانگشت‌های کوچک ضدتکرار را نگه می‌دارد؛ خبر بلافاصله پس از ارسال کامل حذف می‌شود؛ عکس‌ها هرگز روی دیسک ذخیره نمی‌شوند.
- داشبورد فقط روی `127.0.0.1` گوش می‌دهد و هر درخواستش یک رمز تصادفیِ هر اجرا لازم دارد؛ کنترل از بله فقط ادمین‌های واردشده را می‌پذیرد.
- ترجمه متن مقاله‌های عمومی را به سرویس انتخابی می‌فرستد؛ هیچ اطلاعاتی از شما یا توکنتان نه. اگر مهم است، ترجمه را خاموش یا LibreTranslate شخصی راه‌اندازی کنید.
- گذاشتن متن کامل مقاله‌ها در **کانال خصوصی برای مطالعهٔ شخصی** رایج است؛ بازنشر عمومی متن کامل سایت‌های دیگر ممکن است با حقوق نشر/شرایط آن‌ها در تعارض باشد. اگر کانال عمومی است یا برای دیگران می‌گذارید `full_text` را خاموش کنید (فقط خلاصه + لینک). نام منبع و لینک همیشه ذکر می‌شود.

<a id="fa-247"></a>
## ۱۱. اجرای ۲۴ ساعته
- **ویندوز**: پنجرهٔ `start_windows.bat` باز بماند؛ برای شروع با ویندوز یک میان‌بر در `shell:startup` بگذارید.
- **لینوکس (systemd)**: فایل سرویس مثال بخش انگلیسی (۱۱) را استفاده کنید؛ یک‌بار با داشبورد (یا کپی `data/config.json`) تنظیم کنید و بعد از بله کنترل کنید. برای داشبورد روی سرور از تونل SSH استفاده کنید: `ssh -L 8765:127.0.0.1:8765 user@server`.

<a id="fa-trouble"></a>
## ۱۲. عیب‌یابی
| علامت | علت / راه‌حل |
|---|---|
| «توکن نامعتبر» / «اجازه ندارد» / «کانال پیدا نشد» | توکن را دوباره کپی کنید؛ ربات را **ادمین با اجازهٔ ارسال** کنید؛ آیدی کانال را بررسی کنید. |
| اتصال به بله برقرار نمی‌شود | اینترنت را بررسی کنید؛ `bale_proxy` را بگذارید (مثلاً اجرا خارج از ایران). |
| منابع زیادی ناموفق‌اند (۴۰۳ / timeout / اتصال) | سایت‌ها از شبکهٔ شما بسته‌اند یا ضدربات دارند: `fetch_proxy` (VPN/پروکسی) را بگذارید و منابع مرده را غیرفعال کنید (تب «گزارش زنده» ← یک کلیک). منابع ناموفق با فاصلهٔ فزاینده دوباره امتحان می‌شوند. |
| HTTP 429 در ترجمه | IP شما محدود شده: `edge` را اصلی نگه دارید، `translate_delay_sec` را زیاد کنید، پروکسی با IP دیگر بگذارید، یا LibreTranslate شخصی/Google Cloud. |
| ارسال کند است | طراحی همین است: هر دقیقه یک تکهٔ ترجمه. اگر سرویس اجازه می‌دهد `translate_delay_sec` را کم یا اندازهٔ تکه را زیاد کنید، یا ترجمهٔ متن کامل را خاموش کنید. |
| دورهٔ بعد شروع نمی‌شود | فقط وقتی صف خالی شود شروع می‌شود. «گزارش زنده» را برای خبرهای مسدود ببینید؛ `translate_give_up_min` آن‌ها را تمام می‌کند. |
| منوی بله جواب نمی‌دهد | تب «کنترل از بله» را در داشبورد ببینید: باید «آماده» باشد؛ شمارنده‌ها و رویدادها نشان می‌دهند پیام می‌رسد یا نه. `bot_control` را بررسی کنید، دکمهٔ 🏓 پینگ (تب اتصال) را بزنید، در صورت نیاز `bale_proxy` بگذارید، مطمئن شوید با **همان رباتِ توکن** چت می‌کنید، و `/login کد` (یا `/start کد` یا فقط خودِ کد) را بفرستید. |
| «ارسال موقتاً متوقف شد، ۶۰ ثانیه دیگر» با اینکه اینترنت/پروکسی سالم است | در نسخهٔ ۱٫۵ رفع شد: keep-alive کهنه حذف شد و ربات به‌جای صبر کورکورانه بله را پینگ می‌کند و همان خبر را بلافاصله ادامه می‌دهد. گزارش زنده می‌گوید مشکل از بله، پروکسی یا اینترنت است. |
| فقط خلاصه می‌آید | صفحهٔ مقاله پولی/ضدربات یا غیرقابل دسترس است — `fetch_proxy` را امتحان کنید. |

<a id="fa-dev"></a>
## ۱۳. ساختار پروژه و تست
```
run.py                 نقطهٔ شروع (داشبورد + ربات، یا --headless)
app/worker.py          موتور: دوره‌ها، صف، مرحلهٔ ترجمه، ارسال، سلامت منابع
app/composer.py        ساخت خبر: سربرگ، متن کامل، عکس‌ها، اصل-سپس-فارسی
app/article.py         استخراج مقاله، پیدا کردن فید
app/translate.py       سرویس‌ها، فاصله‌گذاری، مکث فزاینده، Retry-After
app/botui.py           کنترل از بله (منوی دکمه‌ای، ورود ادمین)
app/bale.py            کلاینت API بله       app/fetcher.py  فیدها، عکس‌ها، قالب پیام
app/db.py              صف و ضدتکرار (SQLite)  app/config.py   تنظیمات
app/panel.py           سرور داشبورد          app/web/        صفحهٔ داشبورد + فونت وزیرمتن
```
کد به‌صورت سرتاسری با سرورهای شبیه‌سازی‌شدهٔ بله/فید/مترجم تست شده است (چرخهٔ کار، فاصلهٔ ترجمه، جایگزینی سرویس‌ها، ازسرگیری، منوهای بله). با سرورهای **واقعی** بله و سرویس‌های ترجمه از محیط ساخت **راستی‌آزمایی نشده**؛ روی سیستم خودتان از دکمه‌های «تست» استفاده کنید. آدرس‌های غیررسمی (Google، Edge، Lingva) ممکن است هر زمان تغییر کنند.

قدردانی: فونت وزیرمتن (مجوز SIL OFL، فایل `app/web/fonts/OFL.txt`).

</div>
