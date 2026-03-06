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
ANTHROPIC_API_KEY      = os.environ.get("ANTHROPIC_API_KEY", "").strip()
OPENAI_API_KEY         = os.environ.get("OPENAI_API_KEY", "")
ADMIN_KEY              = os.environ.get("ADMIN_KEY", "srd_admin_2024")
STRIPE_SECRET          = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID        = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET  = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
APP_BASE_URL           = os.environ.get("APP_BASE_URL", "https://ai-hair-advisor.onrender.com")
GOOGLE_CLIENT_ID       = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
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
/* Aria PWA Service Worker v8 */
const CACHE = "aria-v8";

self.addEventListener("install", e => {
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  // Never intercept API calls or external resources
  if (url.pathname.startsWith("/api/")) return;
  if (url.origin !== self.location.origin) return;
  // Network-first: always try server, no caching of HTML pages
  e.respondWith(
    fetch(e.request).catch(() => new Response("Offline — please reconnect.", {
      status: 503, headers: {"Content-Type": "text/plain"}
    }))
  );
});
"""
    return Response(sw.strip(), mimetype="application/javascript",
                    headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache, no-store"})

@app.route("/static/icon-192.png")
def icon_192():
    return Response(base64.b64decode(_ICON_192), mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})

@app.route("/static/icon-512.png")
def icon_512():
    return Response(base64.b64decode(_ICON_512), mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})

@app.route("/api/debug-env")
def debug_env():
    return jsonify({
        "has_anthropic_key": bool(ANTHROPIC_API_KEY),
        "anthropic_key_first20": ANTHROPIC_API_KEY[:20] + "..." if ANTHROPIC_API_KEY else "MISSING",
        "anthropic_key_length": len(ANTHROPIC_API_KEY),
        "anthropic_key_valid_prefix": ANTHROPIC_API_KEY.startswith("sk-ant-"),
        "has_google_id": bool(GOOGLE_CLIENT_ID),
        "google_id_prefix": GOOGLE_CLIENT_ID[:16] + "..." if GOOGLE_CLIENT_ID else "MISSING",
        "google_id_length": len(GOOGLE_CLIENT_ID),
    })

@app.route("/api/config")
def public_config():
    # Safe to expose — Google client ID is public by design
    return jsonify({"google_client_id": GOOGLE_CLIENT_ID or ""})


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
    """Receive MediaRecorder audio, transcribe via Anthropic Claude."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio", "fallback": True})
    audio_file  = request.files["audio"]
    audio_bytes = audio_file.read()

    if len(audio_bytes) < 500:
        return jsonify({"text": "", "fallback": True})

    if not ANTHROPIC_API_KEY:
        return jsonify({"text": "", "fallback": True, "error": "No API key"})

    try:
        import base64
        audio_b64 = base64.b64encode(audio_bytes).decode()
        mime      = audio_file.content_type or "audio/webm"

        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Transcribe this audio exactly as spoken. Return ONLY the spoken words, nothing else. No punctuation changes, no commentary."
                    },
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": audio_b64
                        }
                    }
                ]
            }]
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            text = result["content"][0]["text"].strip()
            return jsonify({"text": text})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        # Claude doesn't support audio documents yet — fall back to a prompt-based approach
        # Ask user to type instead
        return jsonify({"text": "", "fallback": True, "error": err_body[:100]})
    except Exception as e:
        return jsonify({"text": "", "fallback": True, "error": str(e)})

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

# ═══════════════════════════════════════════════════════
# ARIA MAIN PAGE
# ═══════════════════════════════════════════════════════
ARIA_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#0d0906">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Aria">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/static/icon-192.png">
<title>Aria — AI Hair Advisor</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300;1,400&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<style>
:root {
  --brand: #c1a3a2;
  --accent: #9d7f6a;
  --bg: #0d0906;
  --text: rgba(255,255,255,0.88);
  --muted: rgba(255,255,255,0.32);
  --border: rgba(255,255,255,0.07);
  --safe-top: env(safe-area-inset-top, 0px);
  --safe-bot: env(safe-area-inset-bottom, 0px);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
html, body {
  height: 100%; height: 100dvh;
  overflow: hidden;
  background: var(--bg);
  color: var(--text);
  font-family: 'Jost', sans-serif;
  font-weight: 300;
  touch-action: manipulation;
}
#shell {
  display: flex; flex-direction: column;
  height: 100dvh;
  padding-top: var(--safe-top);
  padding-bottom: var(--safe-bot);
}
#topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 13px 20px 10px; flex-shrink: 0;
}
.t-brand { font-family:'Cormorant Garamond',serif; font-style:italic; font-size:18px; color:var(--brand); letter-spacing:.02em; }
.t-right { display:flex; align-items:center; gap:10px; }
#lang-sel {
  background:transparent; border:1px solid var(--border); color:var(--muted);
  border-radius:14px; padding:5px 11px; font-size:10px; font-family:'Jost',sans-serif;
  outline:none; letter-spacing:.08em; -webkit-appearance:none; appearance:none; cursor:pointer;
}
#user-pill {
  display:none; align-items:center; gap:6px;
  background:rgba(255,255,255,.04); border:1px solid var(--border);
  border-radius:18px; padding:4px 12px 4px 5px;
  text-decoration:none; color:var(--text); cursor:pointer; transition:border-color .2s;
}
#user-pill:active { border-color:var(--brand); }
#user-av {
  width:24px; height:24px; border-radius:50%; background:var(--brand);
  display:flex; align-items:center; justify-content:center;
  font-size:10px; color:#fff; overflow:hidden; flex-shrink:0;
}
#user-av img { width:100%; height:100%; object-fit:cover; }
#user-name { font-size:11px; }
#btn-login {
  font-size:10px; letter-spacing:.1em; text-transform:uppercase;
  color:var(--muted); background:transparent; border:1px solid var(--border);
  border-radius:14px; padding:5px 14px; cursor:pointer;
  font-family:'Jost',sans-serif; text-decoration:none; transition:all .2s;
}
#btn-login:active { border-color:var(--brand); color:var(--brand); }

#stage {
  flex:1; display:flex; flex-direction:column;
  align-items:center; justify-content:center;
  position:relative; overflow:hidden; padding:24px 20px; gap:22px;
}
#stage::before {
  content:''; position:absolute; width:380px; height:380px; border-radius:50%;
  background:radial-gradient(circle,rgba(193,163,162,.048) 0%,transparent 68%);
  pointer-events:none; animation:bg-breathe 8s ease-in-out infinite;
}
@keyframes bg-breathe { 0%,100%{transform:scale(1);opacity:.5} 50%{transform:scale(1.22);opacity:1} }

#sphere-wrap {
  position:relative; width:min(210px,55vw); height:min(210px,55vw);
  cursor:pointer; flex-shrink:0; will-change:transform;
  user-select:none; -webkit-user-select:none;
}
#sphere-orb {
  position:absolute; inset:0; border-radius:50%;
  background:radial-gradient(circle at 37% 35%,rgba(193,163,162,.55) 0%,rgba(193,163,162,.18) 40%,rgba(193,163,162,.05) 65%,transparent 100%);
  box-shadow:0 0 60px rgba(193,163,162,.45),0 0 120px rgba(193,163,162,.25),0 0 220px rgba(193,163,162,.12),0 0 380px rgba(193,163,162,.06);
  transition:all .45s ease;
}
#sphere-wrap.listening #sphere-orb {
  background:radial-gradient(circle at 37% 35%,rgba(157,127,106,.70) 0%,rgba(157,127,106,.28) 40%,rgba(157,127,106,.08) 65%,transparent 100%);
  box-shadow:0 0 80px rgba(157,127,106,.70),0 0 160px rgba(157,127,106,.40),0 0 300px rgba(157,127,106,.20),0 0 500px rgba(157,127,106,.10);
  animation:listen-pulse .95s ease-in-out infinite;
}
@keyframes listen-pulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.16)} }
#sphere-wrap.speaking #sphere-orb {
  background:radial-gradient(circle at 37% 35%,rgba(230,215,215,.60) 0%,rgba(230,215,215,.20) 40%,rgba(230,215,215,.06) 65%,transparent 100%);
  box-shadow:0 0 80px rgba(230,215,215,.55),0 0 160px rgba(230,215,215,.28),0 0 300px rgba(230,215,215,.13);
  animation:speak-pulse .62s ease-in-out infinite;
}
@keyframes speak-pulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.08)} }
#sphere-wrap.waiting #sphere-orb {
  box-shadow:0 0 90px rgba(193,163,162,.80),0 0 180px rgba(193,163,162,.50),0 0 340px rgba(193,163,162,.28),0 0 520px rgba(193,163,162,.12);
  animation:wait-pulse 1.5s ease-in-out infinite;
}
@keyframes wait-pulse { 0%,100%{opacity:.75;transform:scale(1)} 50%{opacity:1;transform:scale(1.13)} }
#sphere-mic { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; pointer-events:none; }
#sphere-mic svg { width:32px; height:32px; stroke:rgba(255,255,255,.85); fill:none; stroke-width:1.6; stroke-linecap:round; stroke-linejoin:round; opacity:.4; transition:opacity .3s; }
#sphere-wrap.listening  #sphere-mic svg { opacity:.9; }
#sphere-wrap.speaking   #sphere-mic svg { opacity:0; }
#sphere-wrap.waiting    #sphere-mic svg { opacity:0; }
#sphere-play { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; pointer-events:none; opacity:0; transition:opacity .35s; }
#sphere-wrap.waiting #sphere-play { opacity:.80; }
#sphere-play svg { width:30px; height:30px; fill:rgba(255,255,255,.9); }
#wavebars { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; gap:5px; pointer-events:none; opacity:0; transition:opacity .3s; }
#sphere-wrap.listening #wavebars { opacity:1; }
.wb { width:3px; height:18px; background:rgba(255,255,255,.65); border-radius:2px; transform-origin:center; }
.wb:nth-child(1){animation:wbani 1.3s ease-in-out -.32s infinite}
.wb:nth-child(2){animation:wbani 1.3s ease-in-out -.16s infinite}
.wb:nth-child(3){animation:wbani 1.3s ease-in-out 0s infinite}
.wb:nth-child(4){animation:wbani 1.3s ease-in-out -.16s infinite}
.wb:nth-child(5){animation:wbani 1.3s ease-in-out -.32s infinite}
@keyframes wbani { 0%,100%{transform:scaleY(.22)} 50%{transform:scaleY(1)} }

#state-label {
  font-size:10px; letter-spacing:.22em; text-transform:uppercase;
  color:var(--muted); transition:color .4s; flex-shrink:0; text-align:center;
}
#state-label.lit { color:var(--brand); }
#response-box {
  font-family:'Cormorant Garamond',serif; font-style:italic;
  font-size:clamp(14px,3.8vw,18px); color:rgba(255,255,255,.58);
  text-align:center; line-height:1.7; max-width:min(480px,90vw);
  min-height:50px; flex-shrink:0; transition:opacity .3s;
}
#response-box.thinking { animation:think-pulse 1.4s ease-in-out infinite; }
@keyframes think-pulse { 0%,100%{opacity:.22} 50%{opacity:.55} }

#bottombar {
  padding:8px 20px 12px; display:flex; flex-direction:column;
  align-items:center; gap:10px; flex-shrink:0;
}
#mode-btn {
  font-size:9px; letter-spacing:.16em; text-transform:uppercase;
  color:var(--muted); background:transparent; border:1px solid var(--border);
  border-radius:14px; padding:6px 18px; cursor:pointer;
  font-family:'Jost',sans-serif; transition:all .2s;
}
#mode-btn.on { border-color:var(--brand); color:var(--brand); }
#manual-row { display:none; width:100%; max-width:480px; align-items:center; gap:9px; }
#manual-input {
  flex:1; background:rgba(255,255,255,.04); border:1px solid var(--border);
  border-radius:22px; padding:11px 18px; color:var(--text);
  font-family:'Jost',sans-serif; font-size:13px; font-weight:300;
  outline:none; transition:border .2s; -webkit-user-select:text; user-select:text;
}
#manual-input:focus { border-color:var(--brand); }
#manual-input::placeholder { color:rgba(255,255,255,.18); }
#manual-send {
  width:42px; height:42px; background:var(--brand); border:none; border-radius:50%;
  cursor:pointer; display:flex; align-items:center; justify-content:center;
  flex-shrink:0; transition:background .2s;
}
#manual-send:active { background:var(--accent); }
#manual-send svg { width:16px; height:16px; fill:#fff; }

#pw-overlay {
  display:none; position:fixed; inset:0;
  background:rgba(0,0,0,.65); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
  z-index:300; align-items:flex-end; justify-content:center;
}
#pw-sheet {
  background:#141009; border-radius:28px 28px 0 0;
  padding:10px 22px calc(30px + var(--safe-bot)); width:100%; max-width:500px;
  border-top:1px solid rgba(193,163,162,.12); animation:slide-up .32s cubic-bezier(.32,.72,0,1);
}
@keyframes slide-up { from{transform:translateY(100%)} to{transform:translateY(0)} }
.pw-handle { width:34px; height:4px; background:rgba(255,255,255,.10); border-radius:2px; margin:0 auto 22px; }
.pw-badge { display:inline-block; font-size:9px; letter-spacing:.2em; text-transform:uppercase; color:var(--brand); background:rgba(193,163,162,.10); border:1px solid rgba(193,163,162,.2); border-radius:10px; padding:3px 12px; margin-bottom:12px; }
.pw-title { font-family:'Cormorant Garamond',serif; font-size:28px; font-style:italic; color:#fff; margin-bottom:6px; }
.pw-sub { font-size:11px; color:rgba(255,255,255,.36); line-height:1.65; margin-bottom:18px; }
.pw-price { text-align:center; margin-bottom:18px; }
.pw-price-num { font-family:'Cormorant Garamond',serif; font-size:50px; font-style:italic; color:#fff; }
.pw-price-per { font-size:14px; color:rgba(255,255,255,.28); }
.pw-trial { font-size:11px; color:var(--brand); margin-top:4px; }
.pw-feats { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:22px; }
.pw-feat { font-size:11px; color:rgba(255,255,255,.44); display:flex; align-items:center; gap:6px; }
.pw-feat::before { content:'✦'; color:var(--brand); font-size:8px; flex-shrink:0; }
.pw-cta { width:100%; padding:15px; background:linear-gradient(135deg,var(--brand),var(--accent)); color:#fff; border:none; border-radius:28px; font-family:'Jost',sans-serif; font-size:11px; letter-spacing:.16em; text-transform:uppercase; cursor:pointer; margin-bottom:10px; transition:opacity .2s; }
.pw-cta:active { opacity:.85; }
.pw-skip { width:100%; padding:11px; background:transparent; color:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.06); border-radius:28px; font-family:'Jost',sans-serif; font-size:10px; letter-spacing:.1em; text-transform:uppercase; cursor:pointer; }
#install-bar {
  display:none; position:fixed; bottom:0; left:0; right:0;
  background:#141009; border-top:1px solid rgba(255,255,255,.06);
  padding:14px 18px calc(14px + var(--safe-bot));
  z-index:200; flex-direction:row; align-items:center; gap:12px; animation:slide-up .38s ease;
}
#install-bar img { width:42px; height:42px; border-radius:10px; flex-shrink:0; }
.ib-text { flex:1; }
.ib-text strong { display:block; font-size:13px; font-weight:400; color:#fff; margin-bottom:1px; }
.ib-text span { font-size:11px; color:var(--muted); }
#install-go { background:var(--brand); color:#fff; border:none; border-radius:16px; padding:8px 16px; font-family:'Jost',sans-serif; font-size:10px; letter-spacing:.1em; text-transform:uppercase; cursor:pointer; flex-shrink:0; }
#install-dismiss { background:none; border:none; color:rgba(255,255,255,.2); font-size:24px; cursor:pointer; padding:4px; flex-shrink:0; line-height:1; }
</style>
<script>if('serviceWorker'in navigator)navigator.serviceWorker.register('/sw.js').catch(function(){});</script>
</head>
<body>
<div id="shell">
  <div id="topbar">
    <div class="t-brand">SupportRD</div>
    <div class="t-right">
      <select id="lang-sel">
        <option value="en-US">EN</option>
        <option value="es-ES">ES</option>
        <option value="fr-FR">FR</option>
        <option value="pt-BR">PT</option>
        <option value="ar-SA">AR</option>
        <option value="zh-CN">ZH</option>
        <option value="hi-IN">HI</option>
      </select>
      <a href="/dashboard" id="user-pill">
        <div id="user-av"><span id="user-init">?</span></div>
        <span id="user-name">Me</span>
      </a>
      <a href="/login" id="btn-login">Sign In</a>
    </div>
  </div>

  <div id="stage">
    <div id="sphere-wrap" role="button" aria-label="Tap to talk to Aria">
      <div id="sphere-orb"></div>
      <div id="sphere-mic">
        <svg viewBox="0 0 24 24">
          <rect x="9" y="2" width="6" height="11" rx="3"/>
          <path d="M5 10a7 7 0 0 0 14 0"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
          <line x1="8"  y1="21" x2="16" y2="21"/>
        </svg>
      </div>
      <div id="sphere-play">
        <svg viewBox="0 0 24 24"><polygon points="6,3 20,12 6,21"/></svg>
      </div>
      <div id="wavebars">
        <div class="wb"></div><div class="wb"></div><div class="wb"></div>
        <div class="wb"></div><div class="wb"></div>
      </div>
    </div>
    <div id="state-label">Tap to begin</div>
    <div id="response-box">Your personal AI hair advisor — powered by SupportRD</div>
  </div>

  <div id="bottombar">
    <button id="mode-btn">Type Instead</button>
    <div id="manual-row">
      <input id="manual-input" type="text" inputmode="text"
        placeholder="Type your hair question here…" autocomplete="off">
      <button id="manual-send">
        <svg viewBox="0 0 24 24"><path d="M2 12L22 2 16 22 11 13z"/></svg>
      </button>
    </div>
  </div>
</div>

<div id="pw-overlay">
  <div id="pw-sheet">
    <div class="pw-handle"></div>
    <div class="pw-badge">✦ Premium</div>
    <div class="pw-title">Unlock Full Access</div>
    <div class="pw-sub">Get unlimited consultations, your Hair Health Score, and full conversation history.</div>
    <div class="pw-price">
      <div class="pw-price-num">$80</div>
      <div class="pw-price-per">/month</div>
      <div class="pw-trial">✦ 7-day free trial · Cancel anytime</div>
    </div>
    <div class="pw-feats">
      <div class="pw-feat">Unlimited chats</div>
      <div class="pw-feat">Hair Health Score</div>
      <div class="pw-feat">Full history</div>
      <div class="pw-feat">WhatsApp priority</div>
    </div>
    <button class="pw-cta" id="pw-cta-btn">Start Free Trial</button>
    <button class="pw-skip" id="pw-skip-btn">Continue with Free</button>
  </div>
</div>

<div id="install-bar">
  <img src="/static/icon-192.png" alt="Aria">
  <div class="ib-text">
    <strong>Install Aria</strong>
    <span>Add to home screen for the full experience</span>
  </div>
  <button id="install-go">Install</button>
  <button id="install-dismiss">×</button>
</div>

<script>
// ═══════════════════════════════════════════════════════
// ARIA v7 — Clean rewrite. No duplicate vars. No inline events.
// ═══════════════════════════════════════════════════════
(function() {

var sphere   = document.getElementById('sphere-wrap');
var stLbl    = document.getElementById('state-label');
var respBox  = document.getElementById('response-box');
var langSel  = document.getElementById('lang-sel');
var modeBtn  = document.getElementById('mode-btn');
var manRow   = document.getElementById('manual-row');
var manInput = document.getElementById('manual-input');
var manSend  = document.getElementById('manual-send');
var pwOverlay = document.getElementById('pw-overlay');

// App state
var STATE        = 'idle'; // idle | listening | thinking | speaking | waiting
var chatHistory  = [];
var isManual     = false;
var pendingReply = null;

// Credentials
var token = localStorage.getItem('srd_token') || '';
var sessionId = localStorage.getItem('aria_sid') || (function() {
  var id = 'sid_' + Math.random().toString(36).slice(2);
  localStorage.setItem('aria_sid', id);
  return id;
})();

// Speech
var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
var recognition = null;
var mediaRec    = null;
var isRecording = false;
var silTimer    = null;
var noSpeechTmr = null;
var finalTxt    = '';
var interimTxt  = '';
var failCount   = 0;
var useFallback = false;

// Audio
var _actx     = null;
var analyser  = null;
var vizStream = null;
var animFrame = null;
var ambOsc    = null;
var ambGain   = null;

// ── AUTH ──────────────────────────────────────────────
if (token) {
  fetch('/api/auth/me', {headers:{'X-Auth-Token':token}})
    .then(function(r){return r.json();})
    .then(function(d){
      if (d.ok) {
        document.getElementById('user-pill').style.display = 'flex';
        document.getElementById('btn-login').style.display = 'none';
        var n = d.name || '';
        document.getElementById('user-name').textContent = n.split(' ')[0] || 'Me';
        document.getElementById('user-init').textContent = (n[0]||'?').toUpperCase();
        if (d.avatar) document.getElementById('user-av').innerHTML = '<img src="'+d.avatar+'" alt="">';
      } else {
        localStorage.removeItem('srd_token'); token = '';
      }
    }).catch(function(){});
}

// ── AUDIO CONTEXT ────────────────────────────────────
function getCtx() {
  if (!_actx) {
    _actx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (_actx.state === 'suspended') { _actx.resume(); }
  return _actx;
}

function tone(freq, dur, vol, type, delay) {
  try {
    var ctx  = getCtx();
    var osc  = ctx.createOscillator();
    var gain = ctx.createGain();
    var t    = ctx.currentTime + (delay || 0);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = type || 'sine';
    osc.frequency.setValueAtTime(freq, t);
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(vol || 0.13, t + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, t + dur);
    osc.start(t);
    osc.stop(t + dur + 0.02);
  } catch(e) {}
}

function sfxTap()   { tone(680, 0.05, 0.10, 'sine'); }
function sfxError() { tone(220, 0.22, 0.09, 'triangle'); }

function sfxChime() {
  // Called after API responds — Web Audio needs context unlocked at least once
  // (which happens on first sphere tap). Safe to call from async after that.
  try { getCtx(); } catch(e) {}
  tone(880,  0.28, 0.13, 'sine', 0.00);
  tone(1109, 0.30, 0.10, 'sine', 0.13);
  tone(1318, 0.34, 0.08, 'sine', 0.26);
}

var ambRunning = false;
var ambOsc2 = null;

function startAmbient() {
  if (ambRunning) return;
  ambRunning = true;
  try {
    var ctx = getCtx();
    // Clean up any leftover oscillators
    if (ambOsc)  { try { ambOsc.stop();  } catch(e) {} ambOsc  = null; }
    if (ambOsc2) { try { ambOsc2.stop(); } catch(e) {} ambOsc2 = null; }

    ambGain = ctx.createGain();
    ambGain.gain.setValueAtTime(0, ctx.currentTime);
    ambGain.gain.linearRampToValueAtTime(0.030, ctx.currentTime + 3.5);
    ambGain.connect(ctx.destination);

    ambOsc = ctx.createOscillator();
    ambOsc.type = 'sine';
    ambOsc.frequency.value = 174;
    ambOsc.connect(ambGain);
    ambOsc.start();

    // Soft harmonic
    var g2 = ctx.createGain();
    g2.gain.value = 0.010;
    g2.connect(ctx.destination);
    ambOsc2 = ctx.createOscillator();
    ambOsc2.type = 'sine';
    ambOsc2.frequency.value = 348;
    ambOsc2.connect(g2);
    ambOsc2.start();
  } catch(e) { ambRunning = false; }
}

function stopAmbient() {
  if (!ambRunning) return;
  ambRunning = false;
  var o1 = ambOsc; var o2 = ambOsc2; var g = ambGain;
  ambOsc = null; ambOsc2 = null; ambGain = null;
  try {
    if (g && _actx) {
      g.gain.cancelScheduledValues(_actx.currentTime);
      g.gain.setValueAtTime(g.gain.value, _actx.currentTime);
      g.gain.linearRampToValueAtTime(0, _actx.currentTime + 0.4);
    }
    setTimeout(function(){
      try{if(o1)o1.stop();}catch(e){}
      try{if(o2)o2.stop();}catch(e){}
    }, 500);
  } catch(e) {}
}

// ── MIC VISUALIZER ───────────────────────────────────
function startViz(stream) {
  vizStream = stream;
  try {
    var ctx = getCtx();
    var src = ctx.createMediaStreamSource(stream);
    analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.80;
    src.connect(analyser);
    var data = new Uint8Array(analyser.frequencyBinCount);
    var bars = document.querySelectorAll('.wb');
    function tick() {
      if (STATE !== 'listening') {
        sphere.style.transform = '';
        sphere.style.transition = '';
        bars.forEach(function(b){ b.style.transform=''; b.style.animationPlayState='running'; b.style.transition=''; });
        return;
      }
      analyser.getByteFrequencyData(data);
      var sum = 0;
      for (var i = 1; i < 10; i++) sum += data[i];
      var lvl = Math.min(1, sum / (10 * 90));
      sphere.style.transition = 'transform 0.07s ease-out';
      sphere.style.transform  = 'scale(' + (1 + lvl * 0.42) + ')';
      var step = Math.floor(data.length / 5);
      bars.forEach(function(b, i) {
        var s = 0;
        for (var j = i*step; j < (i+1)*step && j < data.length; j++) s += data[j];
        var sc = Math.max(0.15, Math.min(2.8, s/step/60));
        b.style.animationPlayState = 'paused';
        b.style.transition = 'transform 0.06s ease';
        b.style.transform  = 'scaleY('+sc+')';
      });
      animFrame = requestAnimationFrame(tick);
    }
    animFrame = requestAnimationFrame(tick);
  } catch(e) {}
}

function stopViz() {
  if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
  if (vizStream) {
    try { vizStream.getTracks().forEach(function(t){t.stop();}); } catch(e) {}
    vizStream = null;
  }
  sphere.style.transform = '';
  sphere.style.transition = '';
  document.querySelectorAll('.wb').forEach(function(b){
    b.style.transform=''; b.style.animationPlayState='running'; b.style.transition='';
  });
}

// ── SPHERE STATE ─────────────────────────────────────
function setSphereState(s) {
  STATE = s;
  sphere.classList.remove('listening','speaking','waiting');
  stLbl.classList.remove('lit');
  if (s==='listening'||s==='speaking'||s==='waiting') stLbl.classList.add('lit');
  if (s==='listening') sphere.classList.add('listening');
  if (s==='speaking')  sphere.classList.add('speaking');
  if (s==='waiting')   sphere.classList.add('waiting');
}

function setIdle(msg) {
  pendingReply = null;
  setSphereState('idle');
  stLbl.textContent = 'Tap to begin';
  stLbl.classList.remove('lit');
  respBox.classList.remove('thinking');
  if (msg) respBox.textContent = msg;
  stopViz();
}

// ── SPEECH SYNTHESIS ─────────────────────────────────
// speak() stores text and shows waiting state.
// _doSpeak() MUST be called from a real user gesture (handleTap).
// This is the only way speechSynthesis works on iOS/Android.

function speak(text) {
  if (!text) { setIdle(); return; }
  pendingReply = text;
  sfxChime();
  setSphereState('waiting');
  stLbl.textContent = 'Tap sphere to hear \u25B6';
  stopAmbient();
}

function _doSpeak(text) {
  if (!text) { setIdle(); return; }
  pendingReply = null;

  if (!window.speechSynthesis) {
    setSphereState('speaking');
    stLbl.textContent = 'Response ready';
    setTimeout(function(){ setIdle(); startAmbient(); }, 3000);
    return;
  }

  try { window.speechSynthesis.cancel(); } catch(e) {}

  var utt = new SpeechSynthesisUtterance(text);
  utt.lang   = langSel.value;
  utt.rate   = 0.90;
  utt.pitch  = 1.04;
  utt.volume = 1.0;

  try {
    var voices = window.speechSynthesis.getVoices();
    var names  = ['Samantha','Victoria','Karen','Moira','Tessa','Fiona',
                  'Microsoft Zira','Google US English','Hazel'];
    var pick = null;
    for (var i = 0; i < names.length && !pick; i++) {
      (function(n){ pick = voices.find(function(v){ return v.name.indexOf(n)>-1; }); })(names[i]);
    }
    if (!pick) pick = voices.find(function(v){ return /^en/.test(v.lang); });
    if (pick) utt.voice = pick;
  } catch(e) {}

  utt.onstart = function(){ setSphereState('speaking'); stLbl.textContent = 'Speaking\u2026'; };
  utt.onend   = function(){ setIdle(); startAmbient(); };
  utt.onerror = function(ev){
    if (ev.error !== 'canceled' && ev.error !== 'cancelled') setIdle();
  };

  setSphereState('speaking');
  stLbl.textContent = 'Speaking\u2026';
  try { window.speechSynthesis.speak(utt); }
  catch(e) { setIdle(); }
}

// ── API ───────────────────────────────────────────────
function askAria(text) {
  if (!text || text.trim().length < 2) { setIdle("Didn't catch that."); return; }
  stopAmbient(); // stop ambient during thinking
  respBox.textContent = text;
  respBox.classList.add('thinking');
  STATE = 'thinking';
  sphere.classList.remove('listening','speaking','waiting');
  stLbl.textContent = 'Thinking\u2026';
  stLbl.classList.add('lit');
  stopViz();

  var t1 = setTimeout(function(){ if(STATE==='thinking') stLbl.textContent='Still thinking\u2026'; }, 8000);
  var t2 = setTimeout(function(){ if(STATE==='thinking') stLbl.textContent='Almost there\u2026'; }, 20000);
  var ctrl = new AbortController();
  var t3 = setTimeout(function(){ ctrl.abort(); }, 45000);

  fetch('/api/recommend', {
    method:'POST', signal:ctrl.signal,
    headers:{'Content-Type':'application/json','X-Auth-Token':token,'X-Session-Id':sessionId},
    body:JSON.stringify({text:text.trim(), lang:langSel.value, history:chatHistory.slice(-8)})
  })
  .then(function(r){
    if (!r.ok) {
      return r.text().then(function(t){ throw new Error('HTTP '+r.status+': '+t.slice(0,200)); });
    }
    return r.json();
  })
  .then(function(d){
    clearTimeout(t1); clearTimeout(t2); clearTimeout(t3);
    respBox.classList.remove('thinking');
    if (d.error) {
      sfxError();
      // Show the actual error so we can diagnose
      respBox.textContent = 'Error: ' + d.error;
      setIdle('');
      stLbl.textContent = 'Error — tap to retry';
      return;
    }
    var reply = d.recommendation || d.response || '';
    if (!reply) { sfxError(); setIdle('No response. Tap to retry.'); return; }
    chatHistory.push({role:'user',content:text});
    chatHistory.push({role:'assistant',content:reply});
    if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
    respBox.textContent = reply;
    speak(reply);
    if (d.show_paywall) setTimeout(openPW, 1800);
  })
  .catch(function(e){
    clearTimeout(t1); clearTimeout(t2); clearTimeout(t3);
    respBox.classList.remove('thinking');
    var msg = e.name==='AbortError' ? 'Timed out (45s) \u2014 tap to retry.' : ('Network error: ' + e.message);
    respBox.textContent = msg;
    sfxError();
    STATE = 'idle';
    stLbl.textContent = 'Tap to retry';
    stLbl.classList.remove('lit');
  });
}

// ── SPEECH RECOGNITION ───────────────────────────────
function startSpeechRec() {
  if (!SR) { startMediaRec(); return; }

  finalTxt = ''; interimTxt = '';
  var submitted = false;
  var gotAnyResult = false;

  // Android 14 fix: request mic permission explicitly first
  navigator.mediaDevices.getUserMedia({audio:true, video:false})
    .then(function(stream) {
      startViz(stream);
      _doStartSpeechRec(stream, onDone);
    })
    .catch(function(err) {
      setIdle('Mic denied — use typing mode.');
      activateManual();
    });

  function onDone(got) {
    if (submitted) return;
    submitted = true;
    if (got && got.trim().length > 1) {
      failCount = 0;
      askAria(got.trim());
    } else {
      setIdle('Tap and speak \u2014 try again.');
    }
  }

  function _doStartSpeechRec(stream, done) {
    recognition = new SR();
    recognition.lang            = langSel.value;
    recognition.continuous      = false;
    recognition.interimResults  = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = function() {
      stopAmbient();
      setSphereState('listening');
      stLbl.textContent   = 'Listening\u2026';
      respBox.textContent = 'Listening\u2026';

      noSpeechTmr = setTimeout(function() {
        if (STATE !== 'listening' || submitted) return;
        try { recognition.abort(); } catch(e) {}
        if (!gotAnyResult) {
          if (failCount < 2) {
            failCount++;
            stopViz();
            // retry
            submitted = false;
            navigator.mediaDevices.getUserMedia({audio:true,video:false})
              .then(function(s){ startViz(s); _doStartSpeechRec(s, done); })
              .catch(function(){ done(''); });
          } else {
            failCount = 0; useFallback = true;
            stopViz();
            done('');
          }
        }
      }, 7000);
    };

    recognition.onresult = function(ev) {
      clearTimeout(noSpeechTmr); clearTimeout(silTimer);
      gotAnyResult = true; failCount = 0;

      var f = ''; var interim = '';
      for (var i = 0; i < ev.results.length; i++) {
        if (ev.results[i].isFinal) f       += ev.results[i][0].transcript + ' ';
        else                        interim += ev.results[i][0].transcript;
      }
      if (f.length > finalTxt.length) finalTxt = f;
      interimTxt = interim;

      var display = (finalTxt + interimTxt).trim();
      if (display) respBox.textContent = display;

      // If we have a final result wait a short moment then submit
      if (finalTxt.trim().length > 0) {
        clearTimeout(silTimer);
        silTimer = setTimeout(function() {
          try { recognition.stop(); } catch(e) {}
        }, 600);
      } else {
        // only interim — wait longer for silence
        clearTimeout(silTimer);
        silTimer = setTimeout(function() {
          try { recognition.stop(); } catch(e) {}
        }, 1800);
      }
    };

    recognition.onend = function() {
      clearTimeout(silTimer); clearTimeout(noSpeechTmr);
      stopViz();
      if (STATE !== 'listening') return;
      done((finalTxt + interimTxt).trim());
    };

    recognition.onerror = function(ev) {
      clearTimeout(silTimer); clearTimeout(noSpeechTmr);
      stopViz();
      if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
        setIdle('Mic blocked \u2014 use typing.');
        activateManual();
      } else if (ev.error === 'network') {
        useFallback = true;
        startMediaRec();
      } else if (ev.error === 'no-speech') {
        done('');
      } else {
        done('');
      }
    };

    try { recognition.start(); }
    catch(e) { stopViz(); done(''); }
  }
}

function startMediaRec() {
  navigator.mediaDevices.getUserMedia({audio:true,video:false})
    .then(function(stream){
      setSphereState('listening');
      stLbl.textContent='Listening\u2026';
      respBox.textContent='Listening\u2026';
      startViz(stream);
      var chunks=[]; isRecording=true;
      var mime = ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/mp4']
        .find(function(m){ return MediaRecorder.isTypeSupported(m); }) || '';
      mediaRec = new MediaRecorder(stream, mime?{mimeType:mime}:{});
      mediaRec.ondataavailable = function(e){ if(e.data&&e.data.size>0) chunks.push(e.data); };
      mediaRec.onstop = function(){
        isRecording=false; stopViz();
        var blob = new Blob(chunks,{type:mime||'audio/webm'});
        if (blob.size<600){ setIdle('Too short \u2014 tap to try again.'); return; }
        STATE='thinking';
        sphere.classList.remove('listening');
        stLbl.textContent='Processing\u2026';
        respBox.classList.add('thinking');
        var fd=new FormData(); fd.append('audio',blob,'rec.webm');
        fetch('/api/transcribe',{method:'POST',body:fd})
          .then(function(r){return r.json();})
          .then(function(d){
            respBox.classList.remove('thinking');
            if (d.fallback || !d.text) {
              // Transcription failed — show error and switch to typing
              respBox.textContent = d.error ? ('Mic error: ' + d.error) : 'Could not hear you clearly.';
              setIdle('');
              stLbl.textContent = 'Use typing mode \u2193';
              activateManual();
              setTimeout(function(){ manInput.focus(); }, 300);
              return;
            }
            askAria(d.text.trim());
          })text.trim());
          })
          .catch(function(){ respBox.classList.remove('thinking'); setIdle('Audio error.'); });
      };
      mediaRec.start();
      setTimeout(function(){ if(isRecording) stopMediaRec(); }, 13000);
    })
    .catch(function(){ setIdle('Mic denied \u2014 use typing.'); activateManual(); });
}

function stopMediaRec() {
  if (!isRecording||!mediaRec) return;
  isRecording=false;
  try { mediaRec.stop(); } catch(e) {}
}

// ── SPHERE TAP ───────────────────────────────────────
// Called synchronously from pointerup = real user gesture.
// speechSynthesis.speak() works HERE and ONLY here on iOS/Android.

function handleTap() {
  if (isManual) return;

  // Step 1: Unlock AudioContext (iOS requires gesture to start audio)
  getCtx();

  // Step 2: Prime voice list (iOS needs this called before speak())
  if (window.speechSynthesis) { try { window.speechSynthesis.getVoices(); } catch(e){} }

  // Step 3: Start ambient (safe now, ctx unlocked)
  startAmbient();

  // Step 4: Tap click sound
  sfxTap();

  // ── WAITING: has queued reply → speak it NOW ──────
  if (pendingReply) {
    var txt = pendingReply;
    // _doSpeak clears pendingReply internally
    _doSpeak(txt);
    return;
  }

  // ── SPEAKING: tap to stop ─────────────────────────
  if (STATE === 'speaking') {
    try { window.speechSynthesis.cancel(); } catch(e) {}
    setIdle();
    startAmbient();
    return;
  }

  // ── LISTENING: tap to stop ────────────────────────
  if (STATE === 'listening') {
    if (recognition) { try { recognition.stop(); } catch(e){} }
    stopMediaRec();
    clearTimeout(silTimer); clearTimeout(noSpeechTmr);
    stopViz(); setIdle();
    return;
  }

  // ── THINKING: ignore ──────────────────────────────
  if (STATE === 'thinking') return;

// ── IDLE: start listening ─────────────────────────
  // Force MediaRecorder on Android 14 (SpeechRecognition broken in PWA mode)
  var isAndroid14 = /Android 1[4-9]/.test(navigator.userAgent);
  if (SR && !useFallback && !isAndroid14) startSpeechRec();
  else startMediaRec();
}

var _ptDown = false;
sphere.addEventListener('pointerdown',   function(e){ e.preventDefault(); _ptDown=true; },  {passive:false});
sphere.addEventListener('pointerup',     function(e){ e.preventDefault(); if(_ptDown){_ptDown=false; handleTap();} }, {passive:false});
sphere.addEventListener('pointercancel', function(){  _ptDown=false; });
sphere.addEventListener('contextmenu',   function(e){ e.preventDefault(); }, {passive:false});

// ── MANUAL MODE ──────────────────────────────────────
function activateManual() {
  if (isManual) return;
  isManual = true;
  manRow.style.display = 'flex';
  modeBtn.textContent  = 'Voice Mode';
  modeBtn.classList.add('on');
}

modeBtn.addEventListener('click', function(){
  isManual = !isManual;
  manRow.style.display = isManual ? 'flex' : 'none';
  modeBtn.textContent  = isManual ? 'Voice Mode' : 'Type Instead';
  modeBtn.classList.toggle('on', isManual);
  if (isManual) setTimeout(function(){ manInput.focus(); }, 50);
});

function submitManual() {
  var t = manInput.value.trim();
  if (t.length < 2) return;
  manInput.value = '';
  // Unlock audio on this gesture too (user tapped Send)
  getCtx();
  if (window.speechSynthesis) { try { window.speechSynthesis.getVoices(); } catch(e){} }
  startAmbient();
  askAria(t);
}

manSend.addEventListener('click', function(e){
  e.preventDefault();
  // Also unlock audio context on send button tap
  getCtx();
  if (window.speechSynthesis) { try { window.speechSynthesis.getVoices(); } catch(e){} }
  submitManual();
});
manInput.addEventListener('keydown', function(e){
  if (e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); submitManual(); }
});

// ── PAYWALL ───────────────────────────────────────────
function openPW()  { pwOverlay.style.display='flex'; }
function closePW() { pwOverlay.style.display='none'; }
pwOverlay.addEventListener('click', function(e){ if(e.target===pwOverlay) closePW(); });
document.getElementById('pw-skip-btn').addEventListener('click', closePW);
document.getElementById('pw-cta-btn').addEventListener('click', function(){
  if (!token) { window.location.href='/login?next=subscribe'; return; }
  fetch('/api/subscription/checkout',{method:'POST',headers:{'Content-Type':'application/json','X-Auth-Token':token}})
    .then(function(r){return r.json();})
    .then(function(d){ window.location.href=d.checkout_url||'https://supportrd.com/products/hair-advisor-premium'; })
    .catch(function(){ window.location.href='https://supportrd.com/products/hair-advisor-premium'; });
});

// ── PWA INSTALL ───────────────────────────────────────
var deferredInstall = null;
var installBar = document.getElementById('install-bar');

window.addEventListener('beforeinstallprompt', function(e){
  e.preventDefault();
  deferredInstall = e;
  var isPWA = window.matchMedia('(display-mode:standalone)').matches || navigator.standalone;
  if (!isPWA && !localStorage.getItem('pwa-dismissed')) {
    setTimeout(function(){ installBar.style.display='flex'; }, 9000);
  }
});
document.getElementById('install-go').addEventListener('click', function(){
  if (!deferredInstall) return;
  deferredInstall.prompt();
  deferredInstall.userChoice.then(function(r){
    if (r.outcome==='accepted') dismissInstall();
    deferredInstall=null;
  });
});
document.getElementById('install-dismiss').addEventListener('click', function(){ dismissInstall(); });
function dismissInstall(){ localStorage.setItem('pwa-dismissed','1'); installBar.style.display='none'; }
window.addEventListener('appinstalled', dismissInstall);
if (window.matchMedia('(display-mode:standalone)').matches || navigator.standalone) {
  localStorage.setItem('pwa-dismissed','1');
}

})(); // end IIFE
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════
# DASHBOARD PAGE
# ═══════════════════════════════════════════════════════
DASHBOARD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#f0ebe8">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<title>Dashboard — SupportRD</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<style>
:root {
  --brand:#c1a3a2; --accent:#9d7f6a;
  --bg:#f0ebe8; --card:#fff;
  --text:#0d0906; --muted:rgba(0,0,0,.38);
  --border:rgba(193,163,162,.15);
  --safe-top:env(safe-area-inset-top,0px);
  --safe-bot:env(safe-area-inset-bottom,0px);
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}
html,body{height:100%;height:100dvh;overflow:hidden;background:var(--bg);font-family:'Jost',sans-serif;font-weight:300;color:var(--text);}
#shell{display:flex;flex-direction:column;height:100dvh;padding-top:var(--safe-top);padding-bottom:var(--safe-bot);}
#header{display:flex;align-items:center;gap:12px;padding:12px 18px;background:var(--card);border-bottom:1px solid var(--border);flex-shrink:0;box-shadow:0 1px 8px rgba(0,0,0,.04);position:relative;z-index:10;}
#back-btn{width:34px;height:34px;border-radius:50%;background:var(--bg);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:background .18s;}
#back-btn:active{background:#e0d8d4;}
#back-btn svg{width:18px;height:18px;stroke:var(--text);fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;}
.hdr-logo{font-family:'Cormorant Garamond',serif;font-size:18px;font-style:italic;color:var(--text);flex:1;}
.hdr-right{display:flex;align-items:center;gap:9px;}
#d-avatar{width:30px;height:30px;border-radius:50%;background:var(--brand);display:flex;align-items:center;justify-content:center;font-size:12px;color:#fff;overflow:hidden;flex-shrink:0;}
#d-avatar img{width:100%;height:100%;object-fit:cover;}
#d-name{font-size:12px;}
#signout{font-size:9px;letter-spacing:.1em;text-transform:uppercase;background:none;border:1px solid var(--border);border-radius:13px;padding:5px 12px;cursor:pointer;color:var(--accent);font-family:'Jost',sans-serif;transition:all .2s;}
#signout:active{background:var(--accent);color:#fff;border-color:var(--accent);}
#scroll{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:14px 14px 28px;scroll-behavior:smooth;}
.card{background:var(--card);border-radius:18px;padding:18px 18px 20px;margin-bottom:12px;border:1px solid var(--border);box-shadow:0 2px 12px rgba(0,0,0,.04);}
.card-eyebrow{font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:var(--brand);margin-bottom:6px;}
.card-title{font-family:'Cormorant Garamond',serif;font-size:22px;font-style:italic;color:var(--text);margin-bottom:16px;}
.score-card{background:linear-gradient(140deg,#0d0906 0%,#1c1108 100%);border:none;}
.score-card .card-eyebrow{color:rgba(193,163,162,.45);}
.ring-wrap{width:148px;height:148px;margin:0 auto 14px;position:relative;}
.ring-svg{transform:rotate(-90deg);}
.ring-bg{fill:none;stroke:rgba(193,163,162,.09);stroke-width:10;}
.ring-fill{fill:none;stroke-width:10;stroke-linecap:round;stroke-dasharray:390;stroke-dashoffset:390;transition:stroke-dashoffset 2.2s cubic-bezier(.22,1,.36,1),stroke .5s;}
.ring-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.ring-num{font-family:'Cormorant Garamond',serif;font-size:50px;font-style:italic;color:#fff;line-height:1;}
.ring-denom{font-size:11px;color:rgba(255,255,255,.25);}
.score-status{font-family:'Cormorant Garamond',serif;font-size:18px;font-style:italic;color:var(--brand);text-align:center;margin-bottom:4px;}
.score-hint{font-size:11px;color:rgba(255,255,255,.26);text-align:center;line-height:1.65;margin-bottom:16px;max-width:260px;margin-left:auto;margin-right:auto;}
.sub-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.sub-bar-item .sb-label{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:rgba(193,163,162,.38);margin-bottom:4px;}
.sub-bar-item .sb-track{height:3px;background:rgba(255,255,255,.05);border-radius:2px;overflow:hidden;}
.sub-bar-item .sb-fill{height:100%;border-radius:2px;transition:width 1.8s cubic-bezier(.22,1,.36,1);}
.sub-bar-item .sb-val{font-size:9px;color:rgba(255,255,255,.25);margin-top:3px;}
.form-group{margin-bottom:11px;}
.form-group label{display:block;font-size:9px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);margin-bottom:5px;}
select,input[type=text]{width:100%;padding:11px 13px;border:1px solid rgba(193,163,162,.22);border-radius:10px;font-family:'Jost',sans-serif;font-size:13px;color:var(--text);background:#faf6f3;outline:none;-webkit-appearance:none;appearance:none;transition:border .2s;}
select:focus,input[type=text]:focus{border-color:var(--brand);}
.chip-field{display:flex;align-items:center;flex-wrap:wrap;gap:5px;min-height:44px;padding:9px 12px;border:1px solid rgba(193,163,162,.22);border-radius:10px;background:#faf6f3;cursor:pointer;transition:border .2s;touch-action:manipulation;-webkit-user-select:none;user-select:none;}
.chip-field:active{border-color:var(--brand);}
.chip-placeholder{font-size:12px;color:rgba(0,0,0,.26);pointer-events:none;}
.chip-tags{display:flex;flex-wrap:wrap;gap:4px;flex:1;pointer-events:none;}
.chip{display:inline-flex;align-items:center;gap:4px;background:var(--brand);color:#fff;border-radius:10px;padding:3px 9px;font-size:10px;}
.chip-x{font-size:14px;line-height:1;cursor:pointer;opacity:.7;pointer-events:auto;}
.chip-arrow{font-size:18px;color:rgba(0,0,0,.22);flex-shrink:0;margin-left:auto;pointer-events:none;}
.save-btn{width:100%;padding:12px;border:none;border-radius:20px;background:var(--brand);color:#fff;font-family:'Jost',sans-serif;font-size:10px;letter-spacing:.14em;text-transform:uppercase;cursor:pointer;margin-top:9px;transition:background .2s;}
.save-btn:active{background:var(--accent);}
.stats-row{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:16px;}
.stat .s-num{font-family:'Cormorant Garamond',serif;font-size:38px;font-style:italic;color:var(--brand);line-height:1;}
.stat .s-lbl{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-top:2px;}
.cta{display:block;width:100%;padding:15px 18px;border:none;border-radius:14px;text-align:center;cursor:pointer;font-family:'Jost',sans-serif;text-decoration:none;margin-bottom:10px;transition:opacity .18s;}
.cta:active{opacity:.84;}
.cta-t{font-family:'Cormorant Garamond',serif;font-size:17px;font-style:italic;}
.cta-s{font-size:9px;letter-spacing:.1em;text-transform:uppercase;opacity:.72;margin-top:2px;}
.cta-rose{background:linear-gradient(135deg,#c1a3a2,#9d7f6a);color:#fff;}
.cta-dark{background:linear-gradient(135deg,#0d0906,#2a1f18);color:#fff;}
.cta-wa{background:linear-gradient(135deg,#25D366,#128C7E);color:#fff;}
.hist-item{padding:10px 0;border-bottom:1px solid rgba(193,163,162,.09);}
.hist-item:last-child{border-bottom:none;}
.hist-role{font-size:8px;letter-spacing:.14em;text-transform:uppercase;color:var(--brand);margin-bottom:2px;}
.hist-text{font-size:11px;color:var(--muted);line-height:1.55;}
.clr-btn{font-size:9px;color:var(--muted);background:none;border:none;cursor:pointer;letter-spacing:.08em;text-transform:uppercase;margin-top:10px;font-family:'Jost',sans-serif;}

/* ── PICKER ─────────────────────────────────────────── */
#picker-backdrop{
  display:none; position:fixed; inset:0;
  background:rgba(0,0,0,.55);
  backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px);
  z-index:800;
}
#picker-overlay{
  display:none; position:fixed; inset:0;
  z-index:801;
  align-items:flex-end; justify-content:center;
  pointer-events:none;
}
#picker-sheet{
  background:#fff; border-radius:24px 24px 0 0;
  width:100%; max-width:520px;
  padding-bottom:calc(16px + env(safe-area-inset-bottom,0px));
  animation:pkup .30s cubic-bezier(.32,.72,0,1);
  max-height:82vh; display:flex; flex-direction:column;
  pointer-events:auto;
}
@keyframes pkup{from{transform:translateY(100%)}to{transform:translateY(0)}}
.pk-handle{width:32px;height:4px;background:rgba(0,0,0,.1);border-radius:2px;margin:11px auto 0;flex-shrink:0;}
.pk-header{display:flex;align-items:center;justify-content:space-between;padding:14px 18px 12px;border-bottom:1px solid rgba(193,163,162,.14);flex-shrink:0;}
.pk-title{font-family:'Cormorant Garamond',serif;font-size:21px;font-style:italic;}
.pk-done{background:var(--brand);color:#fff;border:none;border-radius:16px;padding:7px 18px;font-family:'Jost',sans-serif;font-size:10px;letter-spacing:.1em;text-transform:uppercase;cursor:pointer;touch-action:manipulation;}
.pk-search-wrap{padding:10px 18px 6px;flex-shrink:0;}
.pk-search{width:100%;padding:9px 15px;border:1px solid rgba(193,163,162,.25);border-radius:20px;font-family:'Jost',sans-serif;font-size:13px;background:#faf6f3;outline:none;color:var(--text);-webkit-user-select:text;user-select:text;}
.pk-list{padding:8px 16px 6px;display:flex;flex-wrap:wrap;gap:8px;overflow-y:auto;-webkit-overflow-scrolling:touch;flex:1;}
.pk-opt{padding:9px 16px;border:1px solid rgba(193,163,162,.2);border-radius:20px;font-size:12px;color:var(--muted);cursor:pointer;background:#faf6f3;transition:all .14s;user-select:none;-webkit-user-select:none;touch-action:manipulation;}
.pk-opt.sel{background:var(--brand);color:#fff;border-color:var(--brand);}
.pk-opt:active{opacity:.8;}

/* ── PAYMENT ─────────────────────────────────────────── */
#pay-overlay{display:none;position:fixed;inset:0;background:var(--bg);z-index:700;flex-direction:column;overflow-y:auto;padding-top:env(safe-area-inset-top,0px);}
.pay-hdr{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;background:#0d0906;flex-shrink:0;}
.pay-hdr-title{font-family:'Cormorant Garamond',serif;font-size:20px;font-style:italic;color:var(--brand);}
.pay-close-btn{background:none;border:none;color:rgba(255,255,255,.3);font-size:28px;cursor:pointer;line-height:1;}
.pay-body{flex:1;padding:28px 20px calc(36px + env(safe-area-inset-bottom,0px));max-width:440px;margin:0 auto;width:100%;}
.pay-hero{text-align:center;margin-bottom:28px;}
.pay-big{font-family:'Cormorant Garamond',serif;font-size:70px;font-style:italic;line-height:1;}
.pay-mo{font-size:16px;color:var(--muted);}
.pay-trial{font-size:11px;color:var(--brand);margin-top:6px;letter-spacing:.04em;}
.pay-box{background:var(--card);border-radius:16px;padding:18px;margin-bottom:22px;}
.pay-box-label{font-size:9px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:12px;}
.pay-feat-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);font-size:12px;color:rgba(0,0,0,.6);}
.pay-feat-row:last-child{border-bottom:none;}
.pay-feat-row::before{content:'✦';color:var(--brand);font-size:9px;flex-shrink:0;}
.pay-go{width:100%;padding:16px;background:linear-gradient(135deg,var(--brand),var(--accent));color:#fff;border:none;border-radius:28px;font-family:'Jost',sans-serif;font-size:11px;letter-spacing:.14em;text-transform:uppercase;cursor:pointer;transition:opacity .2s;}
.pay-go:active{opacity:.85;}
.pay-note{text-align:center;font-size:10px;color:var(--muted);margin-top:10px;line-height:1.65;}
</style>
</head>
<body>
<div id="shell">
  <div id="header">
    <button id="back-btn">
      <svg viewBox="0 0 24 24"><polyline points="15,18 9,12 15,6"/></svg>
    </button>
    <div class="hdr-logo">SupportRD</div>
    <div class="hdr-right">
      <div id="d-avatar"><span id="d-init">?</span></div>
      <span id="d-name">Loading…</span>
      <button id="signout">Sign Out</button>
    </div>
  </div>

  <div id="scroll">
    <div class="card score-card">
      <div class="card-eyebrow">✦ Hair Health Score</div>
      <div class="ring-wrap">
        <svg class="ring-svg" width="148" height="148" viewBox="0 0 148 148">
          <circle class="ring-bg"   cx="74" cy="74" r="62"/>
          <circle class="ring-fill" id="ring" cx="74" cy="74" r="62" stroke="#c1a3a2"/>
        </svg>
        <div class="ring-center">
          <div class="ring-num"   id="score-num">—</div>
          <div class="ring-denom">/ 100</div>
        </div>
      </div>
      <div class="score-status" id="score-status">Complete your profile</div>
      <div class="score-hint"   id="score-hint">Fill in your hair details below to calculate your score</div>
      <div class="sub-grid">
        <div class="sub-bar-item"><div class="sb-label">Moisture</div><div class="sb-track"><div class="sb-fill" id="bar-m" style="width:0%;background:#c1a3a2"></div></div><div class="sb-val" id="val-m">—</div></div>
        <div class="sub-bar-item"><div class="sb-label">Strength</div><div class="sb-track"><div class="sb-fill" id="bar-s" style="width:0%;background:#9d7f6a"></div></div><div class="sb-val" id="val-s">—</div></div>
        <div class="sub-bar-item"><div class="sb-label">Scalp</div><div class="sb-track"><div class="sb-fill" id="bar-sc" style="width:0%;background:#c1a3a2"></div></div><div class="sb-val" id="val-sc">—</div></div>
        <div class="sub-bar-item"><div class="sb-label">Growth</div><div class="sb-track"><div class="sb-fill" id="bar-g" style="width:0%;background:#9d7f6a"></div></div><div class="sb-val" id="val-g">—</div></div>
      </div>
    </div>

    <div class="card">
      <div class="card-eyebrow">Build your score</div>
      <div class="card-title">Hair Profile</div>
      <div class="form-group">
        <label>Hair Type</label>
        <select id="p-type">
          <option value="">Select…</option>
          <option>Straight</option><option>Wavy</option><option>Curly</option>
          <option>Coily / 4C</option><option>Fine</option><option>Thick</option>
        </select>
      </div>
      <div class="form-group">
        <label>Main Concerns</label>
        <div class="chip-field" id="cf-concerns">
          <span class="chip-placeholder" id="ph-concerns">Tap to select…</span>
          <div class="chip-tags" id="tags-concerns"></div>
          <span class="chip-arrow">›</span>
        </div>
        <input type="hidden" id="p-concerns">
      </div>
      <div class="form-group">
        <label>Chemical Treatments</label>
        <div class="chip-field" id="cf-treatments">
          <span class="chip-placeholder" id="ph-treatments">Tap to select…</span>
          <div class="chip-tags" id="tags-treatments"></div>
          <span class="chip-arrow">›</span>
        </div>
        <input type="hidden" id="p-treatments">
      </div>
      <div class="form-group">
        <label>Products Being Used</label>
        <div class="chip-field" id="cf-products">
          <span class="chip-placeholder" id="ph-products">Tap to select…</span>
          <div class="chip-tags" id="tags-products"></div>
          <span class="chip-arrow">›</span>
        </div>
        <input type="hidden" id="p-products">
      </div>
      <div class="form-group">
        <label>Heat Tool Usage</label>
        <select id="p-heat">
          <option value="">Select…</option>
          <option value="never">Never</option>
          <option value="rarely">Rarely (monthly)</option>
          <option value="sometimes">Sometimes (weekly)</option>
          <option value="daily">Daily</option>
        </select>
      </div>
      <div class="form-group">
        <label>Water Type</label>
        <select id="p-water">
          <option value="">Select…</option>
          <option value="soft">Soft water</option>
          <option value="hard">Hard water</option>
          <option value="unknown">Not sure</option>
        </select>
      </div>
      <button class="save-btn" id="save-profile-btn">Save & Update Score</button>
    </div>

    <div class="card">
      <div class="card-eyebrow">Overview</div>
      <div class="card-title">My Journey</div>
      <div class="stats-row">
        <div class="stat"><div class="s-num" id="stat-chats">—</div><div class="s-lbl">Consultations</div></div>
        <div class="stat"><div class="s-num" id="stat-score">—</div><div class="s-lbl">Hair Score</div></div>
      </div>
      <a href="/" class="cta cta-rose"><div class="cta-t">Talk to Aria</div><div class="cta-s">AI Hair Advisor</div></a>
      <button id="upgrade-btn" class="cta cta-dark"><div class="cta-t">Upgrade to Premium</div><div class="cta-s">7-day free trial · $80/month</div></button>
      <a href="https://wa.me/18292332670" target="_blank" class="cta cta-wa"><div class="cta-t">Live Hair Advisor</div><div class="cta-s">WhatsApp · 829-233-2670</div></a>
    </div>

    <div class="card">
      <div class="card-eyebrow">Memory</div>
      <div class="card-title">Recent Chats</div>
      <div id="hist-list"><div style="color:var(--muted);font-size:12px">Loading…</div></div>
      <button id="clr-hist-btn" class="clr-btn">Clear history</button>
    </div>
  </div>
</div>

<!-- PICKER -->
<div id="picker-backdrop"></div>
<div id="picker-overlay">
  <div id="picker-sheet">
    <div class="pk-handle"></div>
    <div class="pk-header">
      <span class="pk-title" id="pk-title">Select</span>
      <button class="pk-done" id="pk-done-btn">Done</button>
    </div>
    <div class="pk-search-wrap">
      <input class="pk-search" id="pk-search" type="text" placeholder="Search…" autocomplete="off">
    </div>
    <div class="pk-list" id="pk-list"></div>
  </div>
</div>

<!-- PAYMENT -->
<div id="pay-overlay">
  <div class="pay-hdr">
    <span class="pay-hdr-title">SupportRD Premium</span>
    <button class="pay-close-btn" id="pay-close-btn">×</button>
  </div>
  <div class="pay-body">
    <div class="pay-hero">
      <div class="pay-big">$80</div>
      <div class="pay-mo">/month</div>
      <div class="pay-trial">✦ 7-day free trial · Cancel anytime</div>
    </div>
    <div class="pay-box">
      <div class="pay-box-label">Everything included</div>
      <div class="pay-feat-row">Unlimited Aria AI consultations</div>
      <div class="pay-feat-row">Full Hair Health Score breakdown</div>
      <div class="pay-feat-row">Personalized product recommendations</div>
      <div class="pay-feat-row">Complete conversation history</div>
      <div class="pay-feat-row">Priority WhatsApp advisor access</div>
    </div>
    <button class="pay-go" id="pay-go-btn">Start Free Trial</button>
    <div class="pay-note">No charge for 7 days. Cancel anytime from your account.</div>
  </div>
</div>

<script>
(function() {
var token = localStorage.getItem('srd_token') || '';
if (!token) { window.location.href = '/login'; }

// ── BACK BUTTON ───────────────────────────────────────
document.getElementById('back-btn').addEventListener('click', function(){
  window.location.href = '/';
});
document.getElementById('signout').addEventListener('click', function(){
  localStorage.removeItem('srd_token');
  window.location.href = '/login';
});

// ── LOAD USER ─────────────────────────────────────────
fetch('/api/auth/me', {headers:{'X-Auth-Token':token}})
  .then(function(r){return r.json();})
  .then(function(d){
    if (!d.ok) { localStorage.removeItem('srd_token'); window.location.href='/login'; return; }
    document.getElementById('d-name').textContent = d.name || 'User';
    document.getElementById('d-init').textContent = (d.name||'?')[0].toUpperCase();
    if (d.avatar) document.getElementById('d-avatar').innerHTML = '<img src="'+d.avatar+'" alt="">';
  })
  .catch(function(){ window.location.href='/login'; });

// ── LOAD PROFILE ──────────────────────────────────────
fetch('/api/profile', {headers:{'X-Auth-Token':token}})
  .then(function(r){return r.json();})
  .then(function(d){
    if (d.hair_type)      document.getElementById('p-type').value  = d.hair_type;
    if (d.heat_usage)     document.getElementById('p-heat').value  = d.heat_usage;
    if (d.water_type)     document.getElementById('p-water').value = d.water_type;
    if (d.hair_concerns)  loadChips('concerns',   d.hair_concerns);
    if (d.treatments)     loadChips('treatments', d.treatments);
    if (d.products_tried) loadChips('products',   d.products_tried);
    recalc();
  })
  .catch(function(){});

// ── LOAD HISTORY ──────────────────────────────────────
fetch('/api/history', {headers:{'X-Auth-Token':token}})
  .then(function(r){return r.json();})
  .then(function(d){
    var h = d.history || [];
    var hl = document.getElementById('hist-list');
    document.getElementById('stat-chats').textContent = h.filter(function(x){return x.role==='user';}).length || '0';
    if (!h.length) { hl.innerHTML='<div style="color:var(--muted);font-size:12px">No conversations yet.</div>'; return; }
    hl.innerHTML = h.slice(0,12).map(function(x){
      return '<div class="hist-item"><div class="hist-role">'+(x.role==='user'?'You':'Aria')+'</div>'+
             '<div class="hist-text">'+x.content.slice(0,130)+'</div></div>';
    }).join('');
  })
  .catch(function(){});

// ── SELECT RECALC ──────────────────────────────────────
document.getElementById('p-type').addEventListener('change', recalc);
document.getElementById('p-heat').addEventListener('change', recalc);
document.getElementById('p-water').addEventListener('change', recalc);

// ── SAVE PROFILE ──────────────────────────────────────
document.getElementById('save-profile-btn').addEventListener('click', saveProfile);

// ── UPGRADE ───────────────────────────────────────────
document.getElementById('upgrade-btn').addEventListener('click', function(){
  document.getElementById('pay-overlay').style.display = 'flex';
});
document.getElementById('pay-close-btn').addEventListener('click', function(){
  document.getElementById('pay-overlay').style.display = 'none';
});
document.getElementById('pay-go-btn').addEventListener('click', goUpgrade);

// ── HISTORY CLEAR ─────────────────────────────────────
document.getElementById('clr-hist-btn').addEventListener('click', clearHistory);

// ══ PICKER DATA ══════════════════════════════════════
var PICKER_DATA = {
  concerns: [
    'Dry hair','Oily scalp','Hair loss / Shedding','Breakage','Thinning',
    'Frizz','Dull — no shine','Split ends','Slow growth','Dandruff',
    'Itchy scalp','Heat damage','Color / Chemical damage','Brittleness',
    'Curl pattern loss','Product buildup','Scalp irritation','Limp / Flat hair'
  ],
  treatments: [
    'None — virgin hair','Relaxer / Perm','Bleach','Hair color / Dye',
    'Keratin treatment','Brazilian blowout','Japanese straightening',
    'Highlights / Balayage','Texturizer','Locs / Dreadlocks',
    'Braids / Weave extensions','Heat styling daily','Heat styling weekly'
  ],
  products: [
    'Formula Exclusiva — SupportRD','Laciador Crece — SupportRD',
    'Gotero Rapido — SupportRD','Gotitas Brillantes — SupportRD',
    'Mascarilla Nutritiva — SupportRD','Shampoo Aloe & Rosemary — SupportRD',
    'Olaplex','Kérastase','Moroccanoil','Redken','Paul Mitchell',
    'Wella Professionals','Joico','Matrix','Biolage','Pureology',
    'Aveda','Bumble and bumble','R+Co','Davines','Color WOW',
    'SheaMoisture','Cantu','Mielle Organics',"Carol's Daughter",
    "Aunt Jackie's",'As I Am','DevaCurl','Ouidad','Curl Junkie',
    'Camille Rose','Briogeo','Pattern Beauty','Melanin Haircare',
    'OGX','Pantene','TRESemmé','Garnier Fructis','Herbal Essences',
    'Dove','Head & Shoulders',"L'Oréal EverPure",'Aussie',
    'Suave Professionals','Nexxus','Schwarzkopf','VO5',
    'Jamaican Black Castor Oil','Argan oil','Coconut oil',
    'Olive oil','Rosemary oil','Tea tree oil','Jojoba oil','Castor oil'
  ]
};
var PICKER_TITLES = { concerns:'Main Concerns', treatments:'Chemical Treatments', products:'Products Being Used' };
var selected = { concerns:[], treatments:[], products:[] };
var activeKey = null;
var filteredOpts = [];

// ── PICKER OPEN/CLOSE ─────────────────────────────────
function openPicker(key) {
  activeKey    = key;
  filteredOpts = PICKER_DATA[key].slice();
  document.getElementById('pk-title').textContent = PICKER_TITLES[key];
  document.getElementById('pk-search').value = '';
  renderOptions(filteredOpts);
  document.getElementById('pk-list').scrollTop = 0;
  document.getElementById('picker-backdrop').style.display = 'block';
  document.getElementById('picker-overlay').style.display  = 'flex';
}

function closePicker() {
  document.getElementById('picker-backdrop').style.display = 'none';
  document.getElementById('picker-overlay').style.display  = 'none';
  if (activeKey) { renderChips(activeKey); recalc(); }
}

// Attach chip-field triggers — click AND touchend for iOS reliability
['concerns','treatments','products'].forEach(function(key) {
  var el = document.getElementById('cf-' + key);
  if (!el) return;
  el.addEventListener('click', function(e) {
    e.stopPropagation();
    e.preventDefault();
    openPicker(key);
  });
  el.addEventListener('touchend', function(e) {
    e.stopPropagation();
    e.preventDefault();
    openPicker(key);
  }, {passive: false});
});

// Backdrop and Done button
document.getElementById('picker-backdrop').addEventListener('click', closePicker);
document.getElementById('picker-backdrop').addEventListener('touchend', function(e){
  e.preventDefault(); closePicker();
}, {passive:false});
document.getElementById('pk-done-btn').addEventListener('click', closePicker);
document.getElementById('pk-done-btn').addEventListener('touchend', function(e){
  e.preventDefault(); closePicker();
}, {passive:false});
document.getElementById('pk-search').addEventListener('input', function(){
  filterPicker(this.value);
});

function renderOptions(opts) {
  var list = document.getElementById('pk-list');
  list.innerHTML = '';
  opts.forEach(function(o) {
    var div = document.createElement('div');
    div.className = 'pk-opt' + (selected[activeKey].indexOf(o) > -1 ? ' sel' : '');
    div.textContent = o;
    div.addEventListener('click', function(e) {
      e.stopPropagation();
      toggleOpt(div, o);
    });
    div.addEventListener('touchend', function(e) {
      e.stopPropagation();
      e.preventDefault();
      toggleOpt(div, o);
    }, {passive:false});
    list.appendChild(div);
  });
}

function filterPicker(q) {
  q = q.toLowerCase();
  filteredOpts = PICKER_DATA[activeKey].filter(function(o){ return o.toLowerCase().indexOf(q) > -1; });
  renderOptions(filteredOpts);
}

function toggleOpt(el, val) {
  var arr = selected[activeKey];
  var idx = arr.indexOf(val);
  if (idx > -1) { arr.splice(idx, 1); el.classList.remove('sel'); }
  else           { arr.push(val);      el.classList.add('sel'); }
}

function renderChips(key) {
  var sel    = selected[key];
  var tags   = document.getElementById('tags-' + key);
  var ph     = document.getElementById('ph-' + key);
  var hidden = document.getElementById('p-' + key);
  ph.style.display = sel.length ? 'none' : '';
  tags.innerHTML = sel.map(function(v) {
    var safeV = v.replace(/'/g, "&#39;");
    return '<span class="chip">' + v +
      '<span class="chip-x" data-key="' + key + '" data-val="' + safeV + '">×</span></span>';
  }).join('');
  // Attach chip-x remove listeners
  tags.querySelectorAll('.chip-x').forEach(function(x) {
    x.addEventListener('click', function(e) {
      e.stopPropagation();
      e.preventDefault();
      removeChip(key, x.getAttribute('data-val'));
    });
  });
  if (hidden) hidden.value = sel.join(', ');
}

function removeChip(key, val) {
  var idx = selected[key].indexOf(val);
  if (idx > -1) selected[key].splice(idx, 1);
  renderChips(key);
  recalc();
}

function loadChips(key, csv) {
  if (!csv) return;
  selected[key] = csv.split(',').map(function(s){return s.trim();}).filter(Boolean);
  renderChips(key);
}

// ══ HAIR HEALTH SCORE ════════════════════════════════
function clamp(n) { return Math.max(10, Math.min(100, n)); }

function recalc() {
  var heat  = document.getElementById('p-heat').value;
  var water = document.getElementById('p-water').value;
  var type  = document.getElementById('p-type').value;
  var con   = (document.getElementById('p-concerns').value   || '').toLowerCase();
  var trx   = (document.getElementById('p-treatments').value || '').toLowerCase();
  var pro   = (document.getElementById('p-products').value   || '').toLowerCase();
  if (!type && !con) return;
  var m=76, s=76, sc=76, g=76;
  if(/dry|brittle/.test(con))         {m-=20;}
  if(/loss|shed|thin|bald/.test(con)) {s-=18;g-=22;}
  if(/oil|greas/.test(con))           {sc-=14;m+=8;}
  if(/frizz/.test(con))               {m-=10;}
  if(/itch|dand|flak|irritat/.test(con)){sc-=18;}
  if(/break/.test(con))               {s-=14;m-=7;}
  if(/dull|shine/.test(con))          {m-=6;}
  if(/buildup/.test(con))             {sc-=10;}
  if(/bleach|color|dye|highlight|balayage/.test(trx)){s-=18;m-=10;}
  if(/relax|perm|textur/.test(trx))   {s-=16;m-=9;}
  if(/keratin|brazili|japanese/.test(trx)){s-=8;m-=5;}
  if(heat==='daily')     {s-=18;m-=13;}
  if(heat==='sometimes') {s-=7;m-=5;}
  if(water==='hard')     {m-=8;sc-=5;}
  if(/formula exclusiva/i.test(pro))  {m+=18;s+=16;}
  if(/laciador|crece/i.test(pro))     {m+=10;g+=12;}
  if(/gotero|rapido/i.test(pro))      {g+=16;sc+=13;}
  if(/mascarilla/i.test(pro))         {m+=10;s+=6;}
  if(/shampoo.*supportrd/i.test(pro)) {sc+=9;}
  if(/olaplex/i.test(pro))            {s+=12;m+=7;}
  if(/morocc/i.test(pro))             {m+=8;}
  if(/k.rastase|kerastase/i.test(pro)){m+=6;s+=5;}
  if(/sheamoisture/i.test(pro))       {m+=6;}
  if(/castor oil|jbco/i.test(pro))    {g+=10;}
  if(/rosemary/i.test(pro))           {g+=8;sc+=5;}
  if(/argan/i.test(pro))              {m+=7;}
  m=clamp(m); s=clamp(s); sc=clamp(sc); g=clamp(g);
  var overall = Math.round((m+s+sc+g)/4);
  animateScore(overall);
  document.getElementById('stat-score').textContent = overall;
  var STATUSES=['Critical','Poor','Fair','Good','Excellent'];
  var COLORS  =['#d97070','#d4956a','#c1a3a2','#7fba4b','#27c961'];
  var DESCS   ={Critical:"Urgent care needed. Let Aria guide you to targeted solutions.",Poor:"Visible damage present. You're in the right place.",Fair:"Managing well — a few key products will elevate your results.",Good:"Almost excellent! You're close to peak hair health.",Excellent:"Your hair is thriving. Keep up the routine!"};
  var li = overall<40?0:overall<55?1:overall<70?2:overall<85?3:4;
  document.getElementById('ring').style.stroke = COLORS[li];
  document.getElementById('score-status').textContent = STATUSES[li];
  document.getElementById('score-hint').textContent   = DESCS[STATUSES[li]];
  [['bar-m','val-m',m],['bar-s','val-s',s],['bar-sc','val-sc',sc],['bar-g','val-g',g]]
    .forEach(function(arr){ document.getElementById(arr[0]).style.width=arr[2]+'%'; document.getElementById(arr[1]).textContent=arr[2]; });
}

var scoreTimer = null;
function animateScore(target) {
  if (scoreTimer) clearInterval(scoreTimer);
  var cur = parseInt(document.getElementById('score-num').textContent) || 0;
  if (isNaN(cur)) cur = 0;
  var diff = target - cur, steps = 24, stepV = diff/steps;
  scoreTimer = setInterval(function() {
    cur += stepV;
    if (Math.abs(cur-target) < 1) { cur=target; clearInterval(scoreTimer); }
    var r = Math.round(cur);
    document.getElementById('score-num').textContent = r;
    document.getElementById('ring').style.strokeDashoffset = 2*Math.PI*62*(1-r/100);
  }, 38);
}

function saveProfile() {
  fetch('/api/profile', {
    method:'POST',
    headers:{'Content-Type':'application/json','X-Auth-Token':token},
    body:JSON.stringify({
      hair_type:      document.getElementById('p-type').value,
      hair_concerns:  document.getElementById('p-concerns').value,
      treatments:     document.getElementById('p-treatments').value,
      products_tried: document.getElementById('p-products').value,
      heat_usage:     document.getElementById('p-heat').value,
      water_type:     document.getElementById('p-water').value
    })
  }).then(function(){recalc();}).catch(function(){});
}

function clearHistory() {
  fetch('/api/history/clear', {method:'POST',headers:{'X-Auth-Token':token}})
    .then(function(){ document.getElementById('hist-list').innerHTML='<div style="color:var(--muted);font-size:12px">Cleared.</div>'; })
    .catch(function(){});
}

function goUpgrade() {
  if (!token) { window.location.href='/login?next=subscribe'; return; }
  fetch('/api/subscription/checkout', {method:'POST',headers:{'Content-Type':'application/json','X-Auth-Token':token}})
    .then(function(r){return r.json();})
    .then(function(d){ window.location.href=d.checkout_url||'https://supportrd.com/products/hair-advisor-premium'; })
    .catch(function(){ window.location.href='https://supportrd.com/products/hair-advisor-premium'; });
}

})();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════
# LOGIN PAGE
# ═══════════════════════════════════════════════════════
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#0d0906">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Sign In — SupportRD</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<script src="https://accounts.google.com/gsi/client" async defer></script>
<style>
:root{--brand:#c1a3a2;--accent:#9d7f6a;--bg:#0d0906;--surface:rgba(255,255,255,.04);--border:rgba(255,255,255,.08);--text:rgba(255,255,255,.87);--muted:rgba(255,255,255,.32);--safe-top:env(safe-area-inset-top,0px);--safe-bot:env(safe-area-inset-bottom,0px);}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}
html,body{height:100%;height:100dvh;overflow:hidden;background:var(--bg);font-family:'Jost',sans-serif;font-weight:300;color:var(--text);}
#shell{display:flex;flex-direction:column;height:100dvh;padding-top:var(--safe-top);padding-bottom:var(--safe-bot);}
#back-header{display:flex;align-items:center;padding:12px 18px;flex-shrink:0;}
#back-btn{width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.05);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .18s;}
#back-btn:active{background:rgba(255,255,255,.12);}
#back-btn svg{width:18px;height:18px;stroke:var(--muted);fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;}
#scroll{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;display:flex;align-items:center;justify-content:center;padding:16px 20px 30px;}
.login-card{width:100%;max-width:380px;}
.l-logo{font-family:'Cormorant Garamond',serif;font-size:42px;font-style:italic;color:var(--brand);text-align:center;margin-bottom:5px;}
.l-tagline{font-size:12px;color:var(--muted);text-align:center;letter-spacing:.06em;margin-bottom:34px;}
.l-tabs{display:flex;background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:12px;margin-bottom:22px;overflow:hidden;}
.l-tab{flex:1;padding:10px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;background:none;border:none;color:var(--muted);cursor:pointer;font-family:'Jost',sans-serif;transition:all .2s;}
.l-tab.active{background:var(--brand);color:#fff;}
.l-form{display:none;flex-direction:column;gap:12px;}
.l-form.show{display:flex;}
.l-group label{display:block;font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:5px;}
.l-group input{width:100%;padding:13px 16px;background:var(--surface);border:1px solid var(--border);border-radius:12px;color:var(--text);font-family:'Jost',sans-serif;font-size:14px;outline:none;transition:border .2s;-webkit-user-select:text;user-select:text;}
.l-group input:focus{border-color:var(--brand);}
.l-group input::placeholder{color:rgba(255,255,255,.18);}
.l-submit{width:100%;padding:14px;background:linear-gradient(135deg,var(--brand),var(--accent));color:#fff;border:none;border-radius:24px;font-family:'Jost',sans-serif;font-size:11px;letter-spacing:.14em;text-transform:uppercase;cursor:pointer;margin-top:2px;transition:opacity .2s;}
.l-submit:active{opacity:.85;}
.l-error{font-size:11px;color:#e07070;text-align:center;min-height:16px;}
.l-divider{display:flex;align-items:center;gap:12px;margin:2px 0;}
.l-divider span{font-size:10px;color:var(--muted);letter-spacing:.08em;flex-shrink:0;}
.l-divider::before,.l-divider::after{content:'';flex:1;height:1px;background:var(--border);}
.g-btn{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;padding:12px 16px;background:#fff;border:1px solid rgba(0,0,0,.14);border-radius:24px;font-family:'Jost',sans-serif;font-size:13px;color:#3c4043;cursor:pointer;transition:box-shadow .2s;}
.g-btn:active{opacity:.9;}
.g-gis-wrap{display:flex;justify-content:center;min-height:44px;}
</style>
</head>
<body>
<div id="shell">
  <div id="back-header">
    <button id="back-btn">
      <svg viewBox="0 0 24 24"><polyline points="15,18 9,12 15,6"/></svg>
    </button>
  </div>
  <div id="scroll">
    <div class="login-card">
      <div class="l-logo">Aria</div>
      <div class="l-tagline">AI Hair Advisor by SupportRD</div>
      <div class="l-tabs">
        <button class="l-tab active" id="tab-in">Sign In</button>
        <button class="l-tab"        id="tab-up">Create Account</button>
      </div>
      <!-- SIGN IN -->
      <div id="form-in" class="l-form show">
        <div class="l-group"><label>Email</label>
          <input id="in-email" type="email" inputmode="email" placeholder="your@email.com" autocomplete="email"></div>
        <div class="l-group"><label>Password</label>
          <input id="in-pass" type="password" placeholder="••••••••" autocomplete="current-password"></div>
        <div class="l-error" id="in-err"></div>
        <button class="l-submit" id="btn-login">Sign In</button>
        <div class="l-divider"><span>or</span></div>
        <div class="g-gis-wrap" id="gis-in">
          <button class="g-btn" id="g-btn-in">
            <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/><path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z"/></svg>
            Continue with Google
          </button>
        </div>
      </div>
      <!-- SIGN UP -->
      <div id="form-up" class="l-form">
        <div class="l-group"><label>Your Name</label>
          <input id="up-name" type="text" placeholder="First Last" autocomplete="name"></div>
        <div class="l-group"><label>Email</label>
          <input id="up-email" type="email" inputmode="email" placeholder="your@email.com" autocomplete="email"></div>
        <div class="l-group"><label>Password</label>
          <input id="up-pass" type="password" placeholder="Create password" autocomplete="new-password"></div>
        <div class="l-error" id="up-err"></div>
        <button class="l-submit" id="btn-register">Create Account</button>
        <div class="l-divider"><span>or</span></div>
        <div class="g-gis-wrap" id="gis-up">
          <button class="g-btn" id="g-btn-up">
            <svg width="18" height="18" viewBox="0 0 18 18"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/><path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z"/></svg>
            Sign up with Google
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
(function() {
var GID = '';
var nextUrl = new URLSearchParams(location.search).get('next') || '/dashboard';

// Fetch config first (bypasses any caching of the HTML template)
fetch('/api/config')
  .then(function(r){ return r.json(); })
  .then(function(d){
    GID = d.google_client_id || '';
    if (GID) initGIS();
  })
  .catch(function(){});

// Back
document.getElementById('back-btn').addEventListener('click', function(){ window.location.href='/'; });

// Tabs
document.getElementById('tab-in').addEventListener('click', function(){ setTab('in'); });
document.getElementById('tab-up').addEventListener('click', function(){ setTab('up'); });

function setTab(t) {
  document.getElementById('tab-in').classList.toggle('active', t==='in');
  document.getElementById('tab-up').classList.toggle('active', t==='up');
  document.getElementById('form-in').classList.toggle('show', t==='in');
  document.getElementById('form-up').classList.toggle('show', t!=='in');
}

function saveAndRedirect(d) {
  localStorage.setItem('srd_token', d.token);
  window.location.href = nextUrl;
}

// Login
document.getElementById('btn-login').addEventListener('click', doLogin);
document.getElementById('btn-register').addEventListener('click', doRegister);

function doLogin() {
  var email = document.getElementById('in-email').value.trim();
  var pass  = document.getElementById('in-pass').value;
  var errEl = document.getElementById('in-err');
  errEl.textContent = '';
  if (!email||!pass) { errEl.textContent='Please fill in all fields.'; return; }
  fetch('/api/auth/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,password:pass})})
    .then(function(r){return r.json();})
    .then(function(d){ if(d.error) errEl.textContent=d.error; else saveAndRedirect(d); })
    .catch(function(){ errEl.textContent='Connection error.'; });
}

function doRegister() {
  var name  = document.getElementById('up-name').value.trim();
  var email = document.getElementById('up-email').value.trim();
  var pass  = document.getElementById('up-pass').value;
  var errEl = document.getElementById('up-err');
  errEl.textContent = '';
  if (!email||!pass) { errEl.textContent='Please fill in all fields.'; return; }
  fetch('/api/auth/register', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,email:email,password:pass})})
    .then(function(r){return r.json();})
    .then(function(d){ if(d.error) errEl.textContent=d.error; else saveAndRedirect(d); })
    .catch(function(){ errEl.textContent='Connection error.'; });
}

// Enter key
document.addEventListener('keydown', function(e){
  if (e.key!=='Enter'||e.shiftKey) return;
  if (document.getElementById('form-in').classList.contains('show')) doLogin();
  else doRegister();
});

// Google
function handleGoogleCred(response) {
  var errEl = document.getElementById('in-err');
  errEl.textContent = 'Signing in with Google…';
  fetch('/api/auth/google', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({credential:response.credential})})
    .then(function(r){return r.json();})
    .then(function(d){
      if (d.error) { errEl.textContent = 'Google error: ' + d.error; }
      else saveAndRedirect(d);
    })
    .catch(function(e){ errEl.textContent = 'Google network error: ' + e.message; });
}
window.handleGoogleCred = handleGoogleCred;

function googleClick(which) {
  var errId = which === 'up' ? 'up-err' : 'in-err';
  var errEl = document.getElementById(errId);
  if (!GID) {
    errEl.textContent = 'Google login not available — use email login.';
    return;
  }
  if (!window.google || !window.google.accounts) {
    errEl.textContent = 'Google script still loading — try again in 2 seconds.';
    return;
  }
  // Try prompt first; if blocked, show message
  try {
    window.google.accounts.id.prompt(function(notification) {
      if (notification.isNotDisplayed()) {
        errEl.textContent = 'Google popup blocked by browser. Try email login or open in Chrome.';
      } else if (notification.isSkippedMoment()) {
        errEl.textContent = 'Google popup skipped. Try email login.';
      }
    });
  } catch(e) {
    errEl.textContent = 'Google error: ' + e.message;
  }
}

document.getElementById('g-btn-in').addEventListener('click', function(){ googleClick('in'); });
document.getElementById('g-btn-up').addEventListener('click', function(){ googleClick('up'); });

function initGIS() {
  if (!GID) return;
  if (!window.google || !window.google.accounts) { setTimeout(initGIS, 500); return; }
  try {
    window.google.accounts.id.initialize({
      client_id:             GID,
      callback:              handleGoogleCred,
      auto_select:           false,
      cancel_on_tap_outside: true,
      ux_mode:               'popup'
    });
    var opts = {theme:'outline', size:'large', shape:'pill', width:300};
    var c1 = document.getElementById('gis-in');
    if (c1) { c1.innerHTML=''; window.google.accounts.id.renderButton(c1, Object.assign({},opts,{text:'signin_with'})); }
    var c2 = document.getElementById('gis-up');
    if (c2) { c2.innerHTML=''; window.google.accounts.id.renderButton(c2, Object.assign({},opts,{text:'signup_with'})); }
    console.log('GIS initialized with client_id:', GID.slice(0,12)+'...');
  } catch(e) {
    document.getElementById('in-err').textContent = 'GIS init error: ' + e.message;
  }
}
// initGIS is called after /api/config fetch above

// Password reset
var rt = new URLSearchParams(location.search).get('reset_token');
if (rt) {
  var np = prompt('Enter your new password:');
  if (np) {
    fetch('/api/auth/reset-password', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:rt,password:np})})
      .then(function(r){return r.json();})
      .then(function(d){ if(d.ok) saveAndRedirect(d); });
  }
}

})();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════
# PAGE ROUTES
# ═══════════════════════════════════════════════════════

@app.route("/")
def index():
    return Response(ARIA_PAGE, mimetype="text/html")

@app.route("/dashboard")
def dashboard():
    return Response(DASHBOARD_PAGE, mimetype="text/html")

@app.route("/login")
def login_page():
    page = LOGIN_PAGE.replace("%GOOGLE_CLIENT_ID%", GOOGLE_CLIENT_ID or "")
    return Response(page, mimetype="text/html")

@app.route("/subscription/success")
def subscription_success():
    return Response("""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Welcome to Premium — SupportRD</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,300&family=Jost:wght@300&display=swap" rel="stylesheet">
<style>*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d0906;color:#fff;font-family:'Jost',sans-serif;font-weight:300;
display:flex;align-items:center;justify-content:center;min-height:100dvh;padding:24px;text-align:center;}
.w{max-width:340px}
.ic{font-size:46px;margin-bottom:20px}
h1{font-family:'Cormorant Garamond',serif;font-size:32px;font-style:italic;color:#c1a3a2;margin-bottom:10px}
p{font-size:13px;color:rgba(255,255,255,.38);line-height:1.7;margin-bottom:28px}
a{display:inline-block;padding:14px 30px;background:linear-gradient(135deg,#c1a3a2,#9d7f6a);
color:#fff;border-radius:28px;text-decoration:none;font-size:11px;letter-spacing:.12em;text-transform:uppercase}
</style></head><body><div class="w">
<div class="ic">✦</div>
<h1>Welcome to Premium</h1>
<p>Your 7-day free trial has started. Unlimited Aria consultations, your Hair Health Score, and full conversation history are all yours.</p>
<a href="/">Talk to Aria</a>
</div></body></html>""", mimetype="text/html")

@app.route("/subscription/cancel")
def subscription_cancel():
    return Response("""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SupportRD</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,300&family=Jost:wght@300&display=swap" rel="stylesheet">
<style>*{box-sizing:border-box;margin:0;padding:0}
body{background:#f0ebe8;font-family:'Jost',sans-serif;font-weight:300;
display:flex;align-items:center;justify-content:center;min-height:100dvh;padding:24px;text-align:center;}
.w{max-width:320px}
h1{font-family:'Cormorant Garamond',serif;font-size:28px;font-style:italic;color:#0d0906;margin-bottom:10px}
p{font-size:13px;color:rgba(0,0,0,.4);line-height:1.7;margin-bottom:28px}
a{display:inline-block;padding:13px 28px;background:#c1a3a2;color:#fff;
border-radius:28px;text-decoration:none;font-size:11px;letter-spacing:.12em;text-transform:uppercase}
</style></head><body><div class="w">
<h1>No worries</h1>
<p>You still have free Aria consultations. Come back any time you\'re ready to upgrade.</p>
<a href="/">Back to Aria</a>
</div></body></html>""", mimetype="text/html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
