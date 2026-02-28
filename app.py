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
transition:transform 0.05s linear;
}

#response{
margin-top:30px;
width:75%;
text-align:center;
font-size:18px;
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
<option value="pt-BR">Português</option>
<option value="fr-FR">Français</option>
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

let selectedLang = "en-US";
let recognition;
let state="idle";
let transcript="";
let silenceTimer;

let audioCtx, analyser, micStream, dataArray;

let premiumVoice;

/* ================= INITIAL GLOW ================= */

let currentColor=[0,255,200];

function animateColor(target){
let start=[...currentColor];
let duration=1000;
let startTime=performance.now();

function frame(now){
let p=Math.min((now-startTime)/duration,1);

let r=Math.floor(start[0]+(target[0]-start[0])*p);
let g=Math.floor(start[1]+(target[1]-start[1])*p);
let b=Math.floor(start[2]+(target[2]-start[2])*p);

halo.style.background=
`radial-gradient(circle, rgba(${r},${g},${b},0.75) 0%, rgba(${r},${g},${b},0.15) 70%)`;

halo.style.boxShadow=
`0 0 120px rgba(${r},${g},${b},0.9),
 0 0 240px rgba(${r},${g},${b},0.6),
 0 0 360px rgba(${r},${g},${b},0.4)`;

if(p<1) requestAnimationFrame(frame);
}

currentColor=target;
requestAnimationFrame(frame);
}

animateColor([0,255,200]);

/* ================= PULSE ================= */

function pulse(){
let scale=1;

if(state==="idle"){
scale=1+Math.sin(Date.now()*0.002)*0.04;
}

if(state==="listening" && analyser){
analyser.getByteTimeDomainData(dataArray);
let sum=0;
for(let i=0;i<dataArray.length;i++){
let v=(dataArray[i]-128)/128;
sum+=v*v;
}
let rms=Math.sqrt(sum/dataArray.length);
scale=1+Math.min(rms*4,0.35);
}

if(state==="speaking"){
scale=1+Math.sin(Date.now()*0.0035)*0.1;
}

halo.style.transform=`scale(${scale})`;
requestAnimationFrame(pulse);
}
pulse();

/* ================= MIC ================= */

async function initMic(){
if(audioCtx) return;

audioCtx=new (window.AudioContext||window.webkitAudioContext)();
micStream=await navigator.mediaDevices.getUserMedia({audio:true});
let source=audioCtx.createMediaStreamSource(micStream);
analyser=audioCtx.createAnalyser();
analyser.fftSize=1024;
source.connect(analyser);
dataArray=new Uint8Array(analyser.fftSize);
}

/* ================= SOUNDS ================= */

function playTone(start,end,duration){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();

osc.type="sine";
osc.frequency.setValueAtTime(start,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(end,ctx.currentTime+duration);

gain.gain.setValueAtTime(0,ctx.currentTime);
gain.gain.linearRampToValueAtTime(0.4,ctx.currentTime+0.2);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+duration);

osc.connect(gain);
gain.connect(ctx.destination);

osc.start();
osc.stop(ctx.currentTime+duration);
}

/* intro deeper */
function playIntro(){ playTone(250,150,1.4); }

/* outro original */
function playOutro(){ playTone(300,180,1.4); }

/* ================= VOICE ================= */

function loadVoice(){
let voices=speechSynthesis.getVoices();

premiumVoice =
voices.find(v=>v.name.includes("Google US English")) ||
voices.find(v=>v.lang==="en-US") ||
voices[0];
}

speechSynthesis.onvoiceschanged=loadVoice;
loadVoice();

langSelect.addEventListener("change",()=>{
selectedLang=langSelect.value;
});

/* ================= SPEAK ================= */

function speak(text){
state="speaking";
animateColor([0,200,255]);

let utter=new SpeechSynthesisUtterance(text);
utter.lang=selectedLang;
utter.voice=premiumVoice;
utter.rate=0.92;

speechSynthesis.cancel();
speechSynthesis.speak(utter);

utter.onend=()=>{
playOutro();
animateColor([0,255,200]);
state="idle";
};
}

/* ================= PRODUCT LOGIC ================= */

function chooseProduct(text){
text=text.toLowerCase();

if(/all.?in.?one|complete|everything/.test(text))
return "Formula Exclusiva is your complete all-in-one restoration solution. Price: $65.";

if(/damage|weak|break/.test(text))
return "Formula Exclusiva strengthens and rebuilds hair integrity. Price: $65.";

if(/color|fade/.test(text))
return "Gotika restores color vibrancy and tone. Price: $54.";

if(/oily|greasy/.test(text))
return "Gotero balances excess oil while keeping hydration. Price: $42.";

if(/dry|frizz|brittle/.test(text))
return "Laciador restores smoothness and softness. Price: $48.";

return "Please describe dryness, oiliness, damage, or color concerns.";
}

/* ================= LISTEN ================= */

async function startListening(){
await initMic();

playIntro();
animateColor([255,210,80]);
state="listening";
transcript="";

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
recognition=new SR();
recognition.lang=selectedLang;
recognition.continuous=true;
recognition.interimResults=true;

recognition.onresult=(event)=>{
transcript="";
for(let i=0;i<event.results.length;i++){
transcript+=event.results[i][0].transcript;
}

clearTimeout(silenceTimer);
silenceTimer=setTimeout(()=>{
recognition.stop();
processTranscript(transcript);
},2000);
};

recognition.start();
}

function processTranscript(text){
let result=chooseProduct(text);
responseBox.innerText=result;
speak(result);
}

halo.addEventListener("click",()=>{
if(state==="idle"){
startListening();
}else{
recognition?.stop();
speechSynthesis.cancel();
animateColor([0,255,200]);
state="idle";
}
});

</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
