import os
from flask import Flask

os.environ["PYTHONUNBUFFERED"] = "1"
app = Flask(__name__)

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Luxury Hair AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

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
width:420px;
height:420px;
display:flex;
justify-content:center;
align-items:center;
}

#halo{
width:300px;
height:300px;
border-radius:50%;
cursor:pointer;
backdrop-filter:blur(80px);
transition:transform 0.2s ease;
}

#response{
margin-top:40px;
width:70%;
text-align:center;
font-size:18px;
}
</style>
</head>
<body>

<div class="wrapper">
<div id="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo=document.getElementById("halo");
const responseBox=document.getElementById("response");

let state="idle";
let recognition=null;
let transcript="";
let silenceTimer=null;
let activeAnimation=null;
let currentColor=[0,255,200];

const FADE_DURATION=1400;

// ======================
// SMOOTH COLOR FADE
// ======================

function lerp(a,b,t){return a+(b-a)*t;}

function animateColor(target){

if(activeAnimation) cancelAnimationFrame(activeAnimation);

const start=[...currentColor];
const startTime=performance.now();

function step(now){
let p=(now-startTime)/FADE_DURATION;
if(p>1)p=1;

let r=Math.floor(lerp(start[0],target[0],p));
let g=Math.floor(lerp(start[1],target[1],p));
let b=Math.floor(lerp(start[2],target[2],p));

halo.style.boxShadow=`
0 0 150px rgba(${r},${g},${b},0.85),
0 0 280px rgba(${r},${g},${b},0.55),
0 0 380px rgba(${r},${g},${b},0.35)
`;

halo.style.background=`
radial-gradient(circle at center,
rgba(${r},${g},${b},0.48) 0%,
rgba(${r},${g},${b},0.35) 40%,
rgba(${r},${g},${b},0.20) 75%,
rgba(${r},${g},${b},0.10) 100%)
`;

currentColor=[r,g,b];

if(p<1) activeAnimation=requestAnimationFrame(step);
}

activeAnimation=requestAnimationFrame(step);
}

animateColor([0,255,200]);

// ======================
// REACTIVE PULSE
// ======================

function pulse(){
let intensity=0.04;
if(state==="listening") intensity=0.09;
if(state==="speaking") intensity=0.11;

let scale=1+Math.sin(Date.now()*0.002)*intensity;
halo.style.transform=`scale(${scale})`;

requestAnimationFrame(pulse);
}
pulse();

// ======================
// NEW INTRO SOUND
// ======================

function playIntro(){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();
osc.type="sawtooth";
osc.frequency.setValueAtTime(180,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(420,ctx.currentTime+0.6);
gain.gain.setValueAtTime(0.18,ctx.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.8);
osc.connect(gain);
gain.connect(ctx.destination);
osc.start();
osc.stop(ctx.currentTime+0.8);
}

// ======================
// NEW OUTRO SOUND
// ======================

function playOutro(){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();
osc.type="triangle";
osc.frequency.setValueAtTime(900,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(400,ctx.currentTime+0.5);
gain.gain.setValueAtTime(0.2,ctx.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.7);
osc.connect(gain);
gain.connect(ctx.destination);
osc.start();
osc.stop(ctx.currentTime+0.7);
}

// ======================
// PRODUCT INTELLIGENCE
// ======================

function chooseProduct(text){

text=text.toLowerCase();

let issues=0;

let dry=/dry|frizz|brittle|rough|no moisture/.test(text);
let damaged=/damaged|break|weak|heat|burn/.test(text);
let tangly=/tangle|knot|matted/.test(text);
let color=/color fade|dull|lost color/.test(text);
let oily=/oily|greasy|oil buildup/.test(text);
let flat=/flat|no bounce|lifeless/.test(text);
let falling=/falling|shedding|thinning/.test(text);

[dry,damaged,tangly,color,oily,flat,falling].forEach(v=>{if(v)issues++;});

if(issues>=2){
return "Formula Exclusiva is an all in one natural professional salon hair treatment designed to restore strength, hydration balance, elasticity and scalp integrity across multiple hair concerns. Price: $65.";
}

if(damaged||falling){
return "Formula Exclusiva is an all in one natural professional salon hair treatment that rebuilds structural weakness and supports healthier growth. Price: $65.";
}

if(color){
return "Gotika is an all natural professional hair color treatment restoring vibrancy and protecting pigment longevity. Price: $54.";
}

if(oily){
return "Gotero is an all natural professional hair gel that regulates excess oil and keeps the scalp balanced without dryness. Price: $42.";
}

if(tangly||flat||dry){
return "Laciador is an all natural professional hair styler improving smoothness, manageability and bounce. Price: $48.";
}

return null;
}

// ======================
// FRIENDLY PROFESSIONAL VOICE
// ======================

function speak(text){

speechSynthesis.cancel();

let voices=speechSynthesis.getVoices();
let selected=voices.find(v=>v.name.toLowerCase().includes("female") && !v.name.toLowerCase().includes("uk"));

const utter=new SpeechSynthesisUtterance(text);
if(selected) utter.voice=selected;

utter.rate=0.95;
utter.pitch=1.05;

state="speaking";
animateColor([0,200,255]);

speechSynthesis.speak(utter);

utter.onend=()=>{
playOutro();
animateColor([0,255,200]);
state="idle";
};
}

// ======================
// LISTEN
// ======================

function startListening(){

playIntro();
animateColor([255,210,80]);
state="listening";

const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
recognition=new SpeechRecognition();
recognition.continuous=true;
recognition.interimResults=true;
transcript="";

recognition.onresult=function(event){

clearTimeout(silenceTimer);

for(let i=event.resultIndex;i<event.results.length;i++){
if(event.results[i].isFinal){
transcript+=event.results[i][0].transcript+" ";
}
}

silenceTimer=setTimeout(()=>{
recognition.stop();
processTranscript(transcript.trim());
},2500);
};

recognition.start();
}

// ======================
// PROCESS
// ======================

function processTranscript(text){

if(!text || text.length<6){
speak("I didn’t quite understand what you said. Could you be more specific like dryness, oily scalp, damage, tangling, color loss, volume issues or shedding?");
return;
}

let result=chooseProduct(text);

if(!result){
speak("I didn’t quite understand what you said. Could you be more specific like dryness, oily scalp, damage, tangling, color loss, volume issues or shedding?");
return;
}

responseBox.innerText=result;
speak(result);
}

// ======================
// CLICK
// ======================

halo.addEventListener("click",()=>{
if(state==="idle"){
startListening();
}else{
speechSynthesis.cancel();
if(recognition) recognition.stop();
animateColor([0,255,200]);
state="idle";
}
});

</script>
</body>
</html>
"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
