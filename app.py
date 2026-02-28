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
font-family:Arial;
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
background:rgba(0,0,0,0.7);
color:white;
border:1px solid rgba(255,255,255,0.3);
padding:7px 10px;
border-radius:8px;
font-size:13px;
cursor:pointer;
}
</style>
</head>
<body>

<div id="langBox">
<select id="langSelect">
<option value="en-US">English (US)</option>
<option value="es-ES">Spanish</option>
<option value="pt-BR">Portuguese</option>
<option value="fr-FR">French</option>
<option value="de-DE">German</option>
<option value="ar-SA">Arabic</option>
<option value="zh-CN">Mandarin</option>
<option value="hi-IN">Hindi</option>
</select>
</div>

<div class="wrapper">
<div id="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo=document.getElementById("halo");
const responseBox=document.getElementById("response");
const langSelect=document.getElementById("langSelect");

let state="idle";
let recognition=null;
let transcript="";
let silenceTimer=null;
let noSpeechTimer=null;

let audioCtx=null;
let analyser=null;
let micStream=null;
let dataArray=null;

let selectedLang="en-US";
let premiumVoice=null;

/* ================= LANGUAGE CHANGE ================= */

langSelect.addEventListener("change", async ()=>{
selectedLang=langSelect.value;
premiumVoice=null;
await loadVoice();
});

/* ================= LOAD VOICE ================= */

async function loadVoice(){
return new Promise(resolve=>{
let voices=speechSynthesis.getVoices();
if(!voices.length){
speechSynthesis.onvoiceschanged=()=>{
setVoice();
resolve();
};
}else{
setVoice();
resolve();
}
});
}

function setVoice(){
let voices=speechSynthesis.getVoices();
premiumVoice=voices.find(v=>v.lang===selectedLang);

if(!premiumVoice){
premiumVoice=voices.find(v=>v.lang.startsWith(selectedLang.split("-")[0]));
}

if(!premiumVoice){
premiumVoice=voices[0];
}
}

/* ================= COLOR FADE ================= */

let currentColor=[0,255,200];

function animateColor(target){
let start=[...currentColor];
let duration=1000;
let startTime=performance.now();

function frame(now){
let progress=Math.min((now-startTime)/duration,1);

let r=Math.floor(start[0]+(target[0]-start[0])*progress);
let g=Math.floor(start[1]+(target[1]-start[1])*progress);
let b=Math.floor(start[2]+(target[2]-start[2])*progress);

halo.style.boxShadow=
`0 0 120px rgba(${r},${g},${b},0.9),
 0 0 260px rgba(${r},${g},${b},0.6),
 0 0 380px rgba(${r},${g},${b},0.4)`;

halo.style.background=
`radial-gradient(circle, rgba(${r},${g},${b},0.65) 0%, rgba(${r},${g},${b},0.2) 70%)`;

if(progress<1) requestAnimationFrame(frame);
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
let val=(dataArray[i]-128)/128;
sum+=val*val;
}
let rms=Math.sqrt(sum/dataArray.length);
scale=1+Math.min(rms*4,0.35);
}

if(state==="speaking"){
scale=1+Math.sin(Date.now()*0.0035)*0.10;
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

/* ================= AUDIO FX ================= */

function playTone(startFreq,endFreq,duration){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();

osc.type="sine";
osc.frequency.setValueAtTime(startFreq,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(endFreq,ctx.currentTime+duration);

gain.gain.setValueAtTime(0,ctx.currentTime);
gain.gain.linearRampToValueAtTime(0.4,ctx.currentTime+0.2);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+duration);

osc.connect(gain);
gain.connect(ctx.destination);

osc.start();
osc.stop(ctx.currentTime+duration);
}

function playIntro(){ playTone(300,180,1.4); }
function playOutro(){ playTone(180,300,1.4); }

/* ================= SPEAK ================= */

function speak(text){
state="speaking";
animateColor([0,200,255]);

let utter=new SpeechSynthesisUtterance(text);
utter.lang=selectedLang;
if(premiumVoice) utter.voice=premiumVoice;
utter.rate=0.92;
utter.pitch=1.02;

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

if(/all.?in.?one|everything|complete/.test(text))
return "Formula Exclusiva is your complete all-in-one restoration solution. Price: $65.";

if(/damage|break|weak/.test(text))
return "Formula Exclusiva strengthens and rebuilds hair integrity. Price: $65.";

if(/color|brassy|fade/.test(text))
return "Gotika restores color vibrancy and tone. Price: $54.";

if(/oily|greasy/.test(text))
return "Gotero balances excess oil while keeping hydration. Price: $42.";

if(/dry|frizz|brittle/.test(text))
return "Laciador restores smoothness and softness. Price: $48.";

return null;
}

/* ================= PROCESS ================= */

function processTranscript(text){
if(!text || text.length<3){
speak("Please describe dryness, oiliness, damage, or color concerns.");
return;
}

let result=chooseProduct(text);
if(!result){
speak("Please describe dryness, oiliness, damage, or color concerns.");
return;
}

responseBox.innerText=result;
speak(result);
}

/* ================= LISTEN ================= */

async function startListening(){
await initMic();
await loadVoice();

playIntro();
animateColor([255,210,80]);
state="listening";
transcript="";

const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
recognition=new SpeechRecognition();
recognition.lang=selectedLang;
recognition.continuous=true;
recognition.interimResults=true;

recognition.onresult=function(event){

clearTimeout(noSpeechTimer);

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

noSpeechTimer=setTimeout(()=>{
if(!transcript){
recognition.stop();
processTranscript("");
}
},3500);
}

/* ================= CLICK ================= */

halo.addEventListener("click",()=>{
if(state==="idle"){
startListening();
}else{
if(recognition) recognition.stop();
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
