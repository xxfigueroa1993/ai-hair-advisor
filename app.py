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

// Translated fallback responses for when API key is not configured
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
    color:    "Gotika es la respuesta para tu color. Restaura la vitalidad, corrige el tono y protege tu pigmento a largo plazo. Precio: $54.",
    colorAf:  "Gotero es tu mejor opción — restaura el brillo natural y el tono mientras equilibra tu cuero cabelludo. A $42, funciona perfectamente.",
    oily:     "Gotero es ideal para el cabello graso — regula la producción de sebo y mantiene tu cuero cabelludo limpio. Precio: $42.",
    oilyHi:  "Formula Exclusiva equilibrará el aceite de tu cuero cabelludo mientras nutre profundamente tu cabello. A $65, lo maneja todo.",
    dry:      "Laciador transformará tu cabello seco — restaurando suavidad, tersura y ese rebote natural saludable. Precio: $48.",
    dryAs:   "Formula Exclusiva es ideal para tu tipo de cabello — penetra profundamente para restaurar elasticidad e hidratación. Precio: $65.",
    tangly:   "Formula Exclusiva aborda la causa raíz de los enredos mientras fortalece cada hebra. Precio: $65.",
    tanglyHi: "Laciador es perfecto — suaviza, desenreda y deja tu cabello manejable con un movimiento hermoso. Precio: $48.",
    flat:     "Laciador le dará a tu cabello el cuerpo y movimiento que le falta — ligero y natural. Precio: $48.",
    default:  "Formula Exclusiva es tu mejor opción general. Cubre humedad, fuerza y salud del cuero cabelludo en un tratamiento profesional. Precio: $65."
  },
  "fr-FR": {
    damaged:  "Formula Exclusiva est exactement ce dont vos cheveux ont besoin. Ce traitement tout-en-un professionnel reconstruit la force et restaure l'hydratation. À 65$, c'est votre solution la plus complète.",
    color:    "Gotika est la réponse pour votre couleur. Elle restaure l'éclat, corrige le ton et protège votre pigment durablement. Prix : 54$.",
    colorAf:  "Gotero est votre meilleur choix — il restaure l'éclat naturel tout en équilibrant votre cuir chevelu. À 42$, il fonctionne parfaitement.",
    oily:     "Gotero est idéal pour les cheveux gras — il régule la production de sébum et garde votre cuir chevelu propre. Prix : 42$.",
    oilyHi:  "Formula Exclusiva équilibrera l'huile de votre cuir chevelu tout en nourrissant profondément vos cheveux. À 65$, il gère les deux.",
    dry:      "Laciador transformera vos cheveux secs — restaurant la douceur, le lissé et ce rebond naturel sain. Prix : 48$.",
    dryAs:   "Formula Exclusiva est idéale pour votre type de cheveux — elle pénètre profondément pour restaurer l'élasticité. Prix : 65$.",
    tangly:   "Formula Exclusiva s'attaque à la cause des nœuds tout en renforçant chaque mèche. Prix : 65$.",
    tanglyHi: "Laciador est parfait — il lisse, démêle et laisse vos cheveux soyeux avec un beau mouvement. Prix : 48$.",
    flat:     "Laciador donnera à vos cheveux le volume et le mouvement qui lui manquent — léger et naturel. Prix : 48$.",
    default:  "Formula Exclusiva est votre meilleur choix global. Il couvre l'hydratation, la force et la santé du cuir chevelu. Prix : 65$."
  },
  "pt-BR": {
    damaged:  "Formula Exclusiva é exatamente o que seu cabelo precisa. Este tratamento profissional tudo-em-um reconstrói a força e restaura a hidratação. Por $65, é sua solução mais completa.",
    color:    "Gotika é a resposta para sua cor. Ela restaura a vibração, corrige o tom e protege seu pigmento por muito tempo. Preço: $54.",
    colorAf:  "Gotero é sua melhor opção — ele restaura o brilho natural enquanto equilibra seu couro cabeludo. Por $42, funciona perfeitamente.",
    oily:     "Gotero é ideal para cabelos oleosos — regula a produção de sebo e mantém seu couro cabeludo limpo. Preço: $42.",
    oilyHi:  "Formula Exclusiva equilibrará o óleo do seu couro cabeludo enquanto nutre profundamente seu cabelo. Por $65, resolve os dois.",
    dry:      "Laciador vai transformar seu cabelo seco — restaurando suavidade, lisura e aquele bounce natural saudável. Preço: $48.",
    dryAs:   "Formula Exclusiva é ideal para seu tipo de cabelo — penetra profundamente para restaurar elasticidade e hidratação. Preço: $65.",
    tangly:   "Formula Exclusiva aborda a causa raiz dos nós enquanto fortalece cada fio. Preço: $65.",
    tanglyHi: "Laciador é perfeito — alisa, desembaraça e deixa seu cabelo maleável com um belo movimento. Preço: $48.",
    flat:     "Laciador dará ao seu cabelo o volume e movimento que faltam — leve e natural. Preço: $48.",
    default:  "Formula Exclusiva é sua melhor escolha geral. Cobre hidratação, força e saúde do couro cabeludo em um tratamento profissional. Preço: $65."
  },
  "de-DE": {
    damaged:  "Formula Exclusiva ist genau das, was Ihr Haar braucht. Diese professionelle All-in-one-Behandlung baut Stärke auf und stellt die Feuchtigkeit wieder her. Für $65 ist es Ihre vollständigste Lösung.",
    color:    "Gotika ist die Antwort für Ihre Farbe. Sie stellt Lebendigkeit wieder her, korrigiert den Ton und schützt Ihr Pigment langfristig. Preis: $54.",
    colorAf:  "Gotero ist Ihre beste Wahl — es stellt natürlichen Glanz und Ton wieder her. Für $42 funktioniert es perfekt.",
    oily:     "Gotero ist ideal für fettiges Haar — es reguliert die Talgproduktion und hält Ihre Kopfhaut sauber. Preis: $42.",
    oilyHi:  "Formula Exclusiva bringt das Öl Ihrer Kopfhaut ins Gleichgewicht und nährt Ihr Haar tief. Für $65 übernimmt es beides.",
    dry:      "Laciador wird Ihr trockenes Haar transformieren — Weichheit, Glätte und natürliches Volumen zurückbringen. Preis: $48.",
    dryAs:   "Formula Exclusiva ist ideal für Ihren Haartyp — dringt tief ein, um Elastizität wiederherzustellen. Preis: $65.",
    tangly:   "Formula Exclusiva bekämpft die Ursache von Verfilzungen und stärkt jeden Strang. Preis: $65.",
    tanglyHi: "Laciador ist perfekt — es glättet, entwirrt und lässt Ihr Haar pflegeleicht mit schöner Bewegung. Preis: $48.",
    flat:     "Laciador gibt Ihrem Haar das Volumen und die Bewegung, die ihm fehlen — leicht und natürlich. Preis: $48.",
    default:  "Formula Exclusiva ist Ihre beste Gesamtlösung. Es deckt Feuchtigkeitsversorgung, Stärke und Kopfhautgesundheit ab. Preis: $65."
  },
  "ar-SA": {
    damaged:  "فورمولا إكسكلوسيفا هو بالضبط ما يحتاجه شعرك. هذا العلاج المهني الشامل يعيد بناء القوة ويستعيد الرطوبة. بسعر $65، إنه حلك الأكثر اكتمالاً.",
    color:    "غوتيكا هي الإجابة لحماية لونك. تستعيد النضارة وتصحح اللون وتحمي الصبغة على المدى البعيد. السعر: $54.",
    colorAf:  "غوتيرو هو خيارك الأفضل — يستعيد البريق الطبيعي ويوازن فروة الرأس. بسعر $42 يعمل بشكل رائع.",
    oily:     "غوتيرو مثالي للشعر الدهني — ينظم إنتاج الزيت ويبقي فروة رأسك نظيفة. السعر: $42.",
    oilyHi:  "فورمولا إكسكلوسيفا سيوازن زيت فروة رأسك مع تغذية شعرك. بسعر $65 يتولى الأمرين معاً.",
    dry:      "لاسيادور سيحول شعرك الجاف — يستعيد النعومة والملمس والارتداد الطبيعي. السعر: $48.",
    dryAs:   "فورمولا إكسكلوسيفا مثالي لنوع شعرك — يخترق بعمق لاستعادة المرونة والترطيب. السعر: $65.",
    tangly:   "فورمولا إكسكلوسيفا يعالج سبب التشابك ويقوي كل خصلة. السعر: $65.",
    tanglyHi: "لاسيادور مثالي — يملس ويفك التشابك ويجعل شعرك قابلاً للتصفيف مع حركة جميلة. السعر: $48.",
    flat:     "لاسيادور سيمنح شعرك الحجم والحركة التي يفتقدها — خفيف وطبيعي. السعر: $48.",
    default:  "فورمولا إكسكلوسيفا هو أفضل خيار شامل لك. يغطي الترطيب والقوة وصحة فروة الرأس. السعر: $65."
  },
  "zh-CN": {
    damaged:  "Formula Exclusiva 正是您的头发所需要的。这款专业全效护理产品能重建发丝强度、恢复水分，全面修护头皮健康。售价 $65，是您最完整的解决方案。",
    color:    "Gotika 是护色的最佳选择。它能恢复色彩活力、校正发色，并长效保护色素。售价 $54。",
    colorAf:  "Gotero 是您的最佳选择——它能恢复自然光泽与发色，同时平衡头皮状态。售价 $42，效果出色。",
    oily:     "Gotero 非常适合油性发质——它能调节皮脂分泌，保持头皮清爽而不过度干燥。售价 $42。",
    oilyHi:  "Formula Exclusiva 能平衡头皮油脂，同时深层滋养发丝。售价 $65，一步到位。",
    dry:      "Laciador 能彻底改善干燥发质——恢复柔软、顺滑和自然弹性。售价 $48。",
    dryAs:   "Formula Exclusiva 最适合您的发质——深层渗透，恢复弹性与持久水分。售价 $65。",
    tangly:   "Formula Exclusiva 从根本上解决打结问题，同时强化每根发丝。售价 $65。",
    tanglyHi: "Laciador 是完美之选——顺滑、解结，让发丝易于打理且充满自然动感。售价 $48。",
    flat:     "Laciador 能赋予发丝所缺失的蓬松感和动感——轻盈自然。售价 $48。",
    default:  "Formula Exclusiva 是您最全面的选择，涵盖水分、强度与头皮健康，一款专业护理产品搞定一切。售价 $65。"
  },
  "hi-IN": {
    damaged:  "Formula Exclusiva बिल्कुल वही है जो आपके बालों को चाहिए। यह पेशेवर ऑल-इन-वन उपचार बालों की मजबूती बहाल करता है और नमी देता है। $65 में यह आपका सबसे संपूर्ण समाधान है।",
    color:    "Gotika आपके बालों के रंग के लिए सही उत्तर है। यह रंग की चमक बहाल करती है, टोन ठीक करती है और पिगमेंट को लंबे समय तक सुरक्षित रखती है। कीमत: $54।",
    colorAf:  "Gotero आपके लिए सबसे अच्छा विकल्प है — यह प्राकृतिक चमक बहाल करता है और स्कैल्प को संतुलित रखता है। $42 में शानदार परिणाम।",
    oily:     "Gotero तैलीय बालों के लिए आदर्श है — यह सीबम उत्पादन को नियंत्रित करता है और स्कैल्प को साफ रखता है। कीमत: $42।",
    oilyHi:  "Formula Exclusiva आपके स्कैल्प के तेल को संतुलित करते हुए बालों को गहराई से पोषण देगा। $65 में दोनों काम एक साथ।",
    dry:      "Laciador सूखे बालों को बदल देगा — मुलायमियत, चिकनाई और प्राकृतिक बाउंस वापस लाएगा। कीमत: $48।",
    dryAs:   "Formula Exclusiva आपके बालों के प्रकार के लिए आदर्श है — गहराई से प्रवेश करके लोच और नमी बहाल करता है। कीमत: $65।",
    tangly:   "Formula Exclusiva उलझन की मूल वजह को दूर करता है और हर बाल को मजबूत बनाता है। कीमत: $65।",
    tanglyHi: "Laciador एकदम सही है — चिकना करता है, उलझन सुलझाता है और बालों को संभालने योग्य बनाता है। कीमत: $48।",
    flat:     "Laciador आपके बालों को वो वॉल्यूम और मूवमेंट देगा जो उन्हें चाहिए — हल्का और प्राकृतिक। कीमत: $48।",
    default:  "Formula Exclusiva आपकी सबसे अच्छी सर्वांगीण पसंद है। यह एक पेशेवर उपचार में नमी, मजबूती और स्कैल्प स्वास्थ्य को कवर करता है। कीमत: $65।"
  }
};

function localRecommend(text) {
  const t   = text.toLowerCase();
  const lang = langSelect.value;
  const R   = LOCAL_RESPONSES[lang] || LOCAL_RESPONSES["en-US"];

  const color   = /color|colour|fade|brassy|pigment|dull|tint|vibrancy|colou?r/.test(t);
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

  if (damaged || falling || n >= 3) return R.damaged;
  if (color)   return african ? R.colorAf  : R.color;
  if (oily)    return hispanic ? R.oilyHi  : R.oily;
  if (dry)     return asian    ? R.dryAs   : R.dry;
  if (tangly)  return (hispanic || african) ? R.tanglyHi : R.tangly;
  if (flat)    return R.flat;
  return R.default;
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
const FAQ_MSGS = {
  "en-US": "All four products are 100% natural, organic, and salon-professional grade — Caribbean formulated. Formula Exclusiva $65 all-in-one treatment. Laciador $48 hair styler. Gotero $42 hair gel. Gotika $54 color treatment.",
  "es-ES": "Los cuatro productos son 100% naturales, orgánicos y de grado profesional — formulados en el Caribe. Formula Exclusiva $65 tratamiento todo en uno. Laciador $48 estilizador. Gotero $42 gel. Gotika $54 tratamiento de color.",
  "fr-FR": "Les quatre produits sont 100% naturels, biologiques et de qualité salon — formulés aux Caraïbes. Formula Exclusiva $65 soin tout-en-un. Laciador $48 stylisant. Gotero $42 gel. Gotika $54 traitement couleur.",
  "pt-BR": "Os quatro produtos são 100% naturais, orgânicos e de grau profissional — formulados no Caribe. Formula Exclusiva $65 tratamento completo. Laciador $48 finalizador. Gotero $42 gel. Gotika $54 tratamento de cor.",
  "de-DE": "Alle vier Produkte sind 100% natürlich, biologisch und salonprofessionell — karibisch formuliert. Formula Exclusiva $65 All-in-one. Laciador $48 Styler. Gotero $42 Gel. Gotika $54 Farbbehandlung.",
  "ar-SA": "المنتجات الأربعة طبيعية 100%، عضوية ومستوى صالون احترافي — مُصاغة في الكاريبي. فورمولا إكسكلوسيفا $65 علاج شامل. لاسيادور $48 مُصفف. غوتيرو $42 جل. غوتيكا $54 علاج للون.",
  "zh-CN": "四款产品均为100%天然有机、沙龙专业级，源自加勒比配方。Formula Exclusiva $65全效护理，Laciador $48造型产品，Gotero $42发胶，Gotika $54护色产品。",
  "hi-IN": "चारों उत्पाद 100% प्राकृतिक, जैविक और सैलून-पेशेवर स्तर के हैं — कैरेबियन फॉर्मूला। Formula Exclusiva $65 ऑल-इन-वन। Laciador $48 स्टाइलर। Gotero $42 जेल। Gotika $54 रंग उपचार।"
};
const CONTACT_MSGS = {
  "en-US": "To speak with one of our professional hair consultants, please email us at support at hairexpert dot com. We'd love to find your perfect product together.",
  "es-ES": "Para hablar con uno de nuestros consultores, escríbenos a support arroba hairexpert punto com. Nos encantaría encontrar tu producto perfecto juntos.",
  "fr-FR": "Pour parler à l'un de nos consultants, envoyez-nous un email à support chez hairexpert point com. Nous aimerions trouver votre produit parfait ensemble.",
  "pt-BR": "Para falar com um de nossos consultores, envie um e-mail para support em hairexpert ponto com. Adoraríamos encontrar seu produto perfeito juntos.",
  "de-DE": "Um mit einem unserer Haarberater zu sprechen, schreiben Sie uns an support bei hairexpert Punkt com. Wir helfen Ihnen gerne, das perfekte Produkt zu finden.",
  "ar-SA": "للتحدث مع أحد مستشارينا، راسلنا على support في hairexpert نقطة com. يسعدنا مساعدتك في إيجاد منتجك المثالي.",
  "zh-CN": "如需与我们的专业发型顾问交流，请发邮件至 support@hairexpert.com，我们很乐意为您找到最合适的产品。",
  "hi-IN": "हमारे पेशेवर बाल सलाहकारों से बात करने के लिए, support@hairexpert.com पर ईमेल करें। हम आपके लिए सही उत्पाद खोजने में मदद करेंगे।"
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
