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
transition:transform 0.04s linear;
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

let audioContext=null;
let analyser=null;
let micSource=null;
let dataArray=null;

// ================= VOICE =================

speechSynthesis.getVoices();
speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();

function getVoice(){
let voices=speechSynthesis.getVoices();
return voices.find(v=>v.lang==="en-US") || voices[0];
}

// ================= COLOR =================

let currentColor=[0,255,200];
const FADE_DURATION=1200;

function lerp(a,b,t){return a+(b-a)*t;}

function animateColor(target){
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
if(p<1) requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
}

animateColor([0,255,200]);

// ================= MIC SETUP =================

async function setupMic(){
audioContext=new (window.AudioContext||window.webkitAudioContext)();
let stream=await navigator.mediaDevices.getUserMedia({audio:true});
micSource=audioContext.createMediaStreamSource(stream);
analyser=audioContext.createAnalyser();
analyser.fftSize=1024;
micSource.connect(analyser);
dataArray=new Uint8Array(analyser.fftSize);
}

// ================= PULSE =================

function pulseLoop(){

let scale=1;

if(state==="idle"){
scale=1+Math.sin(Date.now()*0.002)*0.04;
}

if(state==="listening" && analyser){
analyser.getByteTimeDomainData(dataArray);

// RMS calculation (true amplitude)
let sum=0;
for(let i=0;i<dataArray.length;i++){
let val=(dataArray[i]-128)/128;
sum+=val*val;
}
let rms=Math.sqrt(sum/dataArray.length);

// sensitivity boost
scale=1+Math.min(rms*4,0.35);
}

if(state==="speaking"){
scale=1+Math.sin(Date.now()*0.004)*0.12;
}

halo.style.transform=`scale(${scale})`;
requestAnimationFrame(pulseLoop);
}
pulseLoop();

// ================= SOUNDS =================

function playIntro(){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();
osc.type="sine";
osc.frequency.setValueAtTime(320,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(160,ctx.currentTime+1.2);
gain.gain.setValueAtTime(0.35,ctx.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+1.3);
osc.connect(gain);
gain.connect(ctx.destination);
osc.start();
osc.stop(ctx.currentTime+1.3);
}

function playOutro(){
const ctx=new (window.AudioContext||window.webkitAudioContext)();
const osc=ctx.createOscillator();
const gain=ctx.createGain();
osc.type="sine";
osc.frequency.setValueAtTime(480,ctx.currentTime);
osc.frequency.exponentialRampToValueAtTime(240,ctx.currentTime+1.0);
gain.gain.setValueAtTime(0.3,ctx.currentTime);
gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+1.1);
osc.connect(gain);
gain.connect(ctx.destination);
osc.start();
osc.stop(ctx.currentTime+1.1);
}

// ================= SPEAK =================

function speak(text){
state="speaking";
animateColor([0,200,255]);

const utter=new SpeechSynthesisUtterance(text);
utter.voice=getVoice();
utter.rate=0.95;
utter.pitch=1.02;

speechSynthesis.speak(utter);

utter.onend=()=>{
playOutro();
animateColor([0,255,200]);
state="idle";
};
}

// ================= PRODUCT LOGIC =================

function chooseProduct(text){
text=text.toLowerCase();

if(/all.?in.?one|everything|complete|total repair/.test(text))
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

// ================= PROCESS =================

function processTranscript(text){
if(!text || text.length<3){
speak("I didn't quite understand. Could you describe dryness, oiliness, damage or color concerns?");
return;
}
let result=chooseProduct(text);
if(!result){
speak("I didn't quite understand. Could you describe dryness, oiliness, damage or color concerns?");
return;
}
responseBox.innerText=result;
speak(result);
}

// ================= LISTEN =================

async function startListening(){

if(!audioContext) await setupMic();

playIntro();
animateColor([255,210,80]);
state="listening";
transcript="";

const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
recognition=new SpeechRecognition();
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

// ================= CLICK =================

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

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)
