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
- Never say "I recommend" — say something more natural like "For your [concern], [Product] is exactly what you need."
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

Respond ONLY with your product recommendation. No preamble. No "Sure!" or "Of course!".
If the user's language is not English, respond entirely in that language. The language code will be provided."""


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
  /* Idle breathing — CSS keyframe, always runs unless JS overrides transform */
  animation: idlePulse 3.2s ease-in-out infinite;
}

@keyframes idlePulse {
  0%   { transform: scale(1.00); }
  50%  { transform: scale(1.10); }
  100% { transform: scale(1.00); }
}

/* Speaking pulse — CSS keyframe, no mic data needed */
#halo.speaking {
  animation: speakPulse 0.9s ease-in-out infinite;
}
@keyframes speakPulse {
  0%   { transform: scale(1.05); }
  50%  { transform: scale(1.20); }
  100% { transform: scale(1.05); }
}

/* Listening — NO animation class. JS drives transform via mic volume directly. */
#halo.listening {
  animation: none;
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

/* ── APP STATE ── */
let appState     = "idle";
let recognition  = null;
let silenceTimer = null;
let noSpeechTimer = null;   // module-level so all handlers can clearTimeout it
let finalText    = "";
let isManual     = false;

/* ── AUDIO CONTEXT ── */
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
      [[220,0],[330,0.20],[440,0.40],[660,0.65]].forEach(([freq,delay]) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.connect(g); g.connect(master); o.type = "sine";
        o.frequency.setValueAtTime(freq, now+delay);
        g.gain.setValueAtTime(0, now+delay);
        g.gain.linearRampToValueAtTime(0.06, now+delay+0.5);
        g.gain.exponentialRampToValueAtTime(0.001, now+delay+3.5);
        o.start(now+delay); o.stop(now+delay+4.0);
      });
      const s = ctx.createOscillator(), sg = ctx.createGain();
      s.connect(sg); sg.connect(master); s.type = "sine";
      s.frequency.setValueAtTime(1320, now+0.8);
      s.frequency.exponentialRampToValueAtTime(880, now+2.5);
      sg.gain.setValueAtTime(0, now+0.8);
      sg.gain.linearRampToValueAtTime(0.022, now+1.1);
      sg.gain.exponentialRampToValueAtTime(0.001, now+3.8);
      s.start(now+0.8); s.stop(now+4.0);
      master.gain.setValueAtTime(1, now);
    } else if (type === "outro") {
      [[660,0],[440,0.25],[330,0.50],[220,0.75]].forEach(([freq,delay]) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.connect(g); g.connect(master); o.type = "sine";
        o.frequency.setValueAtTime(freq, now+delay);
        o.frequency.exponentialRampToValueAtTime(freq*0.90, now+delay+2.5);
        g.gain.setValueAtTime(0, now+delay);
        g.gain.linearRampToValueAtTime(0.050, now+delay+0.35);
        g.gain.exponentialRampToValueAtTime(0.001, now+delay+3.2);
        o.start(now+delay); o.stop(now+delay+3.5);
      });
      master.gain.setValueAtTime(1, now);
    }
  } catch(e) { console.warn("Audio:", e); }
}

/* ── MICROPHONE — returns a real Promise ── */
function initMic() {
  if (analyser) return Promise.resolve();
  const ctx = getCtx();
  return navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      const src = ctx.createMediaStreamSource(stream);
      analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      micData = new Uint8Array(analyser.frequencyBinCount);
    })
    .catch(e => console.warn("Mic:", e));
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

/* ── STATE SETTER ── */
function setState(s) {
  appState = s;
  halo.classList.remove("listening", "speaking");
  if (s === "listening") {
    halo.classList.add("listening");
    // Clear any inline transform left from previous session
    // JS mic loop will take over immediately
  }
  if (s === "speaking") {
    halo.classList.add("speaking");
    halo.style.transform = ""; // let CSS keyframe drive it
  }
  if (s === "idle") {
    halo.style.transform = ""; // let CSS idlePulse drive it
  }
}

/* ── MIC-REACTIVE LOOP ──
   Runs ONLY during "listening". Drives transform via mic volume.
   CSS animation:none on .listening means no conflict. ── */
function micReactiveLoop() {
  if (appState !== "listening") {
    // Exit — setState("idle"/"speaking") already cleared inline transform
    return;
  }
  if (analyser && micData) {
    analyser.getByteFrequencyData(micData);
    let sum = 0;
    for (let i = 0; i < micData.length; i++) sum += micData[i];
    const vol = sum / (micData.length * 255); // 0.0–1.0
    const scale = 1.05 + vol * 0.60;          // 1.05 quiet → 1.65 loud
    halo.style.transform = `scale(${scale.toFixed(3)})`;
  } else {
    // Mic not ready yet — soft fallback pulse
    halo.style.transform = `scale(1.08)`;
  }
  requestAnimationFrame(micReactiveLoop);
}

/* ── VOICE SELECTION ── */
function getBestVoice(lang) {
  const voices = speechSynthesis.getVoices();
  if (!voices.length) return null;
  if (lang === "en-US" || lang === "en-GB") {
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
  }
  const byLang = voices.filter(v => v.lang === lang);
  return (
    byLang.find(v => /Google/.test(v.name))         ||
    byLang.find(v => /Natural|Online/.test(v.name)) ||
    byLang.find(v => /Microsoft/.test(v.name))      ||
    byLang.find(v => !v.localService)               ||
    byLang[0]                                        ||
    voices.find(v => v.lang.startsWith(lang.split("-")[0])) ||
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
    setState("speaking");
    setColor(...SPEAK);
    stateLabel.textContent = "Speaking";
    speechSynthesis.speak(utter);
    utter.onend = () => {
      playAmbient("outro");
      setState("idle");
      setColor(...IDLE);
      stateLabel.textContent = "Tap to begin";
    };
  }, 80);
}

/* ── LOCAL RESPONSES ── */
const LOCAL_RESPONSES = {
  "en-US": {
    damaged:  "Formula Exclusiva is exactly what your hair needs. This professional all-in-one treatment rebuilds strength, restores moisture, and revives scalp health. At $65, it's your most complete solution.",
    color:    "Gotika is the answer for your color. It restores vibrancy, corrects tone, and protects your pigment long-term — all naturally. Price: $54.",
    colorAf:  "Gotero is your best match — it restores natural sheen and tone while balancing your scalp. At $42, it works beautifully with your hair's natural texture.",
    oily:     "Gotero is exactly right for oily hair — it regulates sebum production and keeps your scalp clear. Price: $42.",
    oilyHi:  "Formula Exclusiva will balance your scalp's oil while deeply nourishing your hair. At $65, it handles both in one.",
    dry:      "Laciador will transform dry hair — restoring softness, smoothness, and that healthy natural bounce. Price: $48.",
    dryAs:   "Formula Exclusiva is ideal for your hair type — it penetrates deeply to restore elasticity and hydration. Price: $65.",
    tangly:   "Formula Exclusiva addresses the root cause of tangles while strengthening every strand. Price: $65.",
    tanglyHi: "Laciador is perfect — it smooths, detangles, and leaves your hair manageable with beautiful movement. Price: $48.",
    flat:     "Laciador will give your hair the body and movement it's been missing — lightweight and natural. Price: $48.",
    default:  "Formula Exclusiva is your best all-around choice. It covers moisture, strength, and scalp health in one professional treatment. Price: $65."
  },
  "es-ES": {
    damaged:  "Formula Exclusiva es exactamente lo que tu cabello necesita. Este tratamiento profesional todo en uno reconstruye la fuerza y restaura la humedad. A $65, es tu solución más completa.",
    color:    "Gotika es la respuesta para tu color. Restaura la vitalidad, corrige el tono y protege tu pigmento. Precio: $54.",
    colorAf:  "Gotero es tu mejor opción — restaura el brillo natural y equilibra tu cuero cabelludo. A $42, funciona perfectamente.",
    oily:     "Gotero es ideal para el cabello graso — regula la producción de sebo. Precio: $42.",
    oilyHi:  "Formula Exclusiva equilibrará el aceite de tu cuero cabelludo mientras nutre tu cabello. A $65, lo maneja todo.",
    dry:      "Laciador transformará tu cabello seco — restaurando suavidad y ese rebote natural. Precio: $48.",
    dryAs:   "Formula Exclusiva es ideal para tu tipo de cabello — penetra profundamente para restaurar elasticidad. Precio: $65.",
    tangly:   "Formula Exclusiva aborda la causa raíz de los enredos. Precio: $65.",
    tanglyHi: "Laciador es perfecto — suaviza y desenreda dejando tu cabello manejable. Precio: $48.",
    flat:     "Laciador le dará a tu cabello el cuerpo que le falta. Precio: $48.",
    default:  "Formula Exclusiva es tu mejor opción general. Precio: $65."
  },
  "fr-FR": {
    damaged:  "Formula Exclusiva est exactement ce dont vos cheveux ont besoin. Ce traitement tout-en-un reconstruit la force et restaure l'hydratation. À 65$.",
    color:    "Gotika est la réponse pour votre couleur. Elle restaure l'éclat et protège votre pigment. Prix: 54$.",
    colorAf:  "Gotero est votre meilleur choix — il restaure l'éclat naturel. À 42$.",
    oily:     "Gotero est idéal pour les cheveux gras. Prix: 42$.",
    oilyHi:  "Formula Exclusiva équilibrera l'huile tout en nourrissant vos cheveux. À 65$.",
    dry:      "Laciador transformera vos cheveux secs — restaurant douceur et rebond. Prix: 48$.",
    dryAs:   "Formula Exclusiva est idéale pour votre type de cheveux. Prix: 65$.",
    tangly:   "Formula Exclusiva s'attaque aux nœuds tout en renforçant chaque mèche. Prix: 65$.",
    tanglyHi: "Laciador lisse et démêle vos cheveux. Prix: 48$.",
    flat:     "Laciador donnera du volume à vos cheveux. Prix: 48$.",
    default:  "Formula Exclusiva est votre meilleur choix global. Prix: 65$."
  },
  "pt-BR": {
    damaged:  "Formula Exclusiva é exatamente o que seu cabelo precisa. Reconstrói a força e restaura a hidratação. Por $65.",
    color:    "Gotika é a resposta para sua cor. Restaura a vibração e protege seu pigmento. Preço: $54.",
    colorAf:  "Gotero é sua melhor opção — restaura o brilho natural. Por $42.",
    oily:     "Gotero é ideal para cabelos oleosos. Preço: $42.",
    oilyHi:  "Formula Exclusiva equilibrará o óleo enquanto nutre seu cabelo. Por $65.",
    dry:      "Laciador vai transformar seu cabelo seco. Preço: $48.",
    dryAs:   "Formula Exclusiva é ideal para seu tipo de cabelo. Preço: $65.",
    tangly:   "Formula Exclusiva resolve os nós e fortalece cada fio. Preço: $65.",
    tanglyHi: "Laciador alisa e desembaraça seu cabelo. Preço: $48.",
    flat:     "Laciador dará volume ao seu cabelo. Preço: $48.",
    default:  "Formula Exclusiva é sua melhor escolha geral. Preço: $65."
  },
  "de-DE": {
    damaged:  "Formula Exclusiva ist genau das, was Ihr Haar braucht. Baut Stärke auf und stellt Feuchtigkeit wieder her. Für $65.",
    color:    "Gotika ist die Antwort für Ihre Farbe. Stellt Lebendigkeit wieder her. Preis: $54.",
    colorAf:  "Gotero ist Ihre beste Wahl — stellt natürlichen Glanz wieder her. Für $42.",
    oily:     "Gotero ist ideal für fettiges Haar. Preis: $42.",
    oilyHi:  "Formula Exclusiva bringt das Öl ins Gleichgewicht. Für $65.",
    dry:      "Laciador wird Ihr trockenes Haar transformieren. Preis: $48.",
    dryAs:   "Formula Exclusiva ist ideal für Ihren Haartyp. Preis: $65.",
    tangly:   "Formula Exclusiva bekämpft Verfilzungen. Preis: $65.",
    tanglyHi: "Laciador glättet und entwirrt Ihr Haar. Preis: $48.",
    flat:     "Laciador gibt Ihrem Haar Volumen. Preis: $48.",
    default:  "Formula Exclusiva ist Ihre beste Gesamtlösung. Preis: $65."
  },
  "ar-SA": {
    damaged:  "فورمولا إكسكلوسيفا هو ما يحتاجه شعرك. يعيد بناء القوة ويستعيد الرطوبة. بسعر $65.",
    color:    "غوتيكا هي الإجابة لحماية لونك. تستعيد النضارة وتحمي الصبغة. السعر: $54.",
    colorAf:  "غوتيرو هو خيارك الأفضل — يستعيد البريق الطبيعي. بسعر $42.",
    oily:     "غوتيرو مثالي للشعر الدهني. السعر: $42.",
    oilyHi:  "فورمولا إكسكلوسيفا يوازن زيت فروة الرأس. بسعر $65.",
    dry:      "لاسيادور سيحول شعرك الجاف. السعر: $48.",
    dryAs:   "فورمولا إكسكلوسيفا مثالي لنوع شعرك. السعر: $65.",
    tangly:   "فورمولا إكسكلوسيفا يعالج التشابك ويقوي الشعر. السعر: $65.",
    tanglyHi: "لاسيادور يملس ويفك التشابك. السعر: $48.",
    flat:     "لاسيادور يمنح شعرك الحجم. السعر: $48.",
    default:  "فورمولا إكسكلوسيفا هو أفضل خيار شامل. السعر: $65."
  },
  "zh-CN": {
    damaged:  "Formula Exclusiva 正是您的头发所需。重建强度、恢复水分。售价 $65。",
    color:    "Gotika 是护色的最佳选择。恢复色彩活力，保护色素。售价 $54。",
    colorAf:  "Gotero 是您的最佳选择——恢复自然光泽。售价 $42。",
    oily:     "Gotero 非常适合油性发质。售价 $42。",
    oilyHi:  "Formula Exclusiva 平衡头皮油脂，深层滋养。售价 $65。",
    dry:      "Laciador 彻底改善干燥发质。售价 $48。",
    dryAs:   "Formula Exclusiva 最适合您的发质。售价 $65。",
    tangly:   "Formula Exclusiva 解决打结，强化发丝。售价 $65。",
    tanglyHi: "Laciador 顺滑、解结。售价 $48。",
    flat:     "Laciador 赋予发丝蓬松感。售价 $48。",
    default:  "Formula Exclusiva 是您最全面的选择。售价 $65。"
  },
  "hi-IN": {
    damaged:  "Formula Exclusiva बिल्कुल वही है जो आपके बालों को चाहिए। $65 में सबसे संपूर्ण समाधान।",
    color:    "Gotika आपके रंग के लिए सही उत्तर है। कीमत: $54।",
    colorAf:  "Gotero आपके लिए सबसे अच्छा विकल्प है। $42 में शानदार।",
    oily:     "Gotero तैलीय बालों के लिए आदर्श है। कीमत: $42।",
    oilyHi:  "Formula Exclusiva स्कैल्प का तेल संतुलित करेगा। $65।",
    dry:      "Laciador सूखे बालों को बदल देगा। कीमत: $48।",
    dryAs:   "Formula Exclusiva आपके बालों के लिए आदर्श है। कीमत: $65।",
    tangly:   "Formula Exclusiva उलझन दूर करता है। कीमत: $65।",
    tanglyHi: "Laciador चिकना और उलझन-मुक्त करता है। कीमत: $48।",
    flat:     "Laciador वॉल्यूम देगा। कीमत: $48।",
    default:  "Formula Exclusiva सबसे अच्छी सर्वांगीण पसंद है। कीमत: $65।"
  }
};

function localRecommend(text) {
  const t    = text.toLowerCase();
  const lang = langSelect.value;
  const R    = LOCAL_RESPONSES[lang] || LOCAL_RESPONSES["en-US"];

  const damaged = /damag|break|broke|split end|weak|brittle|burnt|burned|chemical|overprocess|heat damage|perm|relaxer|bleach|falling apart|falling out|hair loss|losing hair|bald|thinning|shed|shedding|alopecia|receding/.test(t);
  const color   = /color|colour|fade|fading|faded|brassy|brass|discolor|dull color|grey|gray|graying|highlights|dye|tint|pigment|vibrancy|vibrant|roots/.test(t);
  const oily    = /oil|oily|greasy|grease|sebum|buildup|build.?up|waxy|weighing down|scalp buildup|dirty fast|gets dirty|too shiny|shiny scalp|limp/.test(t);
  const dry     = /dry|frizz|frizzy|rough|coarse|moisture|parched|thirsty|dehydrat|feels like straw|straw|fluffy|puff|poofy|no shine|lacks shine|hard to manage|unmanageable/.test(t);
  const tangly  = /tangl|tangle|knot|knotty|matted|hard to brush|hard to comb|always knotted|detangle|snag|snagging|breaks when.{0,10}brush/.test(t);
  const flat    = /flat|no bounce|no volume|lifeless|limp|fine hair|thin hair|lacks body|no body|no lift|falls flat|weighed down|no movement/.test(t);
  const african   = /african|black hair|afro|natural hair|4[abc]|type 4|coily/.test(t);
  const asian     = /asian|chinese|japanese|korean|east asian/.test(t);
  const hispanic  = /hispanic|latin[ao]?|latin american|spanish/.test(t);
  const n = [color, oily, dry, damaged, tangly, flat].filter(Boolean).length;

  if (damaged || n >= 3)  return R.damaged;
  if (color)              return african ? R.colorAf : R.color;
  if (oily)               return hispanic ? R.oilyHi : R.oily;
  if (dry)                return asian ? R.dryAs : R.dry;
  if (tangly)             return (hispanic || african) ? R.tanglyHi : R.tangly;
  if (flat)               return R.flat;
  return R.default;
}

/* ── AI RECOMMENDATION ── */
async function getRecommendation(text) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const resp = await fetch("https://ai-hair-advisor.onrender.com/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, lang: langSelect.value }),
      signal: controller.signal
    });
    clearTimeout(timeout);
    if (!resp.ok) throw new Error("not ok");
    const data = await resp.json();
    if (data.recommendation) return data.recommendation;
    throw new Error("empty");
  } catch(e) {
    return localRecommend(text);
  }
}

/* ── PROCESS TEXT ── */
async function processText(text) {
  if (!text || text.trim().length < 3) {
    const msg = "Could you describe your hair a little more? Dryness, oiliness, damage, color, volume, or shedding all help me find the right product for you.";
    responseBox.textContent = msg;
    setState("idle");
    setColor(...IDLE);
    stateLabel.textContent = "Tap to begin";
    setTimeout(() => speak(msg), 2500);
    return;
  }
  setState("idle");
  setColor(...IDLE);
  responseBox.textContent = "Analyzing your concern…";
  stateLabel.textContent  = "Thinking";
  const result = await getRecommendation(text);
  const final  = result || localRecommend(text);
  responseBox.textContent = final;
  setTimeout(() => speak(final), 2500);
}

/* ── NO-HEAR MESSAGES ── */
const NO_HEAR = {
  "en-US": "I didn't hear anything. Please tap and describe your hair concern.",
  "es-ES": "No escuché nada. Por favor toca y describe tu preocupación capilar.",
  "fr-FR": "Je n'ai rien entendu. Veuillez appuyer et décrire votre préoccupation.",
  "pt-BR": "Não ouvi nada. Por favor toque e descreva sua preocupação capilar.",
  "de-DE": "Ich habe nichts gehört. Bitte tippen und beschreiben Sie Ihr Haarproblem.",
  "ar-SA": "لم أسمع شيئاً. يرجى النقر ووصف قلقك بشأن شعرك.",
  "zh-CN": "我没有听到任何声音。请点击并描述您的发质问题。",
  "hi-IN": "मुझे कुछ सुनाई नहीं दिया। कृपया टैप करें और अपनी बालों की समस्या बताएं।"
};
function noHear() {
  const msg = NO_HEAR[langSelect.value] || NO_HEAR["en-US"];
  responseBox.textContent = msg;
  setState("idle");
  setColor(...IDLE);
  stateLabel.textContent = "Tap to begin";
  speak(msg);
}

/* ── START LISTENING ── */
function startListening() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    responseBox.textContent = "Please use Chrome for voice input, or switch to Manual Mode.";
    return;
  }

  playAmbient("intro");
  finalText = "";
  setState("listening");
  setColor(...LISTEN);
  stateLabel.textContent  = "Listening…";
  responseBox.textContent = "Listening…";

  // Start mic — .then() guaranteed because initMic returns a real Promise
  initMic().then(() => {
    // Only start loop if still listening (user might have cancelled)
    if (appState === "listening") requestAnimationFrame(micReactiveLoop);
  });

  // Module-level noSpeechTimer — can be cleared from onresult
  noSpeechTimer = setTimeout(() => {
    if (appState !== "listening") return;
    try { recognition.stop(); } catch(e) {}
    noHear();
  }, 7000);

  recognition = new SR();
  recognition.lang           = langSelect.value;
  recognition.continuous     = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    clearTimeout(silenceTimer);
    clearTimeout(noSpeechTimer);  // speech detected — cancel "didn't hear"
    let interim = "";
    finalText = "";
    for (let i = 0; i < event.results.length; i++) {
      if (event.results[i].isFinal) finalText += event.results[i][0].transcript + " ";
      else interim += event.results[i][0].transcript;
    }
    responseBox.textContent = (finalText + interim).trim() || "Listening…";
    // 3s silence → stop recognition
    silenceTimer = setTimeout(() => {
      try { recognition.stop(); } catch(e) {}
    }, 3000);
  };

  recognition.onend = () => {
    clearTimeout(silenceTimer);
    clearTimeout(noSpeechTimer);
    if (appState !== "listening") return;
    const captured = finalText.trim();
    if (captured.length > 2) {
      processText(captured);
    } else {
      noHear();
    }
  };

  recognition.onerror = (e) => {
    clearTimeout(silenceTimer);
    clearTimeout(noSpeechTimer);
    if (e.error === "no-speech") {
      noHear();
    }
  };

  recognition.start();
}

/* ── HALO CLICK ── */
halo.addEventListener("click", () => {
  if (isManual) return;
  if (appState === "listening") {
    clearTimeout(silenceTimer);
    clearTimeout(noSpeechTimer);
    try { recognition.stop(); } catch(e) {}
    setState("idle");
    setColor(...IDLE);
    stateLabel.textContent  = "Tap to begin";
    responseBox.textContent = "Tap the sphere and describe your hair concern.";
    return;
  }
  if (appState === "speaking") {
    speechSynthesis.cancel();
    setState("idle");
    setColor(...IDLE);
    stateLabel.textContent = "Tap to begin";
    return;
  }
  startListening();
});

/* ── MANUAL MODE ── */
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
const FAQ_MSGS = {
  "en-US": "All four products are 100% natural, organic, and salon-professional grade — Caribbean formulated. Formula Exclusiva $65 all-in-one. Laciador $48 styler. Gotero $42 gel. Gotika $54 color treatment.",
  "es-ES": "Los cuatro productos son 100% naturales y de grado profesional. Formula Exclusiva $65. Laciador $48. Gotero $42. Gotika $54.",
  "fr-FR": "Les quatre produits sont 100% naturels et de qualité salon. Formula Exclusiva $65. Laciador $48. Gotero $42. Gotika $54.",
  "pt-BR": "Os quatro produtos são 100% naturais e profissionais. Formula Exclusiva $65. Laciador $48. Gotero $42. Gotika $54.",
  "de-DE": "Alle vier Produkte sind 100% natürlich und salonprofessionell. Formula Exclusiva $65. Laciador $48. Gotero $42. Gotika $54.",
  "ar-SA": "المنتجات الأربعة طبيعية 100%. فورمولا $65. لاسيادور $48. غوتيرو $42. غوتيكا $54.",
  "zh-CN": "四款产品均为100%天然专业级。Formula Exclusiva $65。Laciador $48。Gotero $42。Gotika $54。",
  "hi-IN": "चारों उत्पाद 100% प्राकृतिक हैं। Formula Exclusiva $65। Laciador $48। Gotero $42। Gotika $54।"
};
const CONTACT_MSGS = {
  "en-US": "To speak with one of our professional hair consultants, please email us at support at hairexpert dot com. We'd love to find your perfect product together.",
  "es-ES": "Para hablar con uno de nuestros consultores, escríbenos a support arroba hairexpert punto com.",
  "fr-FR": "Pour parler à l'un de nos consultants, envoyez-nous un email à support chez hairexpert point com.",
  "pt-BR": "Para falar com um de nossos consultores, envie um e-mail para support em hairexpert ponto com.",
  "de-DE": "Um mit einem unserer Berater zu sprechen, schreiben Sie uns an support bei hairexpert Punkt com.",
  "ar-SA": "للتحدث مع أحد مستشارينا، راسلنا على support في hairexpert نقطة com.",
  "zh-CN": "如需与我们的顾问交流，请发邮件至 support@hairexpert.com。",
  "hi-IN": "हमारे सलाहकारों से बात करने के लिए support@hairexpert.com पर ईमेल करें।"
};
document.getElementById("faqBtn").addEventListener("click", () => {
  const msg = FAQ_MSGS[langSelect.value] || FAQ_MSGS["en-US"];
  responseBox.textContent = msg;
  speak(msg);
});
document.getElementById("contactBtn").addEventListener("click", () => {
  const msg = CONTACT_MSGS[langSelect.value] || CONTACT_MSGS["en-US"];
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
    lang      = data.get("lang", "en-US")
    lang_names = {
        "en-US": "English", "es-ES": "Spanish", "fr-FR": "French",
        "pt-BR": "Portuguese", "de-DE": "German", "ar-SA": "Arabic",
        "zh-CN": "Mandarin Chinese", "hi-IN": "Hindi"
    }
    lang_name = lang_names.get(lang, "English")
    lang_instruction = f"\n\nIMPORTANT: Your ENTIRE response must be written in {lang_name}. Do not use English."

    if not ANTHROPIC_API_KEY:
        return jsonify({"recommendation": None, "error": "No API key configured"}), 500

    try:
        import urllib.request as urlreq
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 200,
            "system": SYSTEM_PROMPT + lang_instruction,
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
