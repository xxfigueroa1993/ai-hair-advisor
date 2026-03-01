import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hair Expert Advisor</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&family=Montserrat:wght@300;400&display=swap" rel="stylesheet">

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --teal:  0, 255, 200;
  --gold:  255, 200, 60;
  --blue:  0, 220, 255;
  --transition: 1.8s cubic-bezier(0.4, 0, 0.2, 1);
}

body {
  background: #040709;
  color: #e8f4f0;
  font-family: 'Montserrat', sans-serif;
  font-weight: 300;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  overflow: hidden;
  user-select: none;
}

/* ── TOP BAR ── */
#topBar {
  position: fixed;
  top: 0; left: 0; right: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  z-index: 100;
}

#modeToggle {
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.75);
  border: 1px solid rgba(255,255,255,0.15);
  padding: 7px 16px;
  border-radius: 20px;
  font-size: 12px;
  font-family: 'Montserrat', sans-serif;
  letter-spacing: 0.08em;
  cursor: pointer;
  transition: background 0.3s, color 0.3s;
}
#modeToggle:hover { background: rgba(255,255,255,0.12); color: white; }

#langSelect {
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.75);
  border: 1px solid rgba(255,255,255,0.15);
  padding: 7px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-family: 'Montserrat', sans-serif;
  letter-spacing: 0.05em;
  cursor: pointer;
  outline: none;
}
#langSelect option { background: #0d1117; color: white; }

/* ── SPHERE ── */
.sphere-wrap {
  position: relative;
  width: 320px;
  height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

#halo {
  width: 240px;
  height: 240px;
  border-radius: 50%;
  cursor: pointer;
  position: relative;
  /* Color and glow transition — slow fade */
  transition:
    background var(--transition),
    box-shadow var(--transition);
  will-change: transform, box-shadow, background;

  /* Default idle teal */
  background: radial-gradient(circle at 38% 35%,
    rgba(var(--teal), 0.55) 0%,
    rgba(var(--teal), 0.22) 45%,
    rgba(var(--teal), 0.08) 75%,
    rgba(var(--teal), 0.02) 100%);
  box-shadow:
    0 0  80px rgba(var(--teal), 0.5),
    0 0 160px rgba(var(--teal), 0.3),
    0 0 280px rgba(var(--teal), 0.2),
    0 0 400px rgba(var(--teal), 0.1);
}

/* ── MANUAL FORM ── */
#manualBox {
  display: none;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-top: 28px;
  width: 360px;
}
#manualInput {
  width: 100%;
  padding: 12px 18px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 24px;
  color: white;
  font-family: 'Montserrat', sans-serif;
  font-size: 14px;
  outline: none;
}
#manualInput::placeholder { color: rgba(255,255,255,0.35); }
#manualSubmit {
  padding: 10px 28px;
  background: rgba(0,255,200,0.15);
  border: 1px solid rgba(0,255,200,0.4);
  border-radius: 20px;
  color: rgba(0,255,200,0.9);
  font-family: 'Montserrat', sans-serif;
  font-size: 13px;
  letter-spacing: 0.08em;
  cursor: pointer;
  transition: background 0.3s;
}
#manualSubmit:hover { background: rgba(0,255,200,0.25); }

/* ── RESPONSE ── */
#response {
  margin-top: 32px;
  width: 380px;
  text-align: center;
  font-family: 'Cormorant Garamond', serif;
  font-size: 18px;
  font-weight: 400;
  line-height: 1.6;
  color: rgba(255,255,255,0.85);
  min-height: 64px;
  letter-spacing: 0.02em;
  transition: opacity 0.6s ease;
}

#statusDot {
  position: fixed;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.3);
}

/* ── FOOTER ── */
#footer {
  position: fixed;
  bottom: 16px;
  display: flex;
  gap: 30px;
}
#footer span {
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.3);
  cursor: pointer;
  transition: color 0.3s;
}
#footer span:hover { color: rgba(0,255,200,0.8); }
</style>
</head>
<body>

<div id="topBar">
  <button id="modeToggle">Manual Mode</button>
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

<div id="manualBox">
  <input id="manualInput" placeholder="Describe your hair concern…" />
  <button id="manualSubmit">Analyze</button>
</div>

<div id="response">Tap the sphere and describe your hair concern.</div>

<div id="statusDot">Idle</div>

<div id="footer">
  <span id="faqBtn">FAQ</span>
  <span id="contactBtn">Contact Us</span>
</div>

<script>
/* ═══════════════════════════════════════════════════
   ELEMENTS
═══════════════════════════════════════════════════ */
const halo        = document.getElementById("halo");
const responseBox = document.getElementById("response");
const langSelect  = document.getElementById("langSelect");
const statusDot   = document.getElementById("statusDot");
const modeToggle  = document.getElementById("modeToggle");
const manualBox   = document.getElementById("manualBox");
const manualInput = document.getElementById("manualInput");
const manualSubmit= document.getElementById("manualSubmit");

/* ═══════════════════════════════════════════════════
   STATE
═══════════════════════════════════════════════════ */
let state         = "idle";     // idle | listening | speaking
let recognition   = null;
let silenceTimer  = null;
let finalText     = "";
let isManual      = false;

// Web Audio
let audioCtx      = null;
let analyser      = null;
let micData       = null;

/* ═══════════════════════════════════════════════════
   COLOR SYSTEM  (slow CSS transitions do the fading)
═══════════════════════════════════════════════════ */
function setColor(r, g, b) {
  halo.style.background = `radial-gradient(circle at 38% 35%,
    rgba(${r},${g},${b},0.55) 0%,
    rgba(${r},${g},${b},0.22) 45%,
    rgba(${r},${g},${b},0.08) 75%,
    rgba(${r},${g},${b},0.02) 100%)`;

  halo.style.boxShadow = `
    0 0  80px rgba(${r},${g},${b},0.55),
    0 0 160px rgba(${r},${g},${b},0.35),
    0 0 300px rgba(${r},${g},${b},0.20),
    0 0 440px rgba(${r},${g},${b},0.10)`;
}

// Presets
const C_IDLE   = [0, 255, 200];
const C_LISTEN = [255, 200, 60];
const C_SPEAK  = [0, 220, 255];

setColor(...C_IDLE);

/* ═══════════════════════════════════════════════════
   BREATHING / REACTIVE PULSE LOOP
   - idle:     slow sinusoidal scale 1 → 1.05 → 1  (~5s cycle)
   - listening: driven by live mic volume
   - speaking:  driven by Web Audio oscillation
═══════════════════════════════════════════════════ */
let breathPhase    = 0;
let currentScale   = 1;
let targetScale    = 1;
let speakOscPhase  = 0;

function animationLoop() {
  if (state === "idle") {
    breathPhase += 0.0008; // ~5s full cycle
    targetScale = 1 + 0.05 * Math.sin(breathPhase);

  } else if (state === "listening") {
    if (analyser && micData) {
      analyser.getByteFrequencyData(micData);
      let vol = 0;
      for (let i = 0; i < micData.length; i++) vol += micData[i];
      vol /= (micData.length * 255);
      targetScale = 1 + vol * 0.5; // reactive — up to 1.5x
    } else {
      breathPhase += 0.003;
      targetScale = 1 + 0.04 * Math.sin(breathPhase);
    }

  } else if (state === "speaking") {
    speakOscPhase += 0.04;
    targetScale = 1 + 0.08 + 0.07 * Math.abs(Math.sin(speakOscPhase));
  }

  // Smooth lerp to target
  currentScale += (targetScale - currentScale) * 0.12;
  halo.style.transform = `scale(${currentScale})`;

  requestAnimationFrame(animationLoop);
}
animationLoop();

/* ═══════════════════════════════════════════════════
   MICROPHONE SETUP (Web Audio API)
═══════════════════════════════════════════════════ */
async function initMic() {
  if (audioCtx) return; // already initialised
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const src = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
    micData = new Uint8Array(analyser.frequencyBinCount);
  } catch(e) {
    console.warn("Mic not available:", e);
  }
}

/* ═══════════════════════════════════════════════════
   WEB AUDIO TONES  (replaces missing mp3 files)
═══════════════════════════════════════════════════ */
function playTone(freq, duration, type = "sine", vol = 0.18) {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(vol, ctx.currentTime + 0.04);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + duration + 0.05);
  } catch(e) {}
}

function playIntro() {
  playTone(520, 0.18, "sine", 0.15);
  setTimeout(() => playTone(740, 0.25, "sine", 0.12), 100);
}

function playOutro() {
  playTone(660, 0.15, "sine", 0.12);
  setTimeout(() => playTone(440, 0.30, "sine", 0.10), 90);
}

/* ═══════════════════════════════════════════════════
   PREMIUM VOICE SELECTION
═══════════════════════════════════════════════════ */
function getBestVoice(lang) {
  const voices = speechSynthesis.getVoices();
  const matching = voices.filter(v => v.lang === lang);

  return (
    matching.find(v => /Google/.test(v.name))     ||
    matching.find(v => /Microsoft/.test(v.name))  ||
    matching.find(v => !v.localService)            ||
    matching[0]                                    ||
    voices.find(v => v.lang.startsWith(lang.split('-')[0])) ||
    voices[0]
  );
}

/* ═══════════════════════════════════════════════════
   PRODUCT ENGINE  (your full rule logic)
═══════════════════════════════════════════════════ */
const PRODUCTS = {
  formulaExclusiva: {
    name: "Formula Exclusiva",
    price: "$65",
    desc: "An all-in-one natural professional salon hair treatment — restores strength, elasticity, moisture balance, and scalp health."
  },
  laciador: {
    name: "Laciador",
    price: "$48",
    desc: "An all-natural hair styler — improves manageability, smoothness, bounce, and detangling without harsh chemicals."
  },
  gotero: {
    name: "Gotero",
    price: "$42",
    desc: "An all-natural hair gel — regulates excess oil, supports scalp clarity, and maintains natural flexibility."
  },
  gotika: {
    name: "Gotika",
    price: "$54",
    desc: "An all-natural hair color treatment — restores vibrancy, corrects tone, and protects pigment longevity."
  }
};

function buildReply(product) {
  const p = PRODUCTS[product];
  return `${p.name} — ${p.desc} Price: ${p.price}.`;
}

function parseInput(text) {
  const t = text.toLowerCase();

  const dry      = /dry|frizz|rough|brittle|coarse|moisture|split end/.test(t);
  const damaged  = /damag|break|weak|burn|overprocess|heat damage/.test(t);
  const tangly   = /tangl|knot|hard to brush|snag|matted/.test(t);
  const color    = /color|fade|brassy|discolor|lost color|dull color/.test(t);
  const oily     = /oil|greasy|build.?up|shiny scalp/.test(t);
  const flat     = /flat|no bounce|lifeless|no volume|volume/.test(t);
  const falling  = /fall|shed|hair loss|thin/.test(t);

  const problems = [dry,damaged,tangly,color,oily,flat,falling].filter(Boolean).length;

  // Under 16 color guard (voice heuristic)
  if (color && /under 16|child|kid|young/.test(t))
    return "For color concerns in children under 16, please consult a medical professional first.";

  // Multi-problem or structural damage → Formula Exclusiva
  if (damaged || falling || problems >= 3)
    return buildReply("formulaExclusiva");

  if (color)  return buildReply("gotika");
  if (oily && problems >= 2)  return buildReply("formulaExclusiva");
  if (oily)   return buildReply("gotero");
  if (tangly && problems >= 2) return buildReply("formulaExclusiva");
  if (tangly) return buildReply("laciador");
  if (dry && problems >= 2)  return buildReply("formulaExclusiva");
  if (dry)    return buildReply("laciador");
  if (flat)   return buildReply("laciador");

  // Fallback: ask for more detail
  return null;
}

// Rule-based engine that also reads background/race from text
function chooseProduct(text) {
  const t = text.toLowerCase();

  // Try to detect hair background from voice input
  const isAfrican   = /african|black hair/.test(t);
  const isAsian     = /asian|chinese|japanese|korean/.test(t);
  const isHispanic  = /hispanic|latin/.test(t);
  const isCaucasian = /caucasian|white hair|european/.test(t);
  const isPacific   = /pacific|island/.test(t);
  const isIndian    = /indian|native american|american indian/.test(t);

  const color   = /color|fade|brassy/.test(t);
  const oily    = /oil|greasy/.test(t);
  const dry     = /dry|frizz|rough/.test(t);
  const damaged = /damag|break|weak/.test(t);
  const tangly  = /tangl|knot/.test(t);
  const flat    = /flat|no bounce|volume/.test(t);
  const falling = /fall|shed|thin/.test(t);

  // Exact rule matches (subset of your full table — covering most voice scenarios)
  if (color) {
    if (isAfrican) return buildReply("gotero");
    return buildReply("gotika"); // hispanic, asian, caucasian, indian
  }
  if (oily) {
    if (isHispanic || isPacific) return buildReply("formulaExclusiva");
    return buildReply("gotero");
  }
  if (dry) {
    if (isAsian) return buildReply("formulaExclusiva");
    return buildReply("laciador");
  }
  if (damaged) return buildReply("formulaExclusiva");
  if (tangly) {
    if (isHispanic || isAfrican) return buildReply("laciador");
    return buildReply("formulaExclusiva");
  }
  if (flat) {
    if (isHispanic) return buildReply("laciador");
    if (isAfrican)  return buildReply("formulaExclusiva");
    return buildReply("gotero");
  }
  if (falling) return buildReply("formulaExclusiva");

  // Fall back to semantic analysis
  return parseInput(text);
}

/* ═══════════════════════════════════════════════════
   SPEAK
═══════════════════════════════════════════════════ */
function speak(text) {
  speechSynthesis.cancel();

  const utter   = new SpeechSynthesisUtterance(text);
  utter.lang    = langSelect.value;
  utter.voice   = getBestVoice(langSelect.value);
  utter.rate    = 0.90;
  utter.pitch   = 1.0;

  state = "speaking";
  setColor(...C_SPEAK);
  statusDot.textContent = "Speaking";

  speechSynthesis.speak(utter);

  utter.onend = () => {
    playOutro();
    state = "idle";
    setColor(...C_IDLE);
    statusDot.textContent = "Idle";
  };
}

/* ═══════════════════════════════════════════════════
   PROCESS TEXT → RESPONSE
═══════════════════════════════════════════════════ */
function processText(text) {
  if (!text || text.trim().length < 3) {
    const msg = "I didn't hear a clear concern. Please describe dryness, oiliness, damage, tangling, color loss, volume, or shedding.";
    responseBox.textContent = msg;
    speak(msg);
    return;
  }

  responseBox.textContent = "Analyzing…";
  statusDot.textContent   = "Processing";

  setTimeout(() => {
    const result = chooseProduct(text);

    if (!result) {
      const fallback = "Could you be more specific? Describe dryness, oiliness, damage, tangling, color loss, volume, or shedding.";
      responseBox.textContent = fallback;
      // 2.5s silence before speaking
      setTimeout(() => speak(fallback), 2500);
      return;
    }

    responseBox.textContent = result;

    // 2.5 second silence before AI speaks
    setTimeout(() => speak(result), 2500);

  }, 800);
}

/* ═══════════════════════════════════════════════════
   LISTEN (Voice Recognition)
═══════════════════════════════════════════════════ */
function startListening() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    responseBox.textContent = "Speech recognition is not supported in this browser. Please use Chrome.";
    return;
  }

  playIntro();
  initMic(); // start mic volume tracking

  finalText = "";
  state     = "listening";
  setColor(...C_LISTEN);
  statusDot.textContent   = "Listening…";
  responseBox.textContent = "Listening…";

  recognition = new SR();
  recognition.lang            = langSelect.value;
  recognition.continuous      = true;
  recognition.interimResults  = true;

  recognition.onresult = (event) => {
    clearTimeout(silenceTimer);

    let interim = "";
    finalText   = "";

    for (let i = 0; i < event.results.length; i++) {
      if (event.results[i].isFinal) {
        finalText += event.results[i][0].transcript + " ";
      } else {
        interim += event.results[i][0].transcript;
      }
    }

    responseBox.textContent = (finalText + interim).trim() || "Listening…";

    // Reset 2.5s silence timer every time speech is detected
    silenceTimer = setTimeout(() => {
      recognition.stop();
      processText(finalText.trim() || interim.trim());
    }, 2500);
  };

  recognition.onerror = (e) => {
    console.warn("Recognition error:", e.error);
    if (e.error !== "no-speech") {
      state = "idle";
      setColor(...C_IDLE);
      statusDot.textContent = "Idle";
    }
  };

  recognition.onend = () => {
    // If we ended without processing (e.g., no speech at all)
    if (state === "listening") {
      if (finalText.trim().length < 2) {
        const msg = "I didn't hear anything. Please describe your hair concern.";
        responseBox.textContent = msg;
        speak(msg);
      }
    }
  };

  recognition.start();
}

/* ═══════════════════════════════════════════════════
   CLICK TO START / STOP
═══════════════════════════════════════════════════ */
halo.addEventListener("click", () => {
  if (isManual) return;

  if (state === "listening") {
    clearTimeout(silenceTimer);
    recognition.stop();
    state = "idle";
    setColor(...C_IDLE);
    statusDot.textContent   = "Idle";
    responseBox.textContent = "Tap the sphere and describe your hair concern.";
    return;
  }

  if (state === "speaking") {
    speechSynthesis.cancel();
    state = "idle";
    setColor(...C_IDLE);
    statusDot.textContent   = "Idle";
    return;
  }

  startListening();
});

/* ═══════════════════════════════════════════════════
   MANUAL MODE TOGGLE
═══════════════════════════════════════════════════ */
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

manualInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") manualSubmit.click();
});

/* ═══════════════════════════════════════════════════
   LANGUAGE SWITCH
═══════════════════════════════════════════════════ */
langSelect.addEventListener("change", () => {
  // Force voices to reload for new language
  speechSynthesis.getVoices();
});

// Ensure voices are loaded
speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
setTimeout(() => speechSynthesis.getVoices(), 400);

/* ═══════════════════════════════════════════════════
   FAQ / CONTACT
═══════════════════════════════════════════════════ */
document.getElementById("faqBtn").addEventListener("click", () => {
  const msg = "Frequently Asked Questions: All products are 100% organic and salon-professional grade. Formulated with Caribbean heritage ingredients. Safe for all hair types. Available globally.";
  responseBox.textContent = msg;
  speak(msg);
});

document.getElementById("contactBtn").addEventListener("click", () => {
  const msg = "Contact us at support@hairexpert.com or visit our website for a personalized consultation with one of our professional advisors.";
  responseBox.textContent = msg;
  speak(msg);
});
</script>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
