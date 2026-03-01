import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Luxury Hair AI</title>

<style>
body{
margin:0;
height:100vh;
display:flex;
justify-content:center;
align-items:center;
flex-direction:column;
background:#05080a;
font-family:Arial, sans-serif;
color:white;
overflow:hidden;
}

.wrapper{
width:380px;
height:380px;
display:flex;
justify-content:center;
align-items:center;
}

#sphere{
width:280px;
height:280px;
border-radius:50%;
cursor:pointer;
transition:all 0.15s ease;
}

#response{
margin-top:30px;
width:75%;
text-align:center;
font-size:18px;
min-height:60px;
}

#langBox{
position:absolute;
top:20px;
right:25px;
}

#langSelect{
background:rgba(0,0,0,0.6);
color:white;
border:1px solid rgba(255,255,255,0.3);
padding:6px 10px;
border-radius:8px;
font-size:13px;
cursor:pointer;
}
</style>
</head>
<body>

<div id="langBox">
<select id="langSelect">
<option value="en-US">English</option>
<option value="es-ES">Español</option>
<option value="fr-FR">Français</option>
<option value="pt-BR">Português</option>
<option value="de-DE">Deutsch</option>
<option value="ar-SA">العربية</option>
<option value="zh-CN">中文</option>
<option value="hi-IN">हिन्दी</option>
</select>
</div>

<div class="wrapper">
<div id="sphere"></div>
</div>

<div id="response">Tap the sphere and describe your hair concern.</div>

<script>

const sphere = document.getElementById("sphere");
const responseBox = document.getElementById("response");
const langSelect = document.getElementById("langSelect");

let state = "idle";
let selectedLang = "en-US";
let transcript = "";
let recognition;
let silenceTimer;
let lastSpeechTime = 0;
const SILENCE_DELAY = 2500;

let voice;
let voicesLoaded=false;

/* ================= PREMIUM VOICE ================= */

function loadVoice(){
const voices=speechSynthesis.getVoices();
if(!voices.length) return;

voicesLoaded=true;

const matches=voices.filter(v=>v.lang===selectedLang);

voice=
matches.find(v=>v.name.includes("Google")) ||
matches.find(v=>v.name.includes("Microsoft")) ||
matches.find(v=>!v.localService) ||
matches[0] ||
voices[0];
}

speechSynthesis.onvoiceschanged=loadVoice;
setTimeout(loadVoice,500);

/* ================= COLOR + PULSE ================= */

let baseColor=[0,255,200];
let pulse=0;
let direction=1;

function renderSphere(){
sphere.style.background=
`radial-gradient(circle,
 rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.9) 0%,
 rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.2) 65%,
 rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.05) 100%)`;

sphere.style.boxShadow=
`0 0 ${120+pulse}px rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.9),
 0 0 ${240+pulse}px rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.6),
 0 0 ${360+pulse}px rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.3)`;
}

function ambientPulse(){
if(state==="idle"){
pulse += 0.4*direction;
if(pulse>18||pulse<0) direction*=-1;
renderSphere();
}
requestAnimationFrame(ambientPulse);
}
ambientPulse();

/* ================= RESPONSES ================= */

const responses={
"en-US":{
nothing:"I didn’t hear anything. Please describe dryness, oiliness, damage, or color.",
allinone:"Formula Exclusiva is your complete all-in-one restoration solution. Price: $65.",
damage:"Formula Exclusiva strengthens and rebuilds hair integrity. Price: $65.",
color:"Gotika restores color vibrancy and tone. Price: $54.",
oil:"Gotero balances excess oil while keeping hydration. Price: $42.",
dry:"Laciador restores smoothness and softness. Price: $48."
},
"es-ES":{
nothing:"No escuché nada. Describe sequedad, grasa, daño o color.",
allinone:"Formula Exclusiva es tu solución completa todo-en-uno. Precio: $65.",
damage:"Formula Exclusiva fortalece y repara el cabello. Precio: $65.",
color:"Gotika restaura la vitalidad del color. Precio: $54.",
oil:"Gotero equilibra la grasa del cabello. Precio: $42.",
dry:"Laciador restaura suavidad y brillo. Precio: $48."
}
};

function chooseProduct(text){
const pack=responses[selectedLang]||responses["en-US"];
text=text.toLowerCase();

if(!text||text.length<2) return pack.nothing;
if(/all|todo/.test(text)) return pack.allinone;
if(/damage|daño/.test(text)) return pack.damage;
if(/color/.test(text)) return pack.color;
if(/oil|grasa/.test(text)) return pack.oil;
if(/dry|seco/.test(text)) return pack.dry;

return pack.nothing;
}

/* ================= SPEAK ================= */

function speak(text){
state="speaking";
baseColor=[0,200,255];

let utter=new SpeechSynthesisUtterance(text);
utter.lang=selectedLang;
utter.voice=voice;
utter.rate=0.92;

speechSynthesis.cancel();
speechSynthesis.speak(utter);

let speakPulse=setInterval(()=>{ pulse=Math.random()*35; renderSphere(); },70);

utter.onend=()=>{
clearInterval(speakPulse);
state="idle";
baseColor=[0,255,200];
};
}

/* ================= LISTEN ================= */

function startListening(){
transcript="";
state="listening";
baseColor=[255,200,60];
lastSpeechTime=Date.now();

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
recognition=new SR();
recognition.lang=selectedLang;
recognition.continuous=true;
recognition.interimResults=true;

recognition.onresult=(e)=>{
transcript="";
for(let i=0;i<e.results.length;i++)
transcript+=e.results[i][0].transcript;

lastSpeechTime=Date.now();
clearTimeout(silenceTimer);
silenceTimer=setTimeout(checkSilence,SILENCE_DELAY);

pulse=Math.random()*45;
renderSphere();
};

recognition.start();
}

function checkSilence(){
if(Date.now()-lastSpeechTime>=SILENCE_DELAY){
recognition.stop();
process();
}else{
silenceTimer=setTimeout(checkSilence,SILENCE_DELAY);
}
}

function process(){
let result=chooseProduct(transcript);
responseBox.innerText=result;
speak(result);
}

/* ================= CLICK ================= */

sphere.addEventListener("click",()=>{
if(state==="idle") startListening();
});

langSelect.addEventListener("change",()=>{
selectedLang=langSelect.value;
loadVoice();
});

renderSphere();

</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
