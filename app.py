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
transition:transform 0.08s linear;
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
let micStream=null;
let animationFrame=null;

let currentColor=[0,255,200];
let activeColorAnim=null;

const FADE_DURATION=1400;

// ================= COLOR FADE =================

function lerp(a,b,t){return a+(b-a)*t;}

function animateColor(target){
if(activeColorAnim) cancelAnimationFrame(activeColorAnim);

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
rgba(${r},${g},${b},0.5) 0%,
rgba(${r},${g},${b},0.35) 40%,
rgba(${r},${g},${b},0.2) 75%,
rgba(${r},${g},${b},0.1) 100%)
`;

currentColor=[r,g,b];

if(p<1){
activeColorAnim=requestAnimationFrame(step);
}
}
activeColorAnim=requestAnimationFrame(step);
}

animateColor([0,255,200]);

// ================= AUDIO REACTIVE LOOP =================

function startAudioReactive(){

if(animationFrame) cancelAnimationFrame(animationFrame);

function loop(){

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
scale=1+volume*2.5; // strong mic reaction
}

if(state==="speaking"){
scale=1+Math.sin(Date.now()*0.004)*0.1;
}

halo.style.transform=`scale(${scale})`;

animationFrame=requestAnimationFrame(loop);
}

loop();
}

// ================= NEW CLICK SOUND =================

function playClick(){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();

osc.type="triangle";
osc.frequency.setValueAtTime(700,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(350,ctx.currentTime+0.18);

gain.gain.setValueAtTime(0.3,ctx.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.2);

osc.connect(gain);
gain.connect(ctx.destination);

osc.start();
osc.stop(ctx.currentTime+0.2);
}

// ================= GOLDEN OUTRO (UNCHANGED) =================

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

// ================= SPEAK =================

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

speechSynthesis.speak(utter);

utter.onend=()=>{
playOutro();
animateColor([0,255,200]);
state="idle";
};
}

// ================= LISTEN =================

async function startListening(){

playClick();
animateColor([255,210,80]);
state="listening";

audioCtx=new (window.AudioContext||window.webkitAudioContext)();
await audioCtx.resume();

micStream=await navigator.mediaDevices.getUserMedia({audio:true});
const source=audioCtx.createMediaStreamSource(micStream);
analyser=audioCtx.createAnalyser();
analyser.fftSize=512;
dataArray=new Uint8Array(analyser.fftSize);
source.connect(analyser);

startAudioReactive();

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

// ================= PROCESS =================

function processTranscript(text){
if(!text || text.length<4){
speak("I didn't quite understand. Could you be more specific like dryness, oiliness, damage, tangling, color loss, volume issues or shedding?");
return;
}

speak("Thank you. I'm analyzing your hair concern.");
}

// ================= CLICK =================

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

startAudioReactive();

</script>
</body>
</html>
"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)
