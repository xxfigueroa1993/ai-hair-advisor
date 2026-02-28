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

#languageSelect{
    position:absolute;
    top:20px;
    right:20px;
    padding:8px;
    font-size:14px;
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
    backdrop-filter:blur(60px);
    background:rgba(0,255,200,0.22);
    transition:transform 1.2s ease;
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

<select id="languageSelect">
<option>English</option>
<option>Spanish</option>
<option>French</option>
<option>Arabic</option>
<option>Mandarin</option>
<option>Hindi</option>
<option>Portuguese</option>
</select>

<div class="wrapper">
<div id="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo=document.getElementById("halo");
const responseBox=document.getElementById("response");

let state="idle";
let locked=false;
let currentColor=[0,255,200];
let activeAnimation=null;
let currentOsc=null;
let recognition=null;
let silenceTimer=null;
let noSpeechTimer=null;
let transcript="";

const FADE_DURATION=1750;

// ==========================
// ORIGINAL COLOR FADE ENGINE (UNCHANGED)
// ==========================

function lerp(a,b,t){ return a+(b-a)*t; }

function animateColor(targetColor,onComplete=null){

if(activeAnimation) cancelAnimationFrame(activeAnimation);

const startColor=[...currentColor];
const startTime=performance.now();

function step(now){
let progress=(now-startTime)/FADE_DURATION;
if(progress>1) progress=1;

let r=Math.floor(lerp(startColor[0],targetColor[0],progress));
let g=Math.floor(lerp(startColor[1],targetColor[1],progress));
let b=Math.floor(lerp(startColor[2],targetColor[2],progress));

halo.style.boxShadow=`
0 0 100px rgba(${r},${g},${b},0.55),
0 0 220px rgba(${r},${g},${b},0.35),
0 0 320px rgba(${r},${g},${b},0.25)
`;

halo.style.background=`
radial-gradient(circle at center,
rgba(${r},${g},${b},0.32) 0%,
rgba(${r},${g},${b},0.22) 50%,
rgba(${r},${g},${b},0.15) 75%,
rgba(${r},${g},${b},0.10) 100%)
`;

currentColor=[r,g,b];

if(progress<1){
activeAnimation=requestAnimationFrame(step);
}else{
activeAnimation=null;
if(onComplete) onComplete();
}
}

activeAnimation=requestAnimationFrame(step);
}

// ==========================
// ORIGINAL PULSE ENGINE (UNCHANGED)
// ==========================

function pulse(){
if(state==="idle"){
let scale=1+Math.sin(Date.now()*0.0012)*0.04;
halo.style.transform=`scale(${scale})`;
}
requestAnimationFrame(pulse);
}

// ==========================
// ORIGINAL CLICK SOUND (UNCHANGED)
// ==========================

function playClickSound(){

if(currentOsc){
currentOsc.stop();
currentOsc=null;
}

const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();

osc.type="sine";
osc.frequency.setValueAtTime(220,ctx.currentTime);
osc.frequency.linearRampToValueAtTime(300,ctx.currentTime+1.75);

gain.gain.setValueAtTime(0.12,ctx.currentTime);
gain.gain.linearRampToValueAtTime(0.001,ctx.currentTime+1.75);

osc.connect(gain);
gain.connect(ctx.destination);

osc.start();
osc.stop(ctx.currentTime+1.75);

currentOsc=osc;
}

// ==========================
// ORIGINAL COMPLETION SOUND (UNCHANGED)
// ==========================

function playCompletionSound(){

const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();

osc.type="triangle";
osc.frequency.setValueAtTime(600,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(1200,ctx.currentTime+0.4);

gain.gain.setValueAtTime(0.15,ctx.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.6);

osc.connect(gain);
gain.connect(ctx.destination);

osc.start();
osc.stop(ctx.currentTime+0.6);
}

// ==========================
// PRODUCT ENGINE
// ==========================

function chooseProduct(text){

text=text.toLowerCase();

if(text.length<12) return null;

if(text.includes("under 16") && text.includes("color")){
return "For clients under sixteen experiencing pigment changes, we recommend consulting a licensed medical professional.";
}

if(text.includes("dry"))
return "Laciador restores moisture balance and smoothness. Price: $48.";

if(text.includes("oily"))
return "Gotero balances sebum production without stripping hydration. Price: $42.";

if(text.includes("damaged") || text.includes("fall"))
return "Formula Exclusiva rebuilds structural strength and elasticity. Price: $65.";

if(text.includes("color"))
return "Gotika restores vibrancy and pigment longevity. Price: $54.";

return null;
}

// ==========================
// VOICE (NO FORCED BRITISH)
// ==========================

function speak(text){

speechSynthesis.cancel();

const utter=new SpeechSynthesisUtterance(text);
utter.rate=0.95;
utter.pitch=1.02;
utter.volume=1;

state="speaking";

speechSynthesis.speak(utter);

utter.onend=()=>{
playCompletionSound();
setTimeout(resetToIdle,400);
};
}

// ==========================
// RESET
// ==========================

function resetToIdle(){
state="idle";
animateColor([0,255,200],()=>{
responseBox.innerText="Tap and describe your hair concern.";
});
}

// ==========================
// SPEECH RECOGNITION
// ==========================

function startListening(){

const SpeechRecognition =
window.SpeechRecognition || window.webkitSpeechRecognition;

recognition=new SpeechRecognition();
recognition.continuous=true;
recognition.interimResults=true;

transcript="";
state="listening";

recognition.onresult=function(event){

clearTimeout(silenceTimer);
clearTimeout(noSpeechTimer);

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

noSpeechTimer=setTimeout(()=>{
if(transcript.trim().length<5){
recognition.stop();
speak("I didn’t hear anything. Could you describe your hair concern?");
}
},3500);

}

// ==========================
// PROCESS SPEECH
// ==========================

function processTranscript(text){

if(!text || text.length<10){
speak("I didn’t catch that clearly. Could you describe a specific hair concern?");
return;
}

responseBox.innerText="Analyzing...";

setTimeout(()=>{
animateColor([0,255,255],()=>{

let result=chooseProduct(text);

if(!result){
speak("I didn’t catch a specific hair issue. Could you clarify dryness, oiliness, damage, color fading, or shedding?");
return;
}

responseBox.innerText=result;
speak(result);

});
},3000);
}

// ==========================
// CLICK
// ==========================

halo.addEventListener("click",()=>{

if(state==="listening"){
recognition.stop();
resetToIdle();
return;
}

if(state==="speaking"){
speechSynthesis.cancel();
resetToIdle();
return;
}

playClickSound();
animateColor([255,210,80],()=>{
startListening();
});
});

// INIT
animateColor([0,255,200]);
pulse();

</script>
</body>
</html>
"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
