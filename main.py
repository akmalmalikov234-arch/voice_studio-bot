import os, sys, subprocess

def _need(mod, pkg):
    try:
        __import__(mod)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

for _m, _p in [("telegram", "python-telegram-bot==21.6"), ("edge_tts", "edge-tts"),
               ("speech_recognition", "SpeechRecognition"),
               ("imageio_ffmpeg", "imageio-ffmpeg"), ("flask", "flask")]:
    _need(_m, _p)

import re, math, time, html, shutil, sqlite3, asyncio, tempfile, threading, logging, json, hmac, hashlib, urllib.parse, io
from telegram import (Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M,
                      ReplyKeyboardMarkup, KeyboardButton, WebAppInfo)
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)
from telegram.error import TimedOut, NetworkError, BadRequest, RetryAfter
import edge_tts
import speech_recognition as sr
import imageio_ffmpeg
from flask import Flask, request, jsonify, send_file

# ============ SOZLAMALAR (shu 4 tasini to'ldiring) ============
TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # asosiy admin ID
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
CARD_OWNER = os.getenv("CARD_OWNER", "")
# ==============================================================

TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
CARD_OWNER = os.getenv("CARD_OWNER", "")

# Render / Mini App
APP_URL = os.getenv("APP_URL", "").strip().rstrip("/")
if not APP_URL:
    APP_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
WEB_APP_PATH = "/app"
WEB_APP_URL = f"{APP_URL}{WEB_APP_PATH}" if APP_URL else ""
WEBAPP_MAX_AGE = int(os.getenv("WEBAPP_MAX_AGE", "86400"))

logging.basicConfig(level=logging.INFO)
PAGE = 6     # foydalanuvchi til ro'yxati
APAGE = 8    # admin ro'yxatlari

DEFAULT_LANGS = [
 ("uz", "🇺🇿 O'zbek", "uz-UZ", [("Madina", "uz-UZ-MadinaNeural"), ("Sardor", "uz-UZ-SardorNeural")]),
 ("ru", "🇷🇺 Rus", "ru-RU", [("Svetlana", "ru-RU-SvetlanaNeural"), ("Dmitry", "ru-RU-DmitryNeural")]),
 ("en", "🇬🇧 Ingliz", "en-US", [("Jenny", "en-US-JennyNeural"), ("Guy", "en-US-GuyNeural"), ("Aria", "en-US-AriaNeural")]),
 ("kk", "🇰🇿 Qozoq", "kk-KZ", [("Aigul", "kk-KZ-AigulNeural"), ("Daulet", "kk-KZ-DauletNeural")]),
 ("az", "🇦🇿 Ozarbayjon", "az-AZ", [("Banu", "az-AZ-BanuNeural"), ("Babek", "az-AZ-BabekNeural")]),
 ("tr", "🇹🇷 Turk", "tr-TR", [("Emel", "tr-TR-EmelNeural"), ("Ahmet", "tr-TR-AhmetNeural")]),
 ("ka", "🇬🇪 Gruzin", "ka-GE", [("Eka", "ka-GE-EkaNeural"), ("Giorgi", "ka-GE-GiorgiNeural")]),
 ("uk", "🇺🇦 Ukrain", "uk-UA", [("Polina", "uk-UA-PolinaNeural"), ("Ostap", "uk-UA-OstapNeural")]),
 ("zh", "🇨🇳 Xitoy", "zh-CN", [("Xiaoxiao", "zh-CN-XiaoxiaoNeural"), ("Yunxi", "zh-CN-YunxiNeural")]),
 ("ja", "🇯🇵 Yapon", "ja-JP", [("Nanami", "ja-JP-NanamiNeural"), ("Keita", "ja-JP-KeitaNeural")]),
 ("ko", "🇰🇷 Koreys", "ko-KR", [("SunHi", "ko-KR-SunHiNeural"), ("InJoon", "ko-KR-InJoonNeural")]),
 ("vi", "🇻🇳 Vetnam", "vi-VN", [("HoaiMy", "vi-VN-HoaiMyNeural"), ("NamMinh", "vi-VN-NamMinhNeural")]),
 ("th", "🇹🇭 Tay", "th-TH", [("Premwadee", "th-TH-PremwadeeNeural"), ("Niwat", "th-TH-NiwatNeural")]),
 ("hi", "🇮🇳 Hind", "hi-IN", [("Swara", "hi-IN-SwaraNeural"), ("Madhur", "hi-IN-MadhurNeural")]),
 ("bn", "🇧🇩 Bengal", "bn-IN", [("Tanishaa", "bn-IN-TanishaaNeural"), ("Bashkar", "bn-IN-BashkarNeural")]),
 ("ur", "🇵🇰 Urdu", "ur-PK", [("Uzma", "ur-PK-UzmaNeural"), ("Asad", "ur-PK-AsadNeural")]),
 ("fa", "🇮🇷 Fors", "fa-IR", [("Dilara", "fa-IR-DilaraNeural"), ("Farid", "fa-IR-FaridNeural")]),
 ("ar", "🇸🇦 Arab", "ar-SA", [("Zariyah", "ar-SA-ZariyahNeural"), ("Hamed", "ar-SA-HamedNeural")]),
 ("de", "🇩🇪 Nemis", "de-DE", [("Katja", "de-DE-KatjaNeural"), ("Conrad", "de-DE-ConradNeural")]),
 ("fr", "🇫🇷 Fransuz", "fr-FR", [("Denise", "fr-FR-DeniseNeural"), ("Henri", "fr-FR-HenriNeural")]),
 ("es", "🇪🇸 Ispan", "es-ES", [("Elvira", "es-ES-ElviraNeural"), ("Alvaro", "es-ES-AlvaroNeural")]),
 ("it", "🇮🇹 Italyan", "it-IT", [("Elsa", "it-IT-ElsaNeural"), ("Diego", "it-IT-DiegoNeural")]),
]

# ---------------- DB ----------------
db = sqlite3.connect("bot.db", check_same_thread=False)
db.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0,
  lang TEXT DEFAULT 'uz', voice INTEGER DEFAULT 0, ref_by INTEGER, refs INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,
  uid INTEGER, amount INTEGER, status TEXT DEFAULT 'wait');
CREATE TABLE IF NOT EXISTS cfg(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS channels(chat_id INTEGER PRIMARY KEY, title TEXT, link TEXT);
CREATE TABLE IF NOT EXISTS langs(code TEXT PRIMARY KEY, name TEXT, stt TEXT DEFAULT '',
  active INTEGER DEFAULT 1, pos INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS voices(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, name TEXT, edge TEXT);
""")
for _col in ("banned INTEGER DEFAULT 0", "uname TEXT", "stt_lang TEXT DEFAULT 'uz'", "joined INTEGER DEFAULT 0"):
    try:
        db.execute("ALTER TABLE users ADD COLUMN " + _col)
    except sqlite3.OperationalError:
        pass
if not db.execute("SELECT 1 FROM langs").fetchone():
    for _i, (_code, _name, _stt, _vs) in enumerate(DEFAULT_LANGS):
        db.execute("INSERT INTO langs(code,name,stt,pos) VALUES(?,?,?,?)", (_code, _name, _stt, _i))
        for _vn, _ev in _vs:
            db.execute("INSERT INTO voices(code,name,edge) VALUES(?,?,?)", (_code, _vn, _ev))
db.commit()

CFG = {k: v for k, v in db.execute("SELECT k,v FROM cfg")}
ADMINS = {r[0] for r in db.execute("SELECT id FROM admins")}
DEF = {"tts_price": "0.3", "stt_sec": "5", "start_bonus": "2000", "ref_bonus": "500",
       "min_topup": "1000", "max_tts": "3000", "amounts": "10000,25000,50000,100000",
       "bot_on": "1", "card_number": CARD_NUMBER, "card_owner": CARD_OWNER}
SETS = {
 "tts_price": ("TTS narxi (so'm/belgi)", "num"),
 "stt_sec": ("STT narxi (so'm/soniya)", "num"),
 "start_bonus": ("Yangi foydalanuvchi bonusi", "int"),
 "ref_bonus": ("Do'st taklif bonusi", "int"),
 "min_topup": ("Minimal to'ldirish summasi", "int"),
 "max_tts": ("TTS maksimal belgi soni", "int"),
 "amounts": ("To'ldirish tugmalari (vergul bilan)", "amounts"),
 "card_number": ("Karta raqami", "str"),
 "card_owner": ("Karta egasi", "str"),
}

def S(k): return CFG.get(k, DEF[k])
def Sf(k): return float(S(k))
def Si(k): return int(float(S(k)))

def set_cfg(k, v):
    CFG[k] = v
    db.execute("INSERT OR REPLACE INTO cfg(k,v) VALUES(?,?)", (k, v)); db.commit()

def del_cfg(k):
    CFG.pop(k, None)
    db.execute("DELETE FROM cfg WHERE k=?", (k,)); db.commit()

def one(sql, args=()):
    r = db.execute(sql, args).fetchone()
    return r[0] if r else 0

def is_admin(uid): return uid == ADMIN_ID or uid in ADMINS
def admin_ids(): return {ADMIN_ID} | ADMINS
def fmt(n): return f"{int(n):,}".replace(",", " ")

# ---------------- matnlar (hammasini adminda o'zgartirish mumkin) ----------------
_T = [
 ("btn_stt", "Menyu: ovoz→matn tugmasi", "", "🎙 Ovozni matnga o'tkazish"),
 ("btn_tts", "Menyu: matn→ovoz tugmasi", "", "🔊 Matnni ovozga o'tkazish"),
 ("btn_bal", "Menyu: balans tugmasi", "", "💰 Balans"),
 ("btn_top", "Menyu: to'ldirish tugmasi", "", "💳 Balansni to'ldirish"),
 ("btn_ref", "Menyu: taklif tugmasi", "", "👥 Do'stlarni taklif qilish"),
 ("welcome", "Boshlang'ich xabar (/start)", "{name}", "👋 Xush kelibsiz, {name}! Quyidagi menyudan tanlang."),
 ("menu_hint", "Tushunarsiz xabarga javob", "", "Menyudan tanlang 👇"),
 ("stt_ready", "Ovoz→matn tayyor xabari", "{lang}", "✅ Men tayyor! Ovozli xabar yuboring.\n\n🌐 Til: {lang}"),
 ("tts_ready", "Matn→ovoz tayyor xabari", "{voice}", "✅ Men tayyor! Ovozga aylantirish uchun matn yuboring.\n\n👤 Joriy ovoz: {voice}"),
 ("btn_lang", "Tugma: tilni o'zgartirish", "", "🌐 Tilni o'zgartirish"),
 ("btn_voice", "Tugma: ovozni o'zgartirish", "", "Ovozni o'zgartirish"),
 ("balance", "Balans xabari", "{bal} {stt} {tts}",
  "💰 Balansingiz\n\n📌 Joriy balans: {bal} UZS\n\n📝 Narxlar:\n• STT: {stt} so'm/daqiqa (soniyalar bo'yicha hisoblash)\n• TTS: {tts} so'm/belgi"),
 ("ref", "Taklif xabari", "{bonus} {link} {n}",
  "👥 Do'stlaringizni taklif qiling!\nHar bir do'st uchun {bonus} so'm bonus.\n\n🔗 Havolangiz:\n{link}\n\n👤 Taklif qilinganlar: {n}"),
 ("topup", "To'ldirish: summa tanlash", "{bal}", "💳 Balansni to'ldirish\n💰 Joriy balans: {bal} UZS\n\nSummani tanlang:"),
 ("btn_amount", "Tugma: summa", "{amount}", "{amount} so'm"),
 ("btn_other", "Tugma: boshqa summa", "", "✍️ Boshqa summa"),
 ("ask_amount", "Boshqa summa so'rovi", "", "✍️ Necha so'm to'ldirmoqchisiz? Summani yozing:"),
 ("bad_amount", "Noto'g'ri summa", "{min}", "❗ Summani raqamda yozing (kamida {min} so'm)."),
 ("pay_info", "To'lov ma'lumoti (HTML: <b> <code>)", "{amount} {card} {owner}",
  "💳 To'lov: {amount} so'm\n\nQuyidagi kartaga o'tkazing:\n\n💳 <code>{card}</code>\n👤 {owner}\n\n✅ To'lovdan so'ng <b>chek rasmini</b> shu yerga yuboring."),
 ("send_chek", "Chek so'rash eslatmasi", "", "📎 Iltimos, to'lov chekini rasm qilib yuboring."),
 ("chek_sent", "Chek yuborildi", "", "✅ Chek adminga yuborildi. Tasdiqlangach balansingiz to'ldiriladi."),
 ("chek_fail", "Chek yuborilmadi", "", "❗ Chek adminga yetib bormadi. Keyinroq qayta urinib ko'ring."),
 ("pay_ok", "To'lov tasdiqlandi", "{amount} {bal}", "✅ To'lov tasdiqlandi! Balansingizga {amount} so'm qo'shildi.\n💰 Balans: {bal} so'm"),
 ("pay_no", "To'lov rad etildi", "", "❌ To'lovingiz rad etildi. Muammo bo'lsa admin bilan bog'laning."),
 ("low_bal", "Balans yetarli emas", "{need} {bal}", "❗ Balans yetarli emas. Kerak: {need} so'm, sizda: {bal} so'm."),
 ("tts_confirm", "Aylantirish tasdiqi", "{voice} {lang} {n} {cost} {bal}",
  "🔊 Matnni ovozga aylantirish\n\n👤 Ovoz: {voice} ({lang})\n📝 {n} belgi\n💸 Taxminiy narx: ~{cost} so'm\n💰 Balans: {bal} so'm"),
 ("btn_convert", "Tugma: aylantirish", "", "✅ Aylantirish"),
 ("btn_cancel", "Tugma: bekor qilish", "", "❌ Bekor qilish"),
 ("cancelled", "Bekor qilindi", "", "❌ Bekor qilindi."),
 ("converting", "Ovozga aylantirilmoqda", "", "⏳ Ovozga aylantirilmoqda..."),
 ("tts_done", "Ovoz tayyor izohi", "{voice} {n} {cost} {bal}", "✅ Tayyor · {voice} · {n} belgi · {cost} so'm\n💰 Balans: {bal} so'm"),
 ("stt_wait", "Matnga aylantirilmoqda", "", "⏳ Matnga aylantirilmoqda..."),
 ("stt_done", "Matn tayyor xabari", "{text} {sec} {cost} {bal}", "📝 {text}\n\n✅ Tayyor · {sec} soniya · {cost} so'm\n💰 Balans: {bal} so'm"),
 ("stt_unknown", "Ovoz tushunilmadi", "", "❗ Ovoz tushunilmadi. Tilni to'g'ri tanlaganingizni tekshiring. Pul yechilmadi."),
 ("error", "Xatolik xabari", "", "❗ Xatolik yuz berdi. Pul yechilmadi."),
 ("pick_lang", "Til tanlash", "", "🌐 Tilni tanlang:"),
 ("pick_voice", "Ovoz tanlash", "{lang}", "{lang} — ovozni tanlang:"),
 ("lang_set", "Til tanlandi (STT)", "{lang}", "✅ Til tanlandi: {lang}\n\nOvozli xabar yuboring."),
 ("voice_set", "Ovoz tanlandi", "{voice}", "👤 Ovoz tanlandi: {voice}\n\nOvozga aylantirish uchun matn yuboring."),
 ("first_stt", "Avval tugmani bosing", "{btn}", "Avval «{btn}» tugmasini bosing."),
 ("no_text", "Matn topilmadi", "", "❗ Matn topilmadi, qaytadan yuboring."),
 ("no_langs", "Til/ovoz yo'q", "", "❗ Hozircha mavjud til yoki ovoz yo'q."),
 ("sub_required", "Majburiy obuna xabari", "", "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:"),
 ("btn_check", "Tugma: obunani tekshirish", "", "✅ Obunani tekshirish"),
 ("not_subscribed", "Obuna bo'lmagan", "", "❗ Hali hamma kanallarga obuna bo'lmadingiz."),
 ("banned", "Bloklangan foydalanuvchi", "", "🚫 Siz bloklangansiz."),
 ("maintenance", "Bot o'chiq xabari", "", "🛠 Bot vaqtincha o'chirilgan. Keyinroq urinib ko'ring."),
 ("btn_prev", "Tugma: oldingi", "", "⬅️ Oldingi"),
 ("btn_next", "Tugma: keyingi", "", "Keyingi ➡️"),
 ("bal_changed", "Admin balansni o'zgartirdi", "{bal}", "💰 Balansingiz yangilandi. Joriy balans: {bal} so'm"),
]
TEXTS = {k: (d, p, v) for k, d, p, v in _T}
MENU_KEYS = ["btn_stt", "btn_tts", "btn_bal", "btn_top", "btn_ref"]

def T(k, **kw):
    v = CFG.get("t:" + k, TEXTS[k][2])
    try:
        return v.format(**kw)
    except Exception:
        return TEXTS[k][2].format(**kw)

def menu_kb():
    rows = [[KeyboardButton(T("btn_stt"))],
            [KeyboardButton(T("btn_tts"))],
            [KeyboardButton(T("btn_bal")), KeyboardButton(T("btn_top"))],
            [KeyboardButton(T("btn_ref"))]]
    if WEB_APP_URL:
        rows.append([KeyboardButton("🚀 Mini App", web_app=WebAppInfo(url=WEB_APP_URL))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ---------------- foydalanuvchilar ----------------
def get_user(uid, ref=None):
    r = db.execute("SELECT balance,lang,voice,stt_lang,banned FROM users WHERE id=?", (uid,)).fetchone()
    if r is None:
        ref_ok = bool(ref) and ref != uid and db.execute("SELECT 1 FROM users WHERE id=?", (ref,)).fetchone() is not None
        bal = Si("start_bonus") + (Si("ref_bonus") if ref_ok else 0)
        db.execute("INSERT INTO users(id,balance,lang,stt_lang,ref_by,joined) VALUES(?,?,?,?,?,?)",
                   (uid, bal, "uz", "uz", ref if ref_ok else None, int(time.time())))
        if ref_ok:
            db.execute("UPDATE users SET balance=balance+?, refs=refs+1 WHERE id=?", (Si("ref_bonus"), ref))
        db.commit()
        r = (bal, "uz", 0, "uz", 0)
    return {"bal": r[0], "lang": r[1], "voice": r[2], "stt": r[3] or "uz", "banned": r[4] or 0}

def touch(us):
    get_user(us.id)
    un = us.username or ""
    cur = db.execute("UPDATE users SET uname=? WHERE id=? AND COALESCE(uname,'')!=?", (un, us.id, un))
    if cur.rowcount:
        db.commit()

def add_bal(uid, n):
    db.execute("UPDATE users SET balance=balance+? WHERE id=?", (n, uid)); db.commit()

# ---------------- tillar ----------------
def langs_stt():
    return db.execute("SELECT code,name,stt FROM langs WHERE active=1 AND stt!='' ORDER BY pos,rowid").fetchall()

def langs_tts():
    return db.execute("SELECT code,name FROM langs WHERE active=1 AND EXISTS "
                      "(SELECT 1 FROM voices v WHERE v.code=langs.code) ORDER BY pos,rowid").fetchall()

def lang_row(code):
    return db.execute("SELECT code,name,stt,active FROM langs WHERE code=?", (code,)).fetchone()

def voices_of(code):
    return db.execute("SELECT id,name,edge FROM voices WHERE code=? ORDER BY id", (code,)).fetchall()

def stt_choice(uid):
    rows = langs_stt()
    if not rows:
        return None
    code = get_user(uid)["stt"]
    return next((r for r in rows if r[0] == code), rows[0])   # (code, name, stt)

def tts_choice(uid):
    rows = langs_tts()
    if not rows:
        return None
    u = get_user(uid)
    row = next((r for r in rows if r[0] == u["lang"]), rows[0])
    vs = voices_of(row[0])
    v = next((x for x in vs if x[0] == u["voice"]), vs[0])
    return row[0], row[1], v[1], v[2]   # (code, lang name, voice name, edge voice)

def lang_pick_kb(page, kind):
    rows = langs_stt() if kind == "stt" else langs_tts()
    s = page * PAGE
    kb = [[B(r[1], callback_data=f"lang:{r[0]}")] for r in rows[s:s + PAGE]]
    nav = []
    if page > 0: nav.append(B(T("btn_prev"), callback_data=f"lp:{page-1}"))
    if s + PAGE < len(rows): nav.append(B(T("btn_next"), callback_data=f"lp:{page+1}"))
    if nav: kb.append(nav)
    return M(kb)

def voice_kb(code):
    return M([[B(n, callback_data=f"voice:{code}:{i}")] for i, n, _ in voices_of(code)])

# ---------------- majburiy obuna ----------------
SUBOK = {}

async def missing_subs(bot, uid):
    if SUBOK.get(uid, 0) > time.time():
        return []
    miss = []
    for cid, title, link in db.execute("SELECT chat_id,title,link FROM channels").fetchall():
        try:
            m = await bot.get_chat_member(cid, uid)
            if m.status in ("left", "kicked"):
                miss.append((title or str(cid), link))
        except Exception as e:
            logging.warning("Obuna tekshiruvi xato (%s): %s", cid, e)
    if not miss:
        SUBOK[uid] = time.time() + 30
    return miss

async def gate(u, c):
    uid = u.effective_user.id
    if is_admin(uid):
        return True
    m = u.effective_message
    if get_user(uid)["banned"]:
        await m.reply_text(T("banned")); return False
    if S("bot_on") != "1":
        await m.reply_text(T("maintenance")); return False
    miss = await missing_subs(c.bot, uid)
    if miss:
        rows = [[B(f"📢 {t}", url=l)] for t, l in miss]
        rows.append([B(T("btn_check"), callback_data="chk")])
        await m.reply_text(T("sub_required"), reply_markup=M(rows))
        return False
    return True

# ---------------- foydalanuvchi handlerlari ----------------
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    us = u.effective_user
    ref = None
    if c.args and c.args[0].startswith("ref_"):
        try: ref = int(c.args[0][4:])
        except ValueError: pass
    get_user(us.id, ref)
    touch(us)
    c.user_data.clear()
    if not await gate(u, c):
        return
    await u.message.reply_text(T("welcome", name=us.first_name or ""), reply_markup=menu_kb())

async def cancel_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data.clear()
    await u.message.reply_text("❌ Bekor qilindi.", reply_markup=menu_kb())

async def text_h(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    t = u.message.text.strip()
    ud = c.user_data

    if t == T("btn_stt"):
        ud["mode"] = "stt"
        ch = stt_choice(uid)
        if not ch:
            await u.message.reply_text(T("no_langs")); return
        await u.message.reply_text(T("stt_ready", lang=ch[1]),
            reply_markup=M([[B(T("btn_lang"), callback_data="stt_lang")]]))
    elif t == T("btn_tts"):
        ud["mode"] = "tts"
        ch = tts_choice(uid)
        if not ch:
            await u.message.reply_text(T("no_langs")); return
        await u.message.reply_text(T("tts_ready", voice=ch[2]),
            reply_markup=M([[B(T("btn_voice"), callback_data="chg")]]))
    elif t == T("btn_bal"):
        bal = get_user(uid)["bal"]
        await u.message.reply_text(
            T("balance", bal=fmt(bal), stt=fmt(round(Sf("stt_sec") * 60)), tts=f"{Sf('tts_price'):g}"),
            reply_markup=M([[B(T("btn_top"), callback_data="top")]]))
    elif t == T("btn_top"):
        await show_topup(u.message, uid)
    elif t == T("btn_ref"):
        me = await c.bot.get_me()
        n = one("SELECT refs FROM users WHERE id=?", (uid,))
        await u.message.reply_text(T("ref", bonus=fmt(Si("ref_bonus")),
                                     link=f"https://t.me/{me.username}?start=ref_{uid}", n=n))
    elif ud.get("mode") == "tts":
        await tts_confirm(u, c, t)
    elif ud.get("mode") == "amount":
        digits = "".join(ch for ch in t if ch.isdigit())
        if not digits or int(digits) < Si("min_topup"):
            await u.message.reply_text(T("bad_amount", min=fmt(Si("min_topup"))))
            return
        await ask_receipt(u.message, c, int(digits))
    elif ud.get("mode") == "chek":
        await u.message.reply_text(T("send_chek"))
    else:
        await u.message.reply_text(T("menu_hint"), reply_markup=menu_kb())

async def show_topup(msg, uid):
    bal = get_user(uid)["bal"]
    amts = [int(x) for x in S("amounts").split(",") if x.strip()]
    rows = []
    for i in range(0, len(amts), 2):
        rows.append([B(T("btn_amount", amount=fmt(a)), callback_data=f"amt:{a}") for a in amts[i:i + 2]])
    rows.append([B(T("btn_other"), callback_data="amt:other")])
    await msg.reply_text(T("topup", bal=fmt(bal)), reply_markup=M(rows))

async def ask_receipt(msg, c, amount):
    c.user_data["mode"] = "chek"
    c.user_data["amount"] = amount
    txt = T("pay_info", amount=fmt(amount), card=html.escape(S("card_number")), owner=html.escape(S("card_owner")))
    try:
        await msg.reply_text(txt, parse_mode="HTML")
    except BadRequest:
        await msg.reply_text(re.sub(r"<[^>]+>", "", txt))

def tts_cost(text):
    return max(1, math.ceil(len(text) * Sf("tts_price")))

async def tts_confirm(u, c, text):
    uid = u.effective_user.id
    text = text[:Si("max_tts")]
    ch = tts_choice(uid)
    if not ch:
        await u.message.reply_text(T("no_langs")); return
    cost = tts_cost(text)
    bal = get_user(uid)["bal"]
    if bal < cost:
        await u.message.reply_text(T("low_bal", need=cost, bal=bal),
            reply_markup=M([[B(T("btn_top"), callback_data="top")]]))
        return
    c.user_data["text"] = text
    await u.message.reply_text(
        T("tts_confirm", voice=ch[2], lang=ch[1], n=len(text), cost=cost, bal=fmt(bal)),
        reply_markup=M([[B(T("btn_convert"), callback_data="tts_go")],
                        [B(T("btn_voice"), callback_data="chg"),
                         B(T("btn_cancel"), callback_data="tts_cancel")]]))

async def voice_h(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if c.user_data.get("mode") != "stt":
        await u.message.reply_text(T("first_stt", btn=T("btn_stt")), reply_markup=menu_kb())
        return
    ch = stt_choice(uid)
    if not ch:
        await u.message.reply_text(T("no_langs")); return
    scode = ch[2]
    f = u.message.voice or u.message.audio
    dur = int(f.duration or 1)
    cost = max(1, math.ceil(dur * Sf("stt_sec")))
    bal = get_user(uid)["bal"]
    if bal < cost:
        await u.message.reply_text(T("low_bal", need=cost, bal=bal),
            reply_markup=M([[B(T("btn_top"), callback_data="top")]]))
        return
    add_bal(uid, -cost)
    wait = await u.message.reply_text(T("stt_wait"))
    tmp = tempfile.mkdtemp()
    src, wav = os.path.join(tmp, "a.ogg"), os.path.join(tmp, "a.wav")
    try:
        tg = await c.bot.get_file(f.file_id)
        await tg.download_to_drive(src)
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        def work():
            subprocess.run([ff, "-y", "-i", src, "-ar", "16000", "-ac", "1", wav],
                           check=True, capture_output=True)
            r = sr.Recognizer()
            with sr.AudioFile(wav) as s:
                audio = r.record(s)
            return r.recognize_google(audio, language=scode)
        text = await asyncio.get_running_loop().run_in_executor(None, work)
        nb = get_user(uid)["bal"]
        await wait.edit_text(T("stt_done", text=text, sec=dur, cost=cost, bal=fmt(nb)))
    except sr.UnknownValueError:
        add_bal(uid, cost)
        await wait.edit_text(T("stt_unknown"))
    except Exception as e:
        logging.exception(e)
        add_bal(uid, cost)
        await wait.edit_text(T("error"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

async def photo_h(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    m = u.message
    if c.user_data.get("mode") != "chek":
        await m.reply_text(T("menu_hint"), reply_markup=menu_kb())
        return
    amount = c.user_data.get("amount", 0)
    cur = db.execute("INSERT INTO payments(uid,amount) VALUES(?,?)", (uid, amount))
    pid = cur.lastrowid; db.commit()
    us = u.effective_user
    cap = (f"💳 Yangi to'lov #{pid}\n👤 {us.full_name} (@{us.username or '-'})\n🆔 {uid}\n"
           f"💵 Summa: {fmt(amount)} so'm")
    kb = M([[B("✅ Tasdiqlash", callback_data=f"pok:{pid}"), B("❌ Rad etish", callback_data=f"pno:{pid}")]])
    sent = 0
    for aid in admin_ids():
        try:
            if m.photo:
                await c.bot.send_photo(aid, m.photo[-1].file_id, caption=cap, reply_markup=kb)
            else:
                await c.bot.send_document(aid, m.document.file_id, caption=cap, reply_markup=kb)
            sent += 1
        except Exception as e:
            logging.warning("Adminga chek yuborilmadi (%s): %s", aid, e)
    if not sent:
        db.execute("DELETE FROM payments WHERE id=?", (pid,)); db.commit()
        await m.reply_text(T("chek_fail"))
        return
    c.user_data.clear()
    await m.reply_text(T("chek_sent"), reply_markup=menu_kb())

async def cb(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    uid = q.from_user.id
    d = q.data
    touch(q.from_user)

    # --- to'lovni tasdiqlash (adminlar) ---
    if d.startswith(("pok:", "pno:")):
        if not is_admin(uid):
            await q.answer(); return
        pid = int(d[4:])
        ok = d.startswith("pok:")
        cur = db.execute("UPDATE payments SET status=? WHERE id=? AND status='wait'",
                         ("ok" if ok else "no", pid))
        db.commit()
        if cur.rowcount == 0:
            await q.answer("Allaqachon ko'rib chiqilgan", show_alert=True)
            try: await q.edit_message_reply_markup(None)
            except Exception: pass
            return
        await q.answer()
        row = db.execute("SELECT uid,amount FROM payments WHERE id=?", (pid,)).fetchone()
        if ok:
            add_bal(row[0], row[1])
            msg = T("pay_ok", amount=fmt(row[1]), bal=fmt(get_user(row[0])["bal"]))
        else:
            msg = T("pay_no")
        try: await c.bot.send_message(row[0], msg)
        except Exception as e: logging.warning("Userga xabar ketmadi: %s", e)
        mark = "✅ TASDIQLANDI" if ok else "❌ RAD ETILDI"
        await q.edit_message_caption(caption=(q.message.caption or "") + f"\n\n{mark} — {q.from_user.full_name}")
        return

    # --- obunani tekshirish ---
    if d == "chk":
        SUBOK.pop(uid, None)
        miss = [] if is_admin(uid) else await missing_subs(c.bot, uid)
        if miss:
            await q.answer(T("not_subscribed"), show_alert=True); return
        await q.answer()
        try: await q.message.delete()
        except Exception: pass
        await c.bot.send_message(uid, T("welcome", name=q.from_user.first_name or ""), reply_markup=menu_kb())
        return

    await q.answer()

    if d.startswith("a:"):
        if is_admin(uid):
            await admin_cb(u, c, q, d)
        return

    if not await gate(u, c):
        return

    if d in ("chg", "stt_lang"):
        kind = "stt" if d == "stt_lang" else "tts"
        c.user_data["pick"] = kind
        await q.message.reply_text(T("pick_lang"), reply_markup=lang_pick_kb(0, kind))
    elif d.startswith("lp:"):
        await q.edit_message_reply_markup(lang_pick_kb(int(d[3:]), c.user_data.get("pick", "tts")))
    elif d.startswith("lang:"):
        k = d[5:]
        r = lang_row(k)
        if not r:
            return
        if c.user_data.get("pick") == "stt":
            db.execute("UPDATE users SET stt_lang=? WHERE id=?", (k, uid)); db.commit()
            c.user_data["mode"] = "stt"
            await q.edit_message_text(T("lang_set", lang=r[1]))
        else:
            await q.edit_message_text(T("pick_voice", lang=r[1]), reply_markup=voice_kb(k))
    elif d.startswith("voice:"):
        _, k, i = d.split(":")
        v = db.execute("SELECT name FROM voices WHERE id=? AND code=?", (int(i), k)).fetchone()
        if not v:
            return
        db.execute("UPDATE users SET lang=?, voice=? WHERE id=?", (k, int(i), uid)); db.commit()
        c.user_data["mode"] = "tts"
        await q.edit_message_text(T("voice_set", voice=v[0]))
    elif d == "top":
        await show_topup(q.message, uid)
    elif d.startswith("amt:"):
        v = d[4:]
        if v == "other":
            c.user_data["mode"] = "amount"
            await q.message.reply_text(T("ask_amount"))
        else:
            await ask_receipt(q.message, c, int(v))
    elif d == "tts_cancel":
        c.user_data.pop("text", None)
        await q.edit_message_text(T("cancelled"))
    elif d == "tts_go":
        text = c.user_data.pop("text", None)
        if not text:
            await q.edit_message_text(T("no_text")); return
        ch = tts_choice(uid)
        if not ch:
            await q.edit_message_text(T("no_langs")); return
        cost = tts_cost(text)
        bal = get_user(uid)["bal"]
        if bal < cost:
            await q.edit_message_text(T("low_bal", need=cost, bal=bal)); return
        add_bal(uid, -cost)
        await q.edit_message_text(T("converting"))
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "v.mp3")
        try:
            await edge_tts.Communicate(text, ch[3]).save(path)
            nb = get_user(uid)["bal"]
            with open(path, "rb") as fh:
                await q.message.reply_voice(
                    fh, caption=T("tts_done", voice=ch[2], n=len(text), cost=cost, bal=fmt(nb)))
        except Exception as e:
            logging.exception(e)
            add_bal(uid, cost)
            await q.message.reply_text(T("error"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

# ---------------- ADMIN PANEL ----------------
def panel_kb():
    on = S("bot_on") == "1"
    return M([
        [B("📊 Statistika", callback_data="a:stat"), B("👥 Foydalanuvchi", callback_data="a:usr")],
        [B("🌐 Tillar/ovozlar", callback_data="a:lang:0"), B("📢 Majburiy obuna", callback_data="a:sub")],
        [B("✏️ Matnlar/tugmalar", callback_data="a:txt:0"), B("⚙️ Narx/bonus/karta", callback_data="a:set")],
        [B("📨 Xabar yuborish", callback_data="a:bc"), B("💳 To'lovlar", callback_data="a:pay")],
        [B("👮 Adminlar", callback_data="a:adm"), B("🤖 Bot: YOQIQ ✅" if on else "🤖 Bot: O'CHIQ 🚫", callback_data="a:bot")],
    ])

HOME = [[B("⬅️ Panel", callback_data="a:home")]]
TASKS = set()
EDGE = {"names": None}

async def show(q, text, kb=None):
    try:
        await q.edit_message_text(text, reply_markup=kb)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            await q.message.reply_text(text, reply_markup=kb)

def user_card(uid):
    r = db.execute("SELECT balance,refs,banned,uname FROM users WHERE id=?", (uid,)).fetchone()
    if not r:
        return "❗ Foydalanuvchi topilmadi.", M(HOME)
    ban = "ha 🚫" if r[2] else "yo'q"
    t = (f"👤 ID: {uid}\n🔗 @{r[3] or '-'}\n💰 Balans: {fmt(r[0])} so'm\n"
         f"👥 Takliflar: {r[1]}\n⛔ Bloklangan: {ban}")
    k = M([[B("➕ Qo'shish", callback_data=f"a:u:{uid}:add"), B("➖ Ayirish", callback_data=f"a:u:{uid}:sub")],
           [B("✏️ O'rnatish", callback_data=f"a:u:{uid}:set"), B("💬 Xabar", callback_data=f"a:u:{uid}:msg")],
           [B("✅ Blokdan chiqarish" if r[2] else "🚫 Bloklash", callback_data=f"a:u:{uid}:ban")],
           [B("⬅️ Panel", callback_data="a:home")]])
    return t, k

async def show_langs(q, page):
    rows = db.execute("SELECT code,name,stt,active FROM langs ORDER BY pos,rowid").fetchall()
    s = page * APAGE
    kb = []
    for code, name, stt, act in rows[s:s + APAGE]:
        kb.append([B(name, callback_data=f"a:vl:{code}"),
                   B("✅" if act else "🚫", callback_data=f"a:lt:{code}:{page}"),
                   B("🗑", callback_data=f"a:ld:{code}:{page}")])
    nav = []
    if page > 0: nav.append(B("⬅️", callback_data=f"a:lang:{page-1}"))
    if s + APAGE < len(rows): nav.append(B("➡️", callback_data=f"a:lang:{page+1}"))
    if nav: kb.append(nav)
    kb.append([B("➕ Til qo'shish", callback_data="a:la"), B("➕ Ovoz qo'shish", callback_data="a:va")])
    kb += HOME
    await show(q, f"🌐 Tillar ({len(rows)} ta)\n✅ yoqiq · 🚫 o'chiq · 🗑 o'chirish\nTil nomini bossangiz ovozlari ochiladi.", M(kb))

async def admin_cb(u, c, q, d):
    p = d.split(":")
    a = p[1]
    ud = c.user_data
    uid = q.from_user.id

    if a == "home":
        ud.pop("adm", None)
        await show(q, "🛠 Admin panel\nKerakli bo'limni tanlang:", panel_kb())

    elif a == "stat":
        now = int(time.time())
        txt = (f"📊 Statistika\n\n👥 Foydalanuvchilar: {one('SELECT COUNT(*) FROM users')}\n"
               f"🆕 24 soatda qo'shilgan: {one('SELECT COUNT(*) FROM users WHERE joined>?', (now - 86400,))}\n"
               f"🚫 Bloklangan: {one('SELECT COUNT(*) FROM users WHERE banned=1')}\n"
               f"💰 Userlar balansi jami: {fmt(one('SELECT COALESCE(SUM(balance),0) FROM users'))} so'm\n"
               f"💵 Tasdiqlangan to'lovlar: {fmt(one(chr(83)+'ELECT COALESCE(SUM(amount),0) FROM payments WHERE status=' + chr(39) + 'ok' + chr(39)))} so'm\n"
               f"⏳ Kutilayotgan to'lovlar: {one('SELECT COUNT(*) FROM payments WHERE status=' + chr(39) + 'wait' + chr(39))}\n"
               f"📢 Majburiy kanallar: {one('SELECT COUNT(*) FROM channels')}\n"
               f"🌐 Tillar: {one('SELECT COUNT(*) FROM langs')}")
        await show(q, txt, M(HOME))

    elif a == "bot":
        set_cfg("bot_on", "0" if S("bot_on") == "1" else "1")
        await show(q, "🛠 Admin panel\nKerakli bo'limni tanlang:", panel_kb())

    # ----- foydalanuvchi -----
    elif a == "usr":
        ud["adm"] = {"act": "usr_find"}
        await show(q, "👥 Foydalanuvchi ID raqamini yoki @username ini yuboring:", M(HOME))
    elif a == "u":
        target, op = int(p[2]), p[3]
        if op in ("add", "sub", "set", "msg"):
            ud["adm"] = {"act": "usr_msg" if op == "msg" else "bal_" + op, "uid": target}
            prompts = {"add": "➕ Qancha so'm qo'shilsin? Raqam yuboring:",
                       "sub": "➖ Qancha so'm ayirilsin? Raqam yuboring:",
                       "set": "✏️ Yangi balansni (so'm) yuboring:",
                       "msg": "💬 Foydalanuvchiga yuboriladigan xabarni yuboring:"}
            await show(q, prompts[op], M(HOME))
        elif op == "ban":
            if target != ADMIN_ID:
                db.execute("UPDATE users SET banned=1-COALESCE(banned,0) WHERE id=?", (target,)); db.commit()
            t, k = user_card(target)
            await show(q, t, k)

    # ----- tillar -----
    elif a == "lang":
        await show_langs(q, int(p[2]))
    elif a == "lt":
        db.execute("UPDATE langs SET active=1-active WHERE code=?", (p[2],)); db.commit()
        await show_langs(q, int(p[3]))
    elif a == "ld":
        await show(q, f"🗑 «{p[2]}» tili va uning hamma ovozlari o'chirilsinmi?",
                   M([[B("✅ Ha", callback_data=f"a:ldy:{p[2]}:{p[3]}"), B("❌ Yo'q", callback_data=f"a:lang:{p[3]}")]]))
    elif a == "ldy":
        db.execute("DELETE FROM voices WHERE code=?", (p[2],))
        db.execute("DELETE FROM langs WHERE code=?", (p[2],)); db.commit()
        await show_langs(q, int(p[3]))
    elif a == "vl":
        code = p[2]
        r = lang_row(code)
        if not r:
            await show(q, "❗ Til topilmadi.", M(HOME)); return
        vs = voices_of(code)
        kb = [[B(f"🗣 {n} ({e})", callback_data="a:noop"), B("🗑", callback_data=f"a:vd:{i}:{code}")] for i, n, e in vs]
        kb.append([B("➕ Ovoz qo'shish", callback_data=f"a:va:{code}")])
        kb.append([B("⬅️ Tillar", callback_data="a:lang:0")])
        await show(q, f"{r[1]}\nKod: {code}\nSTT kodi: {r[2] or 'yoq'}\nOvozlar: {len(vs)} ta", M(kb))
    elif a == "vd":
        db.execute("DELETE FROM voices WHERE id=?", (int(p[2]),)); db.commit()
        q.data = f"a:vl:{p[3]}"
        await admin_cb(u, c, q, q.data)
    elif a == "la":
        ud["adm"] = {"act": "lang_add"}
        await show(q, "🌐 Til qo'shish yoki yangilash. Shu ko'rinishda yuboring:\n\n"
                      "kod | nomi | STT kodi\n\nMisol:\npt | 🇵🇹 Portugal | pt-PT\n\n"
                      "• STT (ovozdan matn) kerak bo'lmasa oxiriga - yozing\n"
                      "• Kod kichik harf/raqam (masalan pt)\n"
                      "• Mavjud kod yuborilsa nomi/STT kodi yangilanadi", M(HOME))
    elif a == "va":
        code = p[2] if len(p) > 2 else None
        ud["adm"] = {"act": "voice_add", "code": code}
        if code:
            await show(q, f"🗣 «{code}» tiliga ovoz qo'shish. Yuboring:\n\novoz nomi | edge ovoz\n\n"
                          "Misol:\nRaquel | pt-PT-RaquelNeural", M(HOME))
        else:
            await show(q, "🗣 Ovoz qo'shish. Yuboring:\n\ntil kodi | ovoz nomi | edge ovoz\n\n"
                          "Misol:\npt | Raquel | pt-PT-RaquelNeural\n\n"
                          "Ovoz nomi Microsoft Edge TTS ro'yxatidan tekshiriladi.", M(HOME))

    # ----- majburiy obuna -----
    elif a == "sub":
        rows = db.execute("SELECT chat_id,title,link FROM channels").fetchall()
        kb = [[B(t or str(i), url=l), B("🗑", callback_data=f"a:sd:{i}")] for i, t, l in rows]
        kb.append([B("➕ Kanal qo'shish", callback_data="a:sa")])
        kb += HOME
        await show(q, f"📢 Majburiy obuna ({len(rows)} ta)\nBot kanal/guruhda admin bo'lishi shart.", M(kb))
    elif a == "sa":
        ud["adm"] = {"act": "sub_add"}
        await show(q, "📢 Kanal/guruh @username yoki ID (-100...) yuboring, yoki kanaldan biror xabarni forward qiling.\n\n"
                      "Bot o'sha kanalda admin bo'lishi shart.", M([[B("⬅️ Orqaga", callback_data="a:sub")]]))
    elif a == "sd":
        db.execute("DELETE FROM channels WHERE chat_id=?", (int(p[2]),)); db.commit()
        SUBOK.clear()
        q.data = "a:sub"
        await admin_cb(u, c, q, q.data)

    # ----- matnlar -----
    elif a == "txt":
        page = int(p[2])
        keys = list(TEXTS)
        s = page * APAGE
        kb = [[B(("• " if "t:" + k in CFG else "") + TEXTS[k][0], callback_data=f"a:te:{k}")] for k in keys[s:s + APAGE]]
        nav = []
        if page > 0: nav.append(B("⬅️", callback_data=f"a:txt:{page-1}"))
        if s + APAGE < len(keys): nav.append(B("➡️", callback_data=f"a:txt:{page+1}"))
        if nav: kb.append(nav)
        kb += HOME
        await show(q, "✏️ Matnlar va tugmalar. O'zgartirmoqchi bo'lganingizni tanlang.\n(• belgisi — o'zgartirilgan)", M(kb))
    elif a == "te":
        k = p[2]
        ud["adm"] = {"act": "txt_edit", "key": k}
        cur = CFG.get("t:" + k, TEXTS[k][2])
        ph = TEXTS[k][1] or "yo'q"
        await show(q, f"✏️ {TEXTS[k][0]}\n\nHozirgi matn:\n{cur}\n\nO'zgaruvchilar: {ph}\n"
                      "(o'zgaruvchilarni {} bilan xuddi shunday yozing)\n\nYangi matnni yuboring:",
                   M([[B("♻️ Standartga qaytarish", callback_data=f"a:tr:{k}")],
                      [B("⬅️ Orqaga", callback_data="a:txt:0")]]))
    elif a == "tr":
        del_cfg("t:" + p[2])
        ud.pop("adm", None)
        q.data = "a:txt:0"
        await admin_cb(u, c, q, q.data)

    # ----- sozlamalar -----
    elif a == "set":
        rows = [[B(f"{SETS[k][0]}: {S(k)}", callback_data=f"a:se:{k}")] for k in SETS]
        await show(q, "⚙️ Sozlamalar. O'zgartirmoqchi bo'lganingizni bosing:", M(rows + HOME))
    elif a == "se":
        k = p[2]
        ud["adm"] = {"act": "set_edit", "key": k}
        hint = "vergul bilan raqamlar, masalan: 10000,25000,50000" if SETS[k][1] == "amounts" else ""
        await show(q, f"⚙️ {SETS[k][0]}\nHozirgi: {S(k)}\n{hint}\n\nYangi qiymatni yuboring:",
                   M([[B("⬅️ Orqaga", callback_data="a:set")]]))

    # ----- adminlar -----
    elif a == "adm":
        lines = [f"👑 {ADMIN_ID} (egasi)"] + [f"👮 {i}" for i in sorted(ADMINS)]
        rows = []
        if uid == ADMIN_ID:
            rows += [[B(f"🗑 {i}", callback_data=f"a:ad:{i}")] for i in sorted(ADMINS)]
            rows.append([B("➕ Admin qo'shish", callback_data="a:aa")])
        await show(q, "👮 Adminlar:\n" + "\n".join(lines), M(rows + HOME))
    elif a == "aa" and uid == ADMIN_ID:
        ud["adm"] = {"act": "adm_add"}
        await show(q, "👮 Yangi adminning Telegram ID raqamini yuboring.\n(U botga /start bosgan bo'lishi kerak)", M(HOME))
    elif a == "ad" and uid == ADMIN_ID:
        i = int(p[2])
        ADMINS.discard(i)
        db.execute("DELETE FROM admins WHERE id=?", (i,)); db.commit()
        q.data = "a:adm"
        await admin_cb(u, c, q, q.data)

    # ----- xabar yuborish -----
    elif a == "bc":
        ud["adm"] = {"act": "bc"}
        await show(q, "📨 Hammaga yuboriladigan xabarni yuboring (matn, rasm, video — hammasi bo'ladi):", M(HOME))
    elif a == "bcy":
        st = ud.get("adm")
        if not st or st.get("act") != "bc_confirm":
            return
        ud.pop("adm", None)
        await show(q, "⏳ Yuborilmoqda... Tugagach xabar beraman.")
        t = asyncio.create_task(broadcast(c.bot, st["cid"], st["mid"], q.from_user.id))
        TASKS.add(t); t.add_done_callback(TASKS.discard)
    elif a == "bcn":
        ud.pop("adm", None)
        await show(q, "❌ Bekor qilindi.", M(HOME))

    # ----- to'lovlar -----
    elif a == "pay":
        rows = db.execute("SELECT id,uid,amount,status FROM payments ORDER BY id DESC LIMIT 15").fetchall()
        icon = {"ok": "✅", "no": "❌", "wait": "⏳"}
        lines = [f"{icon.get(s, '')} #{i} · {u_} · {fmt(a_)} so'm" for i, u_, a_, s in rows] or ["Hozircha yo'q"]
        await show(q, "💳 Oxirgi to'lovlar:\n\n" + "\n".join(lines), M(HOME))

async def broadcast(bot, cid, mid, admin_id):
    ids = [r[0] for r in db.execute("SELECT id FROM users WHERE COALESCE(banned,0)=0")]
    ok = fail = 0
    for i in ids:
        try:
            await bot.copy_message(i, cid, mid); ok += 1
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try:
                await bot.copy_message(i, cid, mid); ok += 1
            except Exception:
                fail += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    try:
        await bot.send_message(admin_id, f"✅ Yuborish tugadi.\nYetkazildi: {ok}\nYetkazilmadi: {fail}")
    except Exception:
        pass

async def edge_ok(name):
    try:
        if EDGE["names"] is None:
            EDGE["names"] = {v["ShortName"] for v in await edge_tts.list_voices()}
        return name in EDGE["names"]
    except Exception:
        return True   # tarmoq xatosi bo'lsa tekshirmaymiz

async def admin_input(u, c):
    st = c.user_data.get("adm")
    if not st:
        return False
    act = st["act"]
    m = u.message
    txt = (m.text or "").strip()
    back = M(HOME)
    ud = c.user_data

    if act == "bc_confirm":
        return False

    if act == "usr_find":
        key = txt.lstrip("@")
        if key.isdigit():
            r = db.execute("SELECT id FROM users WHERE id=?", (int(key),)).fetchone()
        else:
            r = db.execute("SELECT id FROM users WHERE lower(uname)=lower(?)", (key,)).fetchone()
        if not r:
            await m.reply_text("❗ Topilmadi. Qayta yuboring yoki /admin.", reply_markup=back); return True
        ud.pop("adm", None)
        t, k = user_card(r[0])
        await m.reply_text(t, reply_markup=k)

    elif act in ("bal_add", "bal_sub", "bal_set"):
        try:
            n = int(txt.replace(" ", "").replace(",", ""))
            assert n >= 0
        except Exception:
            await m.reply_text("❗ Faqat musbat raqam yuboring.", reply_markup=back); return True
        target = st["uid"]
        old = one("SELECT balance FROM users WHERE id=?", (target,))
        new = old + n if act == "bal_add" else max(0, old - n) if act == "bal_sub" else n
        db.execute("UPDATE users SET balance=? WHERE id=?", (new, target)); db.commit()
        ud.pop("adm", None)
        try: await c.bot.send_message(target, T("bal_changed", bal=fmt(new)))
        except Exception: pass
        t, k = user_card(target)
        await m.reply_text(f"✅ Balans: {fmt(old)} → {fmt(new)} so'm\n\n" + t, reply_markup=k)

    elif act == "usr_msg":
        ud.pop("adm", None)
        try:
            await c.bot.copy_message(st["uid"], m.chat_id, m.message_id)
            await m.reply_text("✅ Yuborildi.", reply_markup=back)
        except Exception as e:
            await m.reply_text(f"❗ Yuborilmadi: {e}", reply_markup=back)

    elif act == "lang_add":
        parts = [x.strip() for x in txt.split("|")]
        if len(parts) < 2 or not re.fullmatch(r"[a-z0-9_-]{1,12}", parts[0].lower()) or not parts[1]:
            await m.reply_text("❗ Format: kod | nomi | STT kodi\nMisol: pt | 🇵🇹 Portugal | pt-PT", reply_markup=back); return True
        code, name = parts[0].lower(), parts[1]
        stt = parts[2] if len(parts) > 2 and parts[2] != "-" else ""
        if lang_row(code):
            db.execute("UPDATE langs SET name=?, stt=? WHERE code=?", (name, stt, code))
        else:
            pos = one("SELECT COALESCE(MAX(pos),0)+1 FROM langs")
            db.execute("INSERT INTO langs(code,name,stt,pos) VALUES(?,?,?,?)", (code, name, stt, pos))
        db.commit()
        ud.pop("adm", None)
        await m.reply_text(f"✅ Til saqlandi: {name}\nEndi unga ovoz qo'shing (TTS uchun).",
                           reply_markup=M([[B("➕ Ovoz qo'shish", callback_data=f"a:va:{code}")],
                                           [B("⬅️ Tillar", callback_data="a:lang:0")]]))

    elif act == "voice_add":
        parts = [x.strip() for x in txt.split("|")]
        if st.get("code"):
            parts = [st["code"]] + parts
        if len(parts) != 3 or not all(parts):
            await m.reply_text("❗ Format noto'g'ri. Qayta yuboring yoki /admin.", reply_markup=back); return True
        code, name, edge = parts[0].lower(), parts[1], parts[2]
        if not lang_row(code):
            await m.reply_text(f"❗ «{code}» tili topilmadi. Avval til qo'shing.", reply_markup=back); return True
        if not await edge_ok(edge):
            await m.reply_text(f"❗ «{edge}» degan ovoz Edge TTS'da yo'q. Nomini tekshiring.", reply_markup=back); return True
        db.execute("INSERT INTO voices(code,name,edge) VALUES(?,?,?)", (code, name, edge)); db.commit()
        ud.pop("adm", None)
        await m.reply_text(f"✅ Ovoz qo'shildi: {name}",
                           reply_markup=M([[B("⬅️ Ovozlar", callback_data=f"a:vl:{code}")]]))

    elif act == "sub_add":
        target = None
        fo = getattr(m, "forward_origin", None)
        if fo is not None and getattr(fo, "chat", None) is not None:
            target = fo.chat.id
        else:
            t = txt
            if "t.me/" in t:
                t = t.split("t.me/")[1].split("?")[0].strip("/")
                if t.startswith("+") or t.startswith("joinchat"):
                    await m.reply_text("❗ Yopiq havoladan kanalni aniqlab bo'lmaydi. Kanal ID sini (-100...) yuboring yoki kanaldan xabar forward qiling.", reply_markup=back)
                    return True
                t = "@" + t
            if t.lstrip("-").isdigit():
                target = int(t)
            elif t.startswith("@"):
                target = t
        if target is None:
            await m.reply_text("❗ @username, ID yoki forward xabar yuboring.", reply_markup=back); return True
        try:
            ch = await c.bot.get_chat(target)
            me = await c.bot.get_me()
            mem = await c.bot.get_chat_member(ch.id, me.id)
            if mem.status not in ("administrator", "creator"):
                await m.reply_text("❗ Bot bu kanalda admin emas. Avval botni admin qiling, keyin qayta yuboring.", reply_markup=back)
                return True
            link = f"https://t.me/{ch.username}" if ch.username else (ch.invite_link or await c.bot.export_chat_invite_link(ch.id))
            db.execute("INSERT OR REPLACE INTO channels(chat_id,title,link) VALUES(?,?,?)", (ch.id, ch.title or str(ch.id), link))
            db.commit()
            SUBOK.clear()
            ud.pop("adm", None)
            await m.reply_text(f"✅ Majburiy obunaga qo'shildi: {ch.title}", reply_markup=M([[B("📢 Ro'yxat", callback_data="a:sub")]]))
        except Exception as e:
            await m.reply_text(f"❗ Xato: {e}\nBot kanalda admin ekanini tekshiring.", reply_markup=back)

    elif act == "txt_edit":
        key = st["key"]
        if not m.text:
            await m.reply_text("❗ Matn yuboring.", reply_markup=back); return True
        new = m.text.strip() if key.startswith("btn_") else m.text
        ph = re.findall(r"\{(\w+)\}", TEXTS[key][1])
        try:
            new.format(**{x: "x" for x in ph})
        except Exception:
            await m.reply_text("❗ Matndagi {} belgilari noto'g'ri. Faqat ruxsat etilgan o'zgaruvchilarni ishlating: "
                               + (TEXTS[key][1] or "yo'q"), reply_markup=back)
            return True
        if key in MENU_KEYS and new in [T(k) for k in MENU_KEYS if k != key]:
            await m.reply_text("❗ Menyudagi tugmalar bir xil bo'lmasligi kerak.", reply_markup=back); return True
        set_cfg("t:" + key, new)
        ud.pop("adm", None)
        await m.reply_text("✅ Saqlandi." + (" Tugma yangi holatda ko'rinishi uchun user /start bosishi kerak." if key in MENU_KEYS else ""),
                           reply_markup=M([[B("✏️ Matnlar", callback_data="a:txt:0")], HOME[0][0:1]]))

    elif act == "set_edit":
        key = st["key"]
        kind = SETS[key][1]
        try:
            if kind == "num":
                v = float(txt.replace(",", "."))
                assert v >= 0
                val = str(int(v)) if v == int(v) else str(v)
            elif kind == "int":
                v = int(txt.replace(" ", ""))
                assert v >= 0
                val = str(v)
            elif kind == "amounts":
                nums = [int(x) for x in re.split(r"[,\s]+", txt) if x]
                assert 1 <= len(nums) <= 8 and all(n > 0 for n in nums)
                val = ",".join(str(n) for n in nums)
            else:
                assert txt
                val = txt
        except Exception:
            await m.reply_text("❗ Noto'g'ri qiymat. Qayta yuboring.", reply_markup=back); return True
        set_cfg(key, val)
        ud.pop("adm", None)
        await m.reply_text(f"✅ Saqlandi: {SETS[key][0]} = {val}", reply_markup=M([[B("⚙️ Sozlamalar", callback_data="a:set")]]))

    elif act == "adm_add":
        if u.effective_user.id != ADMIN_ID:
            return True
        try:
            i = int(txt)
        except ValueError:
            await m.reply_text("❗ Faqat ID raqam yuboring.", reply_markup=back); return True
        ADMINS.add(i)
        db.execute("INSERT OR IGNORE INTO admins(id) VALUES(?)", (i,)); db.commit()
        ud.pop("adm", None)
        try: await c.bot.send_message(i, "👮 Siz botga admin qilib tayinlandingiz. /admin buyrug'ini yuboring.")
        except Exception: pass
        await m.reply_text(f"✅ Admin qo'shildi: {i}", reply_markup=M([[B("👮 Adminlar", callback_data="a:adm")]]))

    elif act == "bc":
        n = one("SELECT COUNT(*) FROM users WHERE COALESCE(banned,0)=0")
        st.update({"act": "bc_confirm", "cid": m.chat_id, "mid": m.message_id})
        try:
            await m.reply_text("👆 Xabar shunday ko'rinadi.")
        except Exception:
            pass
        await m.reply_text(f"📨 {n} ta foydalanuvchiga yuborilsinmi?",
                           reply_markup=M([[B("✅ Yuborish", callback_data="a:bcy"), B("❌ Bekor", callback_data="a:bcn")]]))
    return True

async def admin_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not is_admin(u.effective_user.id):
        return
    c.user_data.pop("adm", None)
    await u.message.reply_text("🛠 Admin panel\nKerakli bo'limni tanlang:", reply_markup=panel_kb())

# ---------------- umumiy xabar yo'naltirgich ----------------
async def msg_h(u: Update, c: ContextTypes.DEFAULT_TYPE):
    m = u.message
    if not m:
        return
    us = u.effective_user
    touch(us)
    if is_admin(us.id) and c.user_data.get("adm"):
        if m.text and m.text in [T(k) for k in MENU_KEYS]:
            c.user_data.pop("adm", None)
        elif await admin_input(u, c):
            return
    if not await gate(u, c):
        return
    if m.voice or m.audio:
        await voice_h(u, c)
    elif m.photo or m.document:
        await photo_h(u, c)
    elif m.text:
        await text_h(u, c)

async def on_error(u, c):
    logging.error("Xato: %s", c.error)


# ---------------- Render + Telegram Mini App ----------------
WEB_APP_HTML = r"""<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>AI Voice Studio</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{
  --bg:var(--tg-theme-bg-color,#0b1020);
  --card:var(--tg-theme-secondary-bg-color,#151c31);
  --text:var(--tg-theme-text-color,#fff);
  --muted:var(--tg-theme-hint-color,#9aa6bf);
  --accent:var(--tg-theme-button-color,#4f7cff);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,Arial,sans-serif}
.wrap{max-width:620px;margin:auto;padding:18px 15px 34px}
.hero{padding:20px;border-radius:24px;background:linear-gradient(135deg,#17213b,#10172a);box-shadow:0 12px 35px #0003}
h1{margin:0 0 7px;font-size:27px}.sub{color:var(--muted);font-size:14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-top:14px}
.card{background:var(--card);border:1px solid #ffffff12;border-radius:18px;padding:16px}
button{width:100%;border:0;border-radius:15px;padding:14px 12px;background:var(--accent);color:#fff;font-weight:700;font-size:15px}
button.secondary{background:#ffffff12;color:var(--text)}
textarea{width:100%;min-height:150px;resize:vertical;background:var(--bg);color:var(--text);border:1px solid #ffffff18;border-radius:15px;padding:13px;font-size:15px;outline:none}
.row{display:flex;gap:9px}.row>*{flex:1}.stat{font-size:24px;font-weight:800}.muted{color:var(--muted);font-size:13px}
#status{margin-top:12px;color:var(--muted);min-height:20px}.hidden{display:none}
audio{width:100%;margin-top:12px}
</style>
</head>
<body>
<div class="wrap">
  <section class="hero">
    <h1>🎙 AI Voice Studio</h1>
    <div class="sub" id="hello">Telegram Mini App</div>
    <div class="grid">
      <div class="card"><div class="muted">Balans</div><div class="stat" id="bal">...</div></div>
      <div class="card"><div class="muted">Referallar</div><div class="stat" id="refs">...</div></div>
    </div>
  </section>

  <section class="card" style="margin-top:13px">
    <div style="font-weight:800;margin-bottom:10px">🔊 Matn → ovoz</div>
    <textarea id="text" maxlength="2000" placeholder="Matn yozing..."></textarea>
    <div class="row" style="margin-top:10px">
      <button onclick="tts()">Ovoz yaratish</button>
      <button class="secondary" onclick="clearText()">Tozalash</button>
    </div>
    <audio id="player" controls class="hidden"></audio>
  </section>

  <section class="card" style="margin-top:13px">
    <div style="font-weight:800;margin-bottom:10px">🎙 Ovoz → matn</div>
    <div class="row">
      <button onclick="startRecord()" id="rec">🎙 Yozishni boshlash</button>
      <button class="secondary" onclick="stopRecord()" id="stop" disabled>⏹ To‘xtatish</button>
    </div>
    <div id="sttResult" class="muted" style="margin-top:12px"></div>
  </section>

  <section class="grid">
    <div class="card"><div class="muted">Foydalanuvchi ID</div><div id="uid">...</div></div>
    <div class="card"><div class="muted">Til / Ovoz</div><div id="voice">...</div></div>
  </section>
  <div id="status"></div>
</div>
<script>
const tg=window.Telegram?.WebApp;
if(tg){tg.ready();tg.expand();}
let mediaRecorder=null,chunks=[];
const headers=()=>({'Content-Type':'application/json','X-Telegram-Init-Data':tg?.initData||''});
function status(x){document.getElementById('status').textContent=x||''}
async function api(path,opt={}){
  opt.headers={...(opt.headers||{}),...headers()};
  const r=await fetch(path,opt);
  const data=await r.json().catch(()=>({error:'Server javobi noto‘g‘ri'}));
  if(!r.ok) throw new Error(data.error||'Xatolik');
  return data;
}
async function load(){
  try{
    const d=await api('/api/me');
    document.getElementById('hello').textContent='Salom, '+(d.first_name||'foydalanuvchi')+' 👋';
    document.getElementById('bal').textContent=d.balance+' so‘m';
    document.getElementById('refs').textContent=d.refs;
    document.getElementById('uid').textContent=d.id;
    document.getElementById('voice').textContent=d.language+' · '+d.voice;
  }catch(e){status(e.message)}
}
async function tts(){
  const text=document.getElementById('text').value.trim();
  if(!text)return status('Avval matn yozing.');
  status('⏳ Ovoz tayyorlanmoqda...');
  try{
    const r=await fetch('/api/tts',{method:'POST',headers:headers(),body:JSON.stringify({text})});
    if(!r.ok){const e=await r.json().catch(()=>({error:'Xatolik'}));throw new Error(e.error)}
    const blob=await r.blob();
    const url=URL.createObjectURL(blob);
    const p=document.getElementById('player');p.src=url;p.classList.remove('hidden');p.play().catch(()=>{});
    status('✅ Tayyor.');
    load();
  }catch(e){status('❌ '+e.message)}
}
function clearText(){document.getElementById('text').value='';status('')}
async function startRecord(){
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    chunks=[];mediaRecorder=new MediaRecorder(stream);
    mediaRecorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
    mediaRecorder.onstop=async()=>{
      stream.getTracks().forEach(t=>t.stop());
      const blob=new Blob(chunks,{type:mediaRecorder.mimeType||'audio/webm'});
      const fd=new FormData();fd.append('audio',blob,'voice.webm');
      status('⏳ Ovoz matnga aylantirilmoqda...');
      try{
        const r=await fetch('/api/stt',{method:'POST',headers:{'X-Telegram-Init-Data':tg?.initData||''},body:fd});
        const d=await r.json();if(!r.ok)throw new Error(d.error||'STT xatosi');
        document.getElementById('sttResult').textContent='📝 '+d.text;
        status('✅ Tayyor.');
        load();
      }catch(e){status('❌ '+e.message)}
    };
    mediaRecorder.start();
    document.getElementById('rec').disabled=true;
    document.getElementById('stop').disabled=false;
    status('🔴 Yozilmoqda...');
  }catch(e){status('❌ Mikrofon ruxsati berilmadi.')}
}
function stopRecord(){
  if(mediaRecorder&&mediaRecorder.state!=='inactive')mediaRecorder.stop();
  document.getElementById('rec').disabled=false;
  document.getElementById('stop').disabled=true;
}
load();
</script>
</body>
</html>"""

flask_app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

def _webapp_user(init_data):
    """Telegram Mini App initData HMAC tekshiruvi."""
    if not init_data:
        raise ValueError("Telegram Mini App ichidan oching.")
    try:
        q = urllib.parse.parse_qs(init_data, strict_parsing=True)
        received = q.get("hash", [None])[0]
        if not received:
            raise ValueError("initData hash yo‘q.")
        pairs = []
        for key, vals in q.items():
            if key == "hash":
                continue
            pairs.append((key, vals[0]))
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs))
        secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        calculated = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated, received):
            raise ValueError("Telegram autentifikatsiyasi noto‘g‘ri.")
        auth_date = int(q.get("auth_date", ["0"])[0])
        if auth_date <= 0 or time.time() - auth_date > WEBAPP_MAX_AGE:
            raise ValueError("Sessiya eskirgan. Mini Appni qayta oching.")
        user_raw = q.get("user", ["{}"])[0]
        user = json.loads(user_raw)
        uid = int(user["id"])
        return uid, user
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        raise ValueError(str(e))

def _api_auth():
    uid, user = _webapp_user(request.headers.get("X-Telegram-Init-Data", ""))
    u = get_user(uid)
    if u["banned"]:
        raise ValueError("Hisob bloklangan.")
    return uid, user, u

@flask_app.route("/")
def health():
    return "OK — Telegram bot ishlayapti."

@flask_app.route("/app")
def mini_app():
    return WEB_APP_HTML

@flask_app.route("/api/me")
def api_me():
    try:
        uid, user, u = _api_auth()
        refs = int(one("SELECT refs FROM users WHERE id=?", (uid,)))
        ch = tts_choice(uid)
        return jsonify({
            "id": uid,
            "first_name": user.get("first_name", ""),
            "balance": int(u["bal"]),
            "refs": refs,
            "language": ch[1] if ch else "-",
            "voice": ch[2] if ch else "-"
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception:
        logging.exception("api_me")
        return jsonify({"error": "Server xatosi."}), 500

@flask_app.route("/api/tts", methods=["POST"])
def api_tts():
    try:
        uid, _, u = _api_auth()
        data = request.get_json(silent=True) or {}
        text_value = str(data.get("text", "")).strip()
        max_tts = Si("max_tts")
        if not text_value:
            return jsonify({"error": "Matn bo‘sh."}), 400
        if len(text_value) > max_tts:
            return jsonify({"error": f"Matn {max_tts} belgidan oshmasin."}), 400
        ch = tts_choice(uid)
        if not ch:
            return jsonify({"error": "Ovoz mavjud emas."}), 400
        cost = tts_cost(text_value)
        if int(u["bal"]) < cost:
            return jsonify({"error": f"Balans yetarli emas. Kerak: {cost} so‘m."}), 402

        tmp = tempfile.mkdtemp(prefix="mini_tts_")
        out = os.path.join(tmp, "voice.mp3")
        try:
            asyncio.run(edge_tts.Communicate(text_value, ch[3]).save(out))
            db.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",
                       (cost, uid, cost))
            if db.total_changes <= 0:
                raise ValueError("Balans o‘zgarmadi.")
            db.commit()
            return send_file(out, mimetype="audio/mpeg", as_attachment=False,
                             download_name="voice.mp3")
        except Exception:
            db.rollback()
            raise
        finally:
            # send_file faylni o‘qib bo‘lgach o‘chirish uchun delayed cleanup kerak;
            # Render uchun kichik vaqtinchalik faylni alohida daemon thread tozalaydi.
            def cleanup():
                time.sleep(8)
                shutil.rmtree(tmp, ignore_errors=True)
            threading.Thread(target=cleanup, daemon=True).start()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logging.exception("api_tts")
        return jsonify({"error": "Ovoz yaratishda server xatosi."}), 500

@flask_app.route("/api/stt", methods=["POST"])
def api_stt():
    tmp = None
    charged = False
    uid = None
    cost = 0
    try:
        uid, _, u = _api_auth()
        ch = stt_choice(uid)
        if not ch:
            return jsonify({"error": "STT tili mavjud emas."}), 400
        audio = request.files.get("audio")
        if not audio:
            return jsonify({"error": "Audio topilmadi."}), 400

        tmp = tempfile.mkdtemp(prefix="mini_stt_")
        src_file = os.path.join(tmp, "input.webm")
        wav = os.path.join(tmp, "input.wav")
        audio.save(src_file)

        ff = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ff, "-y", "-i", src_file, "-ar", "16000", "-ac", "1", wav],
                       check=True, capture_output=True)
        with sr.AudioFile(wav) as source:
            rec = sr.Recognizer()
            clip = rec.record(source)

        # Audio uzunligini WAV fayldan hisoblashga urinamiz.
        import wave
        with wave.open(wav, "rb") as wf:
            dur = max(1, math.ceil(wf.getnframes() / float(wf.getframerate())))
        cost = max(1, math.ceil(dur * Sf("stt_sec")))
        if int(u["bal"]) < cost:
            return jsonify({"error": f"Balans yetarli emas. Kerak: {cost} so‘m."}), 402

        db.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",
                   (cost, uid, cost))
        if db.total_changes <= 0:
            db.rollback()
            return jsonify({"error": "Balans yetarli emas."}), 402
        db.commit()
        charged = True

        try:
            result = rec.recognize_google(clip, language=ch[2])
        except sr.UnknownValueError:
            if charged:
                add_bal(uid, cost)
            return jsonify({"error": "Ovozdan matnni aniqlab bo‘lmadi; pul qaytarildi."}), 422

        return jsonify({"text": result, "cost": cost, "balance": int(get_user(uid)["bal"])})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        logging.exception("api_stt")
        if charged and uid is not None:
            add_bal(uid, cost)
        return jsonify({"error": "Ovozdan matn olishda server xatosi; mablag‘ qaytarildi."}), 500
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

def keep_alive():
    port = int(os.getenv("PORT", "8080"))
    threading.Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False),
        daemon=True
    ).start()


# ---------------- ishga tushirish ----------------
def build():
    app = (Application.builder().token(TOKEN).concurrent_updates(True)
           .connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30)
           .get_updates_connect_timeout(30).get_updates_read_timeout(30)
           .get_updates_write_timeout(30).get_updates_pool_timeout(30)
           .build())
    pv = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", start, pv))
    app.add_handler(CommandHandler("admin", admin_cmd, pv))
    app.add_handler(CommandHandler("cancel", cancel_cmd, pv))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(pv & ~filters.COMMAND, msg_h))
    app.add_error_handler(on_error)
    return app

def main():
    if not TOKEN or TOKEN == "BOT_TOKEN_SHU_YERGA":
        raise RuntimeError("BOT_TOKEN Render Environment Variables orqali berilishi kerak.")
    if ADMIN_ID == 123456789:
        logging.warning("ADMIN_ID hali o‘zgartirilmagan.")
    if WEB_APP_URL:
        logging.info("Mini App URL: %s", WEB_APP_URL)
    else:
        logging.warning("APP_URL/RENDER_EXTERNAL_URL yo‘q. Mini App tugmasi ko‘rinmaydi.")
    keep_alive()
    while True:
        asyncio.set_event_loop(asyncio.new_event_loop())
        try:
            build().run_polling(bootstrap_retries=-1, close_loop=False)
            break
        except (TimedOut, NetworkError) as e:
            logging.warning("Tarmoq xatosi, 10 soniyadan keyin qayta uriniladi: %s", e)
            time.sleep(10)

if __name__ == "__main__":
    main()
