import os, json, sqlite3, datetime, hashlib, secrets, threading, random, re
from flask import Flask, request, jsonify, Response

app = Flask(__name__)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

AUTH_DB = os.path.join(os.path.dirname(__file__), "users.db")

_db_lock = threading.Lock()

def get_db():
    """Get a SQLite connection with WAL mode and locking to prevent conflicts."""
    con = sqlite3.connect(AUTH_DB, timeout=60, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.row_factory = sqlite3.Row
    return con

def db_execute(query, params=(), fetchone=False, fetchall=False):
    """Thread-safe DB execute with auto-retry on lock."""
    import time
    for attempt in range(5):
        try:
            with _db_lock:
                con = sqlite3.connect(AUTH_DB, timeout=60, check_same_thread=False)
                con.execute("PRAGMA journal_mode=WAL")
                con.execute("PRAGMA busy_timeout=60000")
                cur = con.execute(query, params)
                result = None
                if fetchone: result = cur.fetchone()
                elif fetchall: result = cur.fetchall()
                con.commit()
                con.close()
                return result
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise

def init_auth_db():
    con = get_db()
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT    UNIQUE NOT NULL,
        name          TEXT,
        password_hash TEXT,
        google_id     TEXT,
        avatar        TEXT,
        created_at    TEXT    DEFAULT (datetime('now')),
        last_login    TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS sessions (
        token      TEXT PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hair_profiles (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER UNIQUE NOT NULL,
        hair_type    TEXT,
        hair_concerns TEXT,
        treatments   TEXT,
        products_tried TEXT,
        last_updated TEXT DEFAULT (datetime('now'))
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS chat_history (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        role       TEXT NOT NULL,
        content    TEXT NOT NULL,
        ts         TEXT DEFAULT (datetime('now'))
    )""")
    con.commit()
    con.close()

init_auth_db()

def hash_password(pw):
    salt = "supportrd_salt_2024"
    return hashlib.sha256((pw + salt).encode()).hexdigest()

def create_session(user_id):
    token = secrets.token_hex(32)
    expires = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
    db_execute("INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,?)", (token, user_id, expires))
    db_execute("UPDATE users SET last_login=? WHERE id=?", (datetime.datetime.utcnow().isoformat(), user_id))
    return token

def get_user_from_token(token):
    if not token: return None
    row = db_execute("""SELECT u.id,u.email,u.name,u.avatar FROM users u
        JOIN sessions s ON s.user_id=u.id
        WHERE s.token=? AND s.expires_at > datetime('now')""", (token,), fetchone=True)
    if row: return {"id":row[0],"email":row[1],"name":row[2],"avatar":row[3]}
    return None

def get_current_user():
    token = request.headers.get("X-Auth-Token") or request.cookies.get("srd_token")
    return get_user_from_token(token)

def get_hair_profile(user_id):
    con = get_db()
    row = con.execute("SELECT * FROM hair_profiles WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    if not row: return {}
    return {"hair_type":row[2],"hair_concerns":row[3],"treatments":row[4],"products_tried":row[5]}

def save_hair_profile(user_id, data):
    con = get_db()
    con.execute("""INSERT INTO hair_profiles (user_id,hair_type,hair_concerns,treatments,products_tried)
        VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
        hair_type=excluded.hair_type, hair_concerns=excluded.hair_concerns,
        treatments=excluded.treatments, products_tried=excluded.products_tried,
        last_updated=datetime('now')""",
        (user_id, data.get("hair_type",""), data.get("hair_concerns",""),
         data.get("treatments",""), data.get("products_tried","")))
    con.commit()
    con.close()

def get_chat_history(user_id, limit=20):
    con = get_db()
    rows = con.execute("""SELECT role,content FROM chat_history
        WHERE user_id=? ORDER BY id DESC LIMIT ?""", (user_id, limit)).fetchall()
    con.close()
    return [{"role":r[0],"content":r[1]} for r in reversed(rows)]

def save_chat_message(user_id, role, content):
    con = get_db()
    con.execute("INSERT INTO chat_history (user_id,role,content) VALUES (?,?,?)",
                (user_id, role, content))
    con.execute("""DELETE FROM chat_history WHERE user_id=? AND id NOT IN
        (SELECT id FROM chat_history WHERE user_id=? ORDER BY id DESC LIMIT 100)""",
                (user_id, user_id))
    con.commit()
    con.close()

# ── ANALYTICS DB ─────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "analytics.db")

def get_analytics_db():
    con = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    return con

def init_db():
    con = get_analytics_db()
    con.execute("""CREATE TABLE IF NOT EXISTS events (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        ts        TEXT    NOT NULL,
        lang      TEXT,
        user_msg  TEXT,
        product   TEXT,
        concern   TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS tips (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        ts         TEXT    NOT NULL,
        lang       TEXT,
        rating     INTEGER,
        tip_amount TEXT,
        product    TEXT
    )""")
    con.commit(); con.close()

init_db()

def log_event(lang, user_msg, product, concern):
    try:
        con = get_analytics_db()
        con.execute("INSERT INTO events (ts,lang,user_msg,product,concern) VALUES (?,?,?,?,?)",
                    (datetime.datetime.utcnow().isoformat(), lang, user_msg, product, concern))
        con.commit(); con.close()
    except Exception as e:
        print("DB log error:", e)

def log_tip(lang, rating, tip_amount, product):
    try:
        con = get_analytics_db()
        con.execute("INSERT INTO tips (ts,lang,rating,tip_amount,product) VALUES (?,?,?,?,?)",
                    (datetime.datetime.utcnow().isoformat(), lang, rating, tip_amount, product))
        con.commit(); con.close()
    except Exception as e:
        print("DB tip log error:", e)

def extract_product(text):
    t = text.lower()
    if "formula exclusiva" in t: return "Formula Exclusiva"
    if "laciador" in t or "crece" in t: return "Laciador Crece"
    if "gotero" in t or "rapido" in t: return "Gotero Rapido"
    if "gotika"           in t: return "Gotitas Brillantes"
    return "Unknown"

def extract_concern(text):
    t = text.lower()
    if any(w in t for w in ["damag","break","weak","fall","shed","bald","thin"]): return "damaged/falling"
    if any(w in t for w in ["color","colour","fade","brassy","grey","gray","dye"]): return "color"
    if any(w in t for w in ["oil","greasy","grease","sebum","buildup"]): return "oily"
    if any(w in t for w in ["dry","frizz","rough","brittle","moisture","parched"]): return "dry"
    if any(w in t for w in ["tangl","knot","matted","detangle"]): return "tangly"
    if any(w in t for w in ["flat","volume","lifeless","limp","fine","no bounce"]): return "flat/volume"
    return "general"

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Aria — a warm, knowledgeable, luxury hair care advisor for SupportRD, a professional Dominican hair care brand. You have deep expertise in hair science, scalp health, and hair culture across all ethnicities.

YOUR PRODUCTS:
- Formula Exclusiva ($55): Professional all-in-one treatment. Apply on dry or damp hair; for wash use 1oz for 5 min in dryer then rinse. Safe for whole family including children. Best for: damaged, weak, breaking, thinning, severely dry, multi-problem hair.
- Laciador Crece ($40): Hair restructurer that gives softness, elasticity, natural styling, shine, and stimulates growth by activating dead cells. Best for: dry hair, frizz, lack of shine, growth, strengthening, styling.
- Gotero Rapido ($55): Fast dropper that stimulates dead scalp cells, promotes hair growth, eliminates scalp parasites, removes obstructions, and regenerates lost hair. Use on scalp every night then remove. Best for: hair loss, scalp issues, slow growth, thinning, parasites.
- Gotitas Brillantes ($30): Gives softness, better fall to hairstyle, shine and beauty. Use after any hairstyle or anytime. Adds warmth and evenness. Best for: finishing, shine, frizz control, styling touch-up.
- Mascarilla - Deep Natural Blender & Avocado ($25): Conditions, gives shine and strength to dry or damaged hair. Keeps hair beautiful and healthy. Best for: deep conditioning, dry/damaged hair, shine boost.
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
- Keep responses to 2-4 sentences. Never use "I recommend" — say "For your hair, [Product] is exactly what you need."
- Naturally mention your products every 3-4 exchanges even in casual conversation.
- Occasionally say: "If you want a 1-on-1 with a live advisor, message us on WhatsApp at 829-233-2670"

PROFESSIONAL RESOURCES:
- Medical: suggest dermatologist for severe hair loss, scalp conditions, alopecia
- Professional: offer to help find a salon — ask for their city
- Trusted sites: AAD (American Academy of Dermatology), Naturally Curly, NAHA

OFF-TOPIC REDIRECT:
- If they bring up unrelated topics (sports, gaming, travel, food, movies), acknowledge warmly and redirect:
  "Ha, love that! But let's get back to what matters — your hair. You mentioned [last hair topic] — any updates?"
- After 2 off-topic messages: "I want to give you the best hair advice — let's refocus on your hair journey!"
- Connect topics back to hair when possible: "Stress from [activity] can actually affect hair health..."

PROFILE AWARENESS:
- If profile shows saved concerns, reference them: "Based on your [concern], this is especially important..."
- Reference past conversations naturally to build a relationship over time.

Respond ONLY with your answer. No preamble. No "Sure!" or "Of course!".
If the language code indicates non-English, respond entirely in that language."""


# ── MAIN APP ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return r"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hair Expert Advisor</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<style>
:root {
  --brand-idle-r:   193;
  --brand-idle-g:   163;
  --brand-idle-b:   162;
  --brand-listen-r: 157;
  --brand-listen-g: 127;
  --brand-listen-b: 106;
  --brand-speak-r:  208;
  --brand-speak-g:  208;
  --brand-speak-b:  208;
  --brand-bg:       #f0ebe8;
  --brand-text:     #0d0906;
  --brand-accent:   rgba(193,163,162,1);
  --brand-accent-lo: rgba(193,163,162,0.08);
  --brand-accent-mid: rgba(193,163,162,0.22);
  --brand-font-head: 'Cormorant Garamond', serif;
  --brand-font-body: 'Jost', sans-serif;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: radial-gradient(ellipse at 50% 60%, #e8e0da 0%, var(--brand-bg) 100%);
  color: var(--brand-text);
  font-family: var(--brand-font-body);
  font-weight: 300;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  overflow: hidden;
  user-select: none;
}

#topBar {
  position: fixed;
  top: 0; left: 0; right: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  z-index: 100;
  background: rgba(250,246,243,0.60);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(193,163,162,0.12);
}

.top-btn {
  background: rgba(0,0,0,0.05);
  color: rgba(0,0,0,0.55);
  border: 1px solid rgba(0,0,0,0.12);
  padding: 8px 18px;
  border-radius: 30px;
  font-size: 11px;
  font-family: var(--brand-font-body);
  font-weight: 300;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.4s ease;
  outline: none;
}
.top-btn:hover {
  background: var(--brand-accent-lo);
  color: var(--brand-accent);
  border-color: var(--brand-accent-mid);
}

#langSelect {
  background: rgba(0,0,0,0.05);
  color: rgba(0,0,0,0.55);
  border: 1px solid rgba(0,0,0,0.12);
  padding: 8px 14px;
  border-radius: 30px;
  font-size: 11px;
  font-family: var(--brand-font-body);
  letter-spacing: 0.08em;
  cursor: pointer;
  outline: none;
  transition: all 0.4s ease;
}
#langSelect option { background: #f0ebe8; color: #0d0906; }

.sphere-wrap {
  width: 300px; height: 300px;
  display: flex; align-items: center; justify-content: center;
}

#halo {
  width: 220px; height: 220px;
  border-radius: 50%;
  cursor: pointer;
  background: radial-gradient(circle at 40% 38%,
    rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.55) 0%,
    rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.18) 42%,
    rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.07) 70%,
    rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.01) 100%);
  box-shadow:
    inset 0 0 40px rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.10),
    0 0  70px rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.45),
    0 0 150px rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.28),
    0 0 280px rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.15),
    0 0 420px rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.07);
  transition:
    background 2.4s cubic-bezier(0.4,0,0.2,1),
    box-shadow  2.4s cubic-bezier(0.4,0,0.2,1);
  animation: idlePulse 3.2s ease-in-out infinite;
}
@keyframes idlePulse {
  0%,100% { transform: scale(1.00); }
  50%     { transform: scale(1.10); }
}
#halo.speaking {
  animation: speakPulse 0.9s ease-in-out infinite;
}
@keyframes speakPulse {
  0%,100% { transform: scale(1.05); }
  50%     { transform: scale(1.20); }
}
#halo.listening { animation: none; }

#stateLabel {
  margin-top: 12px;
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(0,0,0,0.30);
  height: 16px;
}

/* ── CONVERSATION HISTORY ── */
#history {
  width: 420px;
  max-width: 92vw;
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 18px;
  padding: 0 4px;
  scrollbar-width: thin;
  scrollbar-color: rgba(0,0,0,0.12) transparent;
}
#history:empty { display: none; }

.msg {
  padding: 10px 16px;
  border-radius: 18px;
  font-size: 14px;
  line-height: 1.55;
  max-width: 88%;
  animation: fadeIn 0.4s ease;
}
@keyframes fadeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }

.msg.user {
  background: rgba(0,0,0,0.07);
  color: rgba(0,0,0,0.60);
  align-self: flex-end;
  border-bottom-right-radius: 4px;
  font-family: var(--brand-font-body);
}
.msg.ai {
  background: rgba(var(--brand-idle-r),var(--brand-idle-g),var(--brand-idle-b),0.10);
  color: rgba(0,0,0,0.80);
  align-self: flex-start;
  border-bottom-left-radius: 4px;
  font-family: var(--brand-font-head);
  font-style: italic;
  font-size: 15px;
}

#clearBtn {
  margin-top: 8px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(0,0,0,0.25);
  cursor: pointer;
  background: none;
  border: none;
  font-family: var(--brand-font-body);
  transition: color 0.3s;
  display: none;
}
#clearBtn:hover { color: rgba(0,0,0,0.55); }
#clearBtn.visible { display: block; }

#response {
  margin-top: 14px;
  width: 420px;
  max-width: 92vw;
  text-align: center;
  font-family: var(--brand-font-head);
  font-size: 18px;
  font-weight: 300;
  line-height: 1.7;
  color: rgba(0,0,0,0.65);
  min-height: 28px;
  font-style: italic;
}

#manualBox {
  display: none;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  width: 380px;
  max-width: 90vw;
}
#manualInput {
  width: 100%;
  padding: 13px 20px;
  background: rgba(0,0,0,0.04);
  border: 1px solid rgba(0,0,0,0.14);
  border-radius: 30px;
  color: #0d0906;
  font-family: var(--brand-font-body);
  font-size: 14px;
  outline: none;
  transition: border-color 0.3s;
}
#manualInput:focus { border-color: var(--brand-accent-mid); }
#manualInput::placeholder { color: rgba(0,0,0,0.30); }

#manualSubmit {
  padding: 10px 32px;
  background: var(--brand-accent-lo);
  border: 1px solid var(--brand-accent-mid);
  border-radius: 30px;
  color: var(--brand-accent);
  font-family: var(--brand-font-body);
  font-size: 11px;
  font-weight: 300;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.3s;
}
#manualSubmit:hover { background: rgba(193,163,162,0.20); }

/* ══════════════════════════════════════════
   TIP PANEL
══════════════════════════════════════════ */
#tipPanel {
  position: fixed;
  bottom: -320px;
  left: 50%;
  transform: translateX(-50%);
  width: 400px;
  max-width: 94vw;
  background: #faf6f3;
  border: 1px solid rgba(193,163,162,0.35);
  border-radius: 24px 24px 0 0;
  padding: 28px 28px 36px;
  box-shadow: 0 -12px 60px rgba(0,0,0,0.10);
  transition: bottom 0.55s cubic-bezier(0.32,0.72,0,1);
  z-index: 200;
  text-align: center;
}
#tipPanel.open {
  bottom: 0;
}

#tipTitle {
  font-family: var(--brand-font-head);
  font-size: 20px;
  font-style: italic;
  color: rgba(0,0,0,0.70);
  margin-bottom: 4px;
}
#tipSubtitle {
  font-family: var(--brand-font-body);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(0,0,0,0.30);
  margin-bottom: 20px;
}

/* Stars */
#starRow {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 22px;
}
.star {
  font-size: 26px;
  cursor: pointer;
  color: rgba(0,0,0,0.15);
  transition: color 0.2s, transform 0.15s;
  line-height: 1;
}
.star.active { color: #c1a3a2; }
.star:hover  { transform: scale(1.2); }

/* Tip amounts */
#tipAmounts {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.tip-amt {
  padding: 9px 20px;
  border-radius: 30px;
  border: 1px solid rgba(193,163,162,0.40);
  background: rgba(193,163,162,0.07);
  color: rgba(0,0,0,0.55);
  font-family: var(--brand-font-body);
  font-size: 13px;
  font-weight: 400;
  cursor: pointer;
  transition: all 0.25s;
}
.tip-amt:hover, .tip-amt.selected {
  background: rgba(193,163,162,0.22);
  border-color: rgba(193,163,162,0.70);
  color: #0d0906;
}

/* Custom tip input (hidden until "Custom" selected) */
#customTipWrap {
  display: none;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 20px;
}
#customTipWrap.show { display: flex; }
#customTipInput {
  width: 110px;
  padding: 9px 14px;
  border-radius: 30px;
  border: 1px solid rgba(193,163,162,0.40);
  background: rgba(193,163,162,0.07);
  color: #0d0906;
  font-family: var(--brand-font-body);
  font-size: 14px;
  text-align: center;
  outline: none;
}
#customTipInput:focus { border-color: rgba(193,163,162,0.70); }

/* Submit + skip */
#tipSubmit {
  display: block;
  width: 100%;
  padding: 13px;
  border-radius: 30px;
  border: none;
  background: rgba(193,163,162,0.90);
  color: #fff;
  font-family: var(--brand-font-body);
  font-size: 12px;
  font-weight: 400;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  cursor: pointer;
  transition: background 0.3s;
  margin-bottom: 12px;
}
#tipSubmit:hover { background: rgba(157,127,106,0.90); }

#tipSkip {
  font-family: var(--brand-font-body);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(0,0,0,0.25);
  cursor: pointer;
  transition: color 0.3s;
  background: none;
  border: none;
}
#tipSkip:hover { color: rgba(0,0,0,0.50); }

/* Thank-you state */
#tipThanks {
  display: none;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
}
#tipThanks .thanks-icon {
  font-size: 36px;
  margin-bottom: 4px;
}
#tipThanks .thanks-title {
  font-family: var(--brand-font-head);
  font-size: 22px;
  font-style: italic;
  color: rgba(0,0,0,0.70);
}
#tipThanks .thanks-sub {
  font-family: var(--brand-font-body);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(0,0,0,0.30);
}

#footer {
  position: fixed;
  bottom: 22px;
  display: flex;
  gap: 36px;
  z-index: 10;
}
#footer span {
  font-size: 10px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: rgba(0,0,0,0.30);
  cursor: pointer;
  transition: color 0.4s;
}
#footer span:hover { color: var(--brand-accent); }

/* ── AUTH BAR ── */
#authBar {
  display: flex;
  align-items: center;
  gap: 10px;
}
#authBtn {
  padding: 8px 20px;
  border: 1px solid #c1a3a2;
  border-radius: 20px;
  background: #c1a3a2;
  font-family: 'Jost', sans-serif;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  cursor: pointer;
  color: #fff;
  transition: all 0.2s;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 400;
  box-shadow: 0 2px 12px rgba(193,163,162,0.40);
}
#authBtn:hover { background: #9d7f6a; border-color: #9d7f6a; }
#userChip {
  display: none;
  align-items: center;
  gap: 8px;
  background: rgba(255,255,255,0.92);
  border: 1px solid rgba(193,163,162,0.40);
  border-radius: 20px;
  padding: 4px 12px 4px 5px;
}
#userAvatar {
  width: 26px; height: 26px;
  border-radius: 50%;
  background: #c1a3a2;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; color: #fff; overflow: hidden; flex-shrink: 0;
}
#userAvatar img { width: 100%; height: 100%; object-fit: cover; }
#userName { font-size: 11px; color: #0d0906; font-family: 'Jost', sans-serif; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#dashLink { font-size: 10px; color: #9d7f6a; text-decoration: none; letter-spacing: 0.08em; text-transform: uppercase; border-left: 1px solid rgba(193,163,162,0.30); padding-left: 8px; margin-left: 2px; }
#dashLink:hover { color: #c1a3a2; }

/* ── WELCOME BACK BANNER ── */
#welcomeBanner {
  display: none;
  position: fixed;
  top: 56px;
  right: 16px;
  background: #fff;
  border: 1px solid rgba(193,163,162,0.25);
  border-radius: 14px;
  padding: 14px 18px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.10);
  z-index: 999;
  max-width: 260px;
  animation: wbIn 0.4s cubic-bezier(0.22,1,0.36,1);
}
@keyframes wbIn { from{opacity:0;transform:translateY(-8px)} to{opacity:1;transform:translateY(0)} }
#welcomeBanner .wb-name { font-family: 'Cormorant Garamond', serif; font-size: 17px; font-style: italic; color: #0d0906; margin-bottom: 4px; }
#welcomeBanner .wb-score { font-size: 11px; color: rgba(0,0,0,0.40); letter-spacing: 0.06em; margin-bottom: 10px; }
#welcomeBanner .wb-score span { color: #c1a3a2; font-weight: 600; }
#welcomeBanner .wb-btns { display: flex; gap: 8px; }
#welcomeBanner .wb-btn { flex: 1; padding: 8px; border-radius: 10px; font-size: 10px; letter-spacing: 0.10em; text-transform: uppercase; text-align: center; text-decoration: none; font-family: 'Jost', sans-serif; }
.wb-btn-rose { background: #c1a3a2; color: #fff; }
.wb-btn-outline { border: 1px solid rgba(193,163,162,0.40); color: #9d7f6a; }

/* ── PAYWALL BANNER ── */
#paywallBanner {
  display: none;
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  width: 92%;
  max-width: 480px;
  background: #fff;
  border: 1px solid rgba(193,163,162,0.30);
  border-radius: 20px;
  padding: 20px 22px;
  box-shadow: 0 12px 48px rgba(0,0,0,0.14);
  z-index: 2000;
  animation: pwIn 0.45s cubic-bezier(0.22,1,0.36,1);
}
@keyframes pwIn { from{opacity:0;transform:translateX(-50%) translateY(16px)} to{opacity:1;transform:translateX(-50%) translateY(0)} }
#paywallBanner .pw-top { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:10px; }
#paywallBanner .pw-title { font-family:'Cormorant Garamond',serif; font-size:20px; font-style:italic; color:#0d0906; }
#paywallBanner .pw-close { background:none; border:none; font-size:18px; cursor:pointer; color:rgba(0,0,0,0.25); padding:0; line-height:1; }
#paywallBanner .pw-desc { font-size:12px; color:rgba(0,0,0,0.45); line-height:1.6; margin-bottom:14px; letter-spacing:0.03em; }
#paywallBanner .pw-trial { background:linear-gradient(135deg,#c1a3a2,#9d7f6a); color:#fff; font-size:10px; letter-spacing:0.14em; text-transform:uppercase; padding:5px 14px; border-radius:20px; display:inline-block; margin-bottom:14px; }
#paywallBanner .pw-btns { display:flex; gap:10px; }
#paywallBanner .pw-btn-upgrade { flex:2; padding:12px; background:#c1a3a2; color:#fff; border:none; border-radius:24px; font-family:'Jost',sans-serif; font-size:11px; letter-spacing:0.12em; text-transform:uppercase; cursor:pointer; transition:background 0.2s; }
#paywallBanner .pw-btn-upgrade:hover { background:#9d7f6a; }
#paywallBanner .pw-btn-continue { flex:1; padding:12px; background:transparent; color:rgba(0,0,0,0.35); border:1px solid rgba(0,0,0,0.12); border-radius:24px; font-family:'Jost',sans-serif; font-size:11px; letter-spacing:0.08em; text-transform:uppercase; cursor:pointer; }
#paywallBanner .pw-features { display:grid; grid-template-columns:1fr 1fr; gap:5px; margin-bottom:14px; }
#paywallBanner .pw-feature { font-size:11px; color:rgba(0,0,0,0.50); display:flex; align-items:center; gap:5px; }
#paywallBanner .pw-feature::before { content:'✦'; color:#c1a3a2; font-size:9px; }
#paywallCounter { display:none; position:fixed; top:58px; left:50%; transform:translateX(-50%); background:rgba(193,163,162,0.90); backdrop-filter:blur(8px); color:#fff; font-family:'Jost',sans-serif; font-size:10px; letter-spacing:0.12em; text-transform:uppercase; padding:5px 16px; border-radius:20px; z-index:999; }
</style>
</head>
<body>

<!-- ── WELCOME BACK BANNER ── -->
<div id="welcomeBanner">
  <div class="wb-name" id="wb-name">Welcome back!</div>
  <div class="wb-score">Hair Score: <span id="wb-score">—</span></div>
  <div class="wb-btns">
    <a href="/dashboard" class="wb-btn wb-btn-rose">My Profile</a>
    <a href="https://wa.me/18292332670" target="_blank" class="wb-btn wb-btn-outline">Live Advisor</a>
  </div>
</div>

<div id="topBar">
  <button id="modeToggle" class="top-btn">Manual Mode</button>
  <select id="langSelect">
    <option value="en-US">English</option>
    <option value="es-ES">Español</option>
    <option value="fr-FR">Français</option>
    <option value="pt-BR">Português</option>
    <option value="de-DE">Deutsch</option>
    <option value="ar-SA">عربي</option>
    <option value="zh-CN">中文</option>
    <option value="hi-IN">हिن्दी</option>
  </select>
  <div id="authBar">
    <a href="/login" id="authBtn">✦ Sign In</a>
    <div id="userChip">
      <div id="userAvatar"></div>
      <span id="userName"></span>
      <a href="/dashboard" id="dashLink">Dashboard</a>
    </div>
  </div>
</div>

<div class="sphere-wrap"><div id="halo"></div></div>
<div id="stateLabel">Tap to begin</div>

<div id="history"></div>
<button id="clearBtn">Clear conversation</button>

<div id="manualBox">
  <input id="manualInput" placeholder="Describe your hair concern or ask a follow-up…" />
  <button id="manualSubmit">Send</button>
</div>

<div id="response">Tap the sphere and describe your hair concern.</div>

<!-- ══ TIP PANEL ══ -->
<div id="tipPanel">
  <!-- Form view -->
  <div id="tipForm">
    <div id="tipTitle">Did this help?</div>
    <div id="tipSubtitle">Rate your experience &amp; leave a tip</div>

    <div id="starRow">
      <span class="star" data-v="1">★</span>
      <span class="star" data-v="2">★</span>
      <span class="star" data-v="3">★</span>
      <span class="star" data-v="4">★</span>
      <span class="star" data-v="5">★</span>
    </div>

    <div id="tipAmounts">
      <button class="tip-amt" data-amt="1">$1</button>
      <button class="tip-amt" data-amt="2">$2</button>
      <button class="tip-amt" data-amt="5">$5</button>
      <button class="tip-amt" data-amt="custom">Custom</button>
      <button class="tip-amt" data-amt="0">No tip</button>
    </div>

    <div id="customTipWrap">
      <span style="color:rgba(0,0,0,0.40);font-size:16px;">$</span>
      <input id="customTipInput" type="number" min="1" max="100" placeholder="0.00" />
    </div>

    <button id="tipSubmit">Submit</button>
    <button id="tipSkip">Skip</button>
  </div>

  <!-- Thank-you view -->
  <div id="tipThanks">
    <div class="thanks-icon">🌿</div>
    <div class="thanks-title">Thank you!</div>
    <div class="thanks-sub">Your feedback means everything</div>
  </div>
</div>

<div id="footer">
  <span id="faqBtn">FAQ</span>
  <span id="contactBtn">Contact Us</span>
</div>

<!-- ── PAYWALL COUNTER ── -->
<div id="paywallCounter" id="pw-counter">Free responses: <span id="pw-count">3</span> remaining</div>

<!-- ── PAYWALL BANNER ── -->
<div id="paywallBanner">
  <div class="pw-top">
    <div>
      <div class="pw-trial">7-Day Free Trial · $80/mo after</div>
      <div class="pw-title">Unlock Full Hair Analysis</div>
    </div>
    <button class="pw-close" onclick="closePaywall()">✕</button>
  </div>
  <div class="pw-desc">You've used your 3 free responses. Upgrade to Premium for unlimited expert hair advice, your personal Hair Health Score, and full consultation history.</div>
  <div class="pw-features">
    <div class="pw-feature">Unlimited Aria conversations</div>
    <div class="pw-feature">Hair Health Score dashboard</div>
    <div class="pw-feature">Full consultation history</div>
    <div class="pw-feature">Salon recommendations</div>
    <div class="pw-feature">Medical resource guidance</div>
    <div class="pw-feature">Priority live advisor access</div>
  </div>
  <div class="pw-btns">
    <button class="pw-btn-upgrade" onclick="goUpgrade()">Start Free Trial</button>
    <button class="pw-btn-continue" onclick="closePaywall()">Continue Free</button>
  </div>
</div>

<script>
const halo         = document.getElementById("halo");
const responseBox  = document.getElementById("response");
const stateLabel   = document.getElementById("stateLabel");
const langSelect   = document.getElementById("langSelect");
const modeToggle   = document.getElementById("modeToggle");
const manualBox    = document.getElementById("manualBox");
const manualInput  = document.getElementById("manualInput");
const manualSubmit = document.getElementById("manualSubmit");
const historyEl    = document.getElementById("history");
const clearBtn     = document.getElementById("clearBtn");

/* ── TIP PANEL ELEMENTS ── */
const tipPanel       = document.getElementById("tipPanel");
const tipForm        = document.getElementById("tipForm");
const tipThanks      = document.getElementById("tipThanks");
const tipSubmitBtn   = document.getElementById("tipSubmit");
const tipSkipBtn     = document.getElementById("tipSkip");
const customTipWrap  = document.getElementById("customTipWrap");
const customTipInput = document.getElementById("customTipInput");

let tipRating    = 0;
let tipAmount    = null;
let tipProduct   = "";  // last recommended product

/* ── STAR RATING ── */
document.querySelectorAll(".star").forEach(star => {
  star.addEventListener("click", () => {
    tipRating = parseInt(star.dataset.v);
    document.querySelectorAll(".star").forEach(s => {
      s.classList.toggle("active", parseInt(s.dataset.v) <= tipRating);
    });
  });
  star.addEventListener("mouseover", () => {
    const v = parseInt(star.dataset.v);
    document.querySelectorAll(".star").forEach(s => {
      s.classList.toggle("active", parseInt(s.dataset.v) <= v);
    });
  });
  star.addEventListener("mouseout", () => {
    document.querySelectorAll(".star").forEach(s => {
      s.classList.toggle("active", parseInt(s.dataset.v) <= tipRating);
    });
  });
});

/* ── TIP AMOUNT BUTTONS ── */
document.querySelectorAll(".tip-amt").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tip-amt").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");
    tipAmount = btn.dataset.amt;
    customTipWrap.classList.toggle("show", tipAmount === "custom");
    if (tipAmount !== "custom") customTipInput.value = "";
  });
});

/* ── OPEN / CLOSE TIP PANEL ── */
function openTipPanel(product) {
  tipProduct = product || "";
  tipRating  = 0;
  tipAmount  = null;
  document.querySelectorAll(".star").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".tip-amt").forEach(b => b.classList.remove("selected"));
  customTipWrap.classList.remove("show");
  customTipInput.value = "";
  tipForm.style.display   = "block";
  tipThanks.style.display = "none";
  tipPanel.classList.add("open");
}

function closeTipPanel() {
  tipPanel.classList.remove("open");
}

/* ── SUBMIT TIP ── */
tipSubmitBtn.addEventListener("click", async () => {
  let finalAmt = tipAmount;
  if (tipAmount === "custom") {
    const v = parseFloat(customTipInput.value);
    finalAmt = isNaN(v) || v <= 0 ? "0" : v.toFixed(2);
  }
  if (!finalAmt) finalAmt = "0";

  // Log to backend
  try {
    await fetch("https://ai-hair-advisor.onrender.com/api/tip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lang:    langSelect.value,
        rating:  tipRating,
        amount:  finalAmt,
        product: tipProduct
      })
    });
  } catch(e) {}

  // If real money tip (amount > 0), open Shopify checkout in new tab
  if (finalAmt !== "0" && finalAmt !== "custom") {
    const amtCents = Math.round(parseFloat(finalAmt) * 100);
    // Replace 42109000908880 with your tip product variant ID
    const shopifyUrl = "https://supportdr-com.myshopify.com/cart/42109000908880:" + 1 +
      "?properties[tip_amount]=$" + finalAmt + "&checkout";
    window.open(shopifyUrl, "_blank");
  }

  // Show thank you
  tipForm.style.display   = "none";
  tipThanks.style.display = "flex";
  setTimeout(closeTipPanel, 3000);
});

tipSkipBtn.addEventListener("click", () => {
  // Log skip (rating only, no tip)
  try {
    fetch("https://ai-hair-advisor.onrender.com/api/tip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lang:    langSelect.value,
        rating:  tipRating,
        amount:  "skip",
        product: tipProduct
      })
    });
  } catch(e) {}
  closeTipPanel();
});

/* ── STATE ── */
let appState      = "idle";
let recognition   = null;
let silenceTimer  = null;
let noSpeechTimer = null;
let finalText     = "";
let isManual      = false;
let conversationHistory = [];
let lastRecommendedProduct = "";

function addToHistory(role, text) {
  conversationHistory.push({ role, content: text });
  if (role === "assistant") {
    // Try to detect which product was mentioned
    const t = text.toLowerCase();
    if (t.includes("formula exclusiva")) lastRecommendedProduct = "Formula Exclusiva";
    else if (t.includes("laciador")||t.includes("crece")) lastRecommendedProduct = "Laciador Crece";
    else if (t.includes("gotero")||t.includes("rapido")) lastRecommendedProduct = "Gotero Rapido";
    else if (t.includes("gotitas")||t.includes("brillantes")) lastRecommendedProduct = "Gotitas Brillantes";
  }

  const bubble = document.createElement("div");
  bubble.className = "msg " + (role === "user" ? "user" : "ai");
  bubble.textContent = text;
  historyEl.appendChild(bubble);
  historyEl.scrollTop = historyEl.scrollHeight;

  clearBtn.classList.add("visible");
  responseBox.textContent = "";
}

clearBtn.addEventListener("click", () => {
  conversationHistory = [];
  historyEl.innerHTML = "";
  clearBtn.classList.remove("visible");
  responseBox.textContent = "Tap the sphere and describe your hair concern.";
  lastRecommendedProduct = "";
});

/* ── AUDIO ── */
let audioCtx = null;
let analyser = null;
let micData  = null;
function getCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

function playAmbient(type) {
  try {
    const ctx = getCtx(), master = ctx.createGain(), now = ctx.currentTime;
    master.connect(ctx.destination);
    if (type === "intro") {
      [[220,0],[330,0.20],[440,0.40],[660,0.65]].forEach(([f,d]) => {
        const o=ctx.createOscillator(),g=ctx.createGain();
        o.connect(g);g.connect(master);o.type="sine";
        o.frequency.setValueAtTime(f,now+d);
        g.gain.setValueAtTime(0,now+d);
        g.gain.linearRampToValueAtTime(0.06,now+d+0.5);
        g.gain.exponentialRampToValueAtTime(0.001,now+d+3.5);
        o.start(now+d);o.stop(now+d+4.0);
      });
      const s=ctx.createOscillator(),sg=ctx.createGain();
      s.connect(sg);sg.connect(master);s.type="sine";
      s.frequency.setValueAtTime(1320,now+0.8);
      s.frequency.exponentialRampToValueAtTime(880,now+2.5);
      sg.gain.setValueAtTime(0,now+0.8);
      sg.gain.linearRampToValueAtTime(0.022,now+1.1);
      sg.gain.exponentialRampToValueAtTime(0.001,now+3.8);
      s.start(now+0.8);s.stop(now+4.0);
      master.gain.setValueAtTime(1,now);
    } else {
      [[660,0],[440,0.25],[330,0.50],[220,0.75]].forEach(([f,d]) => {
        const o=ctx.createOscillator(),g=ctx.createGain();
        o.connect(g);g.connect(master);o.type="sine";
        o.frequency.setValueAtTime(f,now+d);
        o.frequency.exponentialRampToValueAtTime(f*0.90,now+d+2.5);
        g.gain.setValueAtTime(0,now+d);
        g.gain.linearRampToValueAtTime(0.050,now+d+0.35);
        g.gain.exponentialRampToValueAtTime(0.001,now+d+3.2);
        o.start(now+d);o.stop(now+d+3.5);
      });
      master.gain.setValueAtTime(1,now);
    }
  } catch(e) {}
}

function initMic() {
  if (analyser) return Promise.resolve();
  const ctx = getCtx();
  return navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      const src = ctx.createMediaStreamSource(stream);
      analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.6;
      src.connect(analyser);
      micData = new Uint8Array(analyser.frequencyBinCount);
    })
    .catch(e => console.warn("Mic blocked (iframe):", e));
}

/* ── COLOR ── */
function setColor(r, g, b) {
  halo.style.background = `radial-gradient(circle at 40% 38%,
    rgba(${r},${g},${b},0.52) 0%, rgba(${r},${g},${b},0.18) 42%,
    rgba(${r},${g},${b},0.07) 70%, rgba(${r},${g},${b},0.01) 100%)`;
  halo.style.boxShadow = `
    inset 0 0 40px rgba(${r},${g},${b},0.12),
    0 0  70px rgba(${r},${g},${b},0.50),
    0 0 155px rgba(${r},${g},${b},0.30),
    0 0 290px rgba(${r},${g},${b},0.16),
    0 0 440px rgba(${r},${g},${b},0.08)`;
}
const IDLE=[193,163,162], LISTEN=[157,127,106], SPEAK=[208,208,208];
setColor(...IDLE);

function setState(s) {
  appState = s;
  halo.classList.remove("listening","speaking");
  if (s === "listening") halo.classList.add("listening");
  if (s === "speaking")  { halo.classList.add("speaking"); halo.style.transform=""; }
  if (s === "idle")      halo.style.transform = "";
}

/* ── MIC REACTIVE LOOP ── */
let voiceActivityLevel = 0;
let listenPhase = 0;
function micReactiveLoop() {
  if (appState !== "listening") return;
  let scale;
  if (analyser && micData) {
    analyser.getByteFrequencyData(micData);
    let sum = 0;
    for (let i = 0; i < micData.length; i++) sum += micData[i];
    scale = 1.05 + (sum / (micData.length * 255)) * 0.65;
  } else {
    voiceActivityLevel *= 0.92;
    listenPhase += 0.04;
    scale = 1.05 + 0.03 * Math.sin(listenPhase) + voiceActivityLevel * 0.45;
  }
  halo.style.transform = `scale(${Math.max(1.0, scale).toFixed(3)})`;
  requestAnimationFrame(micReactiveLoop);
}

/* ── VOICE SELECTION ── */
function getBestVoice(lang) {
  const voices = speechSynthesis.getVoices();
  if (!voices.length) return null;
  if (lang === "en-US" || lang === "en-GB") {
    for (const name of ["Google US English","Google UK English Female","Microsoft Aria Online (Natural) - English (United States)","Microsoft Jenny Online (Natural) - English (United States)","Samantha","Karen","Moira","Fiona"]) {
      const v = voices.find(v => v.name === name);
      if (v) return v;
    }
  }
  const byLang = voices.filter(v => v.lang === lang);
  return byLang.find(v=>/Google/.test(v.name)) || byLang.find(v=>/Natural|Online/.test(v.name)) ||
         byLang.find(v=>/Microsoft/.test(v.name)) || byLang.find(v=>!v.localService) || byLang[0] ||
         voices.find(v=>v.lang.startsWith(lang.split("-")[0])) || voices[0];
}

/* ── SPEAK ── */
function speak(text, showTip) {
  speechSynthesis.cancel();
  setTimeout(() => {
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang  = langSelect.value;
    utter.voice = getBestVoice(langSelect.value);
    utter.rate  = 0.88; utter.pitch = 1.05;
    setState("speaking"); setColor(...SPEAK);
    stateLabel.textContent = "Speaking";
    speechSynthesis.speak(utter);
    utter.onend = () => {
      playAmbient("outro");
      setState("idle"); setColor(...IDLE);
      stateLabel.textContent = "Tap to begin";
      if (showTip) {
        setTimeout(() => openTipPanel(lastRecommendedProduct), 1200);
      }
    };
  }, 80);
}

/* ── LOCAL RESPONSES ── */
const LOCAL_R = {
  "en-US": {
    damaged: "Formula Exclusiva is exactly what your hair needs. This professional all-in-one treatment rebuilds strength, restores moisture, and revives scalp health — safe for the whole family including children. At $55, it's your most complete solution.",
    color:   "Gotitas Brillantes is perfect for you. It gives your hair incredible softness, shine, and beauty — just apply after styling and let it work. Price: $30.",
    colorAf: "Gotitas Brillantes adds the perfect warmth, evenness, and shine to your hair. At $30, it's your best finishing touch.",
    oily:    "Gotero Rapido works directly on your scalp to eliminate obstructions and parasites while stimulating growth. Use it every night. Price: $55.",
    oilyHi: "Gotero Rapido is your solution — it targets dead scalp cells, removes obstructions, and regenerates hair. At $55, it's your nightly treatment.",
    dry:     "Laciador Crece restructures your hair giving it softness, elasticity, and natural shine all day. It even stimulates growth. Price: $40.",
    dryAs:  "Formula Exclusiva penetrates deeply to restore elasticity and hydration — perfect for the whole family. Price: $55.",
    tangly:  "Laciador Crece is your answer — it restructures and gives your hair amazing softness and manageability. Price: $40.",
    tanglyH:"Laciador Crece smooths, restructures, and leaves your hair with beautiful shine and elasticity. Price: $40.",
    flat:    "Gotitas Brillantes gives your style the perfect fall, shine, and body it needs. Price: $30.",
    loss:    "Gotero Rapido stimulates every dead cell on your scalp, eliminates parasites, removes obstructions, and regenerates the hair you've lost. Use every night. Price: $55.",
    default: "Formula Exclusiva is your best all-around choice — moisture, strength, and scalp health in one, safe for the whole family. Price: $55."
  },
  "es-ES": {
    damaged:"Formula Exclusiva es exactamente lo que tu cabello necesita. A $55.",
    color:  "Gotika restaura la vitalidad y protege tu pigmento. Precio: $30.",
    colorAf:"Gotero restaura el brillo natural. A $55.",
    oily:   "Gotero regula la producción de sebo. Precio: $55.",
    oilyHi:"Formula Exclusiva equilibra el aceite. A $55.",
    dry:    "Laciador restaura suavidad y rebote. Precio: $40.",
    dryAs: "Formula Exclusiva restaura elasticidad. Precio: $55.",
    tangly: "Formula Exclusiva resuelve los enredos. Precio: $55.",
    tanglyH:"Laciador suaviza y desenreda. Precio: $40.",
    flat:   "Laciador da volumen. Precio: $40.",
    default:"Formula Exclusiva es tu mejor opción. Precio: $55."
  },
  "fr-FR": {
    damaged:"Formula Exclusiva est exactement ce dont vos cheveux ont besoin. À 65$.",
    color:  "Gotika restaure l'éclat et protège votre pigment. Prix: $30.",
    colorAf:"Gotero restaure l'éclat naturel. À 42$.",
    oily:   "Gotero régule la production de sébum. Prix: $55.",
    oilyHi:"Formula Exclusiva équilibre l'huile. À 65$.",
    dry:    "Laciador transforme les cheveux secs. Prix: $40.",
    dryAs: "Formula Exclusiva est idéale pour votre type. Prix: $55.",
    tangly: "Formula Exclusiva s'attaque aux nœuds. Prix: $55.",
    tanglyH:"Laciador lisse et démêle. Prix: $40.",
    flat:   "Laciador donne du volume. Prix: $40.",
    default:"Formula Exclusiva est votre meilleur choix. Prix: $55."
  },
  "pt-BR": {
    damaged:"Formula Exclusiva é o que seu cabelo precisa. Por $55.",
    color:  "Gotika restaura a vibração e protege seu pigmento. Preço: $30.",
    colorAf:"Gotero restaura o brilho natural. Por $55.",
    oily:   "Gotero regula a produção de sebo. Preço: $55.",
    oilyHi:"Formula Exclusiva equilibra o óleo. Por $55.",
    dry:    "Laciador transforma o cabelo seco. Preço: $40.",
    dryAs: "Formula Exclusiva é ideal para seu tipo. Preço: $55.",
    tangly: "Formula Exclusiva resolve os nós. Preço: $55.",
    tanglyH:"Laciador alisa e desembaraça. Preço: $40.",
    flat:   "Laciador dá volume. Preço: $40.",
    default:"Formula Exclusiva é sua melhor escolha. Preço: $55."
  },
  "de-DE": {
    damaged:"Formula Exclusiva ist genau das, was Ihr Haar braucht. Für $55.",
    color:  "Gotika stellt Lebendigkeit wieder her. Preis: $30.",
    colorAf:"Gotero stellt natürlichen Glanz wieder her. Für $55.",
    oily:   "Gotero reguliert Talgproduktion. Preis: $55.",
    oilyHi:"Formula Exclusiva bringt das Öl ins Gleichgewicht. Für $55.",
    dry:    "Laciador transformiert trockenes Haar. Preis: $40.",
    dryAs: "Formula Exclusiva ist ideal für Ihren Haartyp. Preis: $55.",
    tangly: "Formula Exclusiva bekämpft Verfilzungen. Preis: $55.",
    tanglyH:"Laciador glättet und entwirrt. Preis: $40.",
    flat:   "Laciador gibt Volumen. Preis: $40.",
    default:"Formula Exclusiva ist Ihre beste Lösung. Preis: $55."
  },
  "ar-SA": {
    damaged:"فورمولا إكسكلوسيفا هو ما يحتاجه شعرك. بسعر $65.",
    color:  "غوتيكا تستعيد النضارة وتحمي الصبغة. السعر: $54.",
    colorAf:"غوتيرو يستعيد البريق الطبيعي. بسعر $42.",
    oily:   "غوتيرو ينظم إنتاج الزيت. السعر: $42.",
    oilyHi:"فورمولا يوازن زيت فروة الرأس. بسعر $65.",
    dry:    "لاسيادور يحول الشعر الجاف. السعر: $48.",
    dryAs: "فورمولا مثالي لنوع شعرك. السعر: $65.",
    tangly: "فورمولا يعالج التشابك. السعر: $65.",
    tanglyH:"لاسيادور يملس ويفك التشابك. السعر: $48.",
    flat:   "لاسيادور يمنح الحجم. السعر: $48.",
    default:"فورمولا هو أفضل خيار شامل. السعر: $65."
  },
  "zh-CN": {
    damaged:"Formula Exclusiva 正是您需要的。售价 $55。",
    color:  "Gotika 恢复色彩活力，保护色素。售价 $30。",
    colorAf:"Gotero 恢复自然光泽。售价 $55。",
    oily:   "Gotero 调节皮脂分泌。售价 $55。",
    oilyHi:"Formula Exclusiva 平衡油脂。售价 $55。",
    dry:    "Laciador 改善干燥发质。售价 $40。",
    dryAs: "Formula Exclusiva 最适合您的发质。售价 $55。",
    tangly: "Formula Exclusiva 解决打结。售价 $55。",
    tanglyH:"Laciador 顺滑解结。售价 $40。",
    flat:   "Laciador 增加蓬松感。售价 $40。",
    default:"Formula Exclusiva 是您最全面的选择。售价 $55。"
  },
  "hi-IN": {
    damaged:"Formula Exclusiva बिल्कुल वही है जो चाहिए। $65।",
    color:  "Gotika रंग के लिए सही है। $54।",
    colorAf:"Gotero प्राकृतिक चमक बहाल करता है। $42।",
    oily:   "Gotero तैलीय बालों के लिए। $42।",
    oilyHi:"Formula Exclusiva तेल संतुलित करता है। $65।",
    dry:    "Laciador सूखे बालों को बदलता है। $48।",
    dryAs: "Formula Exclusiva आपके बालों के लिए आदर्श। $65।",
    tangly: "Formula Exclusiva उलझन दूर करता है। $65।",
    tanglyH:"Laciador चिकना और उलझन-मुक्त। $48।",
    flat:   "Laciador वॉल्यूम देता है। $48।",
    default:"Formula Exclusiva सबसे अच्छा विकल्प। $65।"
  }
};

function localRecommend(text) {
  const t = text.toLowerCase();
  const R = LOCAL_R[langSelect.value] || LOCAL_R["en-US"];
  const damaged = /damag|break|broke|split end|weak|brittle|burnt|chemical|overprocess|heat damage|perm|relaxer|bleach|falling out|hair loss|bald|thinning|shed|alopecia|receding/.test(t);
  const color   = /color|colour|fade|fading|brassy|discolor|grey|gray|graying|highlights|dye|tint|pigment|vibrancy|roots/.test(t);
  const oily    = /oil|oily|greasy|grease|sebum|buildup|waxy|weighing down|dirty fast|gets dirty|shiny scalp|limp/.test(t);
  const dry     = /dry|frizz|frizzy|rough|coarse|moisture|parched|thirsty|dehydrat|straw|fluffy|puff|no shine|hard to manage/.test(t);
  const tangly  = /tangl|tangle|knot|knotty|matted|hard to brush|hard to comb|detangle|snag/.test(t);
  const flat    = /flat|no bounce|no volume|lifeless|limp|fine hair|thin hair|lacks body|no lift|falls flat/.test(t);
  const african   = /african|black hair|afro|natural hair|4[abc]|coily/.test(t);
  const asian     = /asian|chinese|japanese|korean/.test(t);
  const hispanic  = /hispanic|latin[ao]?|latin american/.test(t);
  const n = [color,oily,dry,damaged,tangly,flat].filter(Boolean).length;
  if (damaged || n >= 3)  return R.damaged;
  if (color)              return african ? R.colorAf : R.color;
  if (oily)               return hispanic ? R.oilyHi : R.oily;
  if (dry)                return asian ? R.dryAs : R.dry;
  if (tangly)             return (hispanic||african) ? R.tanglyH : R.tangly;
  if (flat)               return R.flat;
  return R.default;
}

/* ── AI RECOMMENDATION ── */
async function getRecommendation(userText) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    const authHeaders = {"Content-Type": "application/json", "X-Session-Id": SESSION_ID};
    if(window._srd_token) authHeaders["X-Auth-Token"] = window._srd_token;
    const resp = await fetch("https://ai-hair-advisor.onrender.com/api/recommend", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        text: userText,
        lang: langSelect.value,
        history: conversationHistory.slice(0, -1)
      }),
      signal: controller.signal
    });
    clearTimeout(timeout);
    if (!resp.ok) throw new Error("not ok");
    const data = await resp.json();
    // Handle subscription gating
    handleSubscriptionResponse(data);
    if (data.recommendation) return data.recommendation;
    throw new Error("empty");
  } catch(e) {
    return localRecommend(userText);
  }
}

/* ── PROCESS TEXT ── */
async function processText(text) {
  if (!text || text.trim().length < 3) {
    responseBox.textContent = "Could you describe your hair a little more?";
    setState("idle"); setColor(...IDLE);
    stateLabel.textContent = "Tap to begin";
    setTimeout(() => speak(responseBox.textContent, false), 800);
    return;
  }

  addToHistory("user", text);

  setState("idle"); setColor(...IDLE);
  responseBox.textContent = "Thinking…";
  stateLabel.textContent  = "Thinking";

  const result = await getRecommendation(text);
  const final  = result || localRecommend(text);

  addToHistory("assistant", final);
  // showTip=true → tip panel opens after AI finishes speaking
  setTimeout(() => speak(final, true), 2500);
}

/* ── NO-HEAR ── */
const NO_HEAR = {
  "en-US":"I didn't hear anything. Please tap and describe your hair concern.",
  "es-ES":"No escuché nada. Por favor toca y describe tu preocupación.",
  "fr-FR":"Je n'ai rien entendu. Veuillez appuyer et décrire votre préoccupation.",
  "pt-BR":"Não ouvi nada. Por favor toque e descreva sua preocupação.",
  "de-DE":"Ich habe nichts gehört. Bitte tippen und Ihr Problem beschreiben.",
  "ar-SA":"لم أسمع شيئاً. يرجى النقر ووصف قلقك.",
  "zh-CN":"我没有听到。请点击并描述您的问题。",
  "hi-IN":"मुझे कुछ सुनाई नहीं दिया। कृपया टैप करें।"
};
function noHear() {
  const msg = NO_HEAR[langSelect.value] || NO_HEAR["en-US"];
  responseBox.textContent = msg;
  setState("idle"); setColor(...IDLE);
  stateLabel.textContent = "Tap to begin";
  speak(msg, false);
}

/* ── START LISTENING ── */
function startListening() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { responseBox.textContent = "Please use Chrome or switch to Manual Mode."; return; }

  playAmbient("intro");
  finalText = "";
  setState("listening"); setColor(...LISTEN);
  stateLabel.textContent  = "Listening…";
  responseBox.textContent = conversationHistory.length > 0 ? "Ask a follow-up or describe a new concern…" : "Listening…";

  requestAnimationFrame(micReactiveLoop);
  initMic();

  noSpeechTimer = setTimeout(() => {
    if (appState !== "listening") return;
    try { recognition.stop(); } catch(e) {}
    noHear();
  }, 7000);

  recognition = new SR();
  recognition.lang = langSelect.value;
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    clearTimeout(silenceTimer);
    clearTimeout(noSpeechTimer);
    voiceActivityLevel = 1.0;
    let interim = ""; finalText = "";
    for (let i = 0; i < event.results.length; i++) {
      if (event.results[i].isFinal) finalText += event.results[i][0].transcript + " ";
      else interim += event.results[i][0].transcript;
    }
    responseBox.textContent = (finalText + interim).trim() || "Listening…";
    silenceTimer = setTimeout(() => { try { recognition.stop(); } catch(e) {} }, 3000);
  };

  recognition.onend = () => {
    clearTimeout(silenceTimer); clearTimeout(noSpeechTimer);
    if (appState !== "listening") return;
    const captured = finalText.trim();
    if (captured.length > 2) processText(captured); else noHear();
  };

  recognition.onerror = (e) => {
    clearTimeout(silenceTimer); clearTimeout(noSpeechTimer);
    if (e.error === "no-speech") noHear();
  };

  recognition.start();
}

/* ── CLICK ── */
halo.addEventListener("click", () => {
  if (isManual) return;
  if (appState === "listening") {
    clearTimeout(silenceTimer); clearTimeout(noSpeechTimer);
    try { recognition.stop(); } catch(e) {}
    setState("idle"); setColor(...IDLE);
    stateLabel.textContent  = "Tap to begin";
    responseBox.textContent = "";
    return;
  }
  if (appState === "speaking") {
    speechSynthesis.cancel();
    setState("idle"); setColor(...IDLE);
    stateLabel.textContent = "Tap to begin";
    return;
  }
  startListening();
});

/* ── MANUAL ── */
modeToggle.addEventListener("click", () => {
  isManual = !isManual;
  manualBox.style.display = isManual ? "flex" : "none";
  modeToggle.textContent  = isManual ? "Voice Mode" : "Manual Mode";
});
manualSubmit.addEventListener("click", () => {
  const text = manualInput.value.trim();
  if (text.length < 3) return;
  manualInput.value = "";
  processText(text);
});
manualInput.addEventListener("keydown", e => { if (e.key === "Enter") manualSubmit.click(); });

/* ── LANGUAGE ── */
speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
setTimeout(() => speechSynthesis.getVoices(), 300);

/* ── FAQ / CONTACT ── */
const FAQ_MSGS = {
  "en-US":"All four products are 100% natural, organic, and salon-professional — Caribbean formulated. Formula Exclusiva $65, Laciador $48, Gotero $42, Gotika $54.",
  "es-ES":"Los cuatro son 100% naturales. Formula Exclusiva $65, Laciador $48, Gotero $42, Gotika $54.",
  "fr-FR":"Les quatre sont 100% naturels. Formula Exclusiva $65, Laciador $48, Gotero $42, Gotika $54.",
  "pt-BR":"Os quatro são 100% naturais. Formula Exclusiva $65, Laciador $48, Gotero $42, Gotika $54.",
  "de-DE":"Alle vier sind 100% natürlich. Formula Exclusiva $65, Laciador $48, Gotero $42, Gotika $54.",
  "ar-SA":"المنتجات الأربعة طبيعية 100%. فورمولا $65، لاسيادور $48، غوتيرو $42، غوتيكا $54.",
  "zh-CN":"四款均为100%天然。Formula Exclusiva $65，Laciador $48，Gotero $42，Gotika $54。",
  "hi-IN":"चारों 100% प्राकृतिक। Formula Exclusiva $65, Laciador $48, Gotero $42, Gotika $54।"
};
const CONTACT_MSGS = {
  "en-US":"Email us at support at hairexpert dot com. We'd love to find your perfect product together.",
  "es-ES":"Escríbenos a support arroba hairexpert punto com.",
  "fr-FR":"Envoyez-nous un email à support chez hairexpert point com.",
  "pt-BR":"Envie um e-mail para support em hairexpert ponto com.",
  "de-DE":"Schreiben Sie uns an support bei hairexpert Punkt com.",
  "ar-SA":"راسلنا على support في hairexpert نقطة com.",
  "zh-CN":"发邮件至 support@hairexpert.com。",
  "hi-IN":"support@hairexpert.com पर ईमेल करें।"
};
document.getElementById("faqBtn").addEventListener("click", () => {
  const msg = FAQ_MSGS[langSelect.value]||FAQ_MSGS["en-US"];
  responseBox.textContent = msg; speak(msg, false);
});
document.getElementById("contactBtn").addEventListener("click", () => {
  const msg = CONTACT_MSGS[langSelect.value]||CONTACT_MSGS["en-US"];
  responseBox.textContent = msg; speak(msg, false);
});

// ── AUTH + USER STATE ─────────────────────────────────────────────────────────
(function initAuth(){
  const token = localStorage.getItem('srd_token');
  const cached = localStorage.getItem('srd_user');
  if(!token) return; // show sign in button (default)

  // Show user chip immediately from cache
  if(cached){
    try{
      const u = JSON.parse(cached);
      showUserChip(u.name, u.avatar);
    }catch(e){}
  }

  // Verify token + load profile for welcome banner
  fetch('/api/auth/me', {headers:{'X-Auth-Token':token}})
    .then(r => r.ok ? r.json() : null)
    .then(d => {
      if(!d){ localStorage.removeItem('srd_token'); localStorage.removeItem('srd_user'); return; }
      showUserChip(d.name, d.avatar);
      localStorage.setItem('srd_user', JSON.stringify({name:d.name,email:d.email,avatar:d.avatar||''}));

      // Calc hair score from profile
      let score = '—';
      if(d.profile && (d.profile.hair_concerns || d.profile.hair_type)){
        const concerns = (d.profile.hair_concerns||'').toLowerCase();
        const treatments = (d.profile.treatments||'').toLowerCase();
        const products = (d.profile.products_tried||'').toLowerCase();
        let s = 75;
        if(concerns.includes('dry')) s -= 10;
        if(concerns.includes('damage')) s -= 15;
        if(concerns.includes('breakage')) s -= 20;
        if(concerns.includes('thinning')) s -= 15;
        if(concerns.includes('oily')) s -= 8;
        if(treatments.includes('bleach')) s -= 10;
        if(treatments.includes('relaxer')) s -= 8;
        if(products.includes('formula exclusiva')) s += 12;
        if(products.includes('laciador crece')||products.includes('laciador')) s += 10;
        if(products.includes('gotero rapido')||products.includes('gotero')) s += 8;
        if(products.includes('gotitas brillantes')||products.includes('gotika')) s += 6;
        s = Math.max(0, Math.min(100, s));
        score = s + '%';
      }

      // Show welcome banner for 6 seconds
      document.getElementById('wb-name').textContent = 'Welcome back, ' + (d.name||'').split(' ')[0] + '!';
      document.getElementById('wb-score').textContent = score;
      const banner = document.getElementById('welcomeBanner');
      banner.style.display = 'block';
      setTimeout(()=>{ banner.style.opacity='0'; banner.style.transition='opacity 0.5s'; setTimeout(()=>banner.style.display='none',500); }, 6000);

      // Pass token to recommend calls
      window._srd_token = token;
      window._srd_user = d;
    })
    .catch(()=>{});
})();

function showUserChip(name, avatar){
  document.getElementById('authBtn').style.display = 'none';
  const chip = document.getElementById('userChip');
  chip.style.display = 'flex';
  document.getElementById('userName').textContent = (name||'').split(' ')[0];
  const av = document.getElementById('userAvatar');
  if(avatar){ av.innerHTML = '<img src="'+avatar+'" alt="">'; }
  else { av.textContent = (name||'?')[0].toUpperCase(); }
}

// ── PAYWALL + SUBSCRIPTION SYSTEM ────────────────────────────────────────────
let _paywallDismissed = false;
const SESSION_ID = 'srd_' + Math.random().toString(36).substr(2,9);

function handleSubscriptionResponse(data){
  if(!data) return;
  const count    = data.response_count || 0;
  const limit    = data.free_limit || 3;
  const subbed   = data.subscribed || false;
  const remaining = Math.max(0, limit - count);

  if(subbed) {
    // Hide all paywall elements for subscribers
    document.getElementById('paywallCounter').style.display = 'none';
    document.getElementById('paywallBanner').style.display  = 'none';
    return;
  }

  // Show counter if they've used at least 1 free response
  if(count >= 1 && count < limit){
    const counter = document.getElementById('paywallCounter');
    counter.style.display = 'block';
    document.getElementById('pw-count').textContent = remaining;
    setTimeout(()=>{ counter.style.display='none'; }, 4000);
  }

  // Show soft paywall banner after limit hit
  if(data.show_paywall && !_paywallDismissed){
    setTimeout(()=>{
      document.getElementById('paywallBanner').style.display = 'block';
    }, 800);
  }
}

function closePaywall(){
  _paywallDismissed = true;
  document.getElementById('paywallBanner').style.display = 'none';
}

async function goUpgrade(){
  const token = localStorage.getItem('srd_token');
  if(!token){
    // Not logged in — send to login first
    window.location.href = '/login?next=subscribe';
    return;
  }
  // Create Stripe checkout
  const r = await fetch('/api/subscription/checkout', {
    method:'POST',
    headers:{'Content-Type':'application/json','X-Auth-Token':token}
  });
  const d = await r.json();
  if(d.checkout_url){
    window.location.href = d.checkout_url;
  } else if(d.setup_needed){
    // Stripe not configured yet — send to Shopify subscription page
    window.location.href = 'https://supportrd.com/products/hair-advisor-premium';
  } else {
    alert('Something went wrong. Please try again.');
  }
}
</script>
</body>
</html>"""


# ── API: RECOMMEND (WITH SUBSCRIPTION GATING) ────────────────────────────────
FREE_SYSTEM_PROMPT = """You are Aria, a hair care advisor for SupportRD. Give ONE brief, helpful product recommendation in 2 sentences max. Mention the product name and price. End every response with: "For deeper hair analysis, personalized advice, and your full hair health score, upgrade to SupportRD Premium — start free for 7 days." Keep it warm and helpful."""

@app.route("/api/recommend", methods=["POST","OPTIONS"])
def recommend():
    data       = request.get_json()
    user_text  = data.get("text", "")
    lang       = data.get("lang", "en-US")
    history    = data.get("history", [])
    session_id = request.headers.get("X-Session-Id", request.remote_addr or "anon")

    # Check user + subscription
    user       = get_current_user()
    subscribed = is_subscribed(user["id"]) if user else False

    # Count responses for gating
    count = get_session_count(session_id, user["id"] if user else None)
    show_paywall = not subscribed and count >= FREE_RESPONSE_LIMIT

    lang_names = {
        "en-US":"English","es-ES":"Spanish","fr-FR":"French",
        "pt-BR":"Portuguese","de-DE":"German","ar-SA":"Arabic",
        "zh-CN":"Mandarin Chinese","hi-IN":"Hindi"
    }
    lang_name  = lang_names.get(lang, "English")
    lang_instr = f"\n\nIMPORTANT: Your ENTIRE response must be in {lang_name}."

    # ── CHOOSE SYSTEM PROMPT BASED ON TIER ───────────────────────────────────
    if subscribed:
        # Full premium experience
        profile_context = ""
        if user:
            profile = get_hair_profile(user["id"])
            if profile.get("hair_type") or profile.get("hair_concerns"):
                profile_context = f"""

RETURNING CLIENT PROFILE:
- Name: {user.get("name","this client")}
- Hair type: {profile.get("hair_type","unknown")}
- Known concerns: {profile.get("hair_concerns","none saved")}
- Treatments history: {profile.get("treatments","none saved")}
- Products tried: {profile.get("products_tried","none saved")}
Reference this naturally in your response."""
            save_chat_message(user["id"], "user", user_text)
        active_prompt = SYSTEM_PROMPT + profile_context + lang_instr
        max_tokens    = 350
    else:
        # Free tier — basic response only, always nudge upgrade
        active_prompt = FREE_SYSTEM_PROMPT + lang_instr
        max_tokens    = 180

    if not ANTHROPIC_API_KEY:
        return jsonify({"recommendation": None, "error": "No API key"}), 500

    try:
        import urllib.request as urlreq

        # Build messages
        messages = []
        if subscribed and user:
            db_history = get_chat_history(user["id"], limit=16)
            for h in db_history[:-1]:
                if h.get("role") in ("user","assistant") and h.get("content"):
                    messages.append({"role": h["role"], "content": h["content"]})
        else:
            # Free users only get last 1 exchange for context
            for h in history[-2:]:
                if h.get("role") in ("user","assistant") and h.get("content"):
                    messages.append({"role": h["role"], "content": h["content"]})

        messages.append({"role": "user", "content": user_text})

        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "system": active_prompt,
            "messages": messages
        }).encode("utf-8")

        req = urlreq.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )
        with urlreq.urlopen(req, timeout=12) as resp:
            result    = json.loads(resp.read().decode("utf-8"))
            recommendation = result["content"][0]["text"].strip()

        # Save history + auto-update profile for subscribers
        if subscribed and user:
            save_chat_message(user["id"], "assistant", recommendation)
            concern = extract_concern(user_text)
            if concern:
                profile  = get_hair_profile(user["id"])
                existing = profile.get("hair_concerns","")
                if concern not in existing:
                    updated = (existing + ", " + concern).strip(", ")
                    save_hair_profile(user["id"], {**profile, "hair_concerns": updated})

        # Increment usage counter
        increment_session_count(session_id, user["id"] if user else None)
        new_count = count + 1

        product = extract_product(recommendation)
        concern = extract_concern(user_text)
        log_event(lang, user_text, product, concern)

        return jsonify({
            "recommendation":  recommendation,
            "logged_in":       user is not None,
            "user_name":       user["name"] if user else None,
            "subscribed":      subscribed,
            "response_count":  new_count,
            "free_limit":      FREE_RESPONSE_LIMIT,
            "show_paywall":    show_paywall,
            "paywall_soft":    True
        })

    except Exception as e:
        return jsonify({"recommendation": None, "error": str(e)}), 500


# ── API: TIP LOGGING ──────────────────────────────────────────────────────────
@app.route("/api/tip", methods=["POST"])
def tip():
    data    = request.get_json()
    lang    = data.get("lang", "en-US")
    rating  = data.get("rating", 0)
    amount  = data.get("amount", "skip")
    product = data.get("product", "")
    log_tip(lang, rating, amount, product)
    return jsonify({"ok": True})


# ── ANALYTICS DASHBOARD ───────────────────────────────────────────────────────
ANALYTICS_KEY = os.environ.get("ANALYTICS_KEY", "hairadmin")

@app.route("/analytics")
def analytics():
    key = request.args.get("key", "")
    if key != ANALYTICS_KEY:
        return "Unauthorized. Add ?key=YOUR_ANALYTICS_KEY to the URL.", 401

    try:
        con = get_analytics_db()
        total    = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        products = con.execute("SELECT product, COUNT(*) as n FROM events GROUP BY product ORDER BY n DESC").fetchall()
        concerns = con.execute("SELECT concern, COUNT(*) as n FROM events GROUP BY concern ORDER BY n DESC").fetchall()
        langs    = con.execute("SELECT lang, COUNT(*) as n FROM events GROUP BY lang ORDER BY n DESC").fetchall()
        recent   = con.execute("SELECT ts, lang, user_msg, product, concern FROM events ORDER BY id DESC LIMIT 50").fetchall()
        # Tip stats
        tip_total   = con.execute("SELECT COUNT(*) FROM tips").fetchone()[0]
        avg_rating  = con.execute("SELECT AVG(rating) FROM tips WHERE rating > 0").fetchone()[0]
        tip_amounts = con.execute("SELECT tip_amount, COUNT(*) as n FROM tips GROUP BY tip_amount ORDER BY n DESC").fetchall()
        avg_r = round(avg_rating, 2) if avg_rating else "N/A"
        con.close()
    except Exception as e:
        return f"DB error: {e}", 500

    def bar(n, total):
        pct = int((n / total * 36)) if total else 0
        return "█" * pct + "░" * (36 - pct)

    rows = "".join(f"""<tr>
      <td>{r[0][:16]}</td><td>{r[1]}</td>
      <td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{r[2]}</td>
      <td><b>{r[3]}</b></td><td>{r[4]}</td></tr>""" for r in recent)

    prod_rows = "".join(f"""<tr>
      <td><b>{p[0]}</b></td><td>{p[1]}</td>
      <td style="font-family:monospace;color:#00ffc8">{bar(p[1],total)}</td>
      <td>{round(p[1]/total*100)}%</td></tr>""" for p in products) if products else ""

    concern_rows = "".join(f"""<tr>
      <td>{c[0]}</td><td>{c[1]}</td>
      <td style="font-family:monospace;color:#00c8ff">{bar(c[1],total)}</td>
      <td>{round(c[1]/total*100)}%</td></tr>""" for c in concerns) if concerns else ""

    lang_rows = "".join(f"<tr><td>{l[0]}</td><td>{l[1]}</td><td>{round(l[1]/total*100)}%</td></tr>" for l in langs) if langs else ""

    tip_amt_rows = "".join(f"<tr><td>{t[0]}</td><td>{t[1]}</td></tr>" for t in tip_amounts)

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Hair Advisor Analytics</title>
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@300;400;600&display=swap" rel="stylesheet">
<style>
  body{{background:#040709;color:#dff2ec;font-family:'Jost',sans-serif;font-weight:300;padding:40px;}}
  h1{{font-size:24px;font-weight:400;letter-spacing:0.08em;color:#00ffc8;margin-bottom:8px;}}
  h2{{font-size:13px;font-weight:400;letter-spacing:0.15em;text-transform:uppercase;color:rgba(255,255,255,0.40);margin:36px 0 12px;}}
  .stat{{display:inline-block;background:rgba(0,255,200,0.07);border:1px solid rgba(0,255,200,0.18);
         border-radius:12px;padding:16px 28px;margin:0 12px 12px 0;text-align:center;}}
  .stat .n{{font-size:36px;font-weight:300;color:#00ffc8;}}
  .stat .l{{font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.35);margin-top:4px;}}
  table{{width:100%;border-collapse:collapse;font-size:13px;}}
  th{{text-align:left;padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.08);
      font-size:10px;letter-spacing:0.10em;text-transform:uppercase;color:rgba(255,255,255,0.30);}}
  td{{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.05);color:rgba(255,255,255,0.70);}}
  tr:hover td{{background:rgba(255,255,255,0.03);}}
</style></head><body>
<h1>Hair Advisor — Analytics</h1>
<p style="color:rgba(255,255,255,0.30);font-size:12px;margin-bottom:28px;">Live data · {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC</p>

<div class="stat"><div class="n">{total}</div><div class="l">Total Sessions</div></div>
<div class="stat"><div class="n">{len(products)}</div><div class="l">Products Recommended</div></div>
<div class="stat"><div class="n">{len(langs)}</div><div class="l">Languages Used</div></div>
<div class="stat"><div class="n">{tip_total}</div><div class="l">Tip Submissions</div></div>
<div class="stat"><div class="n">{avg_r}</div><div class="l">Avg Star Rating</div></div>

<h2>Product Recommendations</h2>
<table><tr><th>Product</th><th>Count</th><th>Share</th><th>%</th></tr>{prod_rows}</table>

<h2>Hair Concerns</h2>
<table><tr><th>Concern</th><th>Count</th><th>Share</th><th>%</th></tr>{concern_rows}</table>

<h2>Languages</h2>
<table><tr><th>Language</th><th>Count</th><th>%</th></tr>{lang_rows}</table>

<h2>Tip Amounts</h2>
<table><tr><th>Amount</th><th>Count</th></tr>{tip_amt_rows}</table>

<h2>Recent Sessions (last 50)</h2>
<table><tr><th>Time</th><th>Lang</th><th>Message</th><th>Product</th><th>Concern</th></tr>{rows}</table>
</body></html>"""


# ── SHOPIFY ───────────────────────────────────────────────────────────────────
@app.route("/apps/hair-advisor")
def shopify_proxy():
    return index()



@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        from flask import make_response
        resp = make_response("", 200)
        resp.headers["Access-Control-Allow-Origin"]  = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth-Token, X-Session-Id"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE"
        resp.headers["Access-Control-Max-Age"]       = "3600"
        return resp

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth-Token, X-Session-Id"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE"
    response.headers["Access-Control-Max-Age"]       = "3600"
    return response

@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True, "status": "awake"})

@app.route("/api/test-register", methods=["GET"])
def test_register():
    """Quick test to verify DB and registration works."""
    import traceback
    try:
        con = get_db()
        con.execute("SELECT count(*) FROM users").fetchone()
        con.close()
        test_hash = hash_password("testpass123")
        return jsonify({
            "ok": True,
            "db": "connected",
            "auth_db_path": AUTH_DB,
            "hash_works": len(test_hash) > 0,
            "secrets_module": True
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc()
        })



# ── KEEP-ALIVE SELF PING (prevents Render free tier sleep) ───────────────────

def _keep_alive():
    import time
    import urllib.request as _urlreq
    _url = os.environ.get("APP_BASE_URL","https://ai-hair-advisor.onrender.com") + "/api/ping"
    time.sleep(60)  # Wait for server to fully start
    while True:
        time.sleep(600)  # Ping every 10 minutes
        try: _urlreq.urlopen(_url, timeout=10)
        except: pass

threading.Thread(target=_keep_alive, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# ── MOVEMENT FEED API ─────────────────────────────────────────────────────────
import time as _time

_CITIES = [
    ("Miami, FL", "🇺🇸"), ("New York, NY", "🇺🇸"), ("Los Angeles, CA", "🇺🇸"),
    ("Houston, TX", "🇺🇸"), ("Atlanta, GA", "🇺🇸"), ("Chicago, IL", "🇺🇸"),
    ("Santo Domingo", "🇩🇴"), ("Santiago, DR", "🇩🇴"), ("San Pedro de Macorís", "🇩🇴"),
    ("San Juan, PR", "🇵🇷"), ("Bogotá", "🇨🇴"), ("Medellín", "🇨🇴"),
    ("Ciudad de México", "🇲🇽"), ("Monterrey", "🇲🇽"), ("Madrid", "🇪🇸"),
    ("Barcelona", "🇪🇸"), ("Toronto", "🇨🇦"), ("Montreal", "🇨🇦"),
    ("London", "🇬🇧"), ("Paris", "🇫🇷")
]
_PRODUCTS = ["Formula Exclusiva","Laciador Crece","Gotero Rapido","Gotitas Brillantes"]
_CONCERNS = ["damaged hair","dry hair","frizzy hair","oily scalp",
             "hair thinning","color fading","tangled hair","lack of volume"]
_ACTIONS  = [
    "just ordered {product}",
    "found their solution for {concern}",
    "recommended {product} to a client",
    "reordered {product} for their salon",
    "discovered {product} for {concern}",
    "picked up {product} for {concern}",
]

def _make_movement_event(source="simulated", mins_ago=None):
    city, flag = random.choice(_CITIES)
    product    = random.choice(_PRODUCTS)
    concern    = random.choice(_CONCERNS)
    action     = random.choice(_ACTIONS).format(product=product, concern=concern)
    if mins_ago is None:
        mins_ago = random.randint(0, 55)
    ts = datetime.datetime.utcnow() - datetime.timedelta(minutes=mins_ago)
    return {
        "id":      int(_time.time()*1000) + random.randint(0,999),
        "city":    city,
        "flag":    flag,
        "action":  action,
        "product": product,
        "ts":      ts.isoformat(),
        "source":  source
    }

# Seed 15 simulated events on startup (so the feed is never empty)
_MOVEMENT_EVENTS = [_make_movement_event(mins_ago=random.randint(1,55)) for _ in range(15)]

@app.route("/api/movement", methods=["GET","OPTIONS"])
def movement():
    """Return recent movement events — mix of real orders + simulated activity."""
    live = []
    # Pull real orders from analytics DB (last 30)
    try:
        con = get_analytics_db()
        rows = con.execute(
            "SELECT ts, lang, product FROM events ORDER BY id DESC LIMIT 30"
        ).fetchall()
        con.close()
        lang_city = {
            "en-US": [("New York, NY","🇺🇸"),("Miami, FL","🇺🇸"),("Atlanta, GA","🇺🇸"),
                      ("Chicago, IL","🇺🇸"),("Los Angeles, CA","🇺🇸")],
            "es-ES": [("Madrid","🇪🇸"),("Barcelona","🇪🇸")],
            "pt-BR": [("Bogotá","🇨🇴"),("Medellín","🇨🇴")],
            "fr-FR": [("Paris","🇫🇷"),("Montreal","🇨🇦")],
            "de-DE": [("London","🇬🇧"),("Toronto","🇨🇦")],
            "ar-SA": [("Santo Domingo","🇩🇴"),("Santiago, DR","🇩🇴")],
            "zh-CN": [("New York, NY","🇺🇸"),("Los Angeles, CA","🇺🇸")],
            "hi-IN": [("Houston, TX","🇺🇸"),("Chicago, IL","🇺🇸")],
        }
        for (ts, lang, product) in rows:
            if not product or product == "Unknown":
                continue
            city_list = lang_city.get(lang, [("Miami, FL","🇺🇸")])
            city, flag = random.choice(city_list)
            action = random.choice([
                f"just ordered {product}",
                f"reordered {product} for their salon",
                f"recommended {product} to a client",
            ])
            live.append({
                "id":      hash(ts+product) % 999999,
                "city":    city, "flag": flag,
                "action":  action, "product": product,
                "ts":      ts, "source": "real"
            })
    except Exception as e:
        print("Movement DB error:", e)

    # Add a fresh simulated event to keep the feed feeling live
    _MOVEMENT_EVENTS.insert(0, _make_movement_event(mins_ago=0))
    if len(_MOVEMENT_EVENTS) > 50:
        _MOVEMENT_EVENTS.pop()

    # Merge: real first, then simulated to fill up to 15
    combined = live + _MOVEMENT_EVENTS
    combined = combined[:15]

    return jsonify({
        "events": combined,
        "total":  len(combined) + random.randint(80, 140)  # social proof count
    })


# ── TRANSCRIPT → MOVEMENT EVENT ───────────────────────────────────────────────
@app.route("/api/add-movement", methods=["POST","OPTIONS"])
def add_movement():
    """Accept a cleaned transcript event (from manual upload) and add to feed."""
    data = request.get_json()
    city    = data.get("city", "United States")
    flag    = data.get("flag", "🇺🇸")
    action  = data.get("action", "")
    product = data.get("product", "")
    if not action:
        return jsonify({"error": "action required"}), 400
    event = {
        "id":      int(_time.time()*1000),
        "city":    city, "flag": flag,
        "action":  action, "product": product,
        "ts":      datetime.datetime.utcnow().isoformat(),
        "source":  "transcript"
    }
    _MOVEMENT_EVENTS.insert(0, event)
    return jsonify({"ok": True, "event": event})

# ── TRANSCRIPT PIPELINE ───────────────────────────────────────────────────────
UPLOAD_KEY = os.environ.get("UPLOAD_KEY", "hairadmin")

CLEAN_PROMPT = """You are a privacy filter for a hair care brand's public movement feed.
You receive a raw Microsoft Teams call transcript between a hair product distributor and salon client.

Your job:
1. REMOVE completely: full names, phone numbers, emails, addresses, credit cards, order numbers, any personal info
2. EXTRACT: city/region, product discussed, hair concern, outcome
3. REWRITE as one warm public sentence like:
   "A salon in [City] found their solution for [concern] with [Product]"
4. Return city, flag emoji, product name

Respond ONLY with valid JSON, no preamble:
{"action":"A salon in Miami found their solution for dry hair with Laciador","city":"Miami, FL","flag":"🇺🇸","product":"Laciador Crece"}"""

@app.route("/upload-transcript", methods=["GET","POST"])
def upload_transcript():
    key = request.args.get("key","")
    if key != UPLOAD_KEY:
        return "Unauthorized. Add ?key=YOUR_UPLOAD_KEY to the URL.", 401

    result = error = preview = None

    if request.method == "POST":
        transcript = request.form.get("transcript","").strip()
        if not transcript:
            error = "Please paste a transcript."
        elif not ANTHROPIC_API_KEY:
            error = "No Anthropic API key configured."
        else:
            try:
                import urllib.request as urlreq
                payload = json.dumps({
                    "model":"claude-sonnet-4-20250514","max_tokens":300,
                    "system":CLEAN_PROMPT,
                    "messages":[{"role":"user","content":transcript}]
                }).encode("utf-8")
                req = urlreq.Request(
                    "https://api.anthropic.com/v1/messages", data=payload,
                    headers={"Content-Type":"application/json",
                             "x-api-key":ANTHROPIC_API_KEY,
                             "anthropic-version":"2023-06-01"},
                    method="POST"
                )
                with urlreq.urlopen(req, timeout=15) as resp:
                    raw  = json.loads(resp.read().decode())
                    text = raw["content"][0]["text"].strip()
                    text = text.replace("```json","").replace("```","").strip()
                    cleaned = json.loads(text)

                event = {
                    "id":      int(datetime.datetime.utcnow().timestamp()*1000),
                    "city":    cleaned.get("city","United States"),
                    "flag":    cleaned.get("flag","🇺🇸"),
                    "action":  cleaned.get("action",""),
                    "product": cleaned.get("product",""),
                    "ts":      datetime.datetime.utcnow().isoformat(),
                    "source":  "transcript"
                }
                _MOVEMENT_EVENTS.insert(0, event)
                if len(_MOVEMENT_EVENTS) > 50: _MOVEMENT_EVENTS.pop()
                preview = event
                result  = "Transcript cleaned and published to your live feed!"
            except Exception as e:
                error = f"Error: {e}"

    preview_html = f"""<div style="background:#f0faf5;border:1px solid #c1a3a2;border-radius:12px;
        padding:20px;margin-bottom:24px;">
        <div style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;
        color:#9d7f6a;margin-bottom:8px;">Published to feed</div>
        <div style="font-size:18px;font-style:italic;">{preview['flag']} {preview['city']}</div>
        <div style="font-size:15px;color:rgba(0,0,0,0.65);margin-top:4px;">{preview['action']}</div>
        <div style="font-size:11px;color:rgba(0,0,0,0.30);margin-top:6px;">
        Product: {preview['product']}</div></div>""" if preview else ""

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SupportDR — Upload Transcript</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#f0ebe8;color:#0d0906;font-family:'Jost',sans-serif;font-weight:300;
      min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;}}
.card{{background:#fff;border:1px solid rgba(193,163,162,0.30);border-radius:20px;
       padding:40px;width:100%;max-width:620px;box-shadow:0 8px 48px rgba(0,0,0,0.06);}}
h1{{font-family:'Cormorant Garamond',serif;font-size:28px;font-style:italic;font-weight:300;margin-bottom:6px;}}
.sub{{font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:rgba(0,0,0,0.35);margin-bottom:32px;}}
label{{font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:rgba(0,0,0,0.40);display:block;margin-bottom:8px;}}
textarea{{width:100%;height:240px;padding:16px;border:1px solid rgba(193,163,162,0.35);
          border-radius:12px;font-family:'Jost',sans-serif;font-size:13px;color:#0d0906;
          background:#faf6f3;resize:vertical;outline:none;line-height:1.6;}}
textarea:focus{{border-color:rgba(193,163,162,0.70);}}
textarea::placeholder{{color:rgba(0,0,0,0.25);}}
.steps{{background:rgba(193,163,162,0.07);border-radius:12px;padding:16px 20px;
        margin-bottom:24px;font-size:12px;line-height:1.9;color:rgba(0,0,0,0.50);}}
.steps b{{color:#9d7f6a;font-weight:400;}}
button{{width:100%;padding:14px;margin-top:16px;border:none;border-radius:30px;
        background:rgba(193,163,162,0.90);color:#fff;font-family:'Jost',sans-serif;
        font-size:12px;letter-spacing:0.14em;text-transform:uppercase;cursor:pointer;transition:background 0.3s;}}
button:hover{{background:#9d7f6a;}}
.success{{background:#f0faf5;border:1px solid #c1a3a2;border-radius:10px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#2d6a4f;}}
.err{{background:#fdf0f0;border:1px solid #e4a0a0;border-radius:10px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#8b2020;}}
.feed-link{{text-align:center;margin-top:20px;font-size:11px;letter-spacing:0.10em;text-transform:uppercase;color:rgba(0,0,0,0.30);}}
.feed-link a{{color:#9d7f6a;text-decoration:none;}}
</style></head><body>
<div class="card">
  <h1>Upload Transcript</h1>
  <div class="sub">Private · SupportDR Movement Feed</div>
  <div class="steps">
    <b>How it works:</b><br>
    1. Finish your Microsoft Teams call<br>
    2. Copy the transcript from Teams<br>
    3. Paste below — Claude strips all private info automatically<br>
    4. Clean version goes live on your public feed instantly
  </div>
  {f'<div class="success">✅ {result}</div>' if result else ''}
  {f'<div class="err">❌ {error}</div>' if error else ''}
  {preview_html}
  <form method="POST" action="/upload-transcript?key={key}">
    <label>Paste Microsoft Teams Transcript</label>
    <textarea name="transcript" placeholder="Paste the full Teams transcript here...
Names, phone numbers, addresses, and payment info will be automatically removed.
Only the hair concern, product, and city will appear publicly."></textarea>
    <button type="submit">🌿 Clean &amp; Publish to Feed</button>
  </form>
  <div class="feed-link">
    <a href="https://ai-hair-advisor.onrender.com/analytics?key={key}" target="_blank">View Analytics →</a>
  </div>
</div></body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# ── USER AUTH + HAIR PROFILE SYSTEM ──────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

# ── AUTH ENDPOINTS ────────────────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST","OPTIONS"])
def register():
    try:
        data = request.get_json(force=True, silent=True) or {}
        email = (data.get("email","")).strip().lower()
        name  = data.get("name","").strip()
        pw    = data.get("password","")
        if not email or not pw:
            return jsonify({"error":"Email and password required"}), 400
        if not name:
            return jsonify({"error":"Name is required"}), 400
        if len(pw) < 6:
            return jsonify({"error":"Password must be at least 6 characters"}), 400
        db_execute("INSERT INTO users (email,name,password_hash) VALUES (?,?,?)",
                    (email, name, hash_password(pw)))
        row = db_execute("SELECT id FROM users WHERE email=?", (email,), fetchone=True)
        user_id = row[0]
        token = create_session(user_id)
        return jsonify({"ok":True,"token":token,"name":name,"email":email})
    except sqlite3.IntegrityError:
        return jsonify({"error":"Email already registered"}), 409
    except Exception as e:
        return jsonify({"error":"Registration failed: " + str(e)}), 500

@app.route("/api/auth/login", methods=["POST","OPTIONS"])
def login():
    try:
        data  = request.get_json(force=True, silent=True) or {}
        email = (data.get("email","")).strip().lower()
        pw    = data.get("password","")
        if not email or not pw:
            return jsonify({"error":"Email and password required"}), 400
        row = db_execute(
            "SELECT id,name,avatar FROM users WHERE email=? AND password_hash=?",
            (email, hash_password(pw)), fetchone=True)
        if not row:
            return jsonify({"error":"Invalid email or password"}), 401
        token = create_session(row[0])
        return jsonify({"ok":True,"token":token,"name":row[1],"email":email,"avatar":row[2]})
    except Exception as e:
        return jsonify({"error":"Login failed: " + str(e)}), 500

@app.route("/api/auth/logout", methods=["POST","OPTIONS"])
def logout():
    token = request.headers.get("X-Auth-Token") or request.cookies.get("srd_token")
    if token:
        con = get_db()
        con.execute("DELETE FROM sessions WHERE token=?", (token,))
        con.commit()
        con.close()
    return jsonify({"ok":True})

@app.route("/api/auth/me", methods=["GET","OPTIONS"])
def me():
    user = get_current_user()
    if not user: return jsonify({"error":"Not logged in"}), 401
    profile = get_hair_profile(user["id"])
    history_count = len(get_chat_history(user["id"], limit=100))
    return jsonify({**user, "profile": profile, "chat_count": history_count})

@app.route("/api/auth/google", methods=["POST","OPTIONS"])
def google_auth():
    """Handle Google OAuth — frontend sends the Google ID token"""
    data     = request.get_json()
    g_token  = data.get("credential","")
    # Decode Google JWT payload (no signature check needed for basic use)
    try:
        parts   = g_token.split(".")
        padding = 4 - len(parts[1]) % 4
        payload = json.loads(__import__("base64").b64decode(parts[1] + "="*padding).decode())
        email   = payload.get("email","")
        name    = payload.get("name","")
        avatar  = payload.get("picture","")
        g_id    = payload.get("sub","")
    except Exception as e:
        return jsonify({"error":"Invalid Google token"}), 400

    con = get_db()
    row = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if row:
        user_id = row[0]
        con.execute("UPDATE users SET google_id=?,name=?,avatar=? WHERE id=?",
                    (g_id, name, avatar, user_id))
    else:
        con.execute("INSERT INTO users (email,name,google_id,avatar) VALUES (?,?,?,?)",
                    (email, name, g_id, avatar))
        user_id = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()[0]
    con.commit()
    con.close()
    token = create_session(user_id)
    return jsonify({"ok":True,"token":token,"name":name,"email":email,"avatar":avatar})

# ── HAIR PROFILE ENDPOINTS ────────────────────────────────────────────────────

@app.route("/api/profile", methods=["GET","POST","OPTIONS"])
def profile():
    user = get_current_user()
    if not user: return jsonify({"error":"Not logged in"}), 401
    if request.method == "POST":
        save_hair_profile(user["id"], request.get_json())
        return jsonify({"ok":True})
    return jsonify(get_hair_profile(user["id"]))

@app.route("/api/history", methods=["GET","OPTIONS"])
def history():
    user = get_current_user()
    if not user: return jsonify({"error":"Not logged in"}), 401
    return jsonify({"history": get_chat_history(user["id"], limit=50)})

@app.route("/api/history/clear", methods=["POST","OPTIONS"])
def clear_history():
    user = get_current_user()
    if not user: return jsonify({"error":"Not logged in"}), 401
    con = get_db()
    con.execute("DELETE FROM chat_history WHERE user_id=?", (user["id"],))
    con.commit()
    con.close()
    return jsonify({"ok":True})



# ── LOGIN PAGE ────────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

@app.route("/login")
def login_page():
    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SupportRD — Sign In</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<script src="https://accounts.google.com/gsi/client" async defer></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#f0ebe8;min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:'Jost',sans-serif;font-weight:300;padding:24px;}}
.card{{background:#fff;border-radius:24px;padding:48px 40px;width:100%;max-width:420px;box-shadow:0 12px 48px rgba(0,0,0,0.08);border:1px solid rgba(193,163,162,0.20);}}
.logo{{text-align:center;margin-bottom:32px;}}
.logo-text{{font-family:'Cormorant Garamond',serif;font-size:32px;font-style:italic;font-weight:300;color:#0d0906;}}
.logo-sub{{font-size:10px;letter-spacing:0.24em;text-transform:uppercase;color:#c1a3a2;margin-top:4px;}}
h2{{font-family:'Cormorant Garamond',serif;font-size:22px;font-style:italic;font-weight:300;color:#0d0906;text-align:center;margin-bottom:28px;}}
.tabs{{display:flex;gap:0;border:1px solid rgba(193,163,162,0.30);border-radius:12px;overflow:hidden;margin-bottom:28px;}}
.tab{{flex:1;padding:10px;text-align:center;font-size:12px;letter-spacing:0.10em;text-transform:uppercase;cursor:pointer;background:#fff;color:rgba(0,0,0,0.40);transition:all 0.2s;border:none;font-family:'Jost',sans-serif;}}
.tab.active{{background:#c1a3a2;color:#fff;}}
input{{width:100%;padding:13px 16px;border:1px solid rgba(193,163,162,0.35);border-radius:12px;font-family:'Jost',sans-serif;font-size:14px;color:#0d0906;background:#faf6f3;outline:none;margin-bottom:12px;transition:border 0.2s;}}
input:focus{{border-color:#c1a3a2;}}
input::placeholder{{color:rgba(0,0,0,0.25);}}
.btn{{width:100%;padding:14px;border:none;border-radius:30px;background:#c1a3a2;color:#fff;font-family:'Jost',sans-serif;font-size:12px;letter-spacing:0.14em;text-transform:uppercase;cursor:pointer;transition:background 0.3s;margin-top:4px;}}
.btn:hover{{background:#9d7f6a;}}
.divider{{display:flex;align-items:center;gap:12px;margin:20px 0;}}
.divider-line{{flex:1;height:1px;background:rgba(193,163,162,0.25);}}
.divider-text{{font-size:11px;color:rgba(0,0,0,0.30);letter-spacing:0.08em;}}
.google-wrap{{display:flex;justify-content:center;}}
.err{{background:#fdf0f0;border:1px solid #e4a0a0;border-radius:10px;padding:12px 16px;font-size:13px;color:#8b2020;margin-bottom:16px;display:none;}}
.success{{background:#f0faf5;border:1px solid #c1a3a2;border-radius:10px;padding:12px 16px;font-size:13px;color:#2d6a4f;margin-bottom:16px;display:none;}}
.back{{text-align:center;margin-top:20px;font-size:11px;color:rgba(0,0,0,0.35);letter-spacing:0.08em;}}
.back a{{color:#9d7f6a;text-decoration:none;}}
</style>
</head><body>
<div class="card">
  <div class="logo">
    <div class="logo-text">SupportRD</div>
    <div class="logo-sub">Hair Advisor</div>
  </div>
  <h2>Welcome back</h2>
  <div class="tabs">
    <button class="tab active" onclick="switchTab('login')">Sign In</button>
    <button class="tab" onclick="switchTab('register')">Create Account</button>
  </div>
  <div id="err" class="err"></div>
  <div id="success" class="success"></div>
  <div id="login-form">
    <input type="email" id="l-email" placeholder="Email address">
    <input type="password" id="l-pass" placeholder="Password">
    <button class="btn" onclick="doLogin()">Sign In</button>
  </div>
  <div id="register-form" style="display:none;">
    <input type="text" id="r-name" placeholder="Your name">
    <input type="email" id="r-email" placeholder="Email address">
    <input type="password" id="r-pass" placeholder="Password (min 6 characters)">
    <button class="btn" onclick="doRegister()">Create Account</button>
  </div>
  <div class="divider">
    <div class="divider-line"></div>
    <div class="divider-text">or</div>
    <div class="divider-line"></div>
  </div>
  <div class="google-wrap">
    <div id="g_id_onload" data-client_id="{GOOGLE_CLIENT_ID}" data-callback="handleGoogle"></div>
    <div class="g_id_signin" data-type="standard" data-shape="pill" data-theme="outline" data-text="sign_in_with" data-size="large" data-logo_alignment="left"></div>
  </div>
  <div class="back"><a href="/">← Back to Hair Advisor</a></div>
</div>
<script>
function switchTab(t){{
  document.getElementById('login-form').style.display = t==='login'?'block':'none';
  document.getElementById('register-form').style.display = t==='register'?'block':'none';
  document.querySelectorAll('.tab').forEach((b,i)=>b.classList.toggle('active',(t==='login'&&i===0)||(t==='register'&&i===1)));
  hideMsg();
}}
function showErr(m){{var e=document.getElementById('err');e.textContent=m;e.style.display='block';document.getElementById('success').style.display='none';}}
function showOk(m){{var e=document.getElementById('success');e.textContent=m;e.style.display='block';document.getElementById('err').style.display='none';}}
function hideMsg(){{document.getElementById('err').style.display='none';document.getElementById('success').style.display='none';}}
function saveAndRedirect(data){{
  localStorage.setItem('srd_token', data.token);
  localStorage.setItem('srd_user', JSON.stringify({{name:data.name,email:data.email,avatar:data.avatar||''}}) );
  showOk('Welcome, '+data.name+'! Redirecting...');
  setTimeout(()=>window.location.href='/dashboard',1200);
}}
async function doLogin(){{
  var email=document.getElementById('l-email').value;
  var pass=document.getElementById('l-pass').value;
  if(!email||!pass){{showErr('Please fill in all fields.');return;}}
  var r=await fetch('/api/auth/login',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email,password:pass}})}});
  var d=await r.json();
  if(d.error){{showErr(d.error);}}else{{saveAndRedirect(d);}}
}}
async function doRegister(){{
  var name=document.getElementById('r-name').value;
  var email=document.getElementById('r-email').value;
  var pass=document.getElementById('r-pass').value;
  if(!name||!email||!pass){{showErr('Please fill in all fields.');return;}}
  var r=await fetch('/api/auth/register',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name,email,password:pass}})}});
  var d=await r.json();
  if(d.error){{showErr(d.error);}}else{{saveAndRedirect(d);}}
}}
async function handleGoogle(response){{
  var r=await fetch('/api/auth/google',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{credential:response.credential}})}});
  var d=await r.json();
  if(d.error){{showErr(d.error);}}else{{saveAndRedirect(d);}}
}}
</script>
</body></html>"""


# ── DASHBOARD PAGE ────────────────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    return """<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SupportRD — Hair Health Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#f0ebe8;font-family:'Jost',sans-serif;font-weight:300;min-height:100vh;padding:24px 20px;}

/* HEADER */
.hdr{max-width:1000px;margin:0 auto 28px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;}
.hdr-logo{font-family:'Cormorant Garamond',serif;font-size:26px;font-style:italic;color:#0d0906;}
.hdr-right{display:flex;align-items:center;gap:14px;}
.avatar{width:38px;height:38px;border-radius:50%;background:#c1a3a2;display:flex;align-items:center;justify-content:center;font-size:16px;color:#fff;overflow:hidden;flex-shrink:0;}
.avatar img{width:100%;height:100%;object-fit:cover;}
.uname{font-size:13px;color:#0d0906;}
.btn-xs{padding:7px 16px;border:1px solid rgba(193,163,162,0.45);border-radius:20px;background:transparent;font-family:'Jost',sans-serif;font-size:10px;letter-spacing:0.10em;text-transform:uppercase;cursor:pointer;color:#9d7f6a;transition:all 0.2s;}
.btn-xs:hover{background:#c1a3a2;color:#fff;border-color:#c1a3a2;}

/* LAYOUT */
.wrap{max-width:1000px;margin:0 auto;display:grid;grid-template-columns:1fr 1fr;gap:20px;}
@media(max-width:680px){.wrap{grid-template-columns:1fr;}}
.full{grid-column:1/-1;}
.card{background:#fff;border-radius:20px;padding:28px;border:1px solid rgba(193,163,162,0.18);box-shadow:0 4px 20px rgba(0,0,0,0.05);}
.card-label{font-size:10px;letter-spacing:0.26em;text-transform:uppercase;color:#c1a3a2;margin-bottom:10px;}
.card-title{font-family:'Cormorant Garamond',serif;font-size:20px;font-style:italic;color:#0d0906;margin-bottom:20px;}

/* HAIR HEALTH SCORE — MAIN FEATURE */
.score-card{background:linear-gradient(135deg,#0d0906 0%,#1e1410 100%);border:none;padding:36px 32px;text-align:center;position:relative;overflow:hidden;}
.score-card::after{content:'';position:absolute;right:-60px;top:-60px;width:260px;height:260px;border-radius:50%;background:radial-gradient(circle,rgba(193,163,162,0.12),transparent 70%);pointer-events:none;}
.score-label{font-size:10px;letter-spacing:0.28em;text-transform:uppercase;color:rgba(193,163,162,0.60);margin-bottom:16px;}
.score-ring-wrap{position:relative;width:200px;height:200px;margin:0 auto 20px;}
.score-ring-svg{transform:rotate(-90deg);}
.score-ring-bg{fill:none;stroke:rgba(193,163,162,0.12);stroke-width:12;}
.score-ring-fill{fill:none;stroke-width:12;stroke-linecap:round;transition:stroke-dashoffset 2s cubic-bezier(0.22,1,0.36,1),stroke 1s ease;}
.score-center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;}
.score-number{font-family:'Cormorant Garamond',serif;font-size:64px;font-style:italic;color:#fff;line-height:1;}
.score-pct{font-size:16px;color:rgba(193,163,162,0.70);font-weight:300;}
.score-status{font-family:'Cormorant Garamond',serif;font-size:22px;font-style:italic;color:#c1a3a2;margin-bottom:8px;}
.score-desc{font-size:12px;color:rgba(255,255,255,0.40);letter-spacing:0.06em;line-height:1.6;max-width:320px;margin:0 auto 24px;}
.score-bars{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:4px;}
.score-bar-item{text-align:left;}
.score-bar-label{font-size:10px;letter-spacing:0.10em;text-transform:uppercase;color:rgba(193,163,162,0.50);margin-bottom:6px;}
.score-bar-track{height:4px;background:rgba(255,255,255,0.08);border-radius:2px;overflow:hidden;}
.score-bar-fill{height:100%;border-radius:2px;transition:width 1.5s cubic-bezier(0.22,1,0.36,1);}
.score-bar-val{font-size:11px;color:rgba(255,255,255,0.50);margin-top:4px;}

/* PROFILE FORM */
.form-group{margin-bottom:14px;}
.form-group label{font-size:10px;letter-spacing:0.12em;text-transform:uppercase;color:rgba(0,0,0,0.38);display:block;margin-bottom:6px;}
input,select,textarea{width:100%;padding:11px 14px;border:1px solid rgba(193,163,162,0.30);border-radius:10px;font-family:'Jost',sans-serif;font-size:13px;color:#0d0906;background:#faf6f3;outline:none;transition:border 0.2s;}
input:focus,select:focus{border-color:#c1a3a2;}
.btn-save{width:100%;padding:12px;border:none;border-radius:24px;background:#c1a3a2;color:#fff;font-family:'Jost',sans-serif;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;cursor:pointer;transition:background 0.3s;margin-top:6px;}
.btn-save:hover{background:#9d7f6a;}

/* STATS ROW */
.stats-row{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:20px;}
.stat{text-align:center;}
.stat-n{font-family:'Cormorant Garamond',serif;font-size:40px;font-style:italic;color:#c1a3a2;line-height:1;}
.stat-l{font-size:10px;letter-spacing:0.12em;text-transform:uppercase;color:rgba(0,0,0,0.30);margin-top:3px;}

/* CTA BUTTONS */
.cta-btn{display:block;padding:14px 20px;border-radius:14px;text-decoration:none;text-align:center;margin-bottom:10px;transition:opacity 0.2s;}
.cta-btn:hover{opacity:0.88;}
.cta-rose{background:linear-gradient(135deg,#c1a3a2,#9d7f6a);color:#fff;}
.cta-wa{background:linear-gradient(135deg,#25D366,#128C7E);color:#fff;}
.cta-title{font-family:'Cormorant Garamond',serif;font-size:17px;font-style:italic;}
.cta-sub{font-size:10px;letter-spacing:0.12em;text-transform:uppercase;opacity:0.85;margin-top:2px;}

/* HISTORY */
.h-item{padding:13px 0;border-bottom:1px solid rgba(193,163,162,0.12);}
.h-item:last-child{border-bottom:none;}
.h-role{font-size:9px;letter-spacing:0.14em;text-transform:uppercase;color:#c1a3a2;margin-bottom:3px;}
.h-text{font-size:13px;color:rgba(0,0,0,0.60);line-height:1.5;}
.clear-btn{font-size:10px;color:rgba(0,0,0,0.28);background:none;border:none;cursor:pointer;letter-spacing:0.08em;text-transform:uppercase;margin-top:14px;display:block;}
.clear-btn:hover{color:#c1a3a2;}

/* SCORE COLOR ZONES */
.zone-critical{stroke:#e07070;}
.zone-poor{stroke:#d4956a;}
.zone-fair{stroke:#c1a3a2;}
.zone-good{stroke:#8ec63f;}
.zone-excellent{stroke:#25D366;}
</style>
</head><body>

<div class="hdr">
  <div class="hdr-logo">SupportRD Hair Advisor</div>
  <div class="hdr-right">
    <div style="display:flex;align-items:center;gap:10px;">
      <div class="avatar" id="av"></div>
      <span class="uname" id="un">Loading...</span>
    </div>
    <button class="btn-xs" onclick="doLogout()">Sign Out</button>
  </div>
</div>

<div class="wrap">

  <!-- HAIR HEALTH SCORE — FULL WIDTH HERO -->
  <div class="card score-card full">
    <div class="score-label">Your Hair Health Score</div>
    <div class="score-ring-wrap">
      <svg class="score-ring-svg" width="200" height="200" viewBox="0 0 200 200">
        <circle class="score-ring-bg" cx="100" cy="100" r="88"/>
        <circle class="score-ring-fill" id="score-ring" cx="100" cy="100" r="88"
          stroke-dasharray="553" stroke-dashoffset="553"/>
      </svg>
      <div class="score-center">
        <div class="score-number" id="score-num">0</div>
        <div class="score-pct">/ 100</div>
      </div>
    </div>
    <div class="score-status" id="score-status">Calculating...</div>
    <div class="score-desc" id="score-desc">Complete your hair profile to get your personalized score</div>
    <div class="score-bars">
      <div class="score-bar-item">
        <div class="score-bar-label">Moisture</div>
        <div class="score-bar-track"><div class="score-bar-fill" id="bar-moisture" style="width:0%;background:#c1a3a2;"></div></div>
        <div class="score-bar-val" id="val-moisture">—</div>
      </div>
      <div class="score-bar-item">
        <div class="score-bar-label">Strength</div>
        <div class="score-bar-track"><div class="score-bar-fill" id="bar-strength" style="width:0%;background:#9d7f6a;"></div></div>
        <div class="score-bar-val" id="val-strength">—</div>
      </div>
      <div class="score-bar-item">
        <div class="score-bar-label">Scalp Health</div>
        <div class="score-bar-track"><div class="score-bar-fill" id="bar-scalp" style="width:0%;background:#c1a3a2;"></div></div>
        <div class="score-bar-val" id="val-scalp">—</div>
      </div>
      <div class="score-bar-item">
        <div class="score-bar-label">Growth</div>
        <div class="score-bar-track"><div class="score-bar-fill" id="bar-growth" style="width:0%;background:#9d7f6a;"></div></div>
        <div class="score-bar-val" id="val-growth">—</div>
      </div>
    </div>
  </div>

  <!-- PROFILE FORM -->
  <div class="card">
    <div class="card-label">Build Your Score</div>
    <div class="card-title">Hair Profile</div>
    <div class="form-group"><label>Hair Type</label>
      <select id="p-type" onchange="recalcScore()">
        <option value="">Select...</option>
        <option>Straight</option><option>Wavy</option><option>Curly</option>
        <option>Coily / 4C</option><option>Fine</option><option>Thick</option>
      </select>
    </div>
    <div class="form-group"><label>Main Concerns</label>
      <input type="text" id="p-concerns" placeholder="e.g. dry, frizzy, thinning..." oninput="recalcScore()">
    </div>
    <div class="form-group"><label>Chemical Treatments</label>
      <input type="text" id="p-treatments" placeholder="e.g. relaxer, bleach, keratin..." oninput="recalcScore()">
    </div>
    <div class="form-group"><label>Products Currently Using</label>
      <input type="text" id="p-products" placeholder="e.g. Formula Exclusiva..." oninput="recalcScore()">
    </div>
    <div class="form-group"><label>Heat Tool Usage</label>
      <select id="p-heat" onchange="recalcScore()">
        <option value="">Select frequency...</option>
        <option value="never">Never</option>
        <option value="rarely">Rarely (monthly)</option>
        <option value="sometimes">Sometimes (weekly)</option>
        <option value="daily">Daily</option>
      </select>
    </div>
    <div class="form-group"><label>Water Type at Home</label>
      <select id="p-water" onchange="recalcScore()">
        <option value="">Select...</option>
        <option value="soft">Soft water</option>
        <option value="hard">Hard water</option>
        <option value="unknown">Not sure</option>
      </select>
    </div>
    <button class="btn-save" onclick="saveProfile()">Save & Update Score</button>
  </div>

  <!-- STATS + CTA -->
  <div class="card">
    <div class="card-label">Overview</div>
    <div class="card-title">My Journey</div>
    <div class="stats-row">
      <div class="stat"><div class="stat-n" id="s-chats">—</div><div class="stat-l">Consultations</div></div>
      <div class="stat"><div class="stat-n" id="s-concern">—</div><div class="stat-l">Concerns Logged</div></div>
      <div class="stat"><div class="stat-n" id="s-score-mini">—</div><div class="stat-l">Hair Score</div></div>
    </div>
    <a href="/" class="cta-btn cta-rose">
      <div class="cta-title">Talk to Aria</div>
      <div class="cta-sub">AI Hair Advisor · Free</div>
    </a>
    <a href="https://wa.me/18292332670" target="_blank" class="cta-btn cta-wa">
      <div class="cta-title">Live Human Advisor</div>
      <div class="cta-sub">WhatsApp · 829-233-2670</div>
    </a>
  </div>

  <!-- CHAT HISTORY -->
  <div class="card full">
    <div class="card-label">Conversation Memory</div>
    <div class="card-title">Recent Chat with Aria</div>
    <div id="history-list"><div style="color:rgba(0,0,0,0.28);font-size:13px;">Loading...</div></div>
    <button class="clear-btn" onclick="clearHistory()">Clear chat history</button>
  </div>

</div>

<script>
const token = localStorage.getItem('srd_token');
if(!token){ window.location.href='/login'; }

// ── SCORE ENGINE ──────────────────────────────────────────────────────────────
function calcScore(){
  const concerns  = (document.getElementById('p-concerns').value||'').toLowerCase();
  const treatments= (document.getElementById('p-treatments').value||'').toLowerCase();
  const products  = (document.getElementById('p-products').value||'').toLowerCase();
  const heat      = document.getElementById('p-heat').value;
  const water     = document.getElementById('p-water').value;
  const type      = document.getElementById('p-type').value;

  // Base score per category (0-100 each)
  let moisture=75, strength=75, scalp=75, growth=75;

  // Concerns deductions
  const concernMap={
    'dry':[-20,0,0,0],'frizz':[-10,0,0,0],'damage':[-5,-25,0,-10],
    'breakage':[0,-30,0,-15],'thinning':[0,-15,0,-25],'falling':[0,-10,0,-30],
    'oily':[0,0,-20,0],'dandruff':[0,0,-25,-5],'itchy':[0,0,-20,0],
    'color':[0,-10,0,0],'bleach':[-5,-20,0,-5],'relaxer':[-5,-15,0,0]
  };
  for(const [k,v] of Object.entries(concernMap)){
    if(concerns.includes(k)||treatments.includes(k)){
      moisture+=v[0]; strength+=v[1]; scalp+=v[2]; growth+=v[3];
    }
  }

  // Heat damage
  if(heat==='daily'){strength-=20;moisture-=15;}
  else if(heat==='sometimes'){strength-=8;moisture-=5;}
  else if(heat==='rarely'){strength-=2;}
  else if(heat==='never'){strength+=5;moisture+=5;}

  // Hard water
  if(water==='hard'){scalp-=10;moisture-=8;}
  else if(water==='soft'){scalp+=5;moisture+=5;}

  // SupportRD products boost
  if(products.includes('formula exclusiva')){strength+=15;moisture+=12;}
  if(products.includes('laciador crece')||products.includes('laciador')){moisture+=12;strength+=8;growth+=5;}
  if(products.includes('gotero rapido')||products.includes('gotero')){scalp+=18;growth+=10;}
  if(products.includes('gotitas brillantes')||products.includes('gotika')){moisture+=8;}

  // Hair type base adjustment
  if(type==='Coily / 4C'){moisture-=5;}
  if(type==='Fine'){strength-=5;}

  // Clamp 0-100
  moisture=Math.max(0,Math.min(100,moisture));
  strength=Math.max(0,Math.min(100,strength));
  scalp   =Math.max(0,Math.min(100,scalp));
  growth  =Math.max(0,Math.min(100,growth));

  const overall = Math.round((moisture+strength+scalp+growth)/4);
  return {overall, moisture, strength, scalp, growth};
}

function getZone(score){
  if(score>=85) return {status:'Excellent',desc:'Your hair is thriving! Keep up your routine and maintain this level of care.',cls:'zone-excellent',color:'#25D366'};
  if(score>=70) return {status:'Good',desc:'Your hair is in good shape with room to optimize. A few targeted treatments can push you higher.',cls:'zone-good',color:'#8ec63f'};
  if(score>=50) return {status:'Fair',desc:'Your hair needs some attention. Consistent care with the right products will make a real difference.',cls:'zone-fair',color:'#c1a3a2'};
  if(score>=30) return {status:'Needs Care',desc:'Your hair is showing signs of stress. Start a focused treatment routine as soon as possible.',cls:'zone-poor',color:'#d4956a'};
  return {status:'Critical',desc:'Your hair needs urgent attention. We strongly recommend consulting with our live advisor.',cls:'zone-critical',color:'#e07070'};
}

function animateNumber(el, target, duration){
  const start=Date.now(); const from=parseInt(el.textContent)||0;
  function step(){
    const p=Math.min(1,(Date.now()-start)/duration);
    const ease=1-Math.pow(1-p,3);
    el.textContent=Math.round(from+(target-from)*ease);
    if(p<1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function recalcScore(){
  const s=calcScore();
  const zone=getZone(s.overall);

  // Ring
  const ring=document.getElementById('score-ring');
  const circumference=553;
  const offset=circumference-(circumference*(s.overall/100));
  ring.style.strokeDashoffset=offset;
  ring.className='score-ring-fill '+zone.cls;

  // Number
  animateNumber(document.getElementById('score-num'), s.overall, 1500);
  document.getElementById('s-score-mini').textContent=s.overall+'%';

  // Status
  document.getElementById('score-status').textContent=zone.status;
  document.getElementById('score-desc').textContent=zone.desc;

  // Sub-bars
  const bars=[
    {id:'bar-moisture',val:s.moisture,valId:'val-moisture',color:zone.color},
    {id:'bar-strength',val:s.strength,valId:'val-strength',color:zone.color},
    {id:'bar-scalp',val:s.scalp,valId:'val-scalp',color:zone.color},
    {id:'bar-growth',val:s.growth,valId:'val-growth',color:zone.color},
  ];
  bars.forEach(b=>{
    setTimeout(()=>{
      document.getElementById(b.id).style.width=b.val+'%';
      document.getElementById(b.id).style.background=b.color;
      document.getElementById(b.valId).textContent=b.val+'%';
    },200);
  });
}

// ── DATA LOADING ─────────────────────────────────────────────────────────────
async function loadData(){
  const r=await fetch('/api/auth/me',{headers:{'X-Auth-Token':token}});
  if(r.status===401){window.location.href='/login';return;}
  const d=await r.json();

  document.getElementById('un').textContent=d.name||d.email;
  const av=document.getElementById('av');
  if(d.avatar){av.innerHTML='<img src="'+d.avatar+'" alt="">';}
  else{av.textContent=(d.name||'?')[0].toUpperCase();}

  document.getElementById('s-chats').textContent=d.chat_count||0;
  const concerns=(d.profile?.hair_concerns||'').split(',').filter(c=>c.trim()).length;
  document.getElementById('s-concern').textContent=concerns||0;

  if(d.profile){
    document.getElementById('p-type').value=d.profile.hair_type||'';
    document.getElementById('p-concerns').value=d.profile.hair_concerns||'';
    document.getElementById('p-treatments').value=d.profile.treatments||'';
    document.getElementById('p-products').value=d.profile.products_tried||'';
  }
  setTimeout(recalcScore, 300);
}

async function loadHistory(){
  const r=await fetch('/api/history',{headers:{'X-Auth-Token':token}});
  const d=await r.json();
  const list=document.getElementById('history-list');
  if(!d.history||!d.history.length){
    list.innerHTML='<div style="color:rgba(0,0,0,0.28);font-size:13px;">No conversations yet — start chatting with Aria!</div>';
    return;
  }
  list.innerHTML=d.history.slice(-20).reverse().map(h=>`
    <div class="h-item">
      <div class="h-role">${h.role==='user'?'You':'Aria'}</div>
      <div class="h-text">${h.content}</div>
    </div>`).join('');
}

async function saveProfile(){
  const data={
    hair_type:document.getElementById('p-type').value,
    hair_concerns:document.getElementById('p-concerns').value,
    treatments:document.getElementById('p-treatments').value,
    products_tried:document.getElementById('p-products').value
  };
  await fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json','X-Auth-Token':token},body:JSON.stringify(data)});
  recalcScore();
  const btn=document.querySelector('.btn-save');
  btn.textContent='Saved ✓';
  setTimeout(()=>btn.textContent='Save & Update Score',2000);
}

async function clearHistory(){
  if(!confirm('Clear all chat history?'))return;
  await fetch('/api/history/clear',{method:'POST',headers:{'X-Auth-Token':token}});
  loadHistory();
}

async function doLogout(){
  await fetch('/api/auth/logout',{method:'POST',headers:{'X-Auth-Token':token}});
  localStorage.removeItem('srd_token');
  localStorage.removeItem('srd_user');
  window.location.href='/';
}

loadData();
loadHistory();
</script>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# ── SHOPIFY CUSTOMER BRIDGE ───────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

SHOPIFY_STORE   = os.environ.get("SHOPIFY_STORE", "supportrd.myshopify.com")
SHOPIFY_TOKEN   = os.environ.get("SHOPIFY_ADMIN_TOKEN", "")  # Admin API token

def get_or_create_user_by_shopify(shopify_customer_id, email, name, avatar=""):
    """Link a Shopify customer to our users DB, or create if new."""
    con = get_db()
    row = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if row:
        user_id = row[0]
        con.execute("UPDATE users SET name=?,avatar=? WHERE id=?", (name, avatar, user_id))
    else:
        con.execute("INSERT INTO users (email,name,avatar,google_id) VALUES (?,?,?,?)",
                    (email, name, avatar, f"shopify_{shopify_customer_id}"))
        user_id = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()[0]
    con.commit()
    con.close()
    token = create_session(user_id)
    return token, user_id

@app.route("/api/auth/shopify", methods=["POST","OPTIONS"])
def shopify_auth():
    """
    Called from Shopify page with customer info injected via Liquid.
    Shopify injects: customer.id, customer.email, customer.first_name, customer.last_name
    We create/link their account and return a session token.
    """
    data  = request.get_json()
    cid   = str(data.get("shopify_customer_id",""))
    email = data.get("email","").strip().lower()
    name  = data.get("name","").strip()
    if not email or not cid:
        return jsonify({"error":"Missing customer data"}), 400
    token, user_id = get_or_create_user_by_shopify(cid, email, name)
    profile = get_hair_profile(user_id)
    history_count = len(get_chat_history(user_id, limit=100))
    return jsonify({"ok":True,"token":token,"name":name,"email":email,
                    "user_id":user_id,"profile":profile,"chat_count":history_count})

@app.route("/api/auth/shopify-verify", methods=["GET","POST","OPTIONS"])
def shopify_verify():
    """Verify a session token and return full profile — called on every dashboard load."""
    user = get_current_user()
    if not user: return jsonify({"error":"Not logged in"}), 401
    profile = get_hair_profile(user["id"])
    history = get_chat_history(user["id"], limit=50)
    recs    = get_recommendation_history(user["id"])
    return jsonify({
        "ok": True,
        "user": user,
        "profile": profile,
        "history": history,
        "recommendations": recs,
        "chat_count": len(history)
    })

def get_recommendation_history(user_id):
    """Extract product recommendations from chat history."""
    con = get_db()
    rows = con.execute("""SELECT content, ts FROM chat_history
        WHERE user_id=? AND role='assistant' ORDER BY id DESC LIMIT 50""",
        (user_id,)).fetchall()
    con.close()
    recs = []
    products = ["Formula Exclusiva","Laciador Crece","Gotero Rapido","Gotitas Brillantes","Mascarilla","Shampoo Aloe Vera"]
    for content, ts in rows:
        for p in products:
            if p.lower() in content.lower():
                recs.append({"product":p,"context":content[:120]+"...","ts":ts})
                break
    return recs[:20]

@app.route("/api/rate-experience", methods=["POST","OPTIONS"])
def rate_experience():
    """Save a website experience rating from the dashboard."""
    user = get_current_user()
    if not user: return jsonify({"error":"Not logged in"}), 401
    data   = request.get_json()
    rating = data.get("rating", 0)
    review = data.get("review","")
    con = get_db()
    # Add ratings column if not exists
    try:
        con.execute("ALTER TABLE hair_profiles ADD COLUMN site_rating INTEGER DEFAULT 0")
        con.execute("ALTER TABLE hair_profiles ADD COLUMN site_review TEXT DEFAULT ''")
        con.commit()
    except: pass
    con.execute("""INSERT INTO hair_profiles (user_id, site_rating, site_review)
        VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET
        site_rating=excluded.site_rating, site_review=excluded.site_review""",
        (user["id"], rating, review))
    con.commit()
    con.close()
    return jsonify({"ok":True})



# ═══════════════════════════════════════════════════════════════════════════════
# ── SUBSCRIPTION SYSTEM ───────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

STRIPE_SECRET_KEY      = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID        = os.environ.get("STRIPE_PRICE_ID", "")        # $80/mo price
STRIPE_WEBHOOK_SECRET  = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_TRIAL_DAYS      = 7
FREE_RESPONSE_LIMIT    = 3
SUBSCRIPTION_PRICE_USD = 80
APP_BASE_URL           = os.environ.get("APP_BASE_URL", "https://ai-hair-advisor.onrender.com")

def init_subscription_db():
    con = get_db()
    con.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER UNIQUE NOT NULL,
        stripe_customer TEXT,
        stripe_sub_id   TEXT,
        shopify_sub_id  TEXT,
        status          TEXT DEFAULT 'inactive',
        plan            TEXT DEFAULT 'free',
        trial_start     TEXT,
        trial_end       TEXT,
        current_period_end TEXT,
        created_at      TEXT DEFAULT (datetime('now')),
        updated_at      TEXT DEFAULT (datetime('now'))
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS session_usage (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        user_id    INTEGER,
        count      INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    con.commit()
    con.close()

init_subscription_db()

def get_subscription(user_id):
    con = get_db()
    row = con.execute("SELECT * FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    if not row: return None
    cols = ["id","user_id","stripe_customer","stripe_sub_id","shopify_sub_id",
            "status","plan","trial_start","trial_end","current_period_end","created_at","updated_at"]
    return dict(zip(cols, row))

def is_subscribed(user_id):
    """Returns True if user has active subscription or active trial."""
    sub = get_subscription(user_id)
    if not sub: return False
    if sub["status"] in ("active", "trialing"): return True
    # Check trial manually
    if sub["trial_end"]:
        try:
            trial_end = datetime.datetime.fromisoformat(sub["trial_end"])
            if datetime.datetime.utcnow() < trial_end:
                return True
        except: pass
    return False

def get_session_count(session_id, user_id=None):
    con = get_db()
    if user_id:
        row = con.execute("SELECT count FROM session_usage WHERE user_id=?", (user_id,)).fetchone()
    else:
        row = con.execute("SELECT count FROM session_usage WHERE session_id=? AND user_id IS NULL", (session_id,)).fetchone()
    con.close()
    return row[0] if row else 0

def increment_session_count(session_id, user_id=None):
    con = get_db()
    if user_id:
        row = con.execute("SELECT id FROM session_usage WHERE user_id=?", (user_id,)).fetchone()
        if row:
            con.execute("UPDATE session_usage SET count=count+1 WHERE user_id=?", (user_id,))
        else:
            con.execute("INSERT INTO session_usage (session_id,user_id,count) VALUES (?,?,1)", (session_id, user_id))
    else:
        row = con.execute("SELECT id FROM session_usage WHERE session_id=? AND user_id IS NULL", (session_id,)).fetchone()
        if row:
            con.execute("UPDATE session_usage SET count=count+1 WHERE session_id=?", (session_id,))
        else:
            con.execute("INSERT INTO session_usage (session_id,user_id,count) VALUES (?,NULL,1)", (session_id,))
    con.commit()
    con.close()

# ── SUBSCRIPTION STATUS ENDPOINT ──────────────────────────────────────────────
@app.route("/api/subscription/status", methods=["GET","OPTIONS"])
def subscription_status():
    user = get_current_user()
    session_id = request.headers.get("X-Session-Id","anon")
    if user:
        sub      = get_subscription(user["id"])
        count    = get_session_count(session_id, user["id"])
        subscribed = is_subscribed(user["id"])
        return jsonify({
            "subscribed": subscribed,
            "plan": sub["plan"] if sub else "free",
            "status": sub["status"] if sub else "inactive",
            "trial_end": sub["trial_end"] if sub else None,
            "current_period_end": sub["current_period_end"] if sub else None,
            "response_count": count,
            "free_limit": FREE_RESPONSE_LIMIT,
            "show_paywall": not subscribed and count >= FREE_RESPONSE_LIMIT
        })
    else:
        count = get_session_count(session_id)
        return jsonify({
            "subscribed": False,
            "plan": "free",
            "status": "inactive",
            "response_count": count,
            "free_limit": FREE_RESPONSE_LIMIT,
            "show_paywall": count >= FREE_RESPONSE_LIMIT
        })

# ── STRIPE CHECKOUT ───────────────────────────────────────────────────────────
@app.route("/api/subscription/checkout", methods=["POST","OPTIONS"])
def create_checkout():
    """Create a Stripe checkout session with 7-day free trial."""
    user = get_current_user()
    if not user:
        return jsonify({"error":"Must be logged in to subscribe"}), 401
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        return jsonify({"error":"Stripe not configured","setup_needed":True}), 503

    try:
        import urllib.request as urlreq, urllib.parse as urlparse
        # Create/get Stripe customer
        sub = get_subscription(user["id"])
        stripe_customer = sub["stripe_customer"] if sub else None

        if not stripe_customer:
            cust_data = urlparse.urlencode({
                "email": user["email"],
                "name": user["name"] or user["email"],
                "metadata[user_id]": str(user["id"])
            }).encode()
            req = urlreq.Request("https://api.stripe.com/v1/customers",
                data=cust_data,
                headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}",
                         "Content-Type": "application/x-www-form-urlencoded"},
                method="POST")
            with urlreq.urlopen(req) as r:
                cust = json.loads(r.read())
            stripe_customer = cust["id"]

        # Create checkout session
        params = urlparse.urlencode({
            "customer": stripe_customer,
            "mode": "subscription",
            "line_items[0][price]": STRIPE_PRICE_ID,
            "line_items[0][quantity]": "1",
            "subscription_data[trial_period_days]": str(STRIPE_TRIAL_DAYS),
            "success_url": f"{APP_BASE_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{APP_BASE_URL}/subscription/cancel",
            "metadata[user_id]": str(user["id"])
        }).encode()

        req = urlreq.Request("https://api.stripe.com/v1/checkout/sessions",
            data=params,
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urlreq.urlopen(req) as r:
            session = json.loads(r.read())

        # Save stripe customer id
        con = get_db()
        row = con.execute("SELECT id FROM subscriptions WHERE user_id=?", (user["id"],)).fetchone()
        if row:
            con.execute("UPDATE subscriptions SET stripe_customer=?,updated_at=? WHERE user_id=?",
                        (stripe_customer, datetime.datetime.utcnow().isoformat(), user["id"]))
        else:
            con.execute("INSERT INTO subscriptions (user_id,stripe_customer,status,plan) VALUES (?,?,'inactive','free')",
                        (user["id"], stripe_customer))
        con.commit()
        con.close()

        return jsonify({"checkout_url": session["url"], "session_id": session["id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── STRIPE WEBHOOK ────────────────────────────────────────────────────────────
@app.route("/api/subscription/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig     = request.headers.get("Stripe-Signature","")
    event_type = None
    try:
        if STRIPE_WEBHOOK_SECRET:
            # Verify signature manually
            import hmac, hashlib
            ts    = sig.split(",")[0].split("=")[1]
            v1    = sig.split("v1=")[1].split(",")[0]
            signed = f"{ts}.{payload.decode()}"
            expected = hmac.new(STRIPE_WEBHOOK_SECRET.encode(), signed.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(v1, expected):
                return jsonify({"error":"Invalid signature"}), 400
        event = json.loads(payload)
        event_type = event["type"]
        obj        = event["data"]["object"]
        user_id    = None
        if obj.get("metadata",{}).get("user_id"):
            user_id = int(obj["metadata"]["user_id"])
        elif obj.get("customer"):
            con = get_db()
            row = con.execute("SELECT user_id FROM subscriptions WHERE stripe_customer=?",
                              (obj["customer"],)).fetchone()
            con.close()
            if row: user_id = row[0]

        if not user_id:
            return jsonify({"ok":True})

        con = get_db()
        if event_type in ("customer.subscription.created","customer.subscription.updated"):
            status      = obj.get("status","inactive")
            trial_end   = datetime.datetime.utcfromtimestamp(obj["trial_end"]).isoformat() if obj.get("trial_end") else None
            period_end  = datetime.datetime.utcfromtimestamp(obj["current_period_end"]).isoformat() if obj.get("current_period_end") else None
            sub_id      = obj.get("id","")
            row = con.execute("SELECT id FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
            if row:
                con.execute("""UPDATE subscriptions SET stripe_sub_id=?,status=?,plan='premium',
                    trial_end=?,current_period_end=?,updated_at=? WHERE user_id=?""",
                    (sub_id, status, trial_end, period_end, datetime.datetime.utcnow().isoformat(), user_id))
            else:
                con.execute("""INSERT INTO subscriptions (user_id,stripe_sub_id,status,plan,trial_end,current_period_end)
                    VALUES (?,?,'trialing','premium',?,?)""",
                    (user_id, sub_id, trial_end, period_end))
        elif event_type == "customer.subscription.deleted":
            con.execute("UPDATE subscriptions SET status='canceled',plan='free',updated_at=? WHERE user_id=?",
                        (datetime.datetime.utcnow().isoformat(), user_id))
        elif event_type in ("invoice.payment_failed",):
            con.execute("UPDATE subscriptions SET status='past_due',updated_at=? WHERE user_id=?",
                        (datetime.datetime.utcnow().isoformat(), user_id))
        con.commit()
        con.close()
    except Exception as e:
        print(f"Webhook error: {e}")
    return jsonify({"ok":True})

# ── SHOPIFY SUBSCRIPTION (manual activation for Shopify flow) ─────────────────
@app.route("/api/subscription/activate-shopify", methods=["POST"])
def activate_shopify():
    """Called when a Shopify subscription is confirmed."""
    user = get_current_user()
    if not user: return jsonify({"error":"Not logged in"}), 401
    data   = request.get_json()
    sub_id = data.get("shopify_sub_id","")
    trial_end = (datetime.datetime.utcnow() + datetime.timedelta(days=STRIPE_TRIAL_DAYS)).isoformat()
    con = get_db()
    row = con.execute("SELECT id FROM subscriptions WHERE user_id=?", (user["id"],)).fetchone()
    if row:
        con.execute("""UPDATE subscriptions SET shopify_sub_id=?,status='trialing',plan='premium',
            trial_end=?,updated_at=? WHERE user_id=?""",
            (sub_id, trial_end, datetime.datetime.utcnow().isoformat(), user["id"]))
    else:
        con.execute("""INSERT INTO subscriptions (user_id,shopify_sub_id,status,plan,trial_end)
            VALUES (?,?,'trialing','premium',?)""",
            (user["id"], sub_id, trial_end))
    con.commit()
    con.close()
    return jsonify({"ok":True,"trial_end":trial_end})

# ── SUBSCRIPTION SUCCESS/CANCEL PAGES ─────────────────────────────────────────
@app.route("/subscription/success")
def subscription_success():
    return """<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SupportRD — Welcome to Premium</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#f0ebe8;min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:'Jost',sans-serif;padding:24px;}
.card{background:#fff;border-radius:24px;padding:56px 40px;max-width:460px;width:100%;text-align:center;box-shadow:0 12px 48px rgba(0,0,0,0.08);}
.icon{font-size:56px;margin-bottom:20px;}
.title{font-family:'Cormorant Garamond',serif;font-size:36px;font-style:italic;color:#0d0906;margin-bottom:10px;}
.sub{font-size:13px;color:rgba(0,0,0,0.40);letter-spacing:0.06em;line-height:1.7;margin-bottom:28px;}
.trial-badge{background:linear-gradient(135deg,#c1a3a2,#9d7f6a);color:#fff;padding:10px 24px;border-radius:20px;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;display:inline-block;margin-bottom:28px;}
.btn{display:block;padding:14px;background:#c1a3a2;color:#fff;text-decoration:none;border-radius:30px;font-family:'Jost',sans-serif;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;margin-bottom:10px;transition:background 0.2s;}
.btn:hover{background:#9d7f6a;}
.btn-outline{background:transparent;color:#9d7f6a;border:1px solid rgba(193,163,162,0.40);}
</style></head><body>
<div class="card">
  <div class="icon">🌿</div>
  <div class="title">Welcome to Premium</div>
  <div class="trial-badge">7-Day Free Trial Active</div>
  <div class="sub">Your hair journey just leveled up. You now have unlimited access to Aria, your full hair health dashboard, and priority advisor support.</div>
  <a href="/" class="btn">Talk to Aria Now</a>
  <a href="/dashboard" class="btn btn-outline">View My Dashboard</a>
</div>
<script>
// Update token subscription status in localStorage
var u = localStorage.getItem('srd_user');
if(u){ try{ var p=JSON.parse(u); p.plan='premium'; localStorage.setItem('srd_user',JSON.stringify(p)); }catch(e){} }
</script>
</body></html>"""

@app.route("/subscription/cancel")
def subscription_cancel():
    return """<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SupportRD — No worries</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;1,300&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#f0ebe8;min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:'Jost',sans-serif;padding:24px;}
.card{background:#fff;border-radius:24px;padding:56px 40px;max-width:460px;width:100%;text-align:center;box-shadow:0 12px 48px rgba(0,0,0,0.08);}
.title{font-family:'Cormorant Garamond',serif;font-size:32px;font-style:italic;color:#0d0906;margin-bottom:12px;}
.sub{font-size:13px;color:rgba(0,0,0,0.40);letter-spacing:0.06em;line-height:1.7;margin-bottom:28px;}
.btn{display:block;padding:14px;background:#c1a3a2;color:#fff;text-decoration:none;border-radius:30px;font-family:'Jost',sans-serif;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;margin-bottom:10px;}
.btn-outline{background:transparent;color:#9d7f6a;border:1px solid rgba(193,163,162,0.40);}
</style></head><body>
<div class="card">
  <div class="title">No worries</div>
  <div class="sub">You can still get free hair recommendations from Aria anytime. Upgrade whenever you're ready for the full experience.</div>
  <a href="/" class="btn">Continue with Free</a>
  <a href="/login" class="btn btn-outline">Sign In to Subscribe Later</a>
</div>
</body></html>"""
