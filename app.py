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
transition:transform 0.1s linear;
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
let audioContext, analyser, micSource;
let currentColor=[0,255,200];
let activeAnimation=null;

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
// REAL MICROPHONE REACTIVE PULSE
// ======================

function startMicReactivePulse(stream){
audioContext=new (window.AudioContext||window.webkitAudioContext)();
analyser=audioContext.createAnalyser();
micSource=audioContext.createMediaStreamSource(stream);
micSource.connect(analyser);

analyser.fftSize=256;
let buffer=new Uint8Array(analyser.frequencyBinCount);

function react(){
if(state==="listening"){
analyser.getByteFrequencyData(buffer);
let sum=0;
for(let i=0;i<buffer.length;i++) sum+=buffer[i];
let avg=sum/buffer.length;
let scale=1+(avg/500);
halo.style.transform=`scale(${scale})`;
}
requestAnimationFrame(react);
}
react();
}

// AI voice pulse
function aiPulse(){
if(state==="speaking"){
let scale=1+Math.sin(Date.now()*0.004)*0.1;
halo.style.transform=`scale(${scale})`;
requestAnimationFrame(aiPulse);
}
}

// ======================
// NEW CLICK SOUND ONLY
// ======================

function playClick(){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();

osc.type="square";
osc.frequency.setValueAtTime(520,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(220,ctx.currentTime+0.2);

gain.gain.setValueAtTime(0.25,ctx.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.25);

osc.connect(gain);
gain.connect(ctx.destination);

osc.start();
osc.stop(ctx.currentTime+0.25);
}

// ======================
// GOLDEN OUTRO (UNCHANGED)
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
// SPEECH
// ======================

function speak(text){
speechSynthesis.cancel();

let voices=speechSynthesis.getVoices();
let selected=voices.find(v=>!v.name.toLowerCase().includes("uk"));

const utter=new SpeechSynthesisUtterance(text);
if(selected) utter.voice=selected;
utter.rate=0.95;
utter.pitch=1.05;

state="speaking";
animateColor([0,200,255]);
aiPulse();

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

playClick();
animateColor([255,210,80]);
state="listening";

navigator.mediaDevices.getUserMedia({audio:true}).then(stream=>{
startMicReactivePulse(stream);
});

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

// ======================
// PROCESS
// ======================

function processTranscript(text){
if(!text || text.length<3){
speak("I didn't quite understand what you said. Could you describe dryness, oiliness, damage, tangling, color loss, volume issues or shedding?");
return;
}

speak("Thank you. I am analyzing your hair concern.");
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
