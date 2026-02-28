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

// ================= COLOR =================

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

// ================= PULSE =================

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
scale=1+volume*3;
}

if(state==="speaking"){
scale=1+Math.sin(Date.now()*0.004)*0.12;
}

halo.style.transform=`scale(${scale})`;
requestAnimationFrame(pulseLoop);
}
pulseLoop();

// ================= SOUNDS =================

// INTRO (1.5x deeper, slightly longer so it's clearly lower)
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

// OUTRO (true original intro sound)
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

// ================= PRODUCT LOGIC =================

function chooseProduct(text){
text=text.toLowerCase();

let dry=/dry|frizz|brittle|rough|split|dehydrated/.test(text);
let damaged=/damage|break|weak|burn|chemical|overprocessed/.test(text);
let tangly=/tangle|knot|matted/.test(text);
let color=/color fade|dull|brassy|fading/.test(text);
let oily=/oily|greasy/.test(text);
let flat=/flat|lifeless|volume/.test(text);
let falling=/falling|shedding|thinning/.test(text);

let issues=[dry,damaged,tangly,color,oily,flat,falling].filter(Boolean).length;

if(issues>=2 || damaged || falling){
return "Formula Exclusiva is your ideal solution. It restores structure, hydration balance and long term strength. Price: $65.";
}

if(color){
return "Gotika restores color vibrancy and long term pigment depth. Price: $54.";
}

if(oily){
return "Gotero balances oil while maintaining scalp health. Price: $42.";
}

if(dry || flat || tangly){
return "Laciador restores smoothness and healthy bounce. Price: $48.";
}

return null;
}

// ================= VOICE =================

function getAmericanVoice(){
let voices=speechSynthesis.getVoices();
let preferred=["Google US English","Samantha","Microsoft Zira","Microsoft Jenny"];
for(let name of preferred){
let found=voices.find(v=>v.name.includes(name));
if(found) return found;
}
return voices.find(v=>v.lang==="en-US");
}

function speak(text){
speechSynthesis.cancel();

const utter=new SpeechSynthesisUtterance(text);
let voice=getAmericanVoice();
if(voice) utter.voice=voice;

utter.rate=0.95;
utter.pitch=1.03;

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

playIntro();
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
}

// ================= PROCESS =================

function processTranscript(text){
if(!text || text.length<4){
speak("I didn't quite understand. Could you be more specific like dryness, oiliness, damage or color loss?");
return;
}

let result=chooseProduct(text);

if(!result){
speak("I didn't quite understand. Could you be more specific like dryness, oiliness, damage or color loss?");
return;
}

responseBox.innerText=result;
speak(result);
}

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
