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

#halo{
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
top:18px;
right:22px;
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
<div id="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo = document.getElementById("halo");
const responseBox = document.getElementById("response");
const langSelect = document.getElementById("langSelect");

let selectedLang="en-US";
let state="idle";
let transcript="";
let recognition=null;
let silenceTimer=null;
let lastSpeechTime=0;
const SILENCE_DELAY=2500;

let premiumVoice=null;
let voicesLoaded=false;

/* ================= PREMIUM VOICE ================= */

function selectVoice(){
const voices=speechSynthesis.getVoices();
if(!voices.length) return;

voicesLoaded=true;

const matches=voices.filter(v=>v.lang===selectedLang);

premiumVoice=
matches.find(v=>v.name.includes("Google")) ||
matches.find(v=>v.name.includes("Microsoft")) ||
matches.find(v=>!v.localService) ||
matches[0] ||
voices[0];
}

speechSynthesis.onvoiceschanged=selectVoice;
setTimeout(selectVoice,500);

/* ================= LANGUAGE RESPONSES ================= */

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

/* ================= COLOR + PULSE SYSTEM ================= */

let baseColor=[0,255,200];
let pulseSize=0;
let pulseDirection=1;

function drawSphere(r,g,b){
halo.style.background=
`radial-gradient(circle,
 rgba(${r},${g},${b},0.9) 0%,
 rgba(${r},${g},${b},0.25) 60%,
 rgba(${r},${g},${b},0.08) 100%)`;

halo.style.boxShadow=
`0 0 ${120+pulseSize}px rgba(${r},${g},${b},0.9),
 0 0 ${240+pulseSize}px rgba(${r},${g},${b},0.6),
 0 0 ${360+pulseSize}px rgba(${r},${g},${b},0.3)`;
}

function ambientPulse(){
if(state==="idle"){
pulseSize+=0.5*pulseDirection;
if(pulseSize>20||pulseSize<0) pulseDirection*=-1;
drawSphere(...baseColor);
}
requestAnimationFrame(ambientPulse);
}

ambientPulse();

/* ================= SPEAK ================= */

function speak(text){

state="speaking";
baseColor=[0,200,255];

let utter=new SpeechSynthesisUtterance(text);
utter.lang=selectedLang;
utter.voice=premiumVoice;
utter.rate=0.92;

speechSynthesis.cancel();
speechSynthesis.speak(utter);

let speakPulse=setInterval(()=>{
pulseSize=Math.random()*30;
},80);

utter.onend=()=>{
clearInterval(speakPulse);
baseColor=[0,255,200];
state="idle";
};
}

/* ================= PRODUCT LOGIC ================= */

function chooseProduct(text){

const langPack=responses[selectedLang]||responses["en-US"];
text=text.toLowerCase();

if(!text||text.length<2) return langPack.nothing;
if(/all|todo/.test(text)) return langPack.allinone;
if(/damage|daño/.test(text)) return langPack.damage;
if(/color/.test(text)) return langPack.color;
if(/oil|grasa/.test(text)) return langPack.oil;
if(/dry|seco/.test(text)) return langPack.dry;

return langPack.nothing;
}

/* ================= LISTEN ================= */

function startListening(){

transcript="";
lastSpeechTime=Date.now();
state="listening";
baseColor=[255,210,80];

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
recognition=new SR();
recognition.lang=selectedLang;
recognition.continuous=true;
recognition.interimResults=true;

recognition.onresult=(event)=>{
transcript="";
for(let i=0;i<event.results.length;i++)
transcript+=event.results[i][0].transcript;

lastSpeechTime=Date.now();
clearTimeout(silenceTimer);
silenceTimer=setTimeout(checkSilence,SILENCE_DELAY);

pulseSize=Math.random()*40; // reactive pulse while speaking
};

recognition.start();
}

function checkSilence(){
if(Date.now()-lastSpeechTime>=SILENCE_DELAY){
recognition.stop();
processTranscript();
}else{
silenceTimer=setTimeout(checkSilence,SILENCE_DELAY);
}
}

function processTranscript(){
let result=chooseProduct(transcript);
responseBox.innerText=result;
speak(result);
}

/* ================= CLICK ================= */

halo.addEventListener("click",()=>{
if(state==="idle") startListening();
else{
try{recognition.stop();}catch(e){}
state="idle";
baseColor=[0,255,200];
}
});

langSelect.addEventListener("change",()=>{
selectedLang=langSelect.value;
selectVoice();
});

drawSphere(...baseColor);

</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
