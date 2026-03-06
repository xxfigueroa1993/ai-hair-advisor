"""
SupportRD — Aria AI Hair Advisor
World-class PWA rebuild. Starbucks-tier architecture.
- App shell with instant load
- MediaRecorder + Web Speech API dual-mode voice
- Offline-first service worker
- Native bottom-nav app experience
- No browser chrome in standalone mode
- 60fps CSS animations only
- Skeleton screens, not spinners
"""

import os, json, sqlite3, datetime, hashlib, secrets, threading, random, re, base64
import urllib.request, urllib.parse
from flask import Flask, request, jsonify, Response, redirect

app = Flask(__name__)

# ── ENVIRONMENT ───────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY      = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY         = os.environ.get("OPENAI_API_KEY", "")
ADMIN_KEY              = os.environ.get("ADMIN_KEY", "srd_admin_2024")
STRIPE_SECRET          = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID        = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET  = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
APP_BASE_URL           = os.environ.get("APP_BASE_URL", "https://ai-hair-advisor.onrender.com")
GOOGLE_CLIENT_ID       = os.environ.get("GOOGLE_CLIENT_ID", "")
SMTP_USER              = os.environ.get("SMTP_USER", "")
SMTP_PASS              = os.environ.get("SMTP_PASS", "")
FREE_RESPONSE_LIMIT    = 3
SUBSCRIPTION_PRICE_USD = 80
SHOPIFY_STORE          = os.environ.get("SHOPIFY_STORE", "supportrd.myshopify.com")
SHOPIFY_ADMIN_TOKEN    = os.environ.get("SHOPIFY_ADMIN_TOKEN", "")

# ── DATABASE ──────────────────────────────────────────────────────────────────
DB_PATH = "/tmp/aria_v2.db"

def get_db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    return con

def init_db():
    con = get_db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT,
        email            TEXT UNIQUE,
        password_hash    TEXT,
        google_id        TEXT,
        shopify_id       TEXT,
        avatar_url       TEXT,
        is_premium       INTEGER DEFAULT 0,
        premium_source   TEXT,
        premium_expires  TEXT,
        stripe_customer  TEXT,
        stripe_sub_id    TEXT,
        reset_token      TEXT,
        reset_expires    TEXT,
        created_at       TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS profiles (
        user_id        INTEGER PRIMARY KEY,
        hair_type      TEXT,
        hair_concerns  TEXT,
        treatments     TEXT,
        products_tried TEXT,
        heat_usage     TEXT,
        water_type     TEXT,
        updated_at     TEXT
    );
    CREATE TABLE IF NOT EXISTS chat_history (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        role       TEXT,
        content    TEXT,
        ts         TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS events (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        ts       TEXT,
        lang     TEXT,
        user_msg TEXT,
        product  TEXT,
        concern  TEXT,
        session  TEXT
    );
    CREATE TABLE IF NOT EXISTS movement (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        ts      TEXT,
        msg     TEXT,
        city    TEXT
    );
    CREATE TABLE IF NOT EXISTS premium_codes (
        code       TEXT PRIMARY KEY,
        used_by    INTEGER,
        used_at    TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    con.commit(); con.close()

init_db()

# ── AI PROMPTS ────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Aria — a warm, knowledgeable, luxury hair care advisor for SupportRD, a professional Dominican hair care brand. You have deep expertise in hair science, scalp health, and hair culture across all ethnicities.

YOUR PRODUCTS:
- Formula Exclusiva ($55): Professional all-in-one treatment. Apply on dry or damp hair; for wash use 1oz for 5 min in dryer then rinse. Safe for whole family including children. Best for: damaged, weak, breaking, thinning, severely dry, multi-problem hair.
- Laciador Crece ($40): Hair restructurer that gives softness, elasticity, natural styling, shine, and stimulates growth by activating dead cells. Best for: dry hair, frizz, lack of shine, growth, strengthening, styling.
- Gotero Rapido ($55): Fast dropper that stimulates dead scalp cells, promotes hair growth, eliminates scalp parasites, removes obstructions, and regenerates lost hair. Use on scalp every night then remove. Best for: hair loss, scalp issues, slow growth, thinning, parasites.
- Gotitas Brillantes ($30): Gives softness, better fall to hairstyle, shine and beauty. Use after any hairstyle or anytime. Adds warmth and evenness. Best for: finishing, shine, frizz control, styling touch-up.
- Mascarilla - Deep Natural Blender & Avocado ($25): Conditions, gives shine and strength to dry or damaged hair. Best for: deep conditioning, dry/damaged hair, shine boost.
- Shampoo with Aloe Vera & Rosemary ($20): Cleanses, conditions, stimulates dead cells, strengthens and increases hair. Massage 2-3 min with fingertips into scalp. Best for: scalp stimulation, strengthening, growth, daily cleanse.

HAIR TYPE RULES:
- African/Black hair + dry: Laciador Crece | oily: Gotero Rapido | damaged: Formula Exclusiva
- Asian hair + dry: Formula Exclusiva | oily: Gotero Rapido
- Hispanic/Latino hair + styling/shine: Laciador Crece | loss/growth: Gotero Rapido
- Caucasian hair + damaged: Formula Exclusiva | oily scalp: Gotero Rapido
- Any hair + severe damage/breakage/falling out: Formula Exclusiva (overrides all)
- Any hair + scalp issues/parasites/growth: Gotero Rapido
- Any hair + needs shine/finish: Gotitas Brillantes
- Any hair + deep conditioning: Mascarilla
- Daily cleanse: Shampoo with Aloe Vera & Rosemary

CONSULTATION STYLE:
- You are a knowledgeable friend, not a chatbot. Be warm, confident, conversational.
- Ask diagnostic questions about their full hair history: products used, heat tools, chemical treatments, diet, stress, water type.
- Build on conversation history. Reference what they told you before.
- Keep responses to 2-4 sentences for voice. Never use "I recommend" — say "For your hair, [Product] is exactly what you need."
- Naturally mention your products every 3-4 exchanges.
- Occasionally say: "If you want a 1-on-1 with a live advisor, message us on WhatsApp at 829-233-2670"

OFF-TOPIC REDIRECT:
- If they bring up unrelated topics, acknowledge warmly and redirect back to hair.
- Connect topics back to hair when possible: "Stress from that can actually affect hair health..."

Respond ONLY with your answer. No preamble. No "Sure!" or "Of course!".
If the language code indicates non-English, respond entirely in that language."""

FREE_SYSTEM_PROMPT = """You are Aria, a hair care advisor for SupportRD. Give ONE brief, helpful product recommendation in 2-3 sentences max. Mention product name and price. End with: "For deeper analysis and your full Hair Health Score, upgrade to SupportRD Premium — 7 days free." Keep it warm."""

# ── AUTH HELPERS ──────────────────────────────────────────────────────────────
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def make_session_token(user_id):
    raw = f"{user_id}:{secrets.token_hex(16)}"
    return base64.b64encode(raw.encode()).decode().rstrip("=")

def decode_session_token(token):
    try:
        decoded = base64.b64decode(token + "==").decode()
        uid = int(decoded.split(":")[0])
        return uid
    except:
        return None

def get_current_user():
    token = request.headers.get("X-Auth-Token") or request.args.get("token")
    if not token: return None
    uid = decode_session_token(token)
    if not uid: return None
    try:
        con = get_db()
        row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        con.close()
        return dict(row) if row else None
    except:
        return None

def is_subscribed(user_id):
    try:
        con = get_db()
        row = con.execute("SELECT is_premium,premium_expires FROM users WHERE id=?", (user_id,)).fetchone()
        con.close()
        if not row: return False
        if row["is_premium"]:
            exp = row["premium_expires"]
            if not exp: return True
            try:
                return datetime.datetime.fromisoformat(exp) > datetime.datetime.utcnow()
            except: return True
        return False
    except: return False

def get_session_count(session_id, user_id=None):
    try:
        con = get_db()
        if user_id:
            row = con.execute("SELECT COUNT(*) as c FROM chat_history WHERE user_id=? AND role='assistant'", (user_id,)).fetchone()
        else:
            row = con.execute("SELECT COUNT(*) as c FROM events WHERE session=?", (session_id,)).fetchone()
        con.close()
        return row["c"] if row else 0
    except: return 0

def get_hair_profile(user_id):
    try:
        con = get_db()
        row = con.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        con.close()
        return dict(row) if row else {}
    except: return {}

def save_chat_message(user_id, role, content):
    try:
        con = get_db()
        con.execute("INSERT INTO chat_history (user_id,role,content) VALUES (?,?,?)", (user_id, role, content))
        con.commit(); con.close()
    except: pass

def extract_product(text):
    t = text.lower()
    if "formula exclusiva" in t: return "Formula Exclusiva"
    if "laciador" in t or "crece" in t: return "Laciador Crece"
    if "gotero" in t or "rapido" in t: return "Gotero Rapido"
    if "gotitas" in t or "brillantes" in t: return "Gotitas Brillantes"
    if "mascarilla" in t: return "Mascarilla"
    if "shampoo" in t: return "Shampoo"
    return ""

def extract_concern(text):
    t = text.lower()
    if any(w in t for w in ["damag","break","weak","fall","shed","bald","thin"]): return "damaged/falling"
    if any(w in t for w in ["dry","moistur","brittle"]): return "dryness"
    if any(w in t for w in ["oil","greasy","sebum"]): return "oily"
    if any(w in t for w in ["grow","growth","length"]): return "growth"
    if any(w in t for w in ["frizz","curl","wave"]): return "texture"
    if any(w in t for w in ["scalp","itch","dand","flak"]): return "scalp"
    return ""

# ── ICON GENERATOR ────────────────────────────────────────────────────────────
def make_icon_png(size):
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        img = Image.new("RGBA", (size,size), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        m = size//16
        draw.ellipse([m,m,size-m,size-m], fill="#c1a3a2")
        m2 = size//5
        draw.ellipse([m2,m2,size-m2,size-m2], fill="#9d7f6a")
        fs = size//2
        try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", fs)
        except: font = ImageFont.load_default()
        bb = draw.textbbox((0,0),"A",font=font)
        x = (size-(bb[2]-bb[0]))//2; y = (size-(bb[3]-bb[1]))//2 - size//20
        draw.text((x,y),"A",fill="#f0ebe8",font=font)
        buf = io.BytesIO(); img.save(buf,"PNG"); return buf.getvalue()
    except:
        import struct, zlib
        def chunk(n,d):
            c=zlib.crc32(n+d)&0xffffffff
            return struct.pack('>I',len(d))+n+d+struct.pack('>I',c)
        raw=b''.join(b'\x00'+bytes([193,163,162])*size for _ in range(size))
        png=b'\x89PNG\r\n\x1a\n'
        png+=chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,2,0,0,0))
        png+=chunk(b'IDAT',zlib.compress(raw))
        png+=chunk(b'IEND',b'')
        return png

_ICON_192 = base64.b64encode(make_icon_png(192)).decode()
_ICON_512 = base64.b64encode(make_icon_png(512)).decode()

# ═════════════════════════════════════════════════════════════════════════════
# PWA SHELL & STATIC
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/manifest.json")
def pwa_manifest():
    return jsonify({
        "name": "Aria — AI Hair Advisor",
        "short_name": "Aria",
        "description": "Your personal AI hair advisor by SupportRD.",
        "start_url": "/?pwa=1",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0d0906",
        "theme_color": "#0d0906",
        "icons": [
            {"src":"/static/icon-192.png","sizes":"192x192","type":"image/png","purpose":"any maskable"},
            {"src":"/static/icon-512.png","sizes":"512x512","type":"image/png","purpose":"any maskable"}
        ],
        "categories": ["health","beauty","lifestyle"],
        "screenshots": []
    })

@app.route("/sw.js")
def service_worker():
    sw = r"""
/* Aria PWA Service Worker v5 — Network-first with offline fallback */
const CACHE = "aria-v5";
const SHELL = ["/", "/dashboard", "/login", "/manifest.json", "/static/icon-192.png"];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => Promise.allSettled(SHELL.map(u => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);

  // Always live for API calls — never cache
  if (url.pathname.startsWith("/api/")) return;
  if (url.pathname.startsWith("/blog")) return;

  e.respondWith(
    fetch(e.request)
      .then(resp => {
        if (resp.ok && resp.status < 400) {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      })
      .catch(() =>
        caches.match(e.request)
          .then(cached => cached || caches.match("/"))
      )
  );
});
"""
    return Response(sw.strip(), mimetype="application/javascript",
                    headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

@app.route("/static/icon-192.png")
def icon_192():
    return Response(base64.b64decode(_ICON_192), mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})

@app.route("/static/icon-512.png")
def icon_512():
    return Response(base64.b64decode(_ICON_512), mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})

@app.route("/api/ping")
def ping():
    return jsonify({"ok": True, "ts": datetime.datetime.utcnow().isoformat()})

@app.route("/google65f6d985572e55c5.html")
def google_verify():
    return "google-site-verification: google65f6d985572e55c5.html"

# ═════════════════════════════════════════════════════════════════════════════
# API ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    """Receive MediaRecorder audio, return transcribed text via Whisper."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio", "fallback": True})
    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()
    mime = audio_file.content_type or "audio/webm"

    if not OPENAI_API_KEY or len(audio_bytes) < 500:
        return jsonify({"text": "", "fallback": True})

    try:
        boundary = "ariaSTT" + secrets.token_hex(6)
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="audio.webm"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode() + audio_bytes + (
            f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="language"\r\nContent-Type: text/plain\r\n\r\nen\r\n'
            f"--{boundary}--\r\n"
        ).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": f"multipart/form-data; boundary={boundary}"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return jsonify({"text": result.get("text","").strip()})
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        return jsonify({"error": err[:200], "fallback": True})
    except Exception as e:
        return jsonify({"error": str(e), "fallback": True})

@app.route("/api/recommend", methods=["POST","OPTIONS"])
def recommend():
    if request.method == "OPTIONS":
        return "", 200
    data      = request.get_json(force=True, silent=True) or {}
    user_text = (data.get("text") or data.get("message") or "").strip()
    lang      = data.get("lang", "en-US")
    history   = data.get("history", [])
    session_id = request.headers.get("X-Session-Id", request.remote_addr or "anon")

    user       = get_current_user()
    subscribed = is_subscribed(user["id"]) if user else False
    count      = get_session_count(session_id, user["id"] if user else None)
    show_paywall = not subscribed and count >= FREE_RESPONSE_LIMIT

    lang_names = {
        "en-US":"English","es-ES":"Spanish","fr-FR":"French",
        "pt-BR":"Portuguese","de-DE":"German","ar-SA":"Arabic",
        "zh-CN":"Mandarin Chinese","hi-IN":"Hindi"
    }
    lang_instr = f"\n\nIMPORTANT: Your ENTIRE response must be in {lang_names.get(lang,'English')}."

    if subscribed:
        profile_context = ""
        if user:
            profile = get_hair_profile(user["id"])
            if profile.get("hair_type") or profile.get("hair_concerns"):
                profile_context = f"""

RETURNING CLIENT PROFILE:
- Name: {user.get("name","this client")}
- Hair type: {profile.get("hair_type","unknown")}
- Known concerns: {profile.get("hair_concerns","none saved")}
- Treatments: {profile.get("treatments","none saved")}
- Products tried: {profile.get("products_tried","none saved")}
Reference this naturally."""
            save_chat_message(user["id"], "user", user_text)
        active_prompt = SYSTEM_PROMPT + profile_context + lang_instr
        max_tokens = 350
    else:
        active_prompt = FREE_SYSTEM_PROMPT + lang_instr
        max_tokens = 180

    if not ANTHROPIC_API_KEY:
        return jsonify({"recommendation": None, "error": "No API key configured"}), 500

    messages = history[-8:] + [{"role":"user","content":user_text}]
    payload  = {"model":"claude-haiku-4-5-20251001","max_tokens":max_tokens,
                 "system":active_prompt,"messages":messages}
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,
                 "anthropic-version":"2023-06-01"}
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            result = json.loads(resp.read().decode())
            rec = result["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        return jsonify({"recommendation":None,"error":f"API error: {err[:200]}"}), 500
    except Exception as e:
        return jsonify({"recommendation":None,"error":str(e)}), 500

    if subscribed and user:
        save_chat_message(user["id"], "assistant", rec)
    try:
        con = get_db()
        con.execute("INSERT INTO events (ts,lang,user_msg,product,concern,session) VALUES (?,?,?,?,?,?)",
                    (datetime.datetime.utcnow().isoformat(), lang, user_text[:200],
                     extract_product(rec), extract_concern(user_text), session_id))
        con.commit(); con.close()
    except: pass

    return jsonify({
        "recommendation": rec,
        "show_paywall":   show_paywall,
        "responses_used": count+1,
        "is_premium":     subscribed
    })

@app.route("/api/auth/register", methods=["POST"])
def register():
    data  = request.get_json(force=True, silent=True) or {}
    name  = (data.get("name","")).strip()
    email = (data.get("email","")).strip().lower()
    pw    = data.get("password","")
    if not email or not pw:
        return jsonify({"error":"Email and password required"}), 400
    try:
        con = get_db()
        con.execute("INSERT INTO users (name,email,password_hash) VALUES (?,?,?)",
                    (name, email, hash_pw(pw)))
        con.commit()
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        con.close()
        u = dict(row)
        return jsonify({"ok":True,"token":make_session_token(u["id"]),
                        "name":u["name"],"email":u["email"],"is_premium":u["is_premium"]})
    except sqlite3.IntegrityError:
        return jsonify({"error":"Email already registered"}), 400
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.route("/api/auth/login", methods=["POST"])
def login_api():
    data  = request.get_json(force=True, silent=True) or {}
    email = (data.get("email","")).strip().lower()
    pw    = data.get("password","")
    if not email or not pw:
        return jsonify({"error":"Email and password required"}), 400
    con = get_db()
    row = con.execute("SELECT * FROM users WHERE email=? AND password_hash=?",
                      (email, hash_pw(pw))).fetchone()
    con.close()
    if not row: return jsonify({"error":"Invalid email or password"}), 401
    u = dict(row)
    return jsonify({"ok":True,"token":make_session_token(u["id"]),
                    "name":u["name"],"email":u["email"],"is_premium":u["is_premium"],
                    "avatar":u.get("avatar_url","")})

@app.route("/api/auth/logout", methods=["POST"])
def logout_api():
    return jsonify({"ok": True})

@app.route("/api/auth/google", methods=["POST"])
def google_auth():
    data = request.get_json(force=True, silent=True) or {}
    cred = data.get("credential","")
    if not cred: return jsonify({"error":"No credential"}), 400
    try:
        parts   = cred.split(".")
        payload = json.loads(base64.b64decode(parts[1]+"==").decode())
        email   = payload.get("email","").lower()
        name    = payload.get("name","")
        gid     = payload.get("sub","")
        avatar  = payload.get("picture","")
        if not email: return jsonify({"error":"No email in token"}), 400
        con = get_db()
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row:
            con.execute("UPDATE users SET google_id=?,avatar_url=?,name=? WHERE email=?",
                        (gid, avatar, name or dict(row)["name"], email))
        else:
            con.execute("INSERT INTO users (name,email,google_id,avatar_url) VALUES (?,?,?,?)",
                        (name,email,gid,avatar))
        con.commit()
        u = dict(con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())
        con.close()
        return jsonify({"ok":True,"token":make_session_token(u["id"]),
                        "name":u["name"],"email":u["email"],"is_premium":u["is_premium"],
                        "avatar":avatar})
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.route("/api/auth/shopify-verify", methods=["POST"])
def shopify_verify():
    data  = request.get_json(force=True, silent=True) or {}
    email = (data.get("email","")).strip().lower()
    name  = data.get("name","")
    sid   = str(data.get("id",""))
    if not email: return jsonify({"error":"No email"}), 400
    con = get_db()
    row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if row:
        con.execute("UPDATE users SET shopify_id=?,name=? WHERE email=?",
                    (sid, name or dict(row)["name"], email))
    else:
        con.execute("INSERT INTO users (name,email,shopify_id) VALUES (?,?,?)", (name,email,sid))
    con.commit()
    u = dict(con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())
    con.close()
    return jsonify({"ok":True,"token":make_session_token(u["id"]),
                    "name":u["name"],"email":u["email"],"is_premium":u["is_premium"]})

@app.route("/api/auth/me", methods=["GET"])
def me():
    user = get_current_user()
    if not user: return jsonify({"error":"Not authenticated"}), 401
    return jsonify({"ok":True,"name":user["name"],"email":user["email"],
                    "avatar":user.get("avatar_url",""),"is_premium":is_subscribed(user["id"])})

@app.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    data  = request.get_json(force=True, silent=True) or {}
    email = (data.get("email","")).strip().lower()
    try:
        tok  = secrets.token_urlsafe(32)
        exp  = (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).isoformat()
        con  = get_db()
        con.execute("UPDATE users SET reset_token=?,reset_expires=? WHERE email=?", (tok,exp,email))
        con.commit(); con.close()
        link = f"{APP_BASE_URL}/login?reset_token={tok}"
        if SMTP_USER and SMTP_PASS:
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(f"Reset your Aria password:\n\n{link}\n\nExpires in 2 hours.")
            msg["Subject"] = "Reset your Aria password"
            msg["From"]    = SMTP_USER
            msg["To"]      = email
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
    except: pass
    return jsonify({"ok":True})

@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data  = request.get_json(force=True, silent=True) or {}
    tok   = data.get("token","")
    pw    = data.get("password","")
    if not tok or not pw: return jsonify({"error":"Missing fields"}), 400
    con = get_db()
    row = con.execute("SELECT * FROM users WHERE reset_token=?", (tok,)).fetchone()
    if not row: con.close(); return jsonify({"error":"Invalid token"}), 400
    u = dict(row)
    if u.get("reset_expires"):
        try:
            if datetime.datetime.fromisoformat(u["reset_expires"]) < datetime.datetime.utcnow():
                con.close(); return jsonify({"error":"Token expired"}), 400
        except: pass
    con.execute("UPDATE users SET password_hash=?,reset_token=NULL,reset_expires=NULL WHERE id=?",
                (hash_pw(pw), u["id"]))
    con.commit(); con.close()
    return jsonify({"ok":True,"token":make_session_token(u["id"])})

@app.route("/api/profile", methods=["GET","POST"])
def profile():
    user = get_current_user()
    if not user: return jsonify({"error":"Not authenticated"}), 401
    con = get_db()
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        now  = datetime.datetime.utcnow().isoformat()
        con.execute("""INSERT INTO profiles (user_id,hair_type,hair_concerns,treatments,products_tried,heat_usage,water_type,updated_at)
            VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
            hair_type=excluded.hair_type, hair_concerns=excluded.hair_concerns,
            treatments=excluded.treatments, products_tried=excluded.products_tried,
            heat_usage=excluded.heat_usage, water_type=excluded.water_type, updated_at=excluded.updated_at""",
            (user["id"], data.get("hair_type",""), data.get("hair_concerns",""),
             data.get("treatments",""), data.get("products_tried",""),
             data.get("heat_usage",""), data.get("water_type",""), now))
        con.commit(); con.close()
        return jsonify({"ok":True})
    row = con.execute("SELECT * FROM profiles WHERE user_id=?", (user["id"],)).fetchone()
    con.close()
    return jsonify(dict(row) if row else {})

@app.route("/api/history", methods=["GET"])
def history():
    user = get_current_user()
    if not user: return jsonify({"history":[]})
    con = get_db()
    rows = con.execute(
        "SELECT role,content,ts FROM chat_history WHERE user_id=? ORDER BY id DESC LIMIT 40",
        (user["id"],)).fetchall()
    con.close()
    return jsonify({"history":[dict(r) for r in rows]})

@app.route("/api/history/clear", methods=["POST"])
def clear_history():
    user = get_current_user()
    if not user: return jsonify({"error":"Not authenticated"}), 401
    con = get_db()
    con.execute("DELETE FROM chat_history WHERE user_id=?", (user["id"],))
    con.commit(); con.close()
    return jsonify({"ok":True})

@app.route("/api/subscription/status", methods=["GET"])
def subscription_status():
    user = get_current_user()
    if not user: return jsonify({"is_premium":False,"responses_used":0,"free_limit":FREE_RESPONSE_LIMIT})
    sid   = request.headers.get("X-Session-Id","anon")
    count = get_session_count(sid, user["id"])
    return jsonify({"is_premium":is_subscribed(user["id"]),"responses_used":count,"free_limit":FREE_RESPONSE_LIMIT})

@app.route("/api/subscription/checkout", methods=["POST"])
def create_checkout():
    user = get_current_user()
    if not user: return jsonify({"error":"Must be logged in to subscribe"}), 401
    if STRIPE_SECRET and STRIPE_PRICE_ID:
        try:
            params = {
                "mode":"subscription",
                "payment_method_types[]":"card",
                "line_items[0][price]":STRIPE_PRICE_ID,
                "line_items[0][quantity]":"1",
                "subscription_data[trial_period_days]":"7",
                "success_url":f"{APP_BASE_URL}/subscription/success",
                "cancel_url":f"{APP_BASE_URL}/subscription/cancel",
                "customer_email":user["email"]
            }
            body = urllib.parse.urlencode(params).encode()
            req  = urllib.request.Request(
                "https://api.stripe.com/v1/checkout/sessions", data=body,
                headers={"Authorization":f"Bearer {STRIPE_SECRET}",
                         "Content-Type":"application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=15) as r:
                sess = json.loads(r.read().decode())
            return jsonify({"checkout_url":sess["url"]})
        except Exception as e:
            return jsonify({"setup_needed":True,"error":str(e)})
    return jsonify({"setup_needed":True})

@app.route("/api/subscription/webhook", methods=["POST"])
def stripe_webhook():
    try:
        payload = request.get_data()
        event   = json.loads(payload)
        etype   = event.get("type","")
        if etype in ["checkout.session.completed","customer.subscription.created",
                     "invoice.payment_succeeded"]:
            obj   = event["data"]["object"]
            email = (obj.get("customer_email") or obj.get("customer_details",{}).get("email","")).lower()
            if email:
                exp = (datetime.datetime.utcnow() + datetime.timedelta(days=32)).isoformat()
                con = get_db()
                con.execute("UPDATE users SET is_premium=1,premium_expires=?,premium_source='stripe' WHERE email=?",
                            (exp,email))
                con.commit(); con.close()
        elif etype in ["customer.subscription.deleted","invoice.payment_failed"]:
            obj   = event["data"]["object"]
            email = (obj.get("customer_email","")).lower()
            if email:
                con = get_db()
                con.execute("UPDATE users SET is_premium=0 WHERE email=?", (email,))
                con.commit(); con.close()
    except: pass
    return jsonify({"ok":True})

@app.route("/api/subscription/activate-shopify", methods=["POST"])
def activate_shopify():
    data  = request.get_json(force=True, silent=True) or {}
    email = (data.get("email","")).lower()
    key   = request.headers.get("X-Admin-Key","")
    if key != ADMIN_KEY: return jsonify({"error":"Unauthorized"}), 401
    exp = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
    con = get_db()
    con.execute("UPDATE users SET is_premium=1,premium_expires=?,premium_source='shopify' WHERE email=?",
                (exp,email))
    con.commit(); con.close()
    return jsonify({"ok":True})

@app.route("/api/shopify-order-webhook", methods=["POST"])
def shopify_order_webhook():
    try:
        data  = request.get_json(force=True, silent=True) or {}
        email = (data.get("email","")).lower()
        items = data.get("line_items",[])
        is_prem = any("premium" in (i.get("handle","") + i.get("title","")).lower() for i in items)
        if is_prem and email:
            exp = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
            con = get_db()
            con.execute("UPDATE users SET is_premium=1,premium_expires=?,premium_source='shopify' WHERE email=?",
                        (exp,email))
            con.commit(); con.close()
    except: pass
    return jsonify({"ok":True})

@app.route("/api/admin/generate-code", methods=["POST"])
def generate_code():
    data = request.get_json(force=True, silent=True) or {}
    key  = request.headers.get("X-Admin-Key","") or data.get("admin_key","")
    if key != ADMIN_KEY: return jsonify({"error":"Unauthorized"}), 401
    code = "SRD-" + secrets.token_hex(4).upper()
    con  = get_db()
    con.execute("INSERT OR IGNORE INTO premium_codes (code) VALUES (?)", (code,))
    con.commit(); con.close()
    return jsonify({"ok":True,"code":code})

@app.route("/api/admin/list-codes", methods=["GET"])
def list_codes():
    key = request.args.get("admin_key","")
    if key != ADMIN_KEY: return jsonify({"error":"Unauthorized"}), 401
    con  = get_db()
    rows = con.execute("SELECT code,used_by,used_at,created_at FROM premium_codes ORDER BY created_at DESC").fetchall()
    con.close()
    return jsonify({"codes":[dict(r) for r in rows]})

@app.route("/api/redeem-code", methods=["POST"])
def redeem_code():
    user = get_current_user()
    if not user: return jsonify({"error":"Not authenticated"}), 401
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("code","")).strip().upper()
    con  = get_db()
    row  = con.execute("SELECT * FROM premium_codes WHERE code=? AND used_by IS NULL", (code,)).fetchone()
    if not row: con.close(); return jsonify({"error":"Invalid or already used code"}), 400
    exp = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
    con.execute("UPDATE premium_codes SET used_by=?,used_at=? WHERE code=?",
                (user["id"], datetime.datetime.utcnow().isoformat(), code))
    con.execute("UPDATE users SET is_premium=1,premium_expires=?,premium_source='code' WHERE id=?",
                (exp,user["id"]))
    con.commit(); con.close()
    return jsonify({"ok":True,"message":"Premium activated for 30 days!"})

@app.route("/api/movement", methods=["GET"])
def movement():
    cities  = ["New York","Miami","Los Angeles","Atlanta","Houston","Chicago","Dallas","Toronto","London","São Paulo"]
    topics  = ["hair growth","curl care","damaged hair","scalp health","hair loss","frizz control","moisture routine"]
    templates = ["Someone in {c} just asked about {t}","New consultation: {t}","A client is working on {t}","Just helped someone in {c} with {t}"]
    items = []
    for _ in range(12):
        c = random.choice(cities)
        t = random.choice(topics)
        items.append({"message": random.choice(templates).format(c=c,t=t),
                      "ts": datetime.datetime.utcnow().isoformat()})
    return jsonify({"items": items})

@app.route("/api/hair-trends")
def hair_trends():
    results = []
    lock    = threading.Lock()

    def scrape_reddit():
        try:
            url = "https://www.reddit.com/r/Hair+Haircare+NaturalHair+curlyhair/hot.json?limit=12"
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
            for p in data["data"]["children"][:8]:
                d = p["data"]
                title = d.get("title","")
                if any(kw in title.lower() for kw in ["hair","curl","scalp","growth","damage","frizz","moisture"]):
                    img = d.get("thumbnail","")
                    if img and img.startswith("http"):
                        with lock: results.append({"title":title,"image":img,"source":"reddit","link":"https://reddit.com"+d.get("permalink","")})
        except Exception as e: print(f"Reddit: {e}")

    def scrape_pinterest():
        try:
            query = random.choice(["hair care routine","natural hair","curly hair tips","hair growth"])
            url   = f"https://pinterest.com/search/pins/?q={urllib.parse.quote(query)}"
            req   = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"})
            with urllib.request.urlopen(req, timeout=8) as r:
                html = r.read().decode("utf-8",errors="ignore")
            images = re.findall(r'"url":"(https://i\.pinimg\.com/[^"]+736[^"]+\.jpg)"', html)
            titles = re.findall(r'"title":"([^"]{15,100})"', html)
            hair_t = [t for t in titles if any(kw in t.lower() for kw in ["hair","curl","scalp","growth","damage"])]
            for i,img in enumerate(images[:6]):
                with lock: results.append({"title":hair_t[i] if i<len(hair_t) else query,"image":img,"source":"pinterest","link":"https://auto-engine.onrender.com/blog"})
        except Exception as e: print(f"Pinterest: {e}")

    threads = [threading.Thread(target=f) for f in [scrape_reddit, scrape_pinterest]]
    for t in threads: t.start()
    for t in threads: t.join(timeout=10)
    random.shuffle(results)
    return jsonify({"ok":True,"items":results[:15]})

@app.route("/api/tip", methods=["POST"])
def tip():
    return jsonify({"ok": True})

@app.route("/api/rate-experience", methods=["POST"])
def rate_experience():
    return jsonify({"ok": True})

@app.route("/api/auth/shopify", methods=["GET","POST"])
def shopify_auth():
    return jsonify({"ok": True})

# ═════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/analytics")
def analytics():
    key = request.args.get("key","")
    if key != ADMIN_KEY: return "Unauthorized", 401
    con = get_db()
    uc  = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    pc  = con.execute("SELECT COUNT(*) FROM users WHERE is_premium=1").fetchone()[0]
    ec  = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    recent = con.execute("SELECT ts,lang,user_msg,concern FROM events ORDER BY id DESC LIMIT 20").fetchall()
    con.close()
    rows = "".join(f"<tr><td>{r['ts'][:16]}</td><td>{r['lang']}</td><td>{r['user_msg'][:50]}</td><td>{r['concern']}</td></tr>" for r in recent)
    return f"""<!DOCTYPE html><html><body style='font-family:sans-serif;padding:24px;background:#f8f5f2'>
<h2>SupportRD Analytics</h2><p>Users: <b>{uc}</b> | Premium: <b>{pc}</b> | Events: <b>{ec}</b></p>
<table border=1 cellpadding=6 style='border-collapse:collapse'><tr><th>Time</th><th>Lang</th><th>Message</th><th>Concern</th></tr>{rows}</table>
</body></html>"""

@app.route("/admin-codes")
def admin_codes_page():
    key = request.args.get("key","")
    if key != ADMIN_KEY: return "Unauthorized", 401
    con  = get_db()
    rows = con.execute("SELECT code,used_by,used_at,created_at FROM premium_codes ORDER BY created_at DESC").fetchall()
    con.close()
    items = "".join(f"<tr><td>{r['code']}</td><td>{'Used' if r['used_by'] else 'Available'}</td><td>{r['created_at'][:10]}</td></tr>" for r in rows)
    return f"""<!DOCTYPE html><html><body style='font-family:sans-serif;padding:24px;background:#f8f5f2'>
<h2>Premium Codes</h2>
<form method=post action='/api/admin/generate-code' style='margin-bottom:20px'>
<input type=hidden name=admin_key value='{key}'>
<button>Generate New Code</button></form>
<table border=1 cellpadding=8 style='border-collapse:collapse'><tr><th>Code</th><th>Status</th><th>Created</th></tr>{items}</table>
</body></html>"""

@app.route("/sitemap.xml")
def sitemap():
    urls = [APP_BASE_URL, f"{APP_BASE_URL}/dashboard", f"{APP_BASE_URL}/login"]
    xml  = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls: xml += f"  <url><loc>{u}</loc></url>\n"
    xml += "</urlset>"
    return Response(xml, mimetype="application/xml")

@app.route("/robots.txt")
def robots():
    return Response(f"User-agent: *\nAllow: /\nDisallow: /api\nDisallow: /admin\nSitemap: {APP_BASE_URL}/sitemap.xml\n", mimetype="text/plain")

@app.route("/apps/hair-advisor")
def shopify_proxy():
    return redirect("/")

@app.route("/upload-transcript", methods=["GET","POST"])
def upload_transcript():
    return redirect("/")

@app.route("/api/debug-shopify")
def debug_shopify(): return jsonify({"ok": True})

@app.route("/api/debug-shopify2")
def debug_shopify2(): return jsonify({"ok": True})

@app.route("/api/debug-stripe")
def debug_stripe(): return jsonify({"ok": True})

@app.route("/api/test-register", methods=["GET","POST"])
def test_register(): return jsonify({"ok": True})

@app.route("/api/add-movement", methods=["POST"])
def add_movement(): return jsonify({"ok": True})

# ═════════════════════════════════════════════════════════════════════════════
# PAGE ROUTES — World-class PWA HTML
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return Response(ARIA_PAGE, mimetype="text/html")

@app.route("/dashboard")
def dashboard():
    return Response(DASHBOARD_PAGE, mimetype="text/html")

@app.route("/login")
def login_page():
    page = LOGIN_PAGE.replace('%GOOGLE_CLIENT_ID%', GOOGLE_CLIENT_ID or '')
    return Response(page, mimetype="text/html")

@app.route("/subscription/success")
def subscription_success():
    return Response("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Welcome to Premium</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,300&family=Jost:wght@300&display=swap" rel="stylesheet">
<style>*{box-sizing:border-box;margin:0;padding:0;}body{background:#0d0906;color:#fff;font-family:'Jost',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:24px;}
.wrap{max-width:360px;}.icon{font-size:48px;margin-bottom:20px;}.ttl{font-family:'Cormorant Garamond',serif;font-size:32px;font-style:italic;color:#c1a3a2;margin-bottom:12px;}.sub{font-size:13px;color:rgba(255,255,255,0.45);line-height:1.6;margin-bottom:28px;}
.btn{display:inline-block;padding:14px 28px;background:linear-gradient(135deg,#c1a3a2,#9d7f6a);color:#fff;border-radius:30px;text-decoration:none;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;}</style></head>
<body><div class="wrap"><div class="icon">✦</div><div class="ttl">Welcome to Premium</div>
<div class="sub">Your 7-day free trial has started. Enjoy unlimited Aria consultations, your Hair Health Score, and full history.</div>
<a href="/" class="btn">Talk to Aria</a></div></body></html>""", mimetype="text/html")

@app.route("/subscription/cancel")
def subscription_cancel():
    return Response("""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>No worries</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,300&family=Jost:wght@300&display=swap" rel="stylesheet">
<style>*{box-sizing:border-box;margin:0;padding:0;}body{background:#f0ebe8;font-family:'Jost',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:24px;}
.wrap{max-width:360px;}.ttl{font-family:'Cormorant Garamond',serif;font-size:28px;font-style:italic;color:#0d0906;margin-bottom:12px;}.sub{font-size:13px;color:rgba(0,0,0,0.4);line-height:1.6;margin-bottom:28px;}
.btn{display:inline-block;padding:14px 28px;background:#c1a3a2;color:#fff;border-radius:30px;text-decoration:none;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;}</style></head>
<body><div class="wrap"><div class="ttl">No worries</div>
<div class="sub">You still have free consultations with Aria. Come back whenever you're ready to upgrade.</div>
<a href="/" class="btn">Back to Aria</a></div></body></html>""", mimetype="text/html")

# ═════════════════════════════════════════════════════════════════════════════
# BLOG ROUTES (unchanged from auto-engine)
# ═════════════════════════════════════════════════════════════════════════════
import json as _json, os as _os

BLOG_DIR = "/tmp/srd_blog"

@app.route("/blog")
def blog_index():
    _os.makedirs(BLOG_DIR, exist_ok=True)
    try:
        with open(f"{BLOG_DIR}/index.json","r") as f:
            posts = _json.load(f)
    except: posts = []
    cards = ""
    for p in posts[:30]:
        cards += f"""<a href="/blog/{p.get('handle','')}" class="post-card">
          <div class="pc-date">{p.get('date','')[:10]}</div>
          <div class="pc-title">{p.get('title','')}</div>
          <div class="pc-meta">{(p.get('meta',''))[:100]}</div>
        </a>"""
    if not cards: cards = '<p class="empty">No posts yet — check back soon.</p>'
    return Response(f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hair Care Journal — SupportRD</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;1,400&family=Jost:wght@300;400&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Jost',sans-serif;background:#f0ebe8;color:#0d0906}}
header{{text-align:center;padding:60px 24px 40px;background:#fff;border-bottom:1px solid rgba(193,163,162,0.2)}}
header h1{{font-family:'Cormorant Garamond',serif;font-size:42px;font-style:italic}}
header p{{font-size:13px;color:rgba(0,0,0,0.4);margin-top:8px;letter-spacing:0.08em}}
.container{{max-width:900px;margin:0 auto;padding:40px 24px}}
.section-label{{font-size:11px;color:#c1a3a2;letter-spacing:0.14em;text-transform:uppercase;margin-bottom:12px}}
.section-title{{font-family:'Cormorant Garamond',serif;font-size:30px;font-style:italic;margin-bottom:24px;color:#0d0906}}
.pin-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:52px}}
.pin-card{{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);cursor:pointer;transition:transform 0.2s}}
.pin-card:hover{{transform:translateY(-3px)}}
.pin-card img{{width:100%;height:190px;object-fit:cover;display:block}}
.pin-card .pin-title{{padding:10px 12px;font-size:11px;color:rgba(0,0,0,0.55);line-height:1.4}}
.pin-loading{{text-align:center;padding:40px;color:rgba(0,0,0,0.3);font-size:13px;grid-column:1/-1}}
.post-card{{background:#fff;border-radius:16px;margin-bottom:20px;transition:transform 0.2s;box-shadow:0 2px 12px rgba(0,0,0,0.06);display:block;padding:28px 32px;text-decoration:none;color:inherit}}
.post-card:hover{{transform:translateY(-2px)}}
.pc-date{{font-size:10px;color:#c1a3a2;letter-spacing:0.1em;margin-bottom:6px}}
.pc-title{{font-family:'Cormorant Garamond',serif;font-size:22px;color:#0d0906;margin-bottom:8px;line-height:1.3}}
.pc-meta{{font-size:12px;color:rgba(0,0,0,0.45);line-height:1.6}}
.empty{{text-align:center;color:rgba(0,0,0,0.3);padding:60px;font-size:14px}}
footer{{text-align:center;padding:40px;font-size:12px;color:rgba(0,0,0,0.3)}}
footer a{{color:#c1a3a2;text-decoration:none}}</style></head>
<body><header><h1>Hair Care Journal</h1><p>Expert tips, routines and advice from SupportRD</p></header>
<div class="container">
  <div class="section-label">&#10022; Trending in hair care</div>
  <div class="section-title">What's Inspiring Us This Week</div>
  <div class="pin-grid" id="pin-grid"><div class="pin-loading">Loading trending hair inspiration...</div></div>
  <div class="section-label">&#10022; Expert guides</div>
  <div class="section-title">Hair Care Journal</div>
  {cards}
</div>
<footer><a href="https://supportrd.com">← Back to SupportRD</a> &nbsp;·&nbsp; <a href="/">Try Aria AI →</a></footer>
<script>
var sourceColors={{'reddit':'#ff4500','pinterest':'#e60023','tumblr':'#35465c'}};
fetch('/api/hair-trends').then(function(r){{return r.json();}}).then(function(d){{
  var grid=document.getElementById('pin-grid');
  if(!d.items||!d.items.length){{grid.innerHTML='';return;}}
  grid.innerHTML=d.items.map(function(p){{
    var color=sourceColors[p.source]||'#c1a3a2';
    return '<div class="pin-card" onclick="window.open(\''+p.link+'\',\'_blank\')">'+
      '<img src="'+p.image+'" alt="'+p.title+'" loading="lazy" onerror="this.closest(\'.pin-card\').remove()">'+
      '<div class="pin-title">'+p.title+'<span style="display:block;margin-top:4px;font-size:9px;color:'+color+';text-transform:uppercase;letter-spacing:0.08em">'+p.source+'</span></div></div>';
  }}).join('');
}}).catch(function(){{document.getElementById('pin-grid').innerHTML='';}});
</script></body></html>""", mimetype="text/html")

@app.route("/blog/<handle>")
def blog_post(handle):
    try:
        with open(f"{BLOG_DIR}/{handle}.json","r") as f:
            post = _json.load(f)
    except:
        return "Post not found", 404
    return Response(f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{post['title']} — SupportRD</title>
<meta name="description" content="{post.get('meta','')[:160]}">
<link rel="canonical" href="{APP_BASE_URL}/blog/{handle}">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Jost:wght@300;400&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Jost',sans-serif;background:#f0ebe8;color:#0d0906}}
header{{background:#fff;padding:20px 24px;border-bottom:1px solid rgba(193,163,162,0.2)}}
header a{{font-family:'Cormorant Garamond',serif;font-size:18px;font-style:italic;color:#c1a3a2;text-decoration:none}}
.container{{max-width:740px;margin:0 auto;padding:48px 24px}}
h1{{font-family:'Cormorant Garamond',serif;font-size:clamp(28px,5vw,40px);line-height:1.25;margin-bottom:12px;font-style:italic}}
.meta{{font-size:12px;color:rgba(0,0,0,0.35);margin-bottom:36px;letter-spacing:0.06em}}
.body{{font-size:15px;line-height:1.75;color:rgba(0,0,0,0.72)}}
.body h2{{font-family:'Cormorant Garamond',serif;font-size:24px;font-style:italic;margin:32px 0 12px}}
.body p{{margin-bottom:16px}}
.cta-box{{background:#fff;border-radius:16px;padding:28px;margin-top:48px;text-align:center;border:1px solid rgba(193,163,162,0.2)}}
.cta-box h3{{font-family:'Cormorant Garamond',serif;font-size:24px;font-style:italic;margin-bottom:8px}}
.cta-box p{{font-size:13px;color:rgba(0,0,0,0.45);margin-bottom:18px}}
.cta-btn{{display:inline-block;padding:12px 28px;background:linear-gradient(135deg,#c1a3a2,#9d7f6a);color:#fff;border-radius:24px;text-decoration:none;font-size:11px;letter-spacing:0.12em;text-transform:uppercase}}</style></head>
<body><header><a href="/blog">← Hair Care Journal</a></header>
<div class="container">
  <h1>{post['title']}</h1>
  <div class="meta">{post.get('date','')[:10]}</div>
  <div class="body">{post.get('html','')}</div>
  <div class="cta-box">
    <h3>Get personalized advice from Aria</h3>
    <p>Your AI hair advisor is ready. Ask about your specific hair type, concerns, and get product recommendations tailored just for you.</p>
    <a href="/" class="cta-btn">Talk to Aria Free</a>
  </div>
</div></body></html>""", mimetype="text/html")

# ═════════════════════════════════════════════════════════════════════════════
# WORLD-CLASS PWA PAGES
# ═════════════════════════════════════════════════════════════════════════════

ARIA_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#0d0906">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="Aria">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/static/icon-192.png">
<title>Aria — AI Hair Advisor</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300;1,400&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<style>
/* ── RESET & ROOT ── */
:root {
  --brand: #c1a3a2;
  --accent: #9d7f6a;
  --bg: #0d0906;
  --surface: rgba(255,255,255,0.04);
  --border: rgba(255,255,255,0.07);
  --text: rgba(255,255,255,0.88);
  --muted: rgba(255,255,255,0.35);
  --safe-top: env(safe-area-inset-top, 0px);
  --safe-bot: env(safe-area-inset-bottom, 0px);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
html { height: 100%; overflow: hidden; }
body {
  height: 100%; height: 100dvh;
  background: var(--bg);
  color: var(--text);
  font-family: 'Jost', sans-serif;
  font-weight: 300;
  overflow: hidden;
  touch-action: manipulation;
  user-select: none;
  -webkit-user-select: none;
}

/* ── APP SHELL ── */
#app {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  padding-top: var(--safe-top);
  padding-bottom: var(--safe-bot);
  position: relative;
}

/* ── TOPBAR ── */
#topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 22px 10px;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}
.t-logo {
  font-family: 'Cormorant Garamond', serif;
  font-size: 17px;
  font-style: italic;
  color: var(--brand);
  letter-spacing: 0.04em;
}
.t-right { display: flex; align-items: center; gap: 10px; }
#lang-sel {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 16px;
  padding: 4px 10px;
  font-size: 10px;
  font-family: 'Jost', sans-serif;
  outline: none;
  letter-spacing: 0.08em;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
}
#user-pill {
  display: none;
  align-items: center;
  gap: 7px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 4px 12px 4px 4px;
  text-decoration: none;
  color: var(--text);
  cursor: pointer;
}
#user-av {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--brand);
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; color: #fff;
  overflow: hidden; flex-shrink: 0;
}
#user-av img { width: 100%; height: 100%; object-fit: cover; }
#user-nm { font-size: 10px; letter-spacing: 0.04em; }
#btn-signin {
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 5px 13px;
  cursor: pointer;
  font-family: 'Jost', sans-serif;
  text-decoration: none;
  transition: border-color 0.2s, color 0.2s;
}
#btn-signin:active { border-color: var(--brand); color: var(--brand); }

/* ── SPHERE STAGE ── */
#stage {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: 20px;
}

/* Ambient glow bg */
#stage::before {
  content: '';
  position: absolute;
  width: 300px; height: 300px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(193,163,162,0.06) 0%, transparent 70%);
  pointer-events: none;
  animation: ambient 8s ease-in-out infinite;
}
@keyframes ambient {
  0%,100% { transform: scale(1); opacity: 0.5; }
  50%      { transform: scale(1.2); opacity: 1; }
}

/* ── HALO ── */
#halo {
  width: min(240px, 60vw);
  height: min(240px, 60vw);
  border-radius: 50%;
  position: relative;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.15s ease;
  will-change: transform;
}
#halo:active { transform: scale(0.96); }

#halo-inner {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: radial-gradient(circle at 38% 36%,
    rgba(193,163,162,0.55) 0%,
    rgba(193,163,162,0.20) 40%,
    rgba(193,163,162,0.07) 65%,
    rgba(193,163,162,0.01) 100%);
  box-shadow:
    inset 0 0 60px rgba(193,163,162,0.10),
    0 0   80px rgba(193,163,162,0.55),
    0 0  160px rgba(193,163,162,0.32),
    0 0  300px rgba(193,163,162,0.18),
    0 0  500px rgba(193,163,162,0.08);
  transition: all 0.4s ease;
}

/* Listening state */
#halo.listening #halo-inner {
  animation: pulse-listen 1.0s ease-in-out infinite;
  background: radial-gradient(circle at 38% 36%,
    rgba(157,127,106,0.65) 0%,
    rgba(157,127,106,0.25) 40%,
    rgba(157,127,106,0.08) 65%,
    transparent 100%);
  box-shadow:
    inset 0 0 60px rgba(157,127,106,0.15),
    0 0   80px rgba(157,127,106,0.60),
    0 0  160px rgba(157,127,106,0.35),
    0 0  300px rgba(157,127,106,0.20),
    0 0  500px rgba(157,127,106,0.10);
}
@keyframes pulse-listen {
  0%   { transform: scale(1.00); }
  50%  { transform: scale(1.14); }
  100% { transform: scale(1.00); }
}
/* JS can override with data-level for mic-reactive scaling */
#halo[data-level] #halo-inner { animation: none !important; }

/* Speaking state */
#halo.speaking #halo-inner {
  animation: pulse-speak 0.7s ease-in-out infinite;
  background: radial-gradient(circle at 38% 36%,
    rgba(220,210,210,0.60) 0%,
    rgba(220,210,210,0.22) 40%,
    rgba(220,210,210,0.07) 65%,
    transparent 100%);
  box-shadow:
    inset 0 0 60px rgba(220,210,210,0.12),
    0 0   80px rgba(220,210,210,0.55),
    0 0  160px rgba(220,210,210,0.30),
    0 0  300px rgba(220,210,210,0.15);
}
@keyframes pulse-speak {
  0%,100% { transform: scale(1); }
  50%      { transform: scale(1.04); }
}

/* Mic icon inside halo */
#halo-mic {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
#halo-mic svg {
  width: 32px; height: 32px;
  opacity: 0.45;
  transition: opacity 0.3s;
  stroke: rgba(255,255,255,0.9);
  fill: none;
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
#halo.listening #halo-mic svg { opacity: 0.85; }
#halo.speaking  #halo-mic svg { opacity: 0.0; }

/* Waveform bars (visible when recording) */
#waveform {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s;
}
#halo.listening #waveform { opacity: 1; }
.wave-bar {
  width: 3px;
  height: 20px;
  background: rgba(255,255,255,0.7);
  border-radius: 2px;
  transform-origin: center;
  animation: wave-idle 1.5s ease-in-out infinite;
}
.wave-bar:nth-child(1) { animation-delay: 0.0s; }
.wave-bar:nth-child(2) { animation-delay: 0.15s; }
.wave-bar:nth-child(3) { animation-delay: 0.3s; }
.wave-bar:nth-child(4) { animation-delay: 0.15s; }
.wave-bar:nth-child(5) { animation-delay: 0.0s; }
@keyframes wave-idle {
  0%,100% { transform: scaleY(0.4); }
  50%      { transform: scaleY(1.0); }
}

/* ── TEXT AREA ── */
#state-lbl {
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--muted);
  margin-top: 22px;
  transition: color 0.4s;
  flex-shrink: 0;
}
#resp-box {
  font-family: 'Cormorant Garamond', serif;
  font-size: clamp(14px, 3.8vw, 18px);
  font-style: italic;
  color: rgba(255,255,255,0.65);
  text-align: center;
  line-height: 1.6;
  max-width: min(500px, 88vw);
  min-height: 56px;
  padding: 6px 0;
  transition: opacity 0.3s;
  flex-shrink: 0;
}
#resp-box.loading {
  opacity: 0.4;
  animation: thinking 1.4s ease-in-out infinite;
}
@keyframes thinking {
  0%,100% { opacity: 0.3; }
  50%      { opacity: 0.7; }
}

/* ── BOTTOM BAR ── */
#bottombar {
  padding: 10px 20px 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
#mode-btn {
  font-size: 9px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 6px 16px;
  cursor: pointer;
  font-family: 'Jost', sans-serif;
  transition: border-color 0.2s, color 0.2s;
}
#mode-btn.active { border-color: var(--brand); color: var(--brand); }
#manual-wrap {
  display: none;
  width: 100%;
  max-width: 480px;
  align-items: center;
  gap: 8px;
}
#manual-in {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 11px 18px;
  color: var(--text);
  font-family: 'Jost', sans-serif;
  font-size: 13px;
  font-weight: 300;
  outline: none;
  transition: border-color 0.2s;
  -webkit-user-select: text;
  user-select: text;
}
#manual-in:focus { border-color: var(--brand); }
#manual-in::placeholder { color: rgba(255,255,255,0.2); }
#manual-send {
  width: 42px; height: 42px;
  background: var(--brand);
  border: none; border-radius: 50%;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  transition: background 0.2s;
}
#manual-send:active { background: var(--accent); }
#manual-send svg { width: 16px; height: 16px; fill: #fff; }

/* ── PAYWALL SHEET ── */
#paywall-overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.65);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  z-index: 200;
  align-items: flex-end;
  justify-content: center;
}
#paywall-sheet {
  background: #141009;
  border-radius: 28px 28px 0 0;
  padding: 10px 24px calc(28px + var(--safe-bot)) 24px;
  width: 100%;
  max-width: 500px;
  border-top: 1px solid rgba(193,163,162,0.12);
  animation: sheet-up 0.35s cubic-bezier(0.32, 0.72, 0, 1);
}
@keyframes sheet-up {
  from { transform: translateY(100%); }
  to   { transform: translateY(0); }
}
.pw-handle { width: 36px; height: 4px; background: rgba(255,255,255,0.12); border-radius: 2px; margin: 0 auto 24px; }
.pw-badge { display: inline-block; font-size: 9px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--brand); background: rgba(193,163,162,0.1); border: 1px solid rgba(193,163,162,0.2); border-radius: 12px; padding: 4px 12px; margin-bottom: 14px; }
.pw-ttl { font-family: 'Cormorant Garamond', serif; font-size: 28px; font-style: italic; color: #fff; margin-bottom: 8px; }
.pw-desc { font-size: 12px; color: rgba(255,255,255,0.4); line-height: 1.65; margin-bottom: 20px; }
.pw-price { text-align: center; margin-bottom: 20px; }
.pw-amount { font-family: 'Cormorant Garamond', serif; font-size: 44px; font-style: italic; color: #fff; }
.pw-period { font-size: 14px; color: rgba(255,255,255,0.35); }
.pw-trial { font-size: 11px; color: var(--brand); margin-top: 4px; letter-spacing: 0.04em; }
.pw-feats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 24px; }
.pw-feat { font-size: 11px; color: rgba(255,255,255,0.5); display: flex; align-items: center; gap: 6px; }
.pw-feat::before { content: '✦'; color: var(--brand); font-size: 8px; flex-shrink: 0; }
.pw-cta {
  width: 100%; padding: 16px;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  color: #fff; border: none; border-radius: 28px;
  font-family: 'Jost', sans-serif; font-size: 11px;
  letter-spacing: 0.16em; text-transform: uppercase;
  cursor: pointer; margin-bottom: 10px;
  transition: opacity 0.2s;
}
.pw-cta:active { opacity: 0.85; }
.pw-skip {
  width: 100%; padding: 12px;
  background: transparent; color: rgba(255,255,255,0.2);
  border: 1px solid rgba(255,255,255,0.06); border-radius: 28px;
  font-family: 'Jost', sans-serif; font-size: 10px;
  letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer;
}

/* ── PAYMENT FULLSCREEN ── */
#pay-fs {
  display: none;
  position: fixed; inset: 0;
  background: var(--bg);
  z-index: 300;
  flex-direction: column;
  padding-top: var(--safe-top);
  overflow-y: auto;
}
#pay-fs-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 22px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
#pay-fs-header span { font-family: 'Cormorant Garamond', serif; font-size: 20px; font-style: italic; color: var(--brand); }
#pay-fs-close { background: none; border: none; color: var(--muted); font-size: 24px; cursor: pointer; line-height: 1; }
#pay-fs-body { flex: 1; padding: 32px 24px calc(40px + var(--safe-bot)); max-width: 440px; margin: 0 auto; width: 100%; }
.pay-price-hero { text-align: center; margin-bottom: 32px; }
.pay-price-hero .price-num { font-family: 'Cormorant Garamond', serif; font-size: 72px; font-style: italic; color: #fff; line-height: 1; }
.pay-price-hero .price-per { font-size: 18px; color: var(--muted); }
.pay-price-hero .price-trial { font-size: 12px; color: var(--brand); margin-top: 8px; letter-spacing: 0.06em; }
.pay-feats-card { background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: 22px; margin-bottom: 24px; }
.pay-feats-label { font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); margin-bottom: 16px; }
.pay-feat-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 13px; color: rgba(255,255,255,0.65); }
.pay-feat-row:last-child { border-bottom: none; }
.pay-feat-row::before { content: '✦'; color: var(--brand); font-size: 9px; flex-shrink: 0; }
.pay-go-btn { width: 100%; padding: 18px; background: linear-gradient(135deg, var(--brand), var(--accent)); color: #fff; border: none; border-radius: 32px; font-family: 'Jost', sans-serif; font-size: 12px; letter-spacing: 0.16em; text-transform: uppercase; cursor: pointer; margin-bottom: 12px; }
.pay-note { text-align: center; font-size: 10px; color: var(--muted); line-height: 1.6; }

/* ── INSTALL BANNER ── */
#install-bar {
  display: none;
  position: fixed;
  bottom: 0; left: 0; right: 0;
  background: #141009;
  border-top: 1px solid var(--border);
  padding: 14px 18px calc(14px + var(--safe-bot));
  z-index: 100;
  flex-direction: row;
  align-items: center;
  gap: 12px;
  animation: slide-up 0.4s ease;
}
@keyframes slide-up {
  from { transform: translateY(100%); }
  to   { transform: translateY(0); }
}
#install-bar img { width: 42px; height: 42px; border-radius: 10px; flex-shrink: 0; }
#install-bar-text { flex: 1; }
#install-bar-text strong { display: block; font-size: 13px; font-weight: 400; color: #fff; margin-bottom: 2px; }
#install-bar-text span { font-size: 11px; color: var(--muted); }
#install-do { background: var(--brand); color: #fff; border: none; border-radius: 18px; padding: 8px 16px; font-family: 'Jost', sans-serif; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; cursor: pointer; flex-shrink: 0; }
#install-x { background: none; border: none; color: rgba(255,255,255,0.2); font-size: 22px; cursor: pointer; padding: 4px; flex-shrink: 0; line-height: 1; }
</style>
<script>if("serviceWorker"in navigator){navigator.serviceWorker.register("/sw.js",{scope:"/"}).catch(function(){});}</script>
</head>
<body>
<div id="app">

  <!-- TOP BAR -->
  <div id="topbar">
    <div class="t-logo">SupportRD</div>
    <div class="t-right">
      <select id="lang-sel">
        <option value="en-US">EN</option><option value="es-ES">ES</option>
        <option value="fr-FR">FR</option><option value="pt-BR">PT</option>
        <option value="ar-SA">AR</option><option value="zh-CN">ZH</option>
        <option value="hi-IN">HI</option>
      </select>
      <a href="/dashboard" id="user-pill">
        <div id="user-av"><span id="user-init">?</span></div>
        <span id="user-nm">Dashboard</span>
      </a>
      <a href="/login" id="btn-signin">Sign In</a>
    </div>
  </div>

  <!-- SPHERE STAGE -->
  <div id="stage">
    <div id="halo" role="button" aria-label="Tap to talk to Aria">
      <div id="halo-inner"></div>
      <div id="halo-mic">
        <svg viewBox="0 0 24 24">
          <rect x="9" y="2" width="6" height="11" rx="3"/>
          <path d="M5 10a7 7 0 0 0 14 0"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
        </svg>
      </div>
      <div id="waveform">
        <div class="wave-bar"></div>
        <div class="wave-bar"></div>
        <div class="wave-bar"></div>
        <div class="wave-bar"></div>
        <div class="wave-bar"></div>
      </div>
    </div>
    <div id="state-lbl">Tap to begin</div>
    <div id="resp-box">Your personal AI hair advisor — powered by SupportRD.</div>
  </div>

  <!-- BOTTOM BAR -->
  <div id="bottombar">
    <button id="mode-btn">Manual Mode</button>
    <div id="manual-wrap">
      <input id="manual-in" type="text" inputmode="text" placeholder="Describe your hair concern…" autocomplete="off">
      <button id="manual-send">
        <svg viewBox="0 0 24 24"><path d="M2 12L22 2 16 22 11 13z"/></svg>
      </button>
    </div>
  </div>

</div><!-- #app -->

<!-- PAYWALL BOTTOM SHEET -->
<div id="paywall-overlay" onclick="if(event.target===this)hidePaywall()">
  <div id="paywall-sheet">
    <div class="pw-handle"></div>
    <div class="pw-badge">✦ Unlock Full Experience</div>
    <div class="pw-ttl">SupportRD Premium</div>
    <div class="pw-desc">You've used your free consultations. Upgrade for unlimited expert hair advice, your full Hair Health Score, and conversation history.</div>
    <div class="pw-price">
      <span class="pw-amount">$80</span><span class="pw-period">/month</span>
      <div class="pw-trial">7-day free trial · Cancel anytime</div>
    </div>
    <div class="pw-feats">
      <div class="pw-feat">Unlimited consultations</div>
      <div class="pw-feat">Hair Health Score</div>
      <div class="pw-feat">Full chat history</div>
      <div class="pw-feat">Priority WhatsApp</div>
    </div>
    <button class="pw-cta" onclick="goUpgrade()">Start Free Trial</button>
    <button class="pw-skip" onclick="hidePaywall()">Continue with Free</button>
  </div>
</div>

<!-- PAYMENT FULLSCREEN -->
<div id="pay-fs">
  <div id="pay-fs-header">
    <span>SupportRD Premium</span>
    <button id="pay-fs-close" onclick="document.getElementById('pay-fs').style.display='none'">×</button>
  </div>
  <div id="pay-fs-body">
    <div class="pay-price-hero">
      <div class="price-num">$80</div>
      <div class="price-per">/month</div>
      <div class="price-trial">✦ 7-day free trial included</div>
    </div>
    <div class="pay-feats-card">
      <div class="pay-feats-label">Everything included</div>
      <div class="pay-feat-row">Unlimited Aria AI consultations</div>
      <div class="pay-feat-row">Full Hair Health Score analysis</div>
      <div class="pay-feat-row">Personalized product recommendations</div>
      <div class="pay-feat-row">Complete conversation history</div>
      <div class="pay-feat-row">Priority WhatsApp advisor access</div>
    </div>
    <button class="pay-go-btn" onclick="goUpgrade()">Start Free Trial</button>
    <div class="pay-note">No charge for 7 days. Cancel anytime from your account.</div>
  </div>
</div>

<!-- INSTALL BANNER -->
<div id="install-bar">
  <img src="/static/icon-192.png" alt="Aria">
  <div id="install-bar-text">
    <strong>Install Aria</strong>
    <span>Add to home screen for quick access</span>
  </div>
  <button id="install-do">Install</button>
  <button id="install-x" onclick="dismissInstall()">×</button>
</div>

<script>
// ═══════════════════════════════════════════════════════════
// ARIA PWA — World-class voice interaction engine
// ═══════════════════════════════════════════════════════════

var STATE = 'idle';
var isManual = false;
var history  = [];
var token    = localStorage.getItem('srd_token');
var sessionId = localStorage.getItem('srd_session') || (function(){
  var id = 'sess_' + Math.random().toString(36).slice(2);
  localStorage.setItem('srd_session', id); return id;
})();

// Elements
var halo       = document.getElementById('halo');
var stateLbl   = document.getElementById('state-lbl');
var respBox    = document.getElementById('resp-box');
var langSel    = document.getElementById('lang-sel');
var modeBtn    = document.getElementById('mode-btn');
var manualWrap = document.getElementById('manual-wrap');
var manualIn   = document.getElementById('manual-in');

// ── AUTH BOOTSTRAP ────────────────────────────────────────
if (token) {
  fetch('/api/auth/me', {headers:{'X-Auth-Token':token}})
    .then(function(r){ return r.json(); })
    .then(function(d) {
      if (d.ok) {
        var pill = document.getElementById('user-pill');
        pill.style.display = 'flex';
        document.getElementById('btn-signin').style.display = 'none';
        document.getElementById('user-nm').textContent = (d.name||'').split(' ')[0] || 'Dashboard';
        document.getElementById('user-init').textContent = (d.name||'?')[0].toUpperCase();
        if (d.avatar) document.getElementById('user-av').innerHTML = '<img src="'+d.avatar+'">';
      } else {
        localStorage.removeItem('srd_token');
      }
    }).catch(function(){});
}

// ── VOICE ENGINE — DUAL MODE ──────────────────────────────
// Mode 1: Web Speech API (instant, no cost, works in browser + most PWAs)
// Mode 2: MediaRecorder + server transcription (fallback for strict PWAs)

var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
var recognition = null;
var mediaRecorder = null;
var audioChunks   = [];
var isRecording   = false;
var audioCtx      = null;
var analyser      = null;
var animFn        = null;
var silenceTimer  = null;
var noSpeechTimer = null;
var lastInterim   = '';
var finalText     = '';
var useFallbackSTT = false; // flip to true if Web Speech fails repeatedly
var speechFailCount = 0;

function unlockAudio() {
  // Use shared context
  var ctx = getCtx();
  audioCtx = ctx; // keep audioCtx alias working for micViz
  startAmbient();
}

function setState(s) {
  STATE = s;
  halo.classList.remove('listening','speaking');
  if (s === 'listening') halo.classList.add('listening');
  if (s === 'speaking')  halo.classList.add('speaking');
}

function setIdle(msg) {
  setState('idle');
  stateLbl.textContent = 'Tap to begin';
  if (msg) respBox.textContent = msg;
  respBox.classList.remove('loading');
}

// ── SHARED AUDIO CONTEXT ─────────────────────────────────
var sharedCtx = null;
function getCtx() {
  if (!sharedCtx) sharedCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (sharedCtx.state === 'suspended') sharedCtx.resume();
  return sharedCtx;
}

// ── AMBIENT HUM (idle sphere) ─────────────────────────────
var ambientOsc = null, ambientGain = null;
function startAmbient() {
  try {
    var ctx = getCtx();
    if (ambientOsc) return;
    ambientGain = ctx.createGain();
    ambientGain.gain.setValueAtTime(0, ctx.currentTime);
    ambientGain.gain.linearRampToValueAtTime(0.04, ctx.currentTime + 2);
    ambientGain.connect(ctx.destination);
    ambientOsc = ctx.createOscillator();
    ambientOsc.type = 'sine';
    ambientOsc.frequency.value = 174; // healing frequency, very subtle
    ambientOsc.connect(ambientGain);
    ambientOsc.start();
  } catch(e) {}
}
function stopAmbient() {
  try {
    if (ambientGain) { ambientGain.gain.linearRampToValueAtTime(0, sharedCtx.currentTime + 1); }
    setTimeout(function() { try { if(ambientOsc){ambientOsc.stop();ambientOsc=null;ambientGain=null;} } catch(e){} }, 1100);
  } catch(e) {}
}

// ── SOUND EFFECTS ─────────────────────────────────────────
function playTone(freq, dur, vol, type, ctx2) {
  try {
    var ctx = ctx2 || getCtx();
    var osc  = ctx.createOscillator();
    var gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.type = type || 'sine';
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(freq * 1.3, ctx.currentTime + dur * 0.6);
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(vol || 0.18, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + dur);
  } catch(e) {}
}
// Soft tap click
function playTap() {
  try {
    var ctx = getCtx();
    playTone(600, 0.06, 0.12, 'sine', ctx);
  } catch(e) {}
}
// Two-note chime when Aria responds — warm and airy
function playChime() {
  try {
    var ctx = getCtx();
    playTone(880, 0.25, 0.13, 'sine', ctx);
    setTimeout(function(){ playTone(1108, 0.30, 0.10, 'sine', ctx); }, 120);
    setTimeout(function(){ playTone(1320, 0.35, 0.08, 'sine', ctx); }, 240);
  } catch(e) {}
}
// Error buzz
function playError() {
  try { playTone(220, 0.22, 0.10, 'triangle'); } catch(e) {}
}

// ── SPEECH ENGINE ─────────────────────────────────────────
// The ONLY cross-mobile approach that works 100%:
// Store reply text. On halo tap (real gesture) → speak.
// The halo is already the UX — user taps to start, taps to stop.
// "Tap to hear" becomes the state label. Natural, no extra UI.

var _pendingReply = null;
var _ttsActive    = false;

function warmSpeech() {
  try {
    if (window.speechSynthesis) {
      speechSynthesis.getVoices(); // pre-load voice list
    }
  } catch(e) {}
}

function _doSpeak(text) {
  if (!text || !window.speechSynthesis) { setIdle(); return; }
  _ttsActive = true;

  try { speechSynthesis.cancel(); } catch(e) {}

  var utt = new SpeechSynthesisUtterance(text);
  utt.lang   = langSel ? langSel.value : 'en-US';
  utt.rate   = 0.88;
  utt.pitch  = 1.05;
  utt.volume = 1.0;

  // Best female voice
  try {
    var voices = speechSynthesis.getVoices();
    var want = ['Samantha','Victoria','Karen','Moira','Google US English',
                'Microsoft Zira Desktop','Tessa','Fiona','Hazel'];
    var pick = null;
    for (var i=0; i<want.length && !pick; i++) {
      pick = voices.find(function(v){ return v.name.indexOf(want[i]) > -1; });
    }
    if (!pick) pick = voices.find(function(v){ return /en[-_]/.test(v.lang); });
    if (pick) utt.voice = pick;
  } catch(e) {}

  utt.onstart = function() {
    _pendingReply = null;
    setState('speaking');
    stateLbl.textContent = 'Speaking…';
    playChime();
  };
  utt.onend   = function() { _ttsActive = false; setIdle(); };
  utt.onerror = function(e) {
    _ttsActive = false;
    console.log('TTS error:', e.error);
    // cancelled is normal (user tapped to stop), not an error
    if (e.error !== 'canceled' && e.error !== 'cancelled') setIdle();
  };

  setState('speaking');
  stateLbl.textContent = 'Speaking…';
  try {
    speechSynthesis.speak(utt);
  } catch(e) {
    _ttsActive = false;
    setIdle();
  }
}

// speak() — called from fetch callback (not a gesture).
// Plays chime immediately (Web Audio = no gesture needed).
// Sets pending text + label so next halo tap triggers voice.
// On many Android devices speechSynthesis actually works from
// setTimeout 0 if AudioContext is already unlocked — try it.
function speak(text) {
  if (!text) { setIdle(); return; }
  _pendingReply = text;
  playChime();
  setState('speaking');
  stateLbl.textContent = 'Tap to hear Aria ▶';

  // Try immediate speak (works on desktop + Android Chrome unlocked)
  setTimeout(function() {
    if (_pendingReply && !_ttsActive) {
      _doSpeak(_pendingReply);
    }
  }, 80);
}

// ── MIC REACTIVE ANIMATION ────────────────────────────────
function startMicViz(stream) {
  try {
    // Use sharedCtx (already unlocked via user gesture)
    if (!sharedCtx) sharedCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (sharedCtx.state === 'suspended') sharedCtx.resume();
    audioCtx = sharedCtx;

    var micSrc = sharedCtx.createMediaStreamSource(stream);
    analyser = sharedCtx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.8;
    micSrc.connect(analyser);

    var data = new Uint8Array(analyser.frequencyBinCount);
    var bars = document.querySelectorAll('.wave-bar');

    function tick() {
      if (STATE !== 'listening') {
        bars.forEach(function(b){ b.style.transform=''; b.style.animationPlayState='running'; });
        halo.style.transform = '';
        return;
      }
      analyser.getByteFrequencyData(data);

      // Average voice frequency range (85–255 Hz in FFT bins)
      var sum = 0, count = 0;
      for (var i=2; i<Math.min(data.length, 20); i++) { sum += data[i]; count++; }
      var avg = sum / count / 128.0;
      var level = Math.max(0, Math.min(1, avg));

      // Drive sphere via data-level — CSS handles transform
      var scale = 1 + level * 0.40;
      halo.style.transform = 'scale(' + scale + ')';
      halo.style.transition = 'transform 0.07s ease-out';
      halo.setAttribute('data-level', Math.round(level * 100));

      // Wave bars
      var barStep = Math.floor(data.length / 5);
      var bLevels = [0,0,0,0,0];
      for (var b=0; b<5; b++) {
        var bSum=0;
        for (var j=b*barStep; j<(b+1)*barStep && j<data.length; j++) bSum+=data[j];
        bLevels[b] = Math.max(0.15, Math.min(3.0, (bSum/barStep/80)));
      }
      bars.forEach(function(bar,i){
        bar.style.animationPlayState = 'paused';
        bar.style.transform = 'scaleY(' + bLevels[i] + ')';
        bar.style.transition = 'transform 0.06s ease';
      });

      animFn = requestAnimationFrame(tick);
    }
    animFn = requestAnimationFrame(tick);
  } catch(e) {
    console.log('micViz error:', e);
  }
}

function stopMicViz() {
  cancelAnimationFrame(animFn);
  document.querySelectorAll('.wave-bar').forEach(function(b){
    b.style.transform = '';
    b.style.animationPlayState = 'running';
    b.style.transition = '';
  });
  halo.style.transform = '';
  halo.style.transition = '';
  halo.removeAttribute('data-level');
}

// ── PROCESS TEXT → ARIA ───────────────────────────────────
function processText(text) {
  if (!text || text.trim().length < 2) { setIdle("Didn't catch that — tap to try again."); return; }

  // Show what user said, enter thinking state
  respBox.textContent = text;
  respBox.classList.add('loading');
  STATE = 'thinking'; // distinct from speaking so halo doesn't pulse wrong
  halo.classList.remove('listening','speaking');
  stateLbl.textContent = 'Thinking…';

  // Timeout safety net — if API takes >20s, reset
  var safetyTimer = setTimeout(function() {
    if (STATE === 'thinking') {
      playError();
      setIdle('Taking too long — please try again.');
    }
  }, 20000);

  fetch('/api/recommend', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Token': token || '',
      'X-Session-Id': sessionId
    },
    body: JSON.stringify({
      text:    text.trim(),
      lang:    langSel.value,
      history: history.slice(-8)
    })
  })
  .then(function(r){ return r.json(); })
  .then(function(d) {
    clearTimeout(safetyTimer);
    respBox.classList.remove('loading');
    if (d.error) {
      playError();
      setIdle('Something went wrong. Please try again.');
      return;
    }
    var reply = d.recommendation || d.response || '';
    if (!reply) { playError(); setIdle('No response — please try again.'); return; }
    history.push({role:'user',    content: text});
    history.push({role:'assistant', content: reply});
    if (history.length > 20) history = history.slice(-20);
    respBox.textContent = reply;
    speak(reply); // speak() sets STATE to 'speaking' internally
    if (d.show_paywall) setTimeout(showPaywall, 1800);
  })
  .catch(function(err) {
    clearTimeout(safetyTimer);
    respBox.classList.remove('loading');
    console.log('fetch error:', err);
    playError();
    setIdle('Connection error — please check your internet.');
  });
}

// ── WEB SPEECH API MODE ───────────────────────────────────
var _vizStream = null; // mic stream used for visualization only

function stopVizStream() {
  if (_vizStream) {
    _vizStream.getTracks().forEach(function(t){ t.stop(); });
    _vizStream = null;
  }
  stopMicViz();
}

function startSpeechRecognition() {
  if (!SR) { startMediaRecorder(); return; }

  finalText   = '';
  lastInterim = '';

  // Get mic stream for sphere visualization (separate from SR)
  navigator.mediaDevices.getUserMedia({audio:true, video:false})
    .then(function(stream) {
      _vizStream = stream;
      startMicViz(stream);
    }).catch(function(){});  // silent fail — viz is optional

  recognition = new SR();
  recognition.lang            = langSel.value;
  recognition.continuous      = false;
  recognition.interimResults  = true;
  recognition.maxAlternatives = 1;

  recognition.onstart = function() {
    setState('listening');
    stateLbl.textContent = 'Listening…';
    respBox.textContent  = 'Listening…';
    noSpeechTimer = setTimeout(function() {
      if (STATE !== 'listening') return;
      try { recognition.stop(); } catch(e) {}
      // Retry once silently
      if (speechFailCount < 2) {
        speechFailCount++;
        setTimeout(startSpeechRecognition, 300);
      } else {
        speechFailCount = 0;
        useFallbackSTT = true;
        setIdle("Mic not responding — switched to manual mode.");
        activateManual();
      }
    }, 8000);
  };

  recognition.onresult = function(event) {
    clearTimeout(noSpeechTimer);
    clearTimeout(silenceTimer);
    speechFailCount = 0;
    var interim = ''; finalText = '';
    for (var i=0; i<event.results.length; i++) {
      if (event.results[i].isFinal) finalText += event.results[i][0].transcript + ' ';
      else interim += event.results[i][0].transcript;
    }
    lastInterim = interim;
    var combined = (finalText + interim).trim();
    respBox.textContent = combined || 'Listening…';

    // Pulse sphere based on how many new words arrived
    var wordCount = combined.split(' ').length;
    var scale = Math.min(1.25, 1 + wordCount * 0.015);
    halo.style.transform = 'scale(' + scale + ')';
    clearTimeout(halo._pulseReset);
    halo._pulseReset = setTimeout(function() { halo.style.transform = ''; }, 300);

    silenceTimer = setTimeout(function() {
      try { recognition.stop(); } catch(e) {}
    }, 1800);
  };

  recognition.onend = function() {
    clearTimeout(silenceTimer);
    clearTimeout(noSpeechTimer);
    stopVizStream(); // stop mic viz when SR ends
    if (STATE !== 'listening') return;
    var captured = (finalText + lastInterim).trim();
    if (captured.length > 1) {
      speechFailCount = 0;
      processText(captured);
    } else {
      setIdle("Didn't catch that — tap to try again.");
    }
  };

  recognition.onerror = function(e) {
    clearTimeout(silenceTimer);
    clearTimeout(noSpeechTimer);
    console.log('SR error:', e.error);
    if (e.error === 'no-speech') {
      setIdle("Didn't hear anything — tap to try again.");
    } else if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
      setIdle('Microphone blocked — tap Manual Mode below.');
      activateManual();
    } else if (e.error === 'network') {
      // Network error — try MediaRecorder instead
      useFallbackSTT = true;
      setIdle('Voice service unavailable — use Manual Mode.');
      activateManual();
    } else {
      setIdle('Voice error: ' + e.error + ' — try Manual Mode.');
    }
  };

  try {
    recognition.start();
  } catch(e) {
    setIdle('Could not start mic — use Manual Mode.');
    activateManual();
  }
}

// ── MEDIA RECORDER FALLBACK ───────────────────────────────
function startMediaRecorder() {
  navigator.mediaDevices.getUserMedia({audio:true, video:false})
    .then(function(stream) {
      setState('listening');
      stateLbl.textContent = 'Listening…';
      respBox.textContent  = 'Listening…';
      startMicViz(stream);

      audioChunks  = [];
      isRecording  = true;

      var mimeType = '';
      ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/mp4'].forEach(function(m) {
        if (!mimeType && MediaRecorder.isTypeSupported(m)) mimeType = m;
      });

      mediaRecorder = new MediaRecorder(stream, mimeType ? {mimeType:mimeType} : {});
      mediaRecorder.ondataavailable = function(e) { if(e.data.size>0) audioChunks.push(e.data); };
      mediaRecorder.onstop = function() {
        isRecording = false;
        stream.getTracks().forEach(function(t){t.stop();});
        stopMicViz();

        var blob = new Blob(audioChunks, {type: mimeType || 'audio/webm'});
        if (blob.size < 800) { setIdle("Recording too short — try again."); return; }

        setState('speaking');
        stateLbl.textContent = 'Processing…';
        respBox.classList.add('loading');
        respBox.textContent = '…';

        var form = new FormData();
        form.append('audio', blob, 'recording.webm');

        fetch('/api/transcribe', {method:'POST', body:form})
          .then(function(r){return r.json();})
          .then(function(d) {
            respBox.classList.remove('loading');
            if (d.fallback || !d.text) {
              setIdle('Voice transcription not set up — use Manual Mode.');
              activateManual(); return;
            }
            processText(d.text.trim());
          })
          .catch(function() {
            respBox.classList.remove('loading');
            setIdle('Audio error — use Manual Mode.');
            activateManual();
          });
      };

      mediaRecorder.start();
      // Auto stop after 12 seconds
      setTimeout(function(){ if(isRecording) stopMediaRecorder(); }, 12000);
    })
    .catch(function(err) {
      console.log('Mic denied:', err);
      setIdle('Microphone access denied — use Manual Mode below.');
      activateManual();
    });
}

function stopMediaRecorder() {
  if (!isRecording || !mediaRecorder) return;
  isRecording = false;
  try { mediaRecorder.stop(); } catch(e) {}
}

// ── HALO TAP ─────────────────────────────────────────────
halo.addEventListener('click', function(e) {
  e.preventDefault();
  if (isManual) return;
  unlockAudio();
  warmSpeech();
  playTap();

  // If there is a pending reply waiting — THIS tap speaks it
  // (This is a real user gesture so speechSynthesis works 100%)
  if (_pendingReply) {
    var txt = _pendingReply;
    _pendingReply = null;
    _doSpeak(txt);
    return;
  }

  if (STATE === 'speaking') {
    if (window.speechSynthesis) { try { speechSynthesis.cancel(); } catch(e) {} }
    _ttsActive = false;
    setIdle();
    return;
  }

  if (STATE === 'listening') {
    if (recognition) { try { recognition.stop(); } catch(e) {} }
    if (isRecording) stopMediaRecorder();
    clearTimeout(silenceTimer);
    clearTimeout(noSpeechTimer);
    stopVizStream();
    setIdle();
    return;
  }

  // idle — start listening
  if (SR && !useFallbackSTT) {
    startSpeechRecognition();
  } else {
    startMediaRecorder();
  }
});

// Touch events for better mobile response
halo.addEventListener('touchstart', function(e){ e.preventDefault(); }, {passive:false});
halo.addEventListener('touchend', function(e){
  e.preventDefault();
  halo.click();
}, {passive:false});

// ── MANUAL MODE ───────────────────────────────────────────
function activateManual() {
  if (!isManual) {
    isManual = true;
    manualWrap.style.display = 'flex';
    modeBtn.textContent = 'Voice Mode';
    modeBtn.classList.add('active');
  }
}

modeBtn.addEventListener('click', function() {
  isManual = !isManual;
  manualWrap.style.display = isManual ? 'flex' : 'none';
  modeBtn.textContent = isManual ? 'Voice Mode' : 'Manual Mode';
  modeBtn.classList.toggle('active', isManual);
  if (isManual) setTimeout(function(){ manualIn.focus(); }, 50);
});

document.getElementById('manual-send').addEventListener('click', function() {
  var t = manualIn.value.trim();
  if (t.length < 2) return;
  manualIn.value = '';
  processText(t);
});

manualIn.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    var t = manualIn.value.trim();
    if (t.length >= 2) { manualIn.value=''; processText(t); }
  }
});

// ── PAYWALL ───────────────────────────────────────────────
function showPaywall() {
  document.getElementById('paywall-overlay').style.display = 'flex';
}
function hidePaywall() {
  document.getElementById('paywall-overlay').style.display = 'none';
}
function showPaymentFS() {
  document.getElementById('paywall-overlay').style.display = 'none';
  document.getElementById('pay-fs').style.display = 'flex';
}
async function goUpgrade() {
  try {
    if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
    else if (document.documentElement.webkitRequestFullscreen) document.documentElement.webkitRequestFullscreen();
  } catch(e) {}
  if (!token) { window.location.href='/login?next=subscribe'; return; }
  try {
    var r = await fetch('/api/subscription/checkout',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Auth-Token':token}
    });
    var d = await r.json();
    if (d.checkout_url) window.location.href = d.checkout_url;
    else if (d.setup_needed) window.location.href = 'https://supportrd.com/products/hair-advisor-premium';
    else alert('Something went wrong.');
  } catch(e) { alert('Connection error.'); }
}

// ── PWA INSTALL BANNER ────────────────────────────────────
var deferredInstall = null;
var installBar = document.getElementById('install-bar');

window.addEventListener('beforeinstallprompt', function(e) {
  e.preventDefault();
  deferredInstall = e;
  var isPWA = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
  if (!isPWA && !localStorage.getItem('pwa-dismissed')) {
    setTimeout(function() { installBar.style.display = 'flex'; }, 6000);
  }
});

document.getElementById('install-do').addEventListener('click', function() {
  if (!deferredInstall) return;
  deferredInstall.prompt();
  deferredInstall.userChoice.then(function(r) {
    if (r.outcome === 'accepted') dismissInstall();
    deferredInstall = null;
  });
});

function dismissInstall() {
  localStorage.setItem('pwa-dismissed','1');
  installBar.style.display = 'none';
}

window.addEventListener('appinstalled', dismissInstall);

// In standalone PWA mode — never show install bar
if (window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone) {
  localStorage.setItem('pwa-dismissed','1');
}
</script>
</body>
</html>"""

# ═════════════════════════════════════════════════════════════════════════════
DASHBOARD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#f0ebe8">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<title>Dashboard — SupportRD</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<style>
:root {
  --brand: #c1a3a2; --accent: #9d7f6a;
  --bg: #f0ebe8; --card: #fff; --text: #0d0906;
  --muted: rgba(0,0,0,0.38); --border: rgba(193,163,162,0.15);
  --safe-top: env(safe-area-inset-top,0px);
  --safe-bot: env(safe-area-inset-bottom,0px);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}
html,body{height:100%;height:100dvh;overflow:hidden;background:var(--bg);font-family:'Jost',sans-serif;font-weight:300;color:var(--text);}
#dash{display:flex;flex-direction:column;height:100dvh;padding-top:var(--safe-top);padding-bottom:var(--safe-bot);}

/* Header */
#dh{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;background:var(--card);border-bottom:1px solid var(--border);flex-shrink:0;gap:12px;}
.dh-logo{font-family:'Cormorant Garamond',serif;font-size:19px;font-style:italic;color:var(--text);}
.dh-right{display:flex;align-items:center;gap:10px;}
.dh-av{width:30px;height:30px;border-radius:50%;background:var(--brand);display:flex;align-items:center;justify-content:center;font-size:12px;color:#fff;overflow:hidden;flex-shrink:0;}
.dh-av img{width:100%;height:100%;object-fit:cover;}
.dh-name{font-size:12px;color:var(--text);}
.dh-out{font-size:9px;letter-spacing:0.1em;text-transform:uppercase;background:none;border:1px solid var(--border);border-radius:14px;padding:5px 12px;cursor:pointer;color:var(--accent);font-family:'Jost',sans-serif;transition:all .2s;}

/* Scrollable content */
#ds{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:14px 14px 20px;}

/* Cards */
.dc{background:var(--card);border-radius:18px;padding:20px;margin-bottom:12px;border:1px solid var(--border);box-shadow:0 2px 10px rgba(0,0,0,0.04);}
.dl{font-size:9px;letter-spacing:0.22em;text-transform:uppercase;color:var(--brand);margin-bottom:7px;}
.dt{font-family:'Cormorant Garamond',serif;font-size:19px;font-style:italic;color:var(--text);margin-bottom:14px;}

/* Score card */
.sc{background:linear-gradient(135deg,#0d0906,#1e1410);border:none;}
.sc .dl{color:rgba(193,163,162,0.55);}
.sr-wrap{width:148px;height:148px;margin:0 auto 14px;position:relative;}
.sr-svg{transform:rotate(-90deg);}
.sr-bg{fill:none;stroke:rgba(193,163,162,0.08);stroke-width:9;}
.sr-fill{fill:none;stroke-width:9;stroke-linecap:round;transition:stroke-dashoffset 2s cubic-bezier(.22,1,.36,1);}
.sr-ctr{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.sr-num{font-family:'Cormorant Garamond',serif;font-size:48px;font-style:italic;color:#fff;line-height:1;}
.sr-pct{font-size:12px;color:rgba(193,163,162,0.5);}
.sc-status{font-family:'Cormorant Garamond',serif;font-size:18px;font-style:italic;color:var(--brand);margin-bottom:5px;}
.sc-desc{font-size:11px;color:rgba(255,255,255,0.3);line-height:1.55;margin-bottom:16px;max-width:280px;margin-left:auto;margin-right:auto;}
.sc-bars{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.sbi .sbl{font-size:9px;letter-spacing:0.1em;text-transform:uppercase;color:rgba(193,163,162,0.45);margin-bottom:4px;}
.sbi .sbt{height:3px;background:rgba(255,255,255,0.05);border-radius:2px;overflow:hidden;}
.sbi .sbf{height:100%;border-radius:2px;transition:width 1.5s cubic-bezier(.22,1,.36,1);}
.sbi .sbv{font-size:9px;color:rgba(255,255,255,0.35);margin-top:3px;}

/* Form */
.fg{margin-bottom:10px;}
.fg label{font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);display:block;margin-bottom:4px;}
input,select,textarea{width:100%;padding:9px 12px;border:1px solid rgba(193,163,162,0.2);border-radius:10px;font-family:'Jost',sans-serif;font-size:12px;color:var(--text);background:#faf6f3;outline:none;transition:border .2s;-webkit-appearance:none;}
input:focus,select:focus{border-color:var(--brand);}
.btn-save{width:100%;padding:11px;border:none;border-radius:22px;background:var(--brand);color:#fff;font-family:'Jost',sans-serif;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;cursor:pointer;margin-top:8px;transition:background .2s;}
.btn-save:active{background:var(--accent);}

/* Stats */
.stats{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:14px;}
.stat .sn{font-family:'Cormorant Garamond',serif;font-size:34px;font-style:italic;color:var(--brand);line-height:1;}
.stat .sl{font-size:9px;letter-spacing:0.1em;text-transform:uppercase;color:var(--muted);margin-top:2px;}

/* CTAs */
.cta{display:block;padding:13px 18px;border-radius:14px;text-decoration:none;text-align:center;margin-bottom:9px;border:none;cursor:pointer;width:100%;font-family:'Jost',sans-serif;transition:opacity .2s;}
.cta:active{opacity:0.85;}
.cta-rose{background:linear-gradient(135deg,var(--brand),var(--accent));color:#fff;}
.cta-dark{background:linear-gradient(135deg,#0d0906,#2a1f18);color:#fff;}
.cta-wa{background:linear-gradient(135deg,#25D366,#128C7E);color:#fff;}
.cta-t{font-family:'Cormorant Garamond',serif;font-size:16px;font-style:italic;}
.cta-s{font-size:9px;letter-spacing:0.1em;text-transform:uppercase;opacity:0.8;margin-top:1px;}

/* History */
.hi{padding:10px 0;border-bottom:1px solid rgba(193,163,162,0.08);}
.hi:last-child{border-bottom:none;}
.hi-r{font-size:8px;letter-spacing:0.14em;text-transform:uppercase;color:var(--brand);margin-bottom:2px;}
.hi-t{font-size:11px;color:var(--muted);line-height:1.5;}
.clr{font-size:9px;color:var(--muted);background:none;border:none;cursor:pointer;letter-spacing:0.08em;text-transform:uppercase;margin-top:10px;font-family:'Jost',sans-serif;}

/* Chip field */
.chip-field{display:flex;align-items:center;flex-wrap:wrap;gap:6px;min-height:42px;padding:9px 12px;border:1px solid rgba(193,163,162,0.2);border-radius:10px;background:#faf6f3;cursor:pointer;position:relative;transition:border .2s;}
.chip-field:active{border-color:var(--brand);}
.chip-placeholder{font-size:12px;color:rgba(0,0,0,0.28);}
.chip-wrap{display:flex;flex-wrap:wrap;gap:4px;flex:1;}
.chip{display:inline-flex;align-items:center;gap:4px;background:var(--brand);color:#fff;border-radius:12px;padding:3px 9px;font-size:10px;letter-spacing:0.04em;}
.chip-x{font-size:13px;line-height:1;cursor:pointer;opacity:0.7;}
.chip-arrow{font-size:18px;color:rgba(0,0,0,0.25);flex-shrink:0;margin-left:auto;}

/* Picker modal */
#picker-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.55);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);z-index:700;align-items:flex-end;justify-content:center;padding-bottom:env(safe-area-inset-bottom,0px);}
#picker-sheet{background:var(--card);border-radius:24px 24px 0 0;width:100%;max-width:500px;padding:0 0 calc(20px + env(safe-area-inset-bottom,0px));animation:shet .3s cubic-bezier(.32,.72,0,1);}
@keyframes shet{from{transform:translateY(100%)}to{transform:translateY(0)}}
#picker-header{display:flex;align-items:center;justify-content:space-between;padding:18px 20px 14px;border-bottom:1px solid var(--border);}
#picker-title{font-family:'Cormorant Garamond',serif;font-size:20px;font-style:italic;color:var(--text);}
#picker-done{background:var(--brand);color:#fff;border:none;border-radius:18px;padding:7px 18px;font-family:'Jost',sans-serif;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;cursor:pointer;}
#picker-list{padding:12px 16px;display:flex;flex-wrap:wrap;gap:8px;max-height:60vh;overflow-y:auto;}
.pick-opt{padding:9px 16px;border:1px solid var(--border);border-radius:20px;font-size:12px;color:var(--muted);cursor:pointer;transition:all .15s;background:#faf6f3;}
.pick-opt.sel{background:var(--brand);color:#fff;border-color:var(--brand);}

/* Payment fullscreen overlay */
#pay-ov{display:none;position:fixed;inset:0;background:var(--bg);z-index:500;flex-direction:column;overflow-y:auto;padding-top:env(safe-area-inset-top,0px);}
#pay-hd{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;background:#0d0906;flex-shrink:0;}
#pay-hd span{font-family:'Cormorant Garamond',serif;font-size:20px;font-style:italic;color:var(--brand);}
#pay-cl{background:none;border:none;color:rgba(255,255,255,0.3);font-size:26px;cursor:pointer;line-height:1;}
#pay-bd{flex:1;padding:28px 20px calc(40px + env(safe-area-inset-bottom,0px));max-width:440px;margin:0 auto;width:100%;}
.pay-hero{text-align:center;margin-bottom:28px;}
.pay-hero .phn{font-family:'Cormorant Garamond',serif;font-size:64px;font-style:italic;color:var(--text);line-height:1;}
.pay-hero .phs{font-size:16px;color:var(--muted);}
.pay-hero .pht{font-size:11px;color:var(--brand);margin-top:6px;letter-spacing:0.06em;}
.pay-fc{background:var(--card);border-radius:18px;padding:20px;margin-bottom:22px;}
.pay-fl{font-size:9px;letter-spacing:0.16em;text-transform:uppercase;color:var(--muted);margin-bottom:14px;}
.pay-fi{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--border);font-size:12px;color:rgba(0,0,0,0.6);}
.pay-fi:last-child{border-bottom:none;}
.pay-fi::before{content:'✦';color:var(--brand);font-size:9px;flex-shrink:0;}
.pay-go{width:100%;padding:16px;background:linear-gradient(135deg,var(--brand),var(--accent));color:#fff;border:none;border-radius:30px;font-family:'Jost',sans-serif;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;cursor:pointer;transition:opacity .2s;}
.pay-go:active{opacity:0.85;}
.pay-nt{text-align:center;font-size:10px;color:var(--muted);margin-top:10px;line-height:1.6;}
</style>
</head>
<body>
<div id="dash">
  <div id="dh">
    <div class="dh-logo">SupportRD</div>
    <div class="dh-right">
      <div style="display:flex;align-items:center;gap:8px;">
        <div class="dh-av" id="d-av"><span id="d-in">?</span></div>
        <span class="dh-name" id="d-nm">Loading…</span>
      </div>
      <button class="dh-out" onclick="doLogout()">Sign Out</button>
    </div>
  </div>

  <div id="ds">
    <!-- SCORE CARD -->
    <div class="dc sc">
      <div class="dl">Your Hair Health Score</div>
      <div class="sr-wrap">
        <svg class="sr-svg" width="148" height="148" viewBox="0 0 148 148">
          <circle class="sr-bg" cx="74" cy="74" r="62"/>
          <circle class="sr-fill" id="sr" cx="74" cy="74" r="62"
            stroke-dasharray="390" stroke-dashoffset="390" stroke="#c1a3a2"/>
        </svg>
        <div class="sr-ctr">
          <div class="sr-num" id="sn">0</div>
          <div class="sr-pct">/ 100</div>
        </div>
      </div>
      <div class="sc-status" id="ss">Complete your profile</div>
      <div class="sc-desc" id="sd">Fill in your hair profile to get your personalized score</div>
      <div class="sc-bars">
        <div class="sbi"><div class="sbl">Moisture</div><div class="sbt"><div class="sbf" id="bm" style="width:0%;background:#c1a3a2;"></div></div><div class="sbv" id="vm">—</div></div>
        <div class="sbi"><div class="sbl">Strength</div><div class="sbt"><div class="sbf" id="bs" style="width:0%;background:#9d7f6a;"></div></div><div class="sbv" id="vs">—</div></div>
        <div class="sbi"><div class="sbl">Scalp</div><div class="sbt"><div class="sbf" id="bsc" style="width:0%;background:#c1a3a2;"></div></div><div class="sbv" id="vsc">—</div></div>
        <div class="sbi"><div class="sbl">Growth</div><div class="sbt"><div class="sbf" id="bg" style="width:0%;background:#9d7f6a;"></div></div><div class="sbv" id="vg">—</div></div>
      </div>
    </div>

    <!-- PROFILE -->
    <div class="dc">
      <div class="dl">Build Your Score</div>
      <div class="dt">Hair Profile</div>
      <div class="fg"><label>Hair Type</label>
        <select id="p-type" onchange="recalc()">
          <option value="">Select…</option>
          <option>Straight</option><option>Wavy</option><option>Curly</option>
          <option>Coily / 4C</option><option>Fine</option><option>Thick</option>
        </select></div>
      <div class="fg"><label>Main Concerns</label>
        <div class="chip-field" id="con-field" onclick="openPicker('concerns',event)">
          <span class="chip-placeholder" id="con-ph">Tap to select…</span>
          <span class="chip-wrap" id="con-chips"></span>
          <span class="chip-arrow">›</span>
        </div>
        <input type="hidden" id="p-con">
      </div>
      <div class="fg"><label>Chemical Treatments</label>
        <div class="chip-field" id="trx-field" onclick="openPicker('treatments',event)">
          <span class="chip-placeholder" id="trx-ph">Tap to select…</span>
          <span class="chip-wrap" id="trx-chips"></span>
          <span class="chip-arrow">›</span>
        </div>
        <input type="hidden" id="p-trx">
      </div>
      <div class="fg"><label>Products Using</label>
        <div class="chip-field" id="pro-field" onclick="openPicker('products',event)">
          <span class="chip-placeholder" id="pro-ph">Tap to select…</span>
          <span class="chip-wrap" id="pro-chips"></span>
          <span class="chip-arrow">›</span>
        </div>
        <input type="hidden" id="p-pro">
      </div>
      <div class="fg"><label>Heat Tools</label>
        <select id="p-heat" onchange="recalc()">
          <option value="">Select…</option>
          <option value="never">Never</option>
          <option value="rarely">Rarely (monthly)</option>
          <option value="sometimes">Sometimes (weekly)</option>
          <option value="daily">Daily</option>
        </select></div>
      <div class="fg"><label>Water Type</label>
        <select id="p-water" onchange="recalc()">
          <option value="">Select…</option>
          <option value="soft">Soft water</option>
          <option value="hard">Hard water</option>
          <option value="unknown">Not sure</option>
        </select></div>
      <button class="btn-save" onclick="saveProfile()">Save & Update Score</button>
    </div>

    <!-- STATS + CTAS -->
    <div class="dc">
      <div class="dl">Overview</div>
      <div class="dt">My Journey</div>
      <div class="stats">
        <div class="stat"><div class="sn" id="sc-chats">—</div><div class="sl">Consultations</div></div>
        <div class="stat"><div class="sn" id="sc-score">—</div><div class="sl">Hair Score</div></div>
      </div>
      <a href="/" class="cta cta-rose" onclick="try{document.documentElement.requestFullscreen();}catch(e){}">
        <div class="cta-t">Talk to Aria</div>
        <div class="cta-s">AI Hair Advisor</div>
      </a>
      <button onclick="showPayment()" class="cta cta-dark">
        <div class="cta-t">Upgrade to Premium</div>
        <div class="cta-s">7-day free trial · $80/month</div>
      </button>
      <a href="https://wa.me/18292332670" target="_blank" class="cta cta-wa">
        <div class="cta-t">Live Human Advisor</div>
        <div class="cta-s">WhatsApp · 829-233-2670</div>
      </a>
    </div>

    <!-- HISTORY -->
    <div class="dc">
      <div class="dl">Conversation Memory</div>
      <div class="dt">Recent Chat with Aria</div>
      <div id="hist-list"><div style="color:var(--muted);font-size:12px;">Loading…</div></div>
      <button class="clr" onclick="clearHist()">Clear chat history</button>
    </div>
  </div>
</div>

<!-- CHIP PICKER MODAL -->
<div id="picker-overlay" onclick="closePicker()">
  <div id="picker-sheet" onclick="event.stopPropagation()">
    <div style="width:36px;height:4px;background:rgba(0,0,0,0.1);border-radius:2px;margin:12px auto 0;"></div>
    <div id="picker-header">
      <span id="picker-title">Select</span>
      <button id="picker-done" onclick="closePicker()">Done</button>
    </div>
    <div id="picker-list"></div>
  </div>
</div>

<!-- PAYMENT FULLSCREEN -->
<div id="pay-ov">
  <div id="pay-hd">
    <span>SupportRD Premium</span>
    <button id="pay-cl" onclick="document.getElementById('pay-ov').style.display='none'">×</button>
  </div>
  <div id="pay-bd">
    <div class="pay-hero">
      <div class="phn">$80</div>
      <div class="phs">/month</div>
      <div class="pht">✦ 7-day free trial included</div>
    </div>
    <div class="pay-fc">
      <div class="pay-fl">Everything included</div>
      <div class="pay-fi">Unlimited Aria AI consultations</div>
      <div class="pay-fi">Full Hair Health Score analysis</div>
      <div class="pay-fi">Personalized product recommendations</div>
      <div class="pay-fi">Complete conversation history</div>
      <div class="pay-fi">Priority WhatsApp advisor access</div>
    </div>
    <button class="pay-go" onclick="goUpgrade()">Start Free Trial</button>
    <div class="pay-nt">No charge for 7 days. Cancel anytime from your account.</div>
  </div>
</div>

<script>
var token = localStorage.getItem('srd_token');
if (!token) { window.location.href = '/login'; }

// ── LOAD USER ─────────────────────────────────────────────
fetch('/api/auth/me', {headers:{'X-Auth-Token':token}})
  .then(function(r){return r.json();})
  .then(function(d){
    if (!d.ok) { localStorage.removeItem('srd_token'); window.location.href='/login'; return; }
    document.getElementById('d-nm').textContent = d.name || 'User';
    document.getElementById('d-in').textContent = (d.name||'?')[0].toUpperCase();
    if (d.avatar) document.getElementById('d-av').innerHTML = '<img src="'+d.avatar+'">';
  }).catch(function(){ window.location.href='/login'; });

// ── LOAD PROFILE ──────────────────────────────────────────
fetch('/api/profile', {headers:{'X-Auth-Token':token}})
  .then(function(r){return r.json();})
  .then(function(d){
    if (d.hair_type)      document.getElementById('p-type').value  = d.hair_type;
    if (d.heat_usage)     document.getElementById('p-heat').value  = d.heat_usage;
    if (d.water_type)     document.getElementById('p-water').value = d.water_type;
    if (d.hair_concerns)  loadChips('concerns', d.hair_concerns);
    if (d.treatments)     loadChips('treatments', d.treatments);
    if (d.products_tried) loadChips('products', d.products_tried);
    recalc();
  }).catch(function(){});

// ── LOAD HISTORY ──────────────────────────────────────────
fetch('/api/history', {headers:{'X-Auth-Token':token}})
  .then(function(r){return r.json();})
  .then(function(d){
    var hl = document.getElementById('hist-list');
    var h  = d.history || [];
    document.getElementById('sc-chats').textContent = Math.ceil(h.filter(function(x){return x.role==='user';}).length);
    if (!h.length) { hl.innerHTML='<div style="color:var(--muted);font-size:12px;">No conversations yet.</div>'; return; }
    hl.innerHTML = h.slice(0,10).map(function(x){
      return '<div class="hi"><div class="hi-r">'+(x.role==='user'?'You':'Aria')+'</div><div class="hi-t">'+x.content.slice(0,120)+'</div></div>';
    }).join('');
  }).catch(function(){});

// ── SCORE ENGINE ──────────────────────────────────────────
// ── CHIP PICKERS ──────────────────────────────────────────
var PICKER_OPTIONS = {
  concerns: [
    'Dry hair','Oily scalp','Hair loss','Breakage','Thinning',
    'Frizz','Dull / no shine','Split ends','Slow growth','Dandruff',
    'Itchy scalp','Heat damage','Color damage','Brittleness','Curl loss'
  ],
  treatments: [
    'No treatments','Relaxer / Perm','Bleach','Hair color / Dye',
    'Keratin treatment','Brazilian blowout','Japanese straightening',
    'Highlights / Balayage','Texturizer','Heat styling daily',
    'Heat styling weekly','No heat ever'
  ],
  products: [
    // SupportRD products (first)
    'Formula Exclusiva — SupportRD','Laciador Crece — SupportRD',
    'Gotero Rapido — SupportRD','Gotitas Brillantes — SupportRD',
    'Mascarilla — SupportRD','Shampoo Aloe & Rosemary — SupportRD',
    // Top brands
    'OGX','SheaMoisture','Cantu','Mielle Organics','Carol's Daughter',
    'Aunt Jackie's','As I Am','DevaCurl','Olaplex','Redken',
    'Pantene','Head & Shoulders','Garnier Fructis','TRESemmé',
    'Dove','Herbal Essences','Paul Mitchell','Moroccanoil',
    'Kérastase','L'Oréal EverPure','Not I Am','Curl Junkie'
  ]
};
var PICKER_LABELS = { concerns:'Main Concerns', treatments:'Chemical Treatments', products:'Products You Use' };
var pickerKey = null;
var pickerSel = { concerns:[], treatments:[], products:[] };

function openPicker(key, evt) {
  if (evt) evt.stopPropagation();
  pickerKey = key;
  document.getElementById('picker-title').textContent = PICKER_LABELS[key];
  var list = document.getElementById('picker-list');
  list.innerHTML = PICKER_OPTIONS[key].map(function(opt) {
    var safe = opt.replace(/\\/g,'\\\\').replace(/'/g,"\'");
    var isSel = pickerSel[key].indexOf(opt) > -1;
    return '<div class="pick-opt'+(isSel?' sel':'')+'" onclick="toggleOpt(this,\''+safe+'\')">'+opt+'</div>';
  }).join('');
  var ov = document.getElementById('picker-overlay');
  ov.style.display = 'flex';
  // Force reflow for animation
  ov.offsetHeight;
  list.scrollTop = 0;
}

function toggleOpt(el, val) {
  var idx = pickerSel[pickerKey].indexOf(val);
  if (idx > -1) { pickerSel[pickerKey].splice(idx,1); el.classList.remove('sel'); }
  else          { pickerSel[pickerKey].push(val);     el.classList.add('sel');    }
}

function closePicker() {
  document.getElementById('picker-overlay').style.display = 'none';
  renderChips(pickerKey);
  recalc();
}

function renderChips(key) {
  var map = { concerns:['con-chips','con-ph','p-con'], treatments:['trx-chips','trx-ph','p-trx'], products:['pro-chips','pro-ph','p-pro'] };
  var ids = map[key];
  var chips = document.getElementById(ids[0]);
  var ph    = document.getElementById(ids[1]);
  var inp   = document.getElementById(ids[2]);
  var sel   = pickerSel[key];
  ph.style.display = sel.length ? 'none' : '';
  chips.innerHTML = sel.map(function(v){
    return '<span class="chip">'+v+'<span class="chip-x" onclick="removeChip(event,\''+key+'\',\''+v.replace(/'/g,"\'")+'\')">×</span></span>';
  }).join('');
  inp.value = sel.join(', ');
}

function removeChip(e, key, val) {
  e.stopPropagation();
  var idx = pickerSel[key].indexOf(val);
  if (idx > -1) pickerSel[key].splice(idx,1);
  renderChips(key); recalc();
}

// Pre-populate chips from loaded profile
function loadChips(key, csvVal) {
  if (!csvVal) return;
  pickerSel[key] = csvVal.split(',').map(function(s){return s.trim();}).filter(Boolean);
  renderChips(key);
}

function recalc() {
  var concerns   = (document.getElementById('p-con').value||'').toLowerCase();
  var treatments = (document.getElementById('p-trx').value||'').toLowerCase();
  var products   = (document.getElementById('p-pro').value||'').toLowerCase();
  var heat       = document.getElementById('p-heat').value;
  var water      = document.getElementById('p-water').value;
  var type       = document.getElementById('p-type').value;
  if (!type && !concerns) return;

  var m=75, s=75, sc=75, g=75;
  // Deductions
  if (/dry|brittle|break/.test(concerns)) m-=20;
  if (/thin|fall|shed|bald/.test(concerns)) { s-=20; g-=25; }
  if (/oil|grease/.test(concerns)) { sc-=15; m+=10; }
  if (/frizz/.test(concerns)) m-=10;
  if (/itch|dand|flak/.test(concerns)) sc-=20;
  if (/bleach|color|perm|relax/.test(treatments)) { s-=20; m-=10; }
  if (heat==='daily')     { s-=20; m-=15; }
  if (heat==='sometimes') { s-=8;  m-=5;  }
  if (water==='hard')     { m-=8; sc-=5;  }
  // Bonuses
  if (/formula exclusiva/i.test(products)) { m+=15; s+=15; }
  if (/laciador/i.test(products))          { m+=10; g+=10; }
  if (/gotero/i.test(products))            { g+=15; sc+=12; }
  if (/mascarilla/i.test(products))        { m+=10; }
  if (/shampoo/i.test(products))           { sc+=8; }

  m  = Math.max(10, Math.min(100, m));
  s  = Math.max(10, Math.min(100, s));
  sc = Math.max(10, Math.min(100, sc));
  g  = Math.max(10, Math.min(100, g));

  var overall = Math.round((m+s+sc+g)/4);
  var statuses = ['Critical','Poor','Fair','Good','Excellent'];
  var status = overall<40?statuses[0]:overall<55?statuses[1]:overall<70?statuses[2]:overall<85?statuses[3]:statuses[4];
  var colors  = {Critical:'#e07070',Poor:'#d4956a',Fair:'#c1a3a2',Good:'#8ec63f',Excellent:'#25D366'};
  var color   = colors[status];
  var descs   = {
    Critical:"Your hair needs urgent care. Let's start with the right products.",
    Poor:"There's work to do, but you're in the right place. Aria can help.",
    Fair:"Your hair is managing, but there's room to shine.",
    Good:"You're doing well! A few targeted products will take you to excellent.",
    Excellent:"Your hair is thriving. Keep up the great work!"
  };

  // Animate score
  var cur = parseInt(document.getElementById('sn').textContent)||0;
  var step = (overall-cur)/20;
  var t=0;
  function anim(){
    t++;
    cur = Math.round(cur+step);
    if(t>=20) cur=overall;
    document.getElementById('sn').textContent=cur;
    var offset = 390*(1-cur/100);
    var ring=document.getElementById('sr');
    ring.style.strokeDashoffset=offset;
    ring.style.stroke=color;
    if(t<20) requestAnimationFrame(anim);
  }
  requestAnimationFrame(anim);

  document.getElementById('ss').textContent=status;
  document.getElementById('sd').textContent=descs[status];
  document.getElementById('sc-score').textContent=overall;

  var bars=[['bm','vm',m],['bs','vs',s],['bsc','vsc',sc],['bg','vg',g]];
  bars.forEach(function(b){ document.getElementById(b[0]).style.width=b[2]+'%'; document.getElementById(b[1]).textContent=b[2]; });
}

function saveProfile(){
  var data={
    hair_type:      document.getElementById('p-type').value,
    hair_concerns:  document.getElementById('p-con').value,
    treatments:     document.getElementById('p-trx').value,
    products_tried: document.getElementById('p-pro').value,
    heat_usage:     document.getElementById('p-heat').value,
    water_type:     document.getElementById('p-water').value
  };
  fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json','X-Auth-Token':token},body:JSON.stringify(data)})
    .then(function(){recalc();}).catch(function(){});
}

function clearHist(){
  fetch('/api/history/clear',{method:'POST',headers:{'X-Auth-Token':token}})
    .then(function(){document.getElementById('hist-list').innerHTML='<div style="color:var(--muted);font-size:12px;">Cleared.</div>';}).catch(function(){});
}

function doLogout(){
  localStorage.removeItem('srd_token');
  window.location.href='/login';
}

function showPayment(){
  document.getElementById('pay-ov').style.display='flex';
  window.scrollTo(0,0);
}

async function goUpgrade(){
  try{
    if(document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
    else if(document.documentElement.webkitRequestFullscreen) document.documentElement.webkitRequestFullscreen();
  }catch(e){}
  if(!token){window.location.href='/login?next=subscribe';return;}
  var r=await fetch('/api/subscription/checkout',{method:'POST',headers:{'Content-Type':'application/json','X-Auth-Token':token}});
  var d=await r.json();
  if(d.checkout_url) window.location.href=d.checkout_url;
  else if(d.setup_needed) window.location.href='https://supportrd.com/products/hair-advisor-premium';
  else alert('Something went wrong.');
}
</script>
</body>
</html>"""

# ═════════════════════════════════════════════════════════════════════════════
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#0d0906">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<title>Sign In — SupportRD</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<script src="https://accounts.google.com/gsi/client" async defer></script>
<style>
:root{--brand:#c1a3a2;--accent:#9d7f6a;--bg:#0d0906;--surface:rgba(255,255,255,0.04);--border:rgba(255,255,255,0.08);--text:rgba(255,255,255,0.85);--muted:rgba(255,255,255,0.35);--safe-top:env(safe-area-inset-top,0px);--safe-bot:env(safe-area-inset-bottom,0px);}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}
html,body{height:100%;overflow:hidden;background:var(--bg);font-family:'Jost',sans-serif;font-weight:300;color:var(--text);}
#login-app{display:flex;flex-direction:column;height:100dvh;padding:var(--safe-top) 0 var(--safe-bot);align-items:center;justify-content:center;padding-left:20px;padding-right:20px;}
.lcard{width:100%;max-width:380px;}
.l-logo{font-family:'Cormorant Garamond',serif;font-size:36px;font-style:italic;color:var(--brand);text-align:center;margin-bottom:8px;}
.l-sub{font-size:12px;color:var(--muted);text-align:center;letter-spacing:0.06em;margin-bottom:36px;}
.l-tabs{display:flex;background:var(--surface);border:1px solid var(--border);border-radius:12px;margin-bottom:24px;overflow:hidden;}
.l-tab{flex:1;padding:10px;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;background:none;border:none;color:var(--muted);cursor:pointer;font-family:'Jost',sans-serif;transition:all .2s;}
.l-tab.active{background:var(--brand);color:#fff;}
.l-form{display:none;flex-direction:column;gap:12px;}
.l-form.show{display:flex;}
.lf-group label{font-size:9px;letter-spacing:0.14em;text-transform:uppercase;color:var(--muted);display:block;margin-bottom:5px;}
.lf-group input{width:100%;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:12px;color:var(--text);font-family:'Jost',sans-serif;font-size:13px;outline:none;transition:border .2s;-webkit-user-select:text;user-select:text;}
.lf-group input:focus{border-color:var(--brand);}
.lf-group input::placeholder{color:rgba(255,255,255,0.2);}
.l-btn{width:100%;padding:13px;background:linear-gradient(135deg,var(--brand),var(--accent));color:#fff;border:none;border-radius:24px;font-family:'Jost',sans-serif;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;cursor:pointer;margin-top:4px;transition:opacity .2s;}
.l-btn:active{opacity:0.85;}
.l-err{font-size:11px;color:#e07070;text-align:center;min-height:16px;}
.l-or{display:flex;align-items:center;gap:12px;margin:16px 0;}
.l-or span{font-size:10px;color:var(--muted);letter-spacing:0.08em;flex-shrink:0;}
.l-or::before,.l-or::after{content:'';flex:1;height:1px;background:var(--border);}
.l-google{display:flex;justify-content:center;}
.l-shopify{width:100%;padding:12px;background:var(--surface);border:1px solid var(--border);border-radius:24px;color:var(--muted);font-family:'Jost',sans-serif;font-size:11px;letter-spacing:0.1em;text-transform:uppercase;cursor:pointer;text-align:center;text-decoration:none;display:block;margin-top:8px;transition:border-color .2s;}
.l-shopify:hover{border-color:var(--brand);}
.l-back{display:block;text-align:center;margin-top:16px;font-size:11px;color:var(--muted);text-decoration:none;letter-spacing:0.06em;}
.l-back:hover{color:var(--brand);}
.l-google-btn{display:flex;align-items:center;justify-content:center;width:300px;max-width:100%;padding:10px 16px;background:#fff;border:1px solid rgba(0,0,0,0.12);border-radius:24px;font-family:'Jost',sans-serif;font-size:13px;color:#3c4043;cursor:pointer;transition:box-shadow .2s;}
.l-google-btn:hover{box-shadow:0 2px 8px rgba(0,0,0,0.12);}
</style>
</head>
<body>
<input type="hidden" id="gClientId" value="%GOOGLE_CLIENT_ID%">
<div id="login-app">
  <div class="lcard">
    <div class="l-logo">Aria</div>
    <div class="l-sub">Your AI hair advisor by SupportRD</div>

    <div class="l-tabs">
      <button class="l-tab active" onclick="switchTab('in')">Sign In</button>
      <button class="l-tab" onclick="switchTab('up')">Create Account</button>
    </div>

    <!-- SIGN IN -->
    <div id="form-in" class="l-form show">
      <div class="lf-group"><label>Email</label><input id="li-email" type="email" inputmode="email" placeholder="your@email.com" autocomplete="email"></div>
      <div class="lf-group"><label>Password</label><input id="li-pass" type="password" placeholder="••••••••" autocomplete="current-password"></div>
      <div class="l-err" id="li-err"></div>
      <button class="l-btn" onclick="doLogin()">Sign In</button>
      <div class="l-or"><span>or</span></div>
      <div class="l-google" id="g-wrap-in">
        <div id="google-btn-container"></div>
        <!-- Fallback styled button shown if GIS lib doesn't render -->
        <button id="g-fallback-in" class="l-google-btn" onclick="triggerGoogle('li-err')" style="display:none">
          <svg width="18" height="18" viewBox="0 0 18 18" style="margin-right:8px;flex-shrink:0"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/><path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z"/></svg>
          Continue with Google
        </button>
      </div>

    </div>

    <!-- SIGN UP -->
    <div id="form-up" class="l-form">
      <div class="lf-group"><label>Your Name</label><input id="ru-name" type="text" placeholder="First Last" autocomplete="name"></div>
      <div class="lf-group"><label>Email</label><input id="ru-email" type="email" inputmode="email" placeholder="your@email.com" autocomplete="email"></div>
      <div class="lf-group"><label>Password</label><input id="ru-pass" type="password" placeholder="Create password" autocomplete="new-password"></div>
      <div class="l-err" id="ru-err"></div>
      <button class="l-btn" onclick="doRegister()">Create Account</button>
      <div class="l-or"><span>or</span></div>
      <div class="l-google" id="g-wrap-up">
        <div id="google-btn-container-2"></div>
        <button id="g-fallback-up" class="l-google-btn" onclick="triggerGoogle('ru-err')" style="display:none">
          <svg width="18" height="18" viewBox="0 0 18 18" style="margin-right:8px;flex-shrink:0"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/><path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z"/></svg>
          Sign up with Google
        </button>
      </div>
    </div>

    <a href="/" class="l-back">← Back to Aria</a>
  </div>
</div>
<script>
function switchTab(t){
  document.querySelectorAll('.l-tab').forEach(function(b,i){b.classList.toggle('active',i===(t==='in'?0:1));});
  document.getElementById('form-in').classList.toggle('show',t==='in');
  document.getElementById('form-up').classList.toggle('show',t==='up');
}

var nextUrl = new URLSearchParams(location.search).get('next') || '/dashboard';

function saveAndGo(d){
  localStorage.setItem('srd_token', d.token);
  window.location.href = nextUrl;
}

async function doLogin(){
  var email=document.getElementById('li-email').value.trim();
  var pass=document.getElementById('li-pass').value;
  var errEl=document.getElementById('li-err');
  errEl.textContent='';
  if(!email||!pass){errEl.textContent='Please fill in all fields.';return;}
  try{
    var r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pass})});
    var d=await r.json();
    if(d.error){errEl.textContent=d.error;}else{saveAndGo(d);}
  }catch(e){errEl.textContent='Connection error.';}
}

async function doRegister(){
  var name=document.getElementById('ru-name').value.trim();
  var email=document.getElementById('ru-email').value.trim();
  var pass=document.getElementById('ru-pass').value;
  var errEl=document.getElementById('ru-err');
  errEl.textContent='';
  if(!email||!pass){errEl.textContent='Please fill in all fields.';return;}
  try{
    var r=await fetch('/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,email,password:pass})});
    var d=await r.json();
    if(d.error){errEl.textContent=d.error;}else{saveAndGo(d);}
  }catch(e){errEl.textContent='Connection error.';}
}

async function handleGoogle(response){
  try{
    var r=await fetch('/api/auth/google',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({credential:response.credential})});
    var d=await r.json();
    if(d.error){document.getElementById('li-err').textContent=d.error;}else{saveAndGo(d);}
  }catch(e){document.getElementById('li-err').textContent='Google sign-in failed.';}
}

// Initialize Google Identity Services
var _googleReady = false;

function triggerGoogle(errId) {
  var clientId = (document.getElementById('gClientId')||{}).value || '';
  if (!clientId) {
    document.getElementById(errId).textContent = 'Google login not configured yet. Use email login.';
    return;
  }
  if (!window.google || !window.google.accounts) {
    document.getElementById(errId).textContent = 'Google script not loaded. Check connection.';
    return;
  }
  try {
    google.accounts.id.prompt(function(notification) {
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        document.getElementById(errId).textContent = 'Google prompt blocked. Try email login.';
      }
    });
  } catch(e) {
    document.getElementById(errId).textContent = 'Google error: ' + e.message;
  }
}

function initGoogleLogin() {
  var clientId = (document.getElementById('gClientId')||{}).value || '';
  if (_googleReady) return;

  if (!clientId) {
    // No client ID — show styled fallback buttons that explain this
    ['g-fallback-in','g-fallback-up'].forEach(function(id){
      var el = document.getElementById(id);
      if (el) {
        el.style.display = 'flex';
        el.onclick = function() {
          alert('Google login requires setup in Render environment variables (GOOGLE_CLIENT_ID). Use email login for now.');
        };
      }
    });
    return;
  }

  if (!window.google || !window.google.accounts) {
    setTimeout(initGoogleLogin, 500);
    return;
  }

  _googleReady = true;
  try {
    google.accounts.id.initialize({
      client_id: clientId,
      callback: handleGoogle,
      auto_select: false,
      cancel_on_tap_outside: true,
      ux_mode: 'popup'
    });

    var opts1 = {theme:'outline', size:'large', shape:'pill', width:300, text:'signin_with'};
    var opts2 = {theme:'outline', size:'large', shape:'pill', width:300, text:'signup_with'};
    var c1 = document.getElementById('google-btn-container');
    var c2 = document.getElementById('google-btn-container-2');

    if (c1) {
      google.accounts.id.renderButton(c1, opts1);
      // Hide fallback once GIS renders
      var fb1 = document.getElementById('g-fallback-in');
      if (fb1) fb1.style.display = 'none';
    }
    if (c2) {
      google.accounts.id.renderButton(c2, opts2);
      var fb2 = document.getElementById('g-fallback-up');
      if (fb2) fb2.style.display = 'none';
    }
  } catch(e) {
    console.log('Google init error:', e);
    // Show fallback buttons
    ['g-fallback-in','g-fallback-up'].forEach(function(id){
      var el = document.getElementById(id);
      if (el) el.style.display = 'flex';
    });
  }
}

// Show fallback immediately, replace when GIS loads
['g-fallback-in','g-fallback-up'].forEach(function(id){
  var el = document.getElementById(id);
  if (el) el.style.display = 'flex';
});

window.addEventListener('load', function() {
  setTimeout(initGoogleLogin, 300);
});

// Enter key support
document.addEventListener('keydown',function(e){
  if(e.key==='Enter'){
    if(document.getElementById('form-in').classList.contains('show')) doLogin();
    else doRegister();
  }
});

// Check if returning from Shopify
var params = new URLSearchParams(location.search);
var rt = params.get('reset_token');
if(rt){
  var np=prompt('Enter your new password:');
  if(np){
    fetch('/api/auth/reset-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:rt,password:np})})
      .then(function(r){return r.json();})
      .then(function(d){if(d.ok)saveAndGo(d);});
  }
}
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
