import os, sys, subprocess

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
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")
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
class ThreadDB:
    """Separate SQLite connection per Flask/Telegram thread; WAL for safe concurrent reads."""
    def __init__(self,filename):
        self.filename=filename
        self.local=threading.local()
    def conn(self):
        c=getattr(self.local,'connection',None)
        if c is None:
            c=sqlite3.connect(self.filename,timeout=30,check_same_thread=True)
            c.execute('PRAGMA busy_timeout=30000')
            c.execute('PRAGMA journal_mode=WAL')
            self.local.connection=c
        return c
    def execute(self,*a,**kw):return self.conn().execute(*a,**kw)
    def executescript(self,*a,**kw):return self.conn().executescript(*a,**kw)
    def commit(self):return self.conn().commit()
    def rollback(self):return self.conn().rollback()
    def __enter__(self):return self.conn().__enter__()
    def __exit__(self,*a):return self.conn().__exit__(*a)

db = ThreadDB(os.getenv('DB_PATH','bot.db'))
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
try:
    db.execute("ALTER TABLE payments ADD COLUMN receipt_sent INTEGER DEFAULT 0")
except sqlite3.OperationalError:
    pass

if not db.execute("SELECT 1 FROM langs").fetchone():
    for _i, (_code, _name, _stt, _vs) in enumerate(DEFAULT_LANGS):
        db.execute("INSERT INTO langs(code,name,stt,pos) VALUES(?,?,?,?)", (_code, _name, _stt, _i))
        for _vn, _ev in _vs:
            db.execute("INSERT INTO voices(code,name,edge) VALUES(?,?,?)", (_code, _vn, _ev))
db.commit()

# ============ AI GENERATION / JOB QUEUE (Render + local GPU worker) ============
db.executescript("""
CREATE TABLE IF NOT EXISTS ai_models(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, kind TEXT DEFAULT 'image',
  price INTEGER DEFAULT 1000, enabled INTEGER DEFAULT 0, description TEXT DEFAULT '',
  workflow TEXT DEFAULT '', created INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ai_jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER NOT NULL, model_id INTEGER NOT NULL,
  prompt TEXT NOT NULL, negative TEXT DEFAULT '', params TEXT DEFAULT '{}', status TEXT DEFAULT 'queued',
  cost INTEGER DEFAULT 0, worker_id TEXT DEFAULT '', result_path TEXT DEFAULT '', result_type TEXT DEFAULT '',
  error TEXT DEFAULT '', created INTEGER DEFAULT 0, updated INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ai_jobs_status ON ai_jobs(status, id);
""")

MODEL_CATALOG = [
 ('SDXL / Stable Diffusion','image',1000,'Mahalliy rasm generatsiyasi'),
 ('FLUX.1','image',1500,'FLUX oilasi'),
 ('FLUX.1 Kontext','image',1700,'Rasmni tahrirlash / kontekst'),
 ('Qwen-Image','image',1600,'Qwen Image'),
 ('Hunyuan Image','image',1800,'Tencent Hunyuan Image'),
 ('Stable Diffusion 3.5','image',1500,'SD3.5'),
 ('SDXL Turbo','image',800,'Tezkor rasm'),
 ('SD 1.5','image',600,'Yengil model'),
 ('Kandinsky','image',900,'Kandinsky'),
 ('Playground','image',1000,'Playground oilasi'),
 ('PixArt','image',1000,'PixArt'),
 ('AuraFlow','image',1200,'AuraFlow'),
 ('Kolors','image',1500,'Kolors'),
 ('Wan 2.1 T2V','video',5000,'Text-to-video'),
 ('Wan 2.1 I2V','video',6000,'Image-to-video'),
 ('Wan 2.2','video',7000,'Wan 2.2'),
 ('LTX-Video','video',4500,'LTX Video'),
 ('CogVideoX','video',5500,'CogVideoX'),
 ('HunyuanVideo','video',8000,'HunyuanVideo'),
 ('HunyuanVideo 1.5','video',7500,'HunyuanVideo 1.5'),
 ('Mochi','video',6000,'Mochi video'),
 ('AnimateDiff','video',3500,'AnimateDiff'),
 ('Stable Video Diffusion','video',4500,'SVD'),
 ('CogVideoX I2V','video',6000,'Image-to-video'),
 ('LTXV Image-to-Video','video',5000,'LTXV I2V'),
 ('Hunyuan I2V','video',7500,'Hunyuan image-to-video'),
 ('Open-Sora','video',7000,'Open-Sora'),
 ('VideoCrafter','video',6500,'VideoCrafter'),
 ('ModelScope Video','video',5000,'ModelScope T2V'),
]
now_ts=int(time.time())
for _name,_kind,_price,_desc in MODEL_CATALOG:
    db.execute("INSERT OR IGNORE INTO ai_models(name,kind,price,enabled,description,created) VALUES(?,?,?,?,?,?)",
               (_name,_kind,_price,0,_desc,now_ts))
db.commit()

CFG = {k: v for k, v in db.execute("SELECT k,v FROM cfg")}
ADMINS = {r[0] for r in db.execute("SELECT id FROM admins")}
DEF = {"tts_price": "0.3", "stt_sec": "5", "start_bonus": "2000", "ref_bonus": "500",
       "min_topup": "1000", "max_tts": "3000", "amounts": "10000,25000,50000,100000",
       "bot_on": "1", "card_number": CARD_NUMBER, "card_owner": CARD_OWNER,
       "worker_enabled": "0", "worker_name": "local-gpu-1", "worker_poll_seconds": "2",
       "worker_note": "ComfyUI lokal GPU worker", "image_default_size": "1024x1024",
       "gen_max_prompt": "2000", "worker_key": os.getenv("WORKER_KEY", ""),
       "worker_last_seen": "0", "worker_default_image": "0" }
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
    rows.extend([[KeyboardButton("🎨 AI rasm"), KeyboardButton("🎬 AI video")],
                 [KeyboardButton("🧾 Buyurtmalar"), KeyboardButton("⚙️ Sozlamalar")]])
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
    elif t in ("🎨 AI rasm", "🎬 AI video"):
        kind = "image" if t == "🎨 AI rasm" else "video"
        enabled = db.execute("SELECT id,name,price FROM ai_models WHERE enabled=1 AND kind=? ORDER BY id", (kind,)).fetchall()
        if not enabled:
            await u.message.reply_text("Hozir bu xizmat uchun faol model yo‘q. Admin uni sozlab yoqishi kerak.", reply_markup=menu_kb())
        else:
            kb = [[B(f"{r[1]} · {fmt(r[2])} so‘m", callback_data=f"ai:{r[0]}")] for r in enabled[:30]]
            await u.message.reply_text("Modelni tanlang:", reply_markup=M(kb))
    elif t == "🧾 Buyurtmalar":
        jobs = db.execute("SELECT j.id,m.name,j.status,j.error FROM ai_jobs j JOIN ai_models m ON m.id=j.model_id WHERE j.uid=? ORDER BY j.id DESC LIMIT 8", (uid,)).fetchall()
        txt = "\n".join(f"#{i} {n}: {st}" + (f" ({err[:70]})" if err else "") for i,n,st,err in jobs) or "Buyurtmalar yo‘q."
        await u.message.reply_text(txt)
    elif t == "⚙️ Sozlamalar":
        await u.message.reply_text("Til va ovozni o‘zgartiring:", reply_markup=M([[B("🌐 TTS tili/ovozi",callback_data="chg"),B("🎙 STT tili",callback_data="stt_lang")]]))
    elif t == "🚀 Mini App":
        if WEB_APP_URL:
            await u.message.reply_text("Ilovani oching:", reply_markup=M([[B("🚀 Mini App",web_app=WebAppInfo(url=WEB_APP_URL))]]))
        else: await u.message.reply_text("Mini App manzili sozlanmagan.")
    elif t == "👑 Admin Mini App" and is_admin(uid):
        if WEB_APP_URL:
            await u.message.reply_text("Admin panel:", reply_markup=M([[B("👑 Admin",web_app=WebAppInfo(url=WEB_APP_URL))]]))
    elif ud.get("mode") == "ai_prompt":
        mid=ud.pop("ai_model",None); ud.pop("mode",None)
        if not mid:
            await u.message.reply_text("Modelni qayta tanlang."); return
        result,code=create_ai_job(uid,mid,t)
        await u.message.reply_text(result if code != 200 else f"✅ Buyurtma #{result} qabul qilindi. Natija tayyor bo‘lsa, shu yerga yuboriladi.", reply_markup=menu_kb())
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
    db.execute("UPDATE payments SET receipt_sent=1 WHERE id=?",(pid,));db.commit()
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
        cur = db.execute("UPDATE payments SET status=? WHERE id=? AND status='wait' AND receipt_sent=1",
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

    if d.startswith("ai:"):
        mid=int(d[3:]); row=db.execute("SELECT name,price FROM ai_models WHERE id=? AND enabled=1",(mid,)).fetchone()
        if not row:
            await q.message.reply_text("Model faol emas."); return
        c.user_data["mode"]="ai_prompt"; c.user_data["ai_model"]=mid
        await q.message.reply_text(f"🤖 {row[0]} (narx: {fmt(row[1])} so‘m)\nNima yaratishni yozing:")
        return

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
        *([[B("🚀 AI/Admin Mini App", web_app=WebAppInfo(url=WEB_APP_URL))]] if WEB_APP_URL else []),
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
        if m.text and m.text in [T(k) for k in MENU_KEYS] + ["🎨 AI rasm", "🎬 AI video", "🧾 Buyurtmalar", "⚙️ Sozlamalar", "🚀 Mini App", "👑 Admin Mini App"]:
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
<html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Voice Studio AI</title><script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{--bg:#070b14;--card:#101827;--card2:#0d1420;--text:#f7f9fc;--muted:#8f9db2;--line:#1d2a3d;--a:#6c7cff;--b:#35d6c8;--danger:#ff6678}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 0%,#18244b 0,#070b14 42%),#070b14;color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}button,input,textarea,select{font:inherit}button{cursor:pointer;border:0}.wrap{max-width:760px;margin:auto;padding:18px 14px 90px}.hero{padding:18px 4px 12px}.brand{font-weight:900;font-size:24px}.sub{color:var(--muted);font-size:13px;margin-top:5px}.balance{margin-top:16px;background:linear-gradient(135deg,#151f38,#0d1627);border:1px solid var(--line);border-radius:22px;padding:18px;display:flex;justify-content:space-between;align-items:center}.balnum{font-size:25px;font-weight:900}.pill{padding:7px 10px;border-radius:999px;background:#19243b;color:#b9c6ff;font-size:12px}.tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:14px 0}.tab{background:#101827;color:#aeb9ca;border:1px solid var(--line);border-radius:14px;padding:11px 6px}.tab.active{background:linear-gradient(135deg,#2a3568,#16263e);color:#fff;border-color:#5365b8}.panel{display:none}.panel.active{display:block}.card{background:rgba(16,24,39,.92);border:1px solid var(--line);border-radius:20px;padding:15px;margin:10px 0}.title{font-weight:800;margin-bottom:10px}.hint{font-size:12px;color:var(--muted);line-height:1.5}.textarea,.input,.select{width:100%;background:#09111d;border:1px solid #223047;color:#fff;border-radius:14px;padding:13px;outline:none}.textarea{min-height:130px;resize:vertical}.row{display:grid;grid-template-columns:1fr 1fr;gap:9px}.btn{width:100%;padding:12px 14px;border-radius:13px;background:#202c43;color:#fff;font-weight:800}.btn.primary{background:linear-gradient(135deg,#6677ff,#3d53d8)}.btn.green{background:linear-gradient(135deg,#18bba9,#158c83)}.btn.red{background:#43202a;color:#ffb7c1}.btn:disabled{opacity:.45}.status{min-height:20px;color:#a9b7ca;font-size:13px;margin-top:10px}.audio{width:100%;margin-top:10px}.models{display:grid;gap:8px}.model{border:1px solid var(--line);border-radius:14px;padding:12px;background:#0b1320}.model strong{display:block}.model small{color:var(--muted)}.model.sel{border-color:#6677ff;background:#141d38}.job{padding:12px;border:1px solid var(--line);border-radius:14px;margin:7px 0}.jobtop{display:flex;justify-content:space-between}.ok{color:#50d5a7}.wait{color:#ffc866}.bad{color:#ff7586}.nav{position:fixed;bottom:0;left:0;right:0;background:rgba(7,11,20,.96);border-top:1px solid var(--line);padding:9px 10px;display:grid;grid-template-columns:repeat(5,1fr);gap:5px}.nav button{background:transparent;color:#8290a6;padding:7px 3px;font-size:11px}.nav button.active{color:#fff}.adminbox{border:1px solid #354d7c;background:#0e1930}.hide{display:none!important}.kv{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #1b2738;font-size:13px}.kv:last-child{border:0}.danger{color:#ff7a8a}
</style></head><body><div class="wrap">
<div class="hero"><div class="brand">⚡ Voice Studio AI</div><div class="sub" id="hello">Yuklanmoqda...</div></div>
<div class="balance"><div><div class="sub">Mening balansim</div><div class="balnum" id="bal">0 so‘m</div></div><div class="pill" id="refs">0 referal</div></div>
<div id="home" class="panel active"><div class="tabs"><button class="tab active" onclick="mode('tts',this)">🔊 TTS</button><button class="tab" onclick="mode('stt',this)">🎙 STT</button><button class="tab" onclick="mode('gen',this)">🎨 AI</button></div>
<div id="tts" class="card tool"><div class="title">🔊 Matn → tabiiy ovoz</div><textarea id="text" class="textarea" placeholder="Ovozga aylantiriladigan matn..."></textarea><div class="row" style="margin-top:9px"><button class="btn primary" onclick="tts()">Ovoz yaratish</button><button class="btn" onclick="clearText()">Tozalash</button></div><audio id="player" class="audio hide" controls></audio></div>
<div id="stt" class="card tool hide"><div class="title">🎙 Ovoz → matn</div><div class="hint">Brauzer mikrofonidan yozib, matnga aylantiring.</div><div class="row" style="margin-top:10px"><button class="btn primary" id="rec" onclick="startRecord()">🔴 Yozish</button><button class="btn" id="stop" onclick="stopRecord()" disabled>⏹ To‘xtatish</button></div><input type="file" id="sttFile" accept="audio/*" class="input" style="margin-top:10px"><button class="btn" style="margin-top:8px" onclick="sttUpload()">📁 Audio faylni matnga aylantirish</button><div id="sttResult" class="card" style="margin-top:10px">Natija shu yerda chiqadi.</div></div>
<div id="gen" class="card tool hide"><div class="title">🎨 AI rasm / 🎬 video</div><div id="workerStatus" class="hint" style="margin-bottom:10px">Generator tekshirilmoqda...</div><div id="modelList" class="models"></div><textarea id="prompt" class="textarea" style="margin-top:10px;min-height:100px" placeholder="Nima yaratilsin? Masalan: cinematic Uzbek city at sunset..."></textarea><input id="negative" class="input" style="margin-top:9px" placeholder="Negative prompt (ixtiyoriy)"><div class="row" style="margin-top:9px"><select id="size" class="select"><option>1024x1024</option><option>768x1024</option><option>1024x768</option><option>512x512</option></select><button class="btn primary" onclick="generate()">🚀 Yaratish</button></div><div id="genStatus" class="status"></div></div>
<div class="card"><div class="title">⚙️ Til va ovoz</div><div class="kv"><span>Til</span><b id="lang">-</b></div><div class="kv"><span>Ovoz</span><b id="voice">-</b></div><label class="hint">Matn → ovoz tili</label><select id="ttsLang" class="select" onchange="loadVoices()"></select><label class="hint">Ovoz</label><select id="ttsVoice" class="select"></select><button class="btn" style="margin:8px 0" onclick="saveVoice()">🔊 Ovozni saqlash</button><label class="hint">Ovoz → matn tili</label><select id="sttLang" class="select"></select><button class="btn" style="margin-top:8px" onclick="saveSTTLang()">🎙 Tilni saqlash</button></div></div>
<div id="balancePanel" class="panel"><div class="card"><div class="title">💳 Balansni to‘ldirish</div><div class="hint" id="payInfo">-</div><div id="amounts" class="row" style="margin-top:10px"></div><input id="customAmount" class="input" style="margin-top:9px" placeholder="Boshqa summa"><button class="btn primary" style="margin-top:9px" onclick="topup()">To‘ldirish so‘rovini yuborish</button><div class="status" id="payStatus"></div><div class="hint" style="margin-top:10px">So‘rov yuborgach, to‘lov chekining rasmini yoki PDF faylini shu yerda jo‘nating.</div><input type="file" id="receipt" class="input" accept="image/*,application/pdf" style="margin-top:8px"><button class="btn green" style="margin-top:8px" onclick="sendReceipt()">📎 Chekni adminga yuborish</button></div></div>
<div id="refPanel" class="panel"><div class="card"><div class="title">👥 Referal</div><div class="hint">Har bir haqiqiy yangi taklif uchun bonus admin sozlamasidan boshqariladi.</div><input id="refLink" class="input" style="margin-top:10px" readonly><button class="btn primary" style="margin-top:9px" onclick="copyRef()">Havolani nusxalash</button></div></div>
<div id="jobsPanel" class="panel"><div class="card"><div class="title">🧾 Generatsiyalar</div><div id="jobs">Yuklanmoqda...</div></div></div>
<div id="adminPanel" class="panel"><div class="card adminbox"><div class="title">👑 Admin panel</div><div class="hint">Narxlar, AI modellar, worker, bot holati va foydalanuvchi balanslari shu yerdan boshqariladi.</div><div class="row" style="margin-top:10px"><button class="btn" onclick="adminLoad()">Yangilash</button><button class="btn red" onclick="adminToggle()">Bot holati</button></div></div><div class="card"><div class="title">📊 Statistika</div><div id="astats">-</div></div><div class="card"><div class="title">🤖 AI modellarni boshqarish</div><div id="amodels">-</div><hr style="border-color:#1d2a3d;border-width:1px 0 0;margin:12px 0"><input id="mid" type="hidden"><input id="mname" class="input" placeholder="Model nomi"><div class="row" style="margin-top:8px"><select id="mkind" class="select"><option value="image">🖼️ image</option><option value="video">🎬 video</option></select><input id="mprice" class="input" type="number" placeholder="Narx"></div><textarea id="mworkflow" class="textarea" style="margin-top:8px;min-height:90px" placeholder="ComfyUI API workflow JSON (video va maxsus modellar uchun)"></textarea><div class="row" style="margin-top:8px"><button class="btn primary" onclick="saveModel()">Modelni saqlash</button><button class="btn" onclick="clearModel()">Tozalash</button></div></div><div class="card"><div class="title">💰 Balansni boshqarish</div><input id="auser" class="input" inputmode="numeric" placeholder="Foydalanuvchi Telegram ID"><div class="row" style="margin-top:8px"><input id="adelta" class="input" inputmode="numeric" placeholder="Summa (+/-)"><button class="btn green" onclick="adminBalance()">Saqlash</button></div></div><div class="card"><div class="title">💳 Cheklar</div><button class="btn" onclick="adminPayments()">Cheklarni yangilash</button><div id="apays"></div></div><div class="card"><div class="title">⚙️ Narxlar, bonuslar va karta</div><button class="btn" onclick="adminConfig()">Sozlamalarni ko‘rish</button><div id="aconfig"></div></div><div class="card"><div class="title">⚙️ Worker</div><input id="workerName" class="input" placeholder="Worker nomi"><input id="workerKey" class="input" style="margin-top:8px" placeholder="Worker key (faqat bir marta ko‘rsatish uchun)"><button class="btn primary" style="margin-top:8px" onclick="saveWorker()">Saqlash</button></div></div>
<div id="status" class="status"></div></div>
<div class="nav"><button class="active" onclick="page('home',this)">🏠 Bosh</button><button onclick="page('balancePanel',this)">💳 Balans</button><button onclick="page('refPanel',this)">👥 Referal</button><button onclick="page('jobsPanel',this)">🧾 Ishlar</button><button id="adminNav" class="hide" onclick="page('adminPanel',this)">👑 Admin</button></div>
<script>
const tg=window.Telegram?.WebApp; tg?.ready(); tg?.expand();
const ids=['mid','mname','mkind','mprice','mworkflow','auser','adelta','apays','aconfig','ttsLang','ttsVoice','sttLang','sttFile','sttResult','rec','stop'];
const els=Object.fromEntries(ids.map(id=>[id,document.getElementById(id)]));
const {mid,mname,mkind,mprice,mworkflow,auser,adelta,apays,aconfig,ttsLang,ttsVoice,sttLang,sttFile,sttResult,rec,stop}=els;
const H=()=>({'X-Telegram-Init-Data':tg?.initData||'','Content-Type':'application/json'}); let selectedModel=null;
async function api(url,opt={}){opt.headers={...(opt.headers||{}),...(url.includes('/api/')?H():{})};const r=await fetch(url,opt);const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error||'Xatolik');return d}
function page(id,b){document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));document.getElementById(id).classList.add('active');document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));b?.classList.add('active')}
function mode(id,b){document.querySelectorAll('.tool').forEach(x=>x.classList.add('hide'));document.getElementById(id).classList.remove('hide');document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active')}
async function load(){try{const d=await api('/api/me');document.getElementById('hello').textContent='Salom, '+(d.first_name||'foydalanuvchi')+' 👋';document.getElementById('bal').textContent=d.balance.toLocaleString()+' so‘m';document.getElementById('refs').textContent=d.refs+' referal';document.getElementById('lang').textContent=d.language||'-';document.getElementById('voice').textContent=d.voice||'-';document.getElementById('refLink').value=d.ref_link||'';if(d.is_admin){document.getElementById('adminNav').classList.remove('hide');await adminLoad()}document.getElementById('payInfo').textContent=d.pay_info||'-';document.getElementById('amounts').innerHTML=(d.amounts||[]).map(a=>`<button class="btn" onclick="document.getElementById('customAmount').value=${a}">${a.toLocaleString()} so‘m</button>`).join('');await loadModels();await loadJobs();await loadSettings()}catch(e){status(e.message)}}
function status(x){document.getElementById('status').textContent=x||''}
function clearText(){document.getElementById('text').value=''}
async function tts(){const text=document.getElementById('text').value.trim();if(!text)return status('Matn yozing.');status('⏳ Ovoz tayyorlanmoqda...');try{const r=await fetch('/api/tts',{method:'POST',headers:H(),body:JSON.stringify({text})});if(!r.ok){const e=await r.json();throw Error(e.error)}const blob=await r.blob(),url=URL.createObjectURL(blob);const p=document.getElementById('player');p.src=url;p.classList.remove('hide');p.play().catch(()=>{});status('✅ Tayyor.');load()}catch(e){status('❌ '+e.message)}}
let mediaRecorder,chunks=[];async function startRecord(){try{const s=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];mediaRecorder=new MediaRecorder(s);mediaRecorder.ondataavailable=e=>e.data.size&&chunks.push(e.data);mediaRecorder.onstop=async()=>{s.getTracks().forEach(t=>t.stop());const fd=new FormData();fd.append('audio',new Blob(chunks,{type:mediaRecorder.mimeType||'audio/webm'}),'voice.webm');status('⏳ Aniqlanmoqda...');try{const r=await fetch('/api/stt',{method:'POST',headers:{'X-Telegram-Init-Data':tg?.initData||''},body:fd});const d=await r.json();if(!r.ok)throw Error(d.error);document.getElementById('sttResult').textContent='📝 '+d.text;status('✅ Tayyor.');load()}catch(e){status('❌ '+e.message)}};mediaRecorder.start();rec.disabled=true;stop.disabled=false;status('🔴 Yozilmoqda...')}catch(e){status('❌ Mikrofon ruxsati kerak.')}}
function stopRecord(){if(mediaRecorder&&mediaRecorder.state!=='inactive')mediaRecorder.stop();rec.disabled=false;stop.disabled=true}
let visibleModels=[];
function esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function renderModels(){const box=document.getElementById('modelList');box.innerHTML=visibleModels.length?visibleModels.map(m=>`<div class="model ${selectedModel===m.id?'sel':''}" onclick="selectModel(${m.id})"><strong>${m.kind==='video'?'🎬':'🖼️'} ${esc(m.name)}</strong><small>${esc(m.description||'')} · ${m.price.toLocaleString()} so‘m</small></div>`).join(''):'<div class="hint">Hozircha sozlangan, faol model mavjud emas.</div>'}
async function loadSettings(){const d=await api('/api/languages');ttsLang.innerHTML=d.tts.map(v=>`<option value="${esc(v.code)}">${esc(v.name)}</option>`).join('');sttLang.innerHTML=d.stt.map(v=>`<option value="${esc(v.code)}">${esc(v.name)}</option>`).join('');ttsLang.value=d.current_tts;sttLang.value=d.current_stt;await loadVoices(d.current_voice)}
async function loadVoices(chosen){const d=await api('/api/voices?code='+encodeURIComponent(ttsLang.value));ttsVoice.innerHTML=d.voices.map(v=>`<option value="${v.id}">${esc(v.name)}</option>`).join('');if(chosen)ttsVoice.value=chosen}
async function saveVoice(){try{const d=await api('/api/settings',{method:'POST',body:JSON.stringify({lang:ttsLang.value,voice:Number(ttsVoice.value)})});status('✅ Ovoz saqlandi');document.getElementById('lang').textContent=d.language;document.getElementById('voice').textContent=d.voice}catch(e){status('❌ '+e.message)}}
async function saveSTTLang(){try{await api('/api/settings',{method:'POST',body:JSON.stringify({stt_lang:sttLang.value})});status('✅ STT tili saqlandi')}catch(e){status('❌ '+e.message)}}
async function sttUpload(){const f=sttFile.files[0];if(!f)return status('Audio faylni tanlang.');const fd=new FormData();fd.append('audio',f,f.name);status('⏳ Audio matnga aylantirilmoqda...');try{const r=await fetch('/api/stt',{method:'POST',headers:{'X-Telegram-Init-Data':tg?.initData||''},body:fd});const d=await r.json();if(!r.ok)throw Error(d.error);sttResult.textContent=d.text;status('✅ Tayyor');load()}catch(e){status('❌ '+e.message)}}
async function loadModels(){const d=await api('/api/models');visibleModels=d.models||[];if(!visibleModels.find(m=>m.id===selectedModel))selectedModel=visibleModels[0]?.id||null;renderModels();const note=document.getElementById('workerStatus');if(note)note.textContent=d.worker_online?'🟢 Generator ulangan':'🔴 Generator ulanmagan. Pullik buyurtma qabul qilinmaydi.'}
function selectModel(id){selectedModel=id;renderModels()}
async function generate(){if(!selectedModel)return status('Model tanlang.');const p=document.getElementById('prompt').value.trim();if(!p)return status('Prompt yozing.');document.getElementById('genStatus').textContent='⏳ Navbatga qo‘shilmoqda...';try{const d=await api('/api/generate',{method:'POST',body:JSON.stringify({model_id:selectedModel,prompt:p,negative:document.getElementById('negative').value,size:document.getElementById('size').value})});document.getElementById('genStatus').textContent='✅ #'+d.job_id+' navbatga qo‘shildi. Worker tayyorlagach botga yuboriladi.';loadJobs();load()}catch(e){document.getElementById('genStatus').textContent='❌ '+e.message}}
async function loadJobs(){try{const d=await api('/api/jobs');document.getElementById('jobs').innerHTML=d.jobs.length?d.jobs.map(j=>`<div class="job"><div class="jobtop"><b>#${j.id} · ${esc(j.model)}</b><span class="${j.status==='done'?'ok':j.status==='failed'?'bad':'wait'}">${j.status}</span></div><div class="hint">${j.cost.toLocaleString()} so‘m · ${new Date(j.created*1000).toLocaleString()}</div>${j.error?`<div class="danger">${esc(j.error)}</div>`:''}</div>`).join(''):'Hozircha generatsiya yo‘q.'}catch(e){}}
let lastPayment=0;async function topup(){const a=Number(document.getElementById('customAmount').value);if(!a)return status('Summani kiriting.');document.getElementById('payStatus').textContent='⏳ So‘rov...';try{const d=await api('/api/topup',{method:'POST',body:JSON.stringify({amount:a})});lastPayment=d.payment_id;document.getElementById('payStatus').textContent='✅ So‘rov #'+d.payment_id+' yaratildi. Endi chekni yuklang.'}catch(e){document.getElementById('payStatus').textContent='❌ '+e.message}}
async function sendReceipt(){const f=document.getElementById('receipt').files[0];if(!lastPayment)return status('Avval to‘lov so‘rovini yarating.');if(!f)return status('Chek faylini tanlang.');const fd=new FormData();fd.append('payment_id',lastPayment);fd.append('receipt',f);status('⏳ Chek yuborilmoqda...');try{const r=await fetch('/api/receipt',{method:'POST',headers:{'X-Telegram-Init-Data':tg?.initData||''},body:fd});const d=await r.json();if(!r.ok)throw Error(d.error);status('✅ Chek adminga yuborildi.')}catch(e){status('❌ '+e.message)}}
function copyRef(){navigator.clipboard?.writeText(document.getElementById('refLink').value);status('Referal havola nusxalandi.')}
let adminModelCache={};async function adminLoad(){try{const d=await api('/api/admin/overview');adminModelCache=Object.fromEntries(d.models.map(m=>[m.id,m]));document.getElementById('astats').innerHTML=`<div class="kv"><span>Users</span><b>${d.users}</b></div><div class="kv"><span>Balanslar jami</span><b>${d.balance.toLocaleString()} so‘m</b></div><div class="kv"><span>Queued</span><b>${d.queued}</b></div><div class="kv"><span>Worker</span><b>${d.worker}</b></div>`;document.getElementById('amodels').innerHTML=d.models.map(m=>`<div class="kv"><span>${m.kind==='video'?'🎬':'🖼️'} ${esc(m.name)}<br><small>${m.enabled?'ON':'OFF'} · ${m.price.toLocaleString()} so‘m</small></span><b><button class="btn" style="width:auto;padding:7px" onclick='editModel(${JSON.stringify(m)})'>✏️</button> <button class="btn" style="width:auto;padding:7px" onclick='toggleModel(${m.id})'>${m.enabled?'OFF':'ON'}</button></b></div>`).join('');document.getElementById('workerName').value=d.worker_name||'';status('Admin ma’lumotlari yangilandi.')}catch(e){status('❌ '+e.message)}}
async function adminToggle(){try{const d=await api('/api/admin/toggle',{method:'POST',body:'{}'});status(d.message)}catch(e){status('❌ '+e.message)}}
async function saveWorker(){try{const d=await api('/api/admin/worker',{method:'POST',body:JSON.stringify({name:document.getElementById('workerName').value,key:document.getElementById('workerKey').value})});status(d.message)}catch(e){status('❌ '+e.message)}}
async function adminBalance(){try{const d=await api('/api/admin/balance',{method:'POST',body:JSON.stringify({uid:Number(auser.value),delta:Number(adelta.value)})});status(d.message);adminLoad()}catch(e){status('❌ '+e.message)}}
async function adminPayments(){try{const d=await api('/api/admin/payments');apays.innerHTML=d.payments.map(p=>`<div class="job">#${p.id} · ${p.uid} · ${p.amount.toLocaleString()} so‘m · ${esc(p.status)} ${p.receipt?'📎':''}${p.status==='wait'&&p.receipt?`<div class="row"><button class="btn green" onclick="reviewPayment(${p.id},'ok')">✅ Tasdiqlash</button><button class="btn red" onclick="reviewPayment(${p.id},'no')">❌ Rad</button></div>`:''}</div>`).join('')||'So‘rovlar yo‘q.'}catch(e){status('❌ '+e.message)}}
async function reviewPayment(id,statusValue){if(!confirm('To‘lovni tasdiqlaysizmi?'))return;try{const d=await api('/api/admin/payment',{method:'POST',body:JSON.stringify({id,status:statusValue})});status(d.message);adminPayments();adminLoad()}catch(e){status('❌ '+e.message)}}
async function adminConfig(){try{const d=await api('/api/admin/config');aconfig.innerHTML=Object.entries(d.settings).map(([k,v])=>`<div class="job"><label>${esc(k)}<input class="input" id="cfg_${k}" value="${esc(v)}"></label><button class="btn" style="margin-top:6px" onclick="saveConfig('${k}')">Saqlash</button></div>`).join('')}catch(e){status('❌ '+e.message)}}
async function saveConfig(k){try{const d=await api('/api/admin/config',{method:'POST',body:JSON.stringify({key:k,value:document.getElementById('cfg_'+k).value})});status(d.message);load()}catch(e){status('❌ '+e.message)}}
function clearModel(){mid.value='';mname.value='';mprice.value='';mworkflow.value='';mkind.value='image'}
async function editModel(m){try{const d=await api('/api/admin/model/'+m.id);mid.value=m.id;mname.value=d.name;mkind.value=d.kind;mprice.value=d.price;mworkflow.value=d.workflow||'';status('Model sozlamalari yuklandi.')}catch(e){status('❌ '+e.message)}}
async function toggleModel(id){try{const d=await api('/api/admin/model/'+id+'/toggle',{method:'POST',body:'{}'});status(d.message);adminLoad();loadModels()}catch(e){status('❌ '+e.message)}}
async function saveModel(){try{const d=await api('/api/admin/model',{method:'POST',body:JSON.stringify({id:Number(mid.value)||0,name:mname.value,kind:mkind.value,price:Number(mprice.value)||0,enabled:true,workflow:mworkflow.value})});status(d.message);clearModel();adminLoad();loadModels()}catch(e){status('❌ '+e.message)}}
if(!tg?.initData){status('Mini Appni Telegramdagi bot tugmasidan oching. Oddiy brauzerda hisob autentifikatsiyasi ishlamaydi.')}else{load();setInterval(loadJobs,8000)}
</script></body></html>"""

flask_app = Flask(__name__)
flask_app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
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

@flask_app.route('/api/languages')
def api_languages():
    try:
        uid,_,u=_api_auth()
        tt=db.execute("SELECT code,name FROM langs WHERE active=1 AND EXISTS(SELECT 1 FROM voices v WHERE v.code=langs.code) ORDER BY pos").fetchall()
        st=db.execute("SELECT code,name FROM langs WHERE active=1 AND stt!='' ORDER BY pos").fetchall()
        return jsonify({'tts':[{'code':c,'name':n} for c,n in tt], 'stt':[{'code':c,'name':n} for c,n in st],
                        'current_tts':u['lang'], 'current_stt':u['stt'], 'current_voice':u['voice']})
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/voices')
def api_voices():
    try:
        _api_auth();code=str(request.args.get('code',''))
        rows=db.execute('SELECT v.id,v.name FROM voices v JOIN langs l ON l.code=v.code WHERE v.code=? AND l.active=1',(code,)).fetchall()
        return jsonify({'voices':[{'id':i,'name':n} for i,n in rows]})
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/settings',methods=['POST'])
def api_settings():
    try:
        uid,_,u=_api_auth();d=request.get_json(silent=True) or {}
        if 'lang' in d or 'voice' in d:
            lang=str(d.get('lang',''));voice=int(d.get('voice',0))
            if not db.execute('SELECT 1 FROM voices v JOIN langs l ON v.code=l.code WHERE v.id=? AND v.code=? AND l.active=1',(voice,lang)).fetchone():
                return jsonify({'error':'Ovoz/til mavjud emas.'}),400
            db.execute('UPDATE users SET lang=?,voice=? WHERE id=?',(lang,voice,uid))
        if 'stt_lang' in d:
            st=str(d.get('stt_lang',''))
            if not db.execute("SELECT 1 FROM langs WHERE code=? AND active=1 AND stt!=''",(st,)).fetchone():
                return jsonify({'error':'STT tili mavjud emas.'}),400
            db.execute('UPDATE users SET stt_lang=? WHERE id=?',(st,uid))
        db.commit(); ch=tts_choice(uid)
        return jsonify({'language':ch[1] if ch else '', 'voice':ch[2] if ch else ''})
    except (ValueError,TypeError) as e:return jsonify({'error':str(e)}),400

@flask_app.route("/api/me")
def api_me():
    try:
        uid, user, u = _api_auth()
        refs = int(one("SELECT refs FROM users WHERE id=?", (uid,)))
        ch = tts_choice(uid)
        amounts=[int(x) for x in S("amounts").split(",") if x.strip()]
        ref_link=(f"https://t.me/{BOT_USERNAME}?start=ref_{uid}" if BOT_USERNAME else "")
        return jsonify({
            "id": uid,
            "first_name": user.get("first_name", ""),
            "balance": int(u["bal"]),
            "refs": refs,
            "language": ch[1] if ch else "-",
            "voice": ch[2] if ch else "-",
            "is_admin": is_admin(uid),
            "amounts": amounts,
            "ref_link": ref_link,
            "pay_info": f"Karta: {S('card_number')}\nEgasi: {S('card_owner')}"
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
            cur=db.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",
                       (cost, uid, cost))
            if cur.rowcount != 1:
                raise ValueError("Balans yetarli emas.")
            db.commit()
            with open(out,'rb') as voice_file:
                data=voice_file.read()
            return send_file(io.BytesIO(data), mimetype="audio/mpeg", as_attachment=False,
                             download_name="voice.mp3")
        except Exception:
            db.rollback()
            raise
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
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
        original_name=os.path.basename(audio.filename or 'audio.webm')
        src_file = os.path.join(tmp, 'input'+(os.path.splitext(original_name)[1].lower() or '.webm'))
        wav = os.path.join(tmp, "input.wav")
        audio.save(src_file)
        if os.path.getsize(src_file)>15*1024*1024:
            return jsonify({'error':'Audio 15 MB dan oshmasin.'}),413

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

        cur=db.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",
                   (cost, uid, cost))
        if cur.rowcount != 1:
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


# Worker's heartbeat must be fresh before accepting any paid job.
def worker_online():
    try: return bool(S("worker_enabled") == "1" and int(S("worker_last_seen")) > time.time() - 45)
    except (ValueError, KeyError): return False

def create_ai_job(uid, mid, prompt, negative="", size="1024x1024"):
    prompt=str(prompt).strip()
    if not prompt or len(prompt)>Si("gen_max_prompt"):
        return "Prompt bo‘sh yoki haddan tashqari uzun.",400
    if not worker_online():
        return "AI generator hozir ulanmagan. Mablag‘ yechilmadi.",503
    row=db.execute("SELECT id,name,kind,price,enabled,workflow FROM ai_models WHERE id=?",(mid,)).fetchone()
    if not row or not row[4]:return "Model faol emas.",404
    if row[2]=='video' and not row[5]:return "Video model workflow hali ulanmagan; pul yechilmadi.",503
    if row[2]=='image' and not row[5] and (S("worker_default_image")!='1' or row[1]!='SDXL / Stable Diffusion'):
        return "Bu rasm modeli uchun alohida workflow hali ulanmagan; pul yechilmadi.",503
    cost=max(0,int(row[3])); now=int(time.time())
    try:
        db.execute("BEGIN IMMEDIATE")
        cur=db.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",(cost,uid,cost))
        if cur.rowcount!=1:
            db.rollback();return f"Balans yetarli emas. Kerak: {fmt(cost)} so‘m.",402
        cur=db.execute("INSERT INTO ai_jobs(uid,model_id,prompt,negative,params,status,cost,created,updated) VALUES(?,?,?,?,?,?,?,?,?)",(uid,mid,prompt,str(negative),json.dumps({'size':size}),"queued",cost,now,now))
        jid=cur.lastrowid;db.commit();return jid,200
    except Exception:
        db.rollback(); logging.exception('create_ai_job');return "Buyurtma saqlanmadi. Pul yechilmadi.",500

# ============ AI / ADMIN API ============
def _admin_auth():
    uid, user, u = _api_auth()
    if not is_admin(uid):
        raise ValueError("Faqat admin uchun.")
    return uid, user, u

def _json_int(v, default=0):
    try: return int(float(v))
    except Exception: return default

def _worker_key_ok():
    key=os.getenv("WORKER_KEY", "").strip() or S("worker_key")
    got=request.headers.get("X-Worker-Key", "").strip()
    return bool(key) and hmac.compare_digest(got, key)

@flask_app.route('/api/models')
def api_models():
    try:
        _api_auth()
        rows=db.execute("SELECT id,name,kind,price,description FROM ai_models WHERE enabled=1 ORDER BY kind,id").fetchall()
        return jsonify({'models':[{'id':r[0],'name':r[1],'kind':r[2],'price':r[3],'description':r[4]} for r in rows], 'worker_online':worker_online()})
    except ValueError as e: return jsonify({'error':str(e)}),401

@flask_app.route('/api/generate',methods=['POST'])
def api_generate():
    try:
        uid,_,_=_api_auth();d=request.get_json(silent=True) or {}
        result,code=create_ai_job(uid,_json_int(d.get('model_id')),d.get('prompt',''),d.get('negative',''),str(d.get('size','1024x1024')))
        if code!=200:return jsonify({'error':result}),code
        return jsonify({'job_id':result,'status':'queued'})
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/jobs')
def api_jobs():
    try:
        uid,_,_= _api_auth(); rows=db.execute("SELECT j.id,m.name,j.status,j.cost,j.error,j.created FROM ai_jobs j JOIN ai_models m ON m.id=j.model_id WHERE j.uid=? ORDER BY j.id DESC LIMIT 30",(uid,)).fetchall()
        return jsonify({'jobs':[{'id':r[0],'model':r[1],'status':r[2],'cost':r[3],'error':r[4],'created':r[5]} for r in rows]})
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/topup',methods=['POST'])
def api_topup():
    try:
        uid,_,_= _api_auth(); d=request.get_json(silent=True) or {}; amount=_json_int(d.get('amount'))
        if amount<Si('min_topup'):return jsonify({'error':f'Minimum {fmt(Si("min_topup"))} so‘m.'}),400
        cur=db.execute("INSERT INTO payments(uid,amount,status,receipt_sent) VALUES(?,?,?,0)",(uid,amount,'wait'));db.commit();return jsonify({'payment_id':cur.lastrowid})
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/admin/overview')
def api_admin_overview():
    try:
        _admin_auth(); models=db.execute("SELECT id,name,kind,price,enabled FROM ai_models ORDER BY kind,id").fetchall()
        return jsonify({'users':one('SELECT COUNT(*) FROM users'),'balance':one('SELECT COALESCE(SUM(balance),0) FROM users'),'queued':one("SELECT COUNT(*) FROM ai_jobs WHERE status IN ('queued','running')"),'worker':S('worker_name'),'worker_name':S('worker_name'),'models':[{'id':r[0],'name':r[1],'kind':r[2],'price':r[3],'enabled':bool(r[4])} for r in models]})
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/admin/toggle',methods=['POST'])
def api_admin_toggle():
    try:
        _admin_auth(); val='0' if S('bot_on')=='1' else '1';set_cfg('bot_on',val);return jsonify({'message':'Bot yoqildi.' if val=='1' else 'Bot vaqtincha o‘chirildi.'})
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/admin/worker',methods=['POST'])
def api_admin_worker():
    try:
        _admin_auth();d=request.get_json(silent=True) or {};name=str(d.get('name','local-gpu-1')).strip()[:80];key=str(d.get('key','')).strip()
        set_cfg('worker_name',name or 'local-gpu-1')
        if key:
            if os.getenv('WORKER_KEY','').strip():return jsonify({'error':'WORKER_KEY server sozlamasida belgilangan. O‘sha qiymatdan foydalaning.'}),409
            if len(key)<24:return jsonify({'error':'Worker kaliti kamida 24 belgidan iborat bo‘lsin.'}),400
            set_cfg('worker_key',key)
        return jsonify({'message':'Worker sozlamalari saqlandi.'})
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/admin/model',methods=['POST'])
def api_admin_model():
    try:
        _admin_auth();d=request.get_json(silent=True) or {};mid=_json_int(d.get('id'));name=str(d.get('name','')).strip();kind=str(d.get('kind','image')).lower();price=_json_int(d.get('price'),1000);enabled=1 if d.get('enabled') else 0;workflow=str(d.get('workflow',''))
        if not name or len(name)>90 or kind not in ('image','video') or price<0:return jsonify({'error':'Model ma’lumotlari noto‘g‘ri.'}),400
        if workflow:
            try:
                graph=json.loads(workflow)
                if not isinstance(graph,dict) or not graph:raise ValueError()
            except Exception:return jsonify({'error':'Workflow to‘g‘ri ComfyUI API JSON bo‘lishi shart.'}),400
        if mid:db.execute("UPDATE ai_models SET name=?,kind=?,price=?,enabled=?,workflow=? WHERE id=?",(name,kind,price,enabled,workflow,mid))
        else:db.execute("INSERT INTO ai_models(name,kind,price,enabled,description,workflow,created) VALUES(?,?,?,?,?,?,?)",(name,kind,price,enabled,str(d.get('description','')),workflow,int(time.time())))
        db.commit();return jsonify({'message':'Model saqlandi.'})
    except ValueError as e:return jsonify({'error':str(e)}),401
    except Exception as e:return jsonify({'error':'Model saqlanmadi: '+str(e)}),400

@flask_app.route('/api/admin/model/<int:mid>/toggle',methods=['POST'])
def api_admin_model_toggle(mid):
    try:
        _admin_auth();r=db.execute('SELECT enabled FROM ai_models WHERE id=?',(mid,)).fetchone()
        if not r:return jsonify({'error':'Model topilmadi.'}),404
        db.execute('UPDATE ai_models SET enabled=? WHERE id=?',(0 if r[0] else 1,mid));db.commit();return jsonify({'message':'Model holati yangilandi. Workflow va Worker ham sozlangan bo‘lishi shart.'})
    except ValueError as e:return jsonify({'error':str(e)}),401


@flask_app.route('/worker/heartbeat',methods=['POST'])
def worker_heartbeat():
    if not _worker_key_ok():return jsonify({'error':'worker auth'}),401
    d=request.get_json(silent=True) or {}
    set_cfg('worker_last_seen',str(int(time.time())))
    set_cfg('worker_enabled','1')
    set_cfg('worker_default_image','1' if bool(d.get('default_image')) else '0')
    return jsonify({'ok':True})

@flask_app.route('/api/admin/model/<int:mid>')
def admin_get_model(mid):
    try:
        _admin_auth();r=db.execute('SELECT id,name,kind,price,enabled,description,workflow FROM ai_models WHERE id=?',(mid,)).fetchone()
        if not r:return jsonify({'error':'Model yo‘q'}),404
        return jsonify(dict(zip(('id','name','kind','price','enabled','description','workflow'),r)))
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/admin/config',methods=['GET','POST'])
def admin_config():
    try:
        _admin_auth()
        editable=('tts_price','stt_sec','start_bonus','ref_bonus','min_topup','max_tts','amounts','card_number','card_owner')
        if request.method=='GET':return jsonify({'settings':{k:S(k) for k in editable}})
        d=request.get_json(silent=True) or {};key=d.get('key');val=str(d.get('value','')).strip()
        if key not in editable:return jsonify({'error':'Bu sozlamani o‘zgartirib bo‘lmaydi.'}),400
        if key in ('tts_price','stt_sec') and not (0<=float(val)<=100000):return jsonify({'error':'Noto‘g‘ri narx'}),400
        if key in ('start_bonus','ref_bonus','min_topup','max_tts') and not (0<=int(val)<=100000000):return jsonify({'error':'Noto‘g‘ri qiymat'}),400
        if key=='amounts' and (not val or not all(x.strip().isdigit() for x in val.split(','))):return jsonify({'error':'Summalarni vergul bilan yozing.'}),400
        if len(val)>200:return jsonify({'error':'Juda uzun qiymat'}),400
        set_cfg(key,val);return jsonify({'message':'Sozlama saqlandi.'})
    except ValueError as e:return jsonify({'error':str(e)}),400

@flask_app.route('/api/admin/balance',methods=['POST'])
def admin_balance():
    try:
        _admin_auth();d=request.get_json(silent=True) or {};uid=int(d['uid']);delta=int(d['delta'])
        if not 0<uid or abs(delta)>1000000000:return jsonify({'error':'ID/summa xato'}),400
        with db:
            cur=db.execute('UPDATE users SET balance=balance+? WHERE id=? AND balance+?>=0',(delta,uid,delta))
        if cur.rowcount!=1:return jsonify({'error':'Foydalanuvchi yo‘q yoki balans manfiy bo‘ladi.'}),400
        return jsonify({'message':f'Balans o‘zgardi: {fmt(get_user(uid)["bal"])} so‘m'})
    except (ValueError,KeyError) as e:return jsonify({'error':str(e)}),400

@flask_app.route('/api/admin/payments')
def admin_payments():
    try:
        _admin_auth();rows=db.execute('SELECT id,uid,amount,status,receipt_sent FROM payments ORDER BY id DESC LIMIT 50').fetchall()
        return jsonify({'payments':[{'id':i,'uid':uid,'amount':a,'status':status,'receipt':bool(receipt)} for i,uid,a,status,receipt in rows]})
    except ValueError as e:return jsonify({'error':str(e)}),401

@flask_app.route('/api/admin/payment',methods=['POST'])
def admin_payment():
    try:
        _admin_auth();d=request.get_json(silent=True) or {};pid=int(d['id']);status=str(d['status'])
        if status not in ('ok','no'):return jsonify({'error':'Status xato'}),400
        db.execute('BEGIN IMMEDIATE')
        r=db.execute('SELECT uid,amount,status,receipt_sent FROM payments WHERE id=?',(pid,)).fetchone()
        if not r or r[2]!='wait' or not r[3]:db.rollback();return jsonify({'error':'Chek yuborilmagan yoki oldin tekshirilgan.'}),400
        db.execute('UPDATE payments SET status=? WHERE id=?',(status,pid))
        if status=='ok':db.execute('UPDATE users SET balance=balance+? WHERE id=?',(r[1],r[0]))
        db.commit()
        try:asyncio.run(bot_notify(r[0], '✅ To‘lov tasdiqlandi.' if status=='ok' else '❌ To‘lov rad etildi.'))
        except Exception:logging.exception('Payment notification')
        return jsonify({'message':'Chek ko‘rib chiqildi.'})
    except (ValueError,KeyError) as e:
        db.rollback();return jsonify({'error':str(e)}),400

async def bot_notify(uid,message):
    from telegram import Bot
    async with Bot(TOKEN) as bot:await bot.send_message(chat_id=uid,text=message)

@flask_app.route('/api/receipt',methods=['POST'])
def api_receipt():
    try:
        uid,_,_=_api_auth();pid=int(request.form.get('payment_id','0'));f=request.files.get('receipt')
        if not f:return jsonify({'error':'Chek faylini tanlang.'}),400
        r=db.execute("SELECT amount,status FROM payments WHERE id=? AND uid=?",(pid,uid)).fetchone()
        if not r or r[1]!='wait':return jsonify({'error':'To‘lov so‘rovi topilmadi.'}),404
        file_data=f.read(8*1024*1024+1)
        if len(file_data)>8*1024*1024:return jsonify({'error':'Chek 8 MB dan oshmasin.'}),413
        ext=os.path.splitext(f.filename or '')[1].lower()
        if ext not in ('.png','.jpg','.jpeg','.webp','.pdf'):return jsonify({'error':'PNG, JPG, WEBP yoki PDF yuboring.'}),400
        count=0
        for aid in admin_ids():
            try:
                asyncio.run(bot_send_receipt(aid,io.BytesIO(file_data),f'💳 Mini App chek #{pid}\n👤 {uid}\n💰 {fmt(r[0])} so‘m',pid,ext))
                count+=1
            except Exception:logging.exception('Receipt send to admin')
        if not count:return jsonify({'error':'Adminga yuborib bo‘lmadi. Qayta urinib ko‘ring.'}),503
        db.execute('UPDATE payments SET receipt_sent=1 WHERE id=? AND uid=?',(pid,uid));db.commit()
        return jsonify({'ok':True})
    except ValueError as e:return jsonify({'error':str(e)}),400

async def bot_send_receipt(aid,buf,caption,pid,ext):
    from telegram import Bot
    buf.name='receipt'+ext
    kb=M([[B('✅ Tasdiqlash',callback_data=f'pok:{pid}'),B('❌ Rad',callback_data=f'pno:{pid}')]])
    async with Bot(TOKEN) as bot:
        if ext=='.pdf': await bot.send_document(aid,document=buf,caption=caption,reply_markup=kb)
        else: await bot.send_photo(aid,photo=buf,caption=caption,reply_markup=kb)

@flask_app.route('/worker/next')
def worker_next():
    if not _worker_key_ok():return jsonify({'error':'worker auth'}),401
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT j.id,j.uid,j.model_id,j.prompt,j.negative,j.params,m.name,m.kind,m.workflow FROM ai_jobs j JOIN ai_models m ON m.id=j.model_id WHERE j.status='queued' AND m.enabled=1 ORDER BY j.id LIMIT 1").fetchone()
        if not row:db.rollback();return jsonify({'job':None})
        jid,uid,mid,prompt,negative,params,name,kind,workflow=row
        db.execute("UPDATE ai_jobs SET status='running',worker_id=?,updated=? WHERE id=?",(S('worker_name'),int(time.time()),jid));db.commit()
        return jsonify({'job':{'id':jid,'uid':uid,'model_id':mid,'prompt':prompt,'negative':negative,'params':json.loads(params or '{}'),'name':name,'kind':kind,'workflow':workflow or ''}})
    except Exception:db.rollback();logging.exception('worker_next');return jsonify({'error':'queue error'}),500

@flask_app.route('/worker/result',methods=['POST'])
def worker_result():
    if not _worker_key_ok():return jsonify({'error':'worker auth'}),401
    jid=_json_int(request.form.get('job_id')); status=request.form.get('status','failed')
    err=str(request.form.get('error',''))[:500];f=request.files.get('file')
    if status not in ('done','failed'):return jsonify({'error':'status xato'}),400
    if status=='done' and not f:return jsonify({'error':'fayl yo‘q'}),400
    path=''
    if status=='done':
        ext=os.path.splitext(f.filename or '')[1].lower()
        if ext not in ('.png','.jpg','.jpeg','.webp','.mp4','.webm','.gif'):
            return jsonify({'error':'Fayl turi xato'}),400
        root='/tmp/ai_results';os.makedirs(root,exist_ok=True)
        path=os.path.join(root,f'{jid}{ext}')
        f.save(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT uid,cost,status FROM ai_jobs WHERE id=?",(jid,)).fetchone()
        if not row:db.rollback();return jsonify({'error':'job yo‘q'}),404
        uid,cost,old=row
        if old!='running':db.rollback();return jsonify({'error':'Bu buyurtma allaqachon yakunlangan.'}),409
        if status=='done':
            kind='video' if os.path.splitext(path)[1].lower() in ('.mp4','.webm','.gif') else 'image'
            db.execute("UPDATE ai_jobs SET status='done',result_path=?,result_type=?,error='',updated=? WHERE id=?",(path,kind,int(time.time()),jid))
        else:
            db.execute("UPDATE ai_jobs SET status='failed',error=?,updated=? WHERE id=?",(err or 'Worker xatosi',int(time.time()),jid))
            db.execute('UPDATE users SET balance=balance+? WHERE id=?',(cost,uid))
        db.commit()
        if status=='done':
            try:
                if kind=='video':
                    with open(path,'rb') as fh:asyncio.run(bot_send_video(uid,fh,caption=f'🎬 #{jid} Tayyor'))
                else:
                    with open(path,'rb') as fh:asyncio.run(bot_send_photo(uid,fh,caption=f'🎨 #{jid} Tayyor'))
            except Exception:logging.exception('media delivery: job #%s',jid)
        return jsonify({'ok':True,'refunded':cost if status=='failed' else 0})
    except Exception:
        db.rollback(); logging.exception('worker result');return jsonify({'error':'Natija qayd etilmadi.'}),500

async def bot_send_photo(uid,fh,caption=''):
    # Temporary standalone bot client for worker callback; token never leaves server-side code.
    from telegram import Bot
    async with Bot(TOKEN) as b: await b.send_photo(chat_id=uid,photo=fh,caption=caption)

async def bot_send_video(uid,fh,caption=''):
    from telegram import Bot
    async with Bot(TOKEN) as b: await b.send_video(chat_id=uid,video=fh,caption=caption,supports_streaming=True)

@flask_app.route('/admin')
def admin_page():
    # Admin uses the same authenticated Mini App UI; opening /admin from Telegram keeps initData available.
    return WEB_APP_HTML

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
    global BOT_USERNAME
    if not BOT_USERNAME:
        try:
            from telegram import Bot
            async def _username():
                async with Bot(TOKEN) as b:return (await b.get_me()).username or ''
            BOT_USERNAME=asyncio.run(_username())
        except Exception as exc:logging.warning('BOT_USERNAME olinmadi: %s',exc)
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
