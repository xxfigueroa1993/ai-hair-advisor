import os, json, sqlite3, datetime
from flask import Flask, request, jsonify

app = Flask(__name__)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── ANALYTICS DB ─────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "analytics.db")

def init_db():
    con = sqlite3.connect(DB_PATH)
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
        con = sqlite3.connect(DB_PATH)
        con.execute("INSERT INTO events (ts,lang,user_msg,product,concern) VALUES (?,?,?,?,?)",
                    (datetime.datetime.utcnow().isoformat(), lang, user_msg, product, concern))
        con.commit(); con.close()
    except Exception as e:
        print("DB log error:", e)

def log_tip(lang, rating, tip_amount, product):
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("INSERT INTO tips (ts,lang,rating,tip_amount,product) VALUES (?,?,?,?,?)",
                    (datetime.datetime.utcnow().isoformat(), lang, rating, tip_amount, product))
        con.commit(); con.close()
    except Exception as e:
        print("DB tip log error:", e)

def extract_product(text):
    t = text.lower()
    if "formula exclusiva" in t: return "Formula Exclusiva"
    if "laciador"         in t: return "Laciador"
    if "gotero"           in t: return "Gotero"
    if "gotika"           in t: return "Gotika"
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
SYSTEM_PROMPT = """You are a luxury hair care expert advisor for a professional salon brand.
You have memory of this conversation and can answer follow-up questions naturally.

PRODUCTS:
- Formula Exclusiva ($65): All-in-one natural professional salon treatment. Best for: damaged, weak, breaking, thinning, falling out, severely dry, multi-problem hair.
- Laciador ($48): All-natural hair styler. Best for: dry hair needing smoothness, tangly/knotty hair, frizz, lack of bounce, manageability issues.
- Gotero ($42): All-natural hair gel. Best for: oily/greasy hair, scalp oil balance, hair that loses shape, flat hair needing definition without frizz.
- Gotika ($54): All-natural hair color treatment. Best for: faded color, brassy tones, dull color, color loss, wanting to enhance natural color.

RULES:
- On first message: recommend exactly one product, state its name, price, and why it's perfect.
- On follow-up questions: answer naturally and conversationally using the conversation history.
- Be warm, confident, and professional — like a luxury salon consultant who remembers what was just said.
- Keep responses to 2-3 sentences maximum.
- Never say "I recommend" — use natural phrasing like "For your concern, [Product] is exactly what you need."
- Sound like a knowledgeable friend, not a chatbot.

BACKGROUND RULES (when mentioned):
- African/Black hair + dry → Laciador | oily → Gotero | damaged → Formula Exclusiva
- Asian hair + dry → Formula Exclusiva | oily → Gotero
- Hispanic/Latino hair + color → Gotika | dry → Laciador
- Caucasian/White hair + damaged → Formula Exclusiva | oily → Gotero
- Any hair + severe damage/breakage/falling out → Formula Exclusiva (overrides everything)

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
  padding: 18px 28px;
  z-index: 100;
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
</style>
</head>
<body>

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
    <option value="hi-IN">हिन्दी</option>
  </select>
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
    else if (t.includes("laciador"))     lastRecommendedProduct = "Laciador";
    else if (t.includes("gotero"))       lastRecommendedProduct = "Gotero";
    else if (t.includes("gotika"))       lastRecommendedProduct = "Gotika";
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
    damaged: "Formula Exclusiva is exactly what your hair needs. This professional all-in-one treatment rebuilds strength, restores moisture, and revives scalp health. At $65, it's your most complete solution.",
    color:   "Gotika is the answer for your color. It restores vibrancy, corrects tone, and protects your pigment long-term — all naturally. Price: $54.",
    colorAf: "Gotero restores natural sheen and tone while balancing your scalp. At $42, it works beautifully with your hair's natural texture.",
    oily:    "Gotero regulates sebum production and keeps your scalp clear. Price: $42.",
    oilyHi: "Formula Exclusiva balances your scalp's oil while deeply nourishing your hair. At $65, it handles both in one.",
    dry:     "Laciador transforms dry hair — restoring softness, smoothness, and natural bounce. Price: $48.",
    dryAs:  "Formula Exclusiva penetrates deeply to restore elasticity and hydration. Price: $65.",
    tangly:  "Formula Exclusiva addresses the root cause of tangles while strengthening every strand. Price: $65.",
    tanglyH:"Laciador smooths, detangles, and leaves your hair manageable with beautiful movement. Price: $48.",
    flat:    "Laciador gives your hair the body and movement it's been missing. Price: $48.",
    default: "Formula Exclusiva is your best all-around choice — moisture, strength, and scalp health in one. Price: $65."
  },
  "es-ES": {
    damaged:"Formula Exclusiva es exactamente lo que tu cabello necesita. A $65.",
    color:  "Gotika restaura la vitalidad y protege tu pigmento. Precio: $54.",
    colorAf:"Gotero restaura el brillo natural. A $42.",
    oily:   "Gotero regula la producción de sebo. Precio: $42.",
    oilyHi:"Formula Exclusiva equilibra el aceite. A $65.",
    dry:    "Laciador restaura suavidad y rebote. Precio: $48.",
    dryAs: "Formula Exclusiva restaura elasticidad. Precio: $65.",
    tangly: "Formula Exclusiva resuelve los enredos. Precio: $65.",
    tanglyH:"Laciador suaviza y desenreda. Precio: $48.",
    flat:   "Laciador da volumen. Precio: $48.",
    default:"Formula Exclusiva es tu mejor opción. Precio: $65."
  },
  "fr-FR": {
    damaged:"Formula Exclusiva est exactement ce dont vos cheveux ont besoin. À 65$.",
    color:  "Gotika restaure l'éclat et protège votre pigment. Prix: 54$.",
    colorAf:"Gotero restaure l'éclat naturel. À 42$.",
    oily:   "Gotero régule la production de sébum. Prix: 42$.",
    oilyHi:"Formula Exclusiva équilibre l'huile. À 65$.",
    dry:    "Laciador transforme les cheveux secs. Prix: 48$.",
    dryAs: "Formula Exclusiva est idéale pour votre type. Prix: 65$.",
    tangly: "Formula Exclusiva s'attaque aux nœuds. Prix: 65$.",
    tanglyH:"Laciador lisse et démêle. Prix: 48$.",
    flat:   "Laciador donne du volume. Prix: 48$.",
    default:"Formula Exclusiva est votre meilleur choix. Prix: 65$."
  },
  "pt-BR": {
    damaged:"Formula Exclusiva é o que seu cabelo precisa. Por $65.",
    color:  "Gotika restaura a vibração e protege seu pigmento. Preço: $54.",
    colorAf:"Gotero restaura o brilho natural. Por $42.",
    oily:   "Gotero regula a produção de sebo. Preço: $42.",
    oilyHi:"Formula Exclusiva equilibra o óleo. Por $65.",
    dry:    "Laciador transforma o cabelo seco. Preço: $48.",
    dryAs: "Formula Exclusiva é ideal para seu tipo. Preço: $65.",
    tangly: "Formula Exclusiva resolve os nós. Preço: $65.",
    tanglyH:"Laciador alisa e desembaraça. Preço: $48.",
    flat:   "Laciador dá volume. Preço: $48.",
    default:"Formula Exclusiva é sua melhor escolha. Preço: $65."
  },
  "de-DE": {
    damaged:"Formula Exclusiva ist genau das, was Ihr Haar braucht. Für $65.",
    color:  "Gotika stellt Lebendigkeit wieder her. Preis: $54.",
    colorAf:"Gotero stellt natürlichen Glanz wieder her. Für $42.",
    oily:   "Gotero reguliert Talgproduktion. Preis: $42.",
    oilyHi:"Formula Exclusiva bringt das Öl ins Gleichgewicht. Für $65.",
    dry:    "Laciador transformiert trockenes Haar. Preis: $48.",
    dryAs: "Formula Exclusiva ist ideal für Ihren Haartyp. Preis: $65.",
    tangly: "Formula Exclusiva bekämpft Verfilzungen. Preis: $65.",
    tanglyH:"Laciador glättet und entwirrt. Preis: $48.",
    flat:   "Laciador gibt Volumen. Preis: $48.",
    default:"Formula Exclusiva ist Ihre beste Lösung. Preis: $65."
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
    damaged:"Formula Exclusiva 正是您需要的。售价 $65。",
    color:  "Gotika 恢复色彩活力，保护色素。售价 $54。",
    colorAf:"Gotero 恢复自然光泽。售价 $42。",
    oily:   "Gotero 调节皮脂分泌。售价 $42。",
    oilyHi:"Formula Exclusiva 平衡油脂。售价 $65。",
    dry:    "Laciador 改善干燥发质。售价 $48。",
    dryAs: "Formula Exclusiva 最适合您的发质。售价 $65。",
    tangly: "Formula Exclusiva 解决打结。售价 $65。",
    tanglyH:"Laciador 顺滑解结。售价 $48。",
    flat:   "Laciador 增加蓬松感。售价 $48。",
    default:"Formula Exclusiva 是您最全面的选择。售价 $65。"
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
    const resp = await fetch("https://ai-hair-advisor.onrender.com/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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
</script>
</body>
</html>"""


# ── API: RECOMMEND ────────────────────────────────────────────────────────────
@app.route("/api/recommend", methods=["POST"])
def recommend():
    data      = request.get_json()
    user_text = data.get("text", "")
    lang      = data.get("lang", "en-US")
    history   = data.get("history", [])

    lang_names = {
        "en-US":"English","es-ES":"Spanish","fr-FR":"French",
        "pt-BR":"Portuguese","de-DE":"German","ar-SA":"Arabic",
        "zh-CN":"Mandarin Chinese","hi-IN":"Hindi"
    }
    lang_name  = lang_names.get(lang, "English")
    lang_instr = f"\n\nIMPORTANT: Your ENTIRE response must be in {lang_name}."

    if not ANTHROPIC_API_KEY:
        return jsonify({"recommendation": None, "error": "No API key"}), 500

    try:
        import urllib.request as urlreq

        messages = []
        for h in history:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user_text})

        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 250,
            "system": SYSTEM_PROMPT + lang_instr,
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
            result = json.loads(resp.read().decode("utf-8"))
            recommendation = result["content"][0]["text"].strip()

        product = extract_product(recommendation)
        concern = extract_concern(user_text)
        log_event(lang, user_text, product, concern)

        return jsonify({"recommendation": recommendation})

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
        con = sqlite3.connect(DB_PATH)
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

@app.after_request
def add_headers(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["X-Frame-Options"]              = "ALLOWALL"
    response.headers["Content-Security-Policy"]      = "frame-ancestors *"
    response.headers["Permissions-Policy"]           = "microphone=*, camera=()"
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
