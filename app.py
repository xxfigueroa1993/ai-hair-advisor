import os
from flask import Flask, request, jsonify
import json

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = """You are a luxury hair care expert advisor for a professional salon brand. 
You recommend exactly ONE of these four products based on the customer's hair concerns:

PRODUCTS:
- Formula Exclusiva ($65): All-in-one natural professional salon treatment. Best for: damaged, weak, breaking, thinning, falling out, severely dry, multi-problem hair. The premium all-rounder.
- Laciador ($48): All-natural hair styler. Best for: dry hair needing smoothness, tangly/knotty hair, frizz, lack of bounce, manageability issues.
- Gotero ($42): All-natural hair gel. Best for: oily/greasy hair, scalp oil balance, hair that loses shape, flat hair needing definition without frizz.
- Gotika ($54): All-natural hair color treatment. Best for: faded color, brassy tones, dull color, color loss, wanting to enhance natural color.

RULES:
- Always recommend exactly one product
- Be warm, confident, and professional — like a luxury salon consultant
- Keep response to 2-3 sentences maximum
- State the product name, its price, and WHY it's perfect for their specific concern
- If the concern is color-related in someone under 16, recommend seeing a professional first
- If multiple concerns, pick the one product that addresses the PRIMARY issue
- Never say "I recommend" — say something more natural like "For your [concern], [Product] is exactly what you need." or "Based on what you've described, [Product] at $X will [benefit]."
- Sound like a knowledgeable friend, not a chatbot

BACKGROUND RULES (when mentioned):
- African/Black hair + dry → Laciador
- African/Black hair + oily → Gotero  
- African/Black hair + damaged → Formula Exclusiva
- Asian hair + dry → Formula Exclusiva
- Asian hair + oily → Gotero
- Hispanic/Latino hair + color → Gotika
- Hispanic/Latino hair + dry → Laciador
- Caucasian/White hair + damaged → Formula Exclusiva
- Caucasian/White hair + oily → Gotero
- Any hair + severe damage/breakage/falling out → Formula Exclusiva (overrides everything)

Respond ONLY with your product recommendation. No preamble. No "Sure!" or "Of course!"."""


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
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: radial-gradient(ellipse at 50% 60%, #050d0a 0%, #030608 100%);
  color: #dff2ec;
  font-family: 'Jost', sans-serif;
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
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.50);
  border: 1px solid rgba(255,255,255,0.10);
  padding: 8px 18px;
  border-radius: 30px;
  font-size: 11px;
  font-family: 'Jost', sans-serif;
  font-weight: 300;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.4s ease;
  outline: none;
}
.top-btn:hover {
  background: rgba(0,255,200,0.08);
  color: rgba(0,255,200,0.80);
  border-color: rgba(0,255,200,0.22);
}

#langSelect {
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.50);
  border: 1px solid rgba(255,255,255,0.10);
  padding: 8px 14px;
  border-radius: 30px;
  font-size: 11px;
  font-family: 'Jost', sans-serif;
  letter-spacing: 0.08em;
  cursor: pointer;
  outline: none;
  transition: all 0.4s ease;
}
#langSelect option { background: #060e0b; color: white; }

.sphere-wrap {
  width: 300px;
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

#halo {
  width: 220px;
  height: 220px;
  border-radius: 50%;
  cursor: pointer;
  will-change: transform;
  background: radial-gradient(circle at 40% 38%,
    rgba(0,255,200,0.50) 0%,
    rgba(0,255,200,0.18) 42%,
    rgba(0,255,200,0.07) 70%,
    rgba(0,255,200,0.01) 100%);
  box-shadow:
    inset 0 0 40px rgba(0,255,200,0.10),
    0 0  70px rgba(0,255,200,0.45),
    0 0 150px rgba(0,255,200,0.28),
    0 0 280px rgba(0,255,200,0.15),
    0 0 420px rgba(0,255,200,0.07);
  transition:
    background 2.4s cubic-bezier(0.4,0,0.2,1),
    box-shadow  2.4s cubic-bezier(0.4,0,0.2,1);
}

#stateLabel {
  margin-top: 12px;
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.20);
  height: 16px;
  transition: color 1s ease;
}

#response {
  margin-top: 26px;
  width: 400px;
  max-width: 90vw;
  text-align: center;
  font-family: 'Cormorant Garamond', serif;
  font-size: 19px;
  font-weight: 300;
  line-height: 1.7;
  color: rgba(255,255,255,0.78);
  min-height: 72px;
  font-style: italic;
  transition: opacity 0.7s ease;
}

#manualBox {
  display: none;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-top: 20px;
  width: 380px;
  max-width: 90vw;
}
#manualInput {
  width: 100%;
  padding: 13px 20px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 30px;
  color: white;
  font-family: 'Jost', sans-serif;
  font-size: 14px;
  outline: none;
  transition: border-color 0.3s;
}
#manualInput:focus { border-color: rgba(0,255,200,0.35); }
#manualInput::placeholder { color: rgba(255,255,255,0.22); }

#manualSubmit {
  padding: 10px 32px;
  background: rgba(0,255,200,0.08);
  border: 1px solid rgba(0,255,200,0.28);
  border-radius: 30px;
  color: rgba(0,255,200,0.80);
  font-family: 'Jost', sans-serif;
  font-size: 11px;
  font-weight: 300;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.3s;
}
#manualSubmit:hover { background: rgba(0,255,200,0.15); }

#footer {
  position: fixed;
  bottom: 22px;
  display: flex;
  gap: 36px;
}
#footer span {
  font-size: 10px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.20);
  cursor: pointer;
  transition: color 0.4s;
}
#footer span:hover { color: rgba(0,255,200,0.65); }
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

<div class="sphere-wrap">
  <div id="halo"></div>
</div>
<div id="stateLabel">Tap to begin</div>

<div id="manualBox">
  <input id="manualInput" placeholder="Describe your hair concern…" />
  <button id="manualSubmit">Analyze</button>
</div>

<div id="response">Tap the sphere and describe your hair concern.</div>

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

let appState     = "idle";
let recognition  = null;
let silenceTimer = null;
let finalText    = "";
let isManual     = false;

let audioCtx = null;
let analyser = null;
let micData  = null;

function getCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

/* ── DEEP AMBIENT SOUNDS ── */
function playAmbient(type) {
  try {
    const ctx    = getCtx();
    const master = ctx.createGain();
    master.connect(ctx.destination);
    const now = ctx.currentTime;

    if (type === "intro") {
      // Soft rising pad chord — wide, spread, slow
      [[220, 0], [330, 0.20], [440, 0.40], [660, 0.65]].forEach(([freq, delay]) => {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.connect(g); g.connect(master);
        o.type = "sine";
        o.frequency.setValueAtTime(freq, now + delay);
        g.gain.setValueAtTime(0, now + delay);
        g.gain.linearRampToValueAtTime(0.06, now + delay + 0.5);
        g.gain.exponentialRampToValueAtTime(0.001, now + delay + 3.5);
        o.start(now + delay);
        o.stop(now + delay + 4.0);
      });
      // Shimmer high tone
      const s = ctx.createOscillator();
      const sg = ctx.createGain();
      s.connect(sg); sg.connect(master);
      s.type = "sine";
      s.frequency.setValueAtTime(1320, now + 0.8);
      s.frequency.exponentialRampToValueAtTime(880, now + 2.5);
      sg.gain.setValueAtTime(0, now + 0.8);
      sg.gain.linearRampToValueAtTime(0.022, now + 1.1);
      sg.gain.exponentialRampToValueAtTime(0.001, now + 3.8);
      s.start(now + 0.8); s.stop(now + 4.0);
      master.gain.setValueAtTime(1, now);

    } else if (type === "outro") {
      // Descending resolution — calming, wide
      [[660, 0], [440, 0.25], [330, 0.50], [220, 0.75]].forEach(([freq, delay]) => {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.connect(g); g.connect(master);
        o.type = "sine";
        o.frequency.setValueAtTime(freq, now + delay);
        o.frequency.exponentialRampToValueAtTime(freq * 0.90, now + delay + 2.5);
        g.gain.setValueAtTime(0, now + delay);
        g.gain.linearRampToValueAtTime(0.050, now + delay + 0.35);
        g.gain.exponentialRampToValueAtTime(0.001, now + delay + 3.2);
        o.start(now + delay);
        o.stop(now + delay + 3.5);
      });
      master.gain.setValueAtTime(1, now);
    }
  } catch(e) { console.warn("Audio error:", e); }
}

/* ── MICROPHONE ── */
async function initMic() {
  if (analyser) return;
  try {
    const ctx = getCtx();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const src = ctx.createMediaStreamSource(stream);
    analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
    micData = new Uint8Array(analyser.frequencyBinCount);
  } catch(e) { console.warn("Mic unavailable:", e); }
}

/* ── COLOR ── */
function setColor(r, g, b) {
  halo.style.background = `radial-gradient(circle at 40% 38%,
    rgba(${r},${g},${b},0.52) 0%,
    rgba(${r},${g},${b},0.18) 42%,
    rgba(${r},${g},${b},0.07) 70%,
    rgba(${r},${g},${b},0.01) 100%)`;
  halo.style.boxShadow = `
    inset 0 0 40px rgba(${r},${g},${b},0.12),
    0 0  70px rgba(${r},${g},${b},0.50),
    0 0 155px rgba(${r},${g},${b},0.30),
    0 0 290px rgba(${r},${g},${b},0.16),
    0 0 440px rgba(${r},${g},${b},0.08)`;
}

const IDLE   = [0, 255, 200];
const LISTEN = [255, 200, 60];
const SPEAK  = [0, 220, 255];
setColor(...IDLE);

/* ── ANIMATION LOOP ── */
let breathPhase = 0, speakPhase = 0, smoothScale = 1, targetScale = 1;
(function loop() {
  if (appState === "idle") {
    breathPhase += 0.00065;
    targetScale = 1 + 0.052 * Math.sin(breathPhase);
  } else if (appState === "listening") {
    if (analyser && micData) {
      analyser.getByteFrequencyData(micData);
      let vol = 0;
      for (let i = 0; i < micData.length; i++) vol += micData[i];
      vol /= (micData.length * 255);
      targetScale = 1 + vol * 0.55;
    } else {
      breathPhase += 0.003;
      targetScale = 1 + 0.04 * Math.sin(breathPhase);
    }
  } else if (appState === "speaking") {
    speakPhase += 0.038;
    targetScale = 1 + 0.075 + 0.065 * Math.abs(Math.sin(speakPhase));
  }
  smoothScale += (targetScale - smoothScale) * 0.10;
  halo.style.transform = `scale(${smoothScale.toFixed(4)})`;
  requestAnimationFrame(loop);
})();

/* ── VOICE SELECTION ── */
function getBestVoice(lang) {
  const voices = speechSynthesis.getVoices();
  if (!voices.length) return null;
  const preferred = [
    "Google US English", "Google UK English Female", "Google UK English Male",
    "Microsoft Aria Online (Natural) - English (United States)",
    "Microsoft Jenny Online (Natural) - English (United States)",
    "Microsoft Guy Online (Natural) - English (United States)",
    "Samantha", "Karen", "Moira", "Fiona"
  ];
  for (const name of preferred) {
    const v = voices.find(v => v.name === name);
    if (v) return v;
  }
  const byLang = voices.filter(v => v.lang === lang);
  return (
    byLang.find(v => /Google/.test(v.name)) ||
    byLang.find(v => /Natural|Online/.test(v.name)) ||
    byLang.find(v => /Microsoft/.test(v.name)) ||
    byLang.find(v => !v.localService) ||
    byLang[0] ||
    voices.find(v => v.lang.startsWith(lang.split('-')[0])) ||
    voices[0]
  );
}

/* ── SPEAK ── */
function speak(text) {
  speechSynthesis.cancel();
  setTimeout(() => {
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang  = langSelect.value;
    utter.voice = getBestVoice(langSelect.value);
    utter.rate  = 0.88;
    utter.pitch = 1.05;
    appState = "speaking";
    setColor(...SPEAK);
    stateLabel.textContent = "Speaking";
    speechSynthesis.speak(utter);
    utter.onend = () => {
      playAmbient("outro");
      appState = "idle";
      setColor(...IDLE);
      stateLabel.textContent = "Tap to begin";
    };
  }, 80);
}

/* ── AI RECOMMENDATION ── */
async function getRecommendation(text) {
  try {
    const resp = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, lang: langSelect.value })
    });
    if (!resp.ok) throw new Error("API unavailable");
    const data = await resp.json();
    if (data.recommendation) return data.recommendation;
    throw new Error("No recommendation");
  } catch(e) {
    return localRecommend(text);
  }
}

function localRecommend(text) {
  const t = text.toLowerCase();
  const color   = /color|fade|brassy|pigment|dull|tint|vibrancy/.test(t);
  const oily    = /oil|greasy|grease|sebum|buildup/.test(t);
  const dry     = /dry|frizz|rough|brittle|moisture|parched/.test(t);
  const damaged = /damag|break|weak|burn|overprocess|chemical|perm/.test(t);
  const tangly  = /tangl|knot|matted|detangle/.test(t);
  const flat    = /flat|no bounce|volume|lifeless|thin|fine/.test(t);
  const falling = /fall|shed|loss|bald|alopecia|thinning/.test(t);
  const african   = /african|black hair/.test(t);
  const asian     = /asian|chinese|japanese|korean/.test(t);
  const hispanic  = /hispanic|latin/.test(t);
  const n = [color,oily,dry,damaged,tangly,flat,falling].filter(Boolean).length;

  if (damaged || falling || n >= 3)
    return "Formula Exclusiva is exactly what your hair needs. This professional all-in-one treatment rebuilds strength, restores moisture, and revives scalp health from the inside out. At $65, it's your most complete solution.";
  if (color) {
    if (african) return "Gotero is your best match here — it restores natural sheen and tone while balancing your scalp. At $42, it works beautifully with your hair's natural texture.";
    return "Gotika is the answer for your color. It restores vibrancy, corrects tone, and protects your pigment long-term — all naturally. Price: $54.";
  }
  if (oily) {
    if (hispanic) return "Formula Exclusiva will bring your scalp into balance while giving your hair deep nourishment it needs. At $65, it handles oil and care in one.";
    return "Gotero is exactly right for oily hair — it regulates sebum production and keeps your scalp clear without stripping your natural hydration. Price: $42.";
  }
  if (dry) {
    if (asian) return "Formula Exclusiva is the ideal choice for your hair type — it penetrates deeply to restore elasticity and long-term hydration. Price: $65.";
    return "Laciador will transform dry hair — restoring softness, smoothness, and that healthy natural bounce. Price: $48.";
  }
  if (tangly) {
    if (hispanic || african) return "Laciador is perfect for your hair — it smooths, detangles, and leaves your hair manageable with beautiful movement. Price: $48.";
    return "Formula Exclusiva addresses the root cause of tangles while strengthening every strand. Price: $65.";
  }
  if (flat)
    return "Laciador will give your hair the body and movement it's been missing — lightweight and natural. Price: $48.";
  return "Formula Exclusiva is your best all-around choice. It covers moisture, strength, and scalp health in one professional treatment. Price: $65.";
}

/* ── PROCESS ── */
async function processText(text) {
  if (!text || text.trim().length < 3) {
    const msg = "Could you describe your hair a little more? Dryness, oiliness, damage, color, volume, or shedding all help me give you the right answer.";
    responseBox.textContent = msg;
    setTimeout(() => speak(msg), 2500);
    return;
  }
  responseBox.textContent = "Analyzing your concern…";
  stateLabel.textContent  = "Thinking";
  const result = await getRecommendation(text);
  responseBox.textContent = result;
  setTimeout(() => speak(result), 2500);
}

/* ── LISTEN ── */
function startListening() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    responseBox.textContent = "Please use Chrome for voice input, or switch to Manual Mode.";
    return;
  }
  playAmbient("intro");
  initMic();
  finalText = "";
  appState  = "listening";
  setColor(...LISTEN);
  stateLabel.textContent  = "Listening…";
  responseBox.textContent = "Listening…";

  recognition = new SR();
  recognition.lang           = langSelect.value;
  recognition.continuous     = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    clearTimeout(silenceTimer);
    let interim = "";
    finalText = "";
    for (let i = 0; i < event.results.length; i++) {
      if (event.results[i].isFinal) finalText += event.results[i][0].transcript + " ";
      else interim += event.results[i][0].transcript;
    }
    responseBox.textContent = (finalText + interim).trim() || "Listening…";
    // 3-second silence timer — resets on every speech event
    silenceTimer = setTimeout(() => {
      try { recognition.stop(); } catch(e) {}
    }, 3000);
  };

  recognition.onend = () => {
    clearTimeout(silenceTimer);
    if (appState === "listening") {
      const captured = finalText.trim();
      if (captured.length > 2) {
        processText(captured);
      } else {
        const msg = "I didn't quite catch that. Please tap and describe your hair concern.";
        responseBox.textContent = msg;
        appState = "idle";
        setColor(...IDLE);
        stateLabel.textContent = "Tap to begin";
      }
    }
  };

  recognition.onerror = (e) => {
    clearTimeout(silenceTimer);
    if (e.error === "no-speech") {
      appState = "idle";
      setColor(...IDLE);
      stateLabel.textContent  = "Tap to begin";
      responseBox.textContent = "Tap the sphere and describe your hair concern.";
    }
  };

  recognition.start();
}

/* ── CLICK ── */
halo.addEventListener("click", () => {
  if (isManual) return;
  if (appState === "listening") {
    clearTimeout(silenceTimer);
    try { recognition.stop(); } catch(e) {}
    appState = "idle";
    setColor(...IDLE);
    stateLabel.textContent  = "Tap to begin";
    responseBox.textContent = "Tap the sphere and describe your hair concern.";
    return;
  }
  if (appState === "speaking") {
    speechSynthesis.cancel();
    appState = "idle";
    setColor(...IDLE);
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
  processText(text);
});
manualInput.addEventListener("keydown", e => { if (e.key === "Enter") manualSubmit.click(); });

/* ── LANGUAGE ── */
speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
setTimeout(() => speechSynthesis.getVoices(), 300);
langSelect.addEventListener("change", () => speechSynthesis.getVoices());

/* ── FAQ / CONTACT ── */
document.getElementById("faqBtn").addEventListener("click", () => {
  const msg = "All four of our products are 100% natural, organic, and salon-professional grade — formulated with Caribbean heritage. Formula Exclusiva at $65 is our all-in-one treatment. Laciador at $48 is our hair styler. Gotero at $42 is our hair gel. And Gotika at $54 is our color treatment.";
  responseBox.textContent = msg;
  speak(msg);
});
document.getElementById("contactBtn").addEventListener("click", () => {
  const msg = "To speak with one of our professional hair consultants, please email us at support at hairexpert dot com. We'd love to find your perfect product together.";
  responseBox.textContent = msg;
  speak(msg);
});
</script>
</body>
</html>"""


@app.route("/api/recommend", methods=["POST"])
def recommend():
    data      = request.get_json()
    user_text = data.get("text", "")

    if not ANTHROPIC_API_KEY:
        return jsonify({"recommendation": None, "error": "No API key configured"}), 500

    try:
        import urllib.request as urlreq
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 200,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_text}]
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
            return jsonify({"recommendation": result["content"][0]["text"].strip()})

    except Exception as e:
        return jsonify({"recommendation": None, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
