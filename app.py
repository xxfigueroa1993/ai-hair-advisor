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
backdrop-filter:blur(90px);
transition:transform 0.05s linear;
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
let noSpeechTimer=null;

let audioCtx=null;
let analyser=null;
let dataArray=null;
let micSource=null;

let currentColor=[0,255,200];
let colorAnim=null;

const FADE_DURATION=1200;

// ===================== COLOR FADE =====================

function lerp(a,b,t){return a+(b-a)*t;}

function animateColor(target){
if(colorAnim) cancelAnimationFrame(colorAnim);

const start=[...currentColor];
const startTime=performance.now();

function frame(now){
let p=(now-startTime)/FADE_DURATION;
if(p>1)p=1;

let r=Math.floor(lerp(start[0],target[0],p));
let g=Math.floor(lerp(start[1],target[1],p));
let b=Math.floor(lerp(start[2],target[2],p));

halo.style.boxShadow=`
0 0 160px rgba(${r},${g},${b},0.9),
0 0 320px rgba(${r},${g},${b},0.6),
0 0 420px rgba(${r},${g},${b},0.4)
`;

halo.style.background=`
radial-gradient(circle,
rgba(${r},${g},${b},0.55) 0%,
rgba(${r},${g},${b},0.4) 40%,
rgba(${r},${g},${b},0.25) 75%,
rgba(${r},${g},${b},0.1) 100%)
`;

currentColor=[r,g,b];

if(p<1) colorAnim=requestAnimationFrame(frame);
}
colorAnim=requestAnimationFrame(frame);
}

animateColor([0,255,200]);

// ===================== REACTIVE PULSE =====================

function pulseLoop(){
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
let volume=Math.sqrt(sum/dataArray.length);
scale=1+volume*3; // strong mic reaction
}

if(state==="speaking"){
scale=1+Math.sin(Date.now()*0.004)*0.12;
}

halo.style.transform=`scale(${scale})`;
requestAnimationFrame(pulseLoop);
}

pulseLoop();

// ===================== INTRO SOUND (SLOW LUXURY) =====================

function playClick(){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();

osc.type="sine";
osc.frequency.setValueAtTime(480,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(220,ctx.currentTime+0.9);

gain.gain.setValueAtTime(0.3,ctx.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+1);

osc.connect(gain);
gain.connect(ctx.destination);

osc.start();
osc.stop(ctx.currentTime+1);
}

// ===================== OUTRO SOUND (SLOW GOLDEN) =====================

function playOutro(){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();

osc.type="triangle";
osc.frequency.setValueAtTime(1100,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(500,ctx.currentTime+1.1);

gain.gain.setValueAtTime(0.3,ctx.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+1.3);

osc.connect(gain);
gain.connect(ctx.destination);

osc.start();
osc.stop(ctx.currentTime+1.3);
}

// ===================== PRODUCT LOGIC =====================

function chooseProduct(text){

text=text.toLowerCase();

let dry=/dry|frizz|brittle|rough|split/.test(text);
let damaged=/damaged|break|weak|burn/.test(text);
let tangly=/tangle|knot/.test(text);
let color=/color fade|dull|lost color/.test(text);
let oily=/oily|greasy|oil buildup/.test(text);
let flat=/flat|lifeless|no bounce/.test(text);
let falling=/falling|shedding|thinning/.test(text);

let count=[dry,damaged,tangly,color,oily,flat,falling].filter(Boolean).length;

if(count>=2 || damaged || falling){
return "Formula Exclusiva is an all in one natural professional salon hair treatment restoring strength, hydration balance, elasticity and scalp integrity. Price: $65.";
}
if(color){
return "Gotika is an all natural professional hair color treatment restoring vibrancy and protecting pigment longevity. Price: $54.";
}
if(oily){
return "Gotero is an all natural professional hair gel regulating excess oil while preserving moisture. Price: $42.";
}
if(dry||flat||tangly){
return "Laciador is an all natural professional hair styler improving smoothness, manageability and bounce. Price: $48.";
}
return null;
}

// ===================== SPEAK =====================

function speak(text){

speechSynthesis.cancel();

let voices=speechSynthesis.getVoices();
let voice=voices.find(v=>!v.name.toLowerCase().includes("uk"));

const utter=new SpeechSynthesisUtterance(text);
if(voice) utter.voice=voice;
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

// ===================== LISTEN =====================

async function startListening(){

playClick();
animateColor([255,210,80]);
state="listening";

audioCtx=new (window.AudioContext||window.webkitAudioContext)();
await audioCtx.resume();

let stream=await navigator.mediaDevices.getUserMedia({audio:true});
micSource=audioCtx.createMediaStreamSource(stream);
analyser=audioCtx.createAnalyser();
analyser.fftSize=512;
dataArray=new Uint8Array(analyser.fftSize);
micSource.connect(analyser);

const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
recognition=new SpeechRecognition();
recognition.continuous=true;
recognition.interimResults=true;
transcript="";

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
if(transcript.trim().length<3){
recognition.stop();
speak("I can't hear you. Could you describe your hair concern?");
}
},3500);
}

// ===================== PROCESS =====================

function processTranscript(text){

if(!text || text.length<4){
speak("I didn't quite understand. Could you be more specific like dryness, oiliness, damage, tangling, color loss, volume issues or shedding?");
return;
}

let result=chooseProduct(text);

if(!result){
speak("I didn't quite understand. Could you be more specific like dryness, oiliness, damage, tangling, color loss, volume issues or shedding?");
return;
}

responseBox.innerText=result;
speak(result);
}

// ===================== CLICK =====================

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
    app.run(host="0.0.0.0", port=port)
