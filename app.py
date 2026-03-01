import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Hair Expert Advisor</title>

<style>
body{
margin:0;
background:black;
font-family:Arial,Helvetica,sans-serif;
color:white;
display:flex;
flex-direction:column;
align-items:center;
justify-content:center;
height:100vh;
overflow:hidden;
}

select{
position:absolute;
top:20px;
right:20px;
padding:8px;
background:black;
color:white;
border:1px solid #444;
}

#modeToggle{
position:absolute;
top:20px;
left:20px;
padding:8px 14px;
background:black;
color:white;
border:1px solid #444;
cursor:pointer;
}

.wrapper{
position:relative;
width:300px;
height:300px;
display:flex;
align-items:center;
justify-content:center;
}

#halo{
width:230px;
height:230px;
border-radius:50%;
transition:background 2s ease, box-shadow 2s ease;
cursor:pointer;
}

#response{
position:absolute;
bottom:60px;
width:70%;
text-align:center;
font-size:18px;
opacity:0.9;
}

#manualBox{
display:none;
position:absolute;
bottom:140px;
width:60%;
text-align:center;
}

input{
width:80%;
padding:10px;
border:none;
outline:none;
}

button{
padding:8px 12px;
margin-top:10px;
cursor:pointer;
}
</style>
</head>

<body>

<button id="modeToggle">Switch to Manual</button>

<select id="languageSelect">
<option value="en-US">English</option>
<option value="es-ES">Spanish</option>
<option value="fr-FR">French</option>
<option value="ar-SA">Arabic</option>
<option value="zh-CN">Mandarin</option>
<option value="hi-IN">Hindi</option>
<option value="pt-PT">Portuguese</option>
</select>

<div class="wrapper">
<div id="halo"></div>
</div>

<div id="manualBox">
<input id="manualInput" placeholder="Describe your hair concern"/>
<br>
<button onclick="processManual()">Analyze</button>
</div>

<div id="response">Tap the halo and describe your hair concern.</div>

<audio id="introSound" src="https://assets.mixkit.co/sfx/preview/mixkit-interface-click-1126.mp3"></audio>
<audio id="outroSound" src="https://assets.mixkit.co/sfx/preview/mixkit-software-interface-start-2574.mp3"></audio>

<script>

const halo=document.getElementById("halo");
const responseBox=document.getElementById("response");
const languageSelect=document.getElementById("languageSelect");
const introSound=document.getElementById("introSound");
const outroSound=document.getElementById("outroSound");

let state="idle";
let recognition=null;
let silenceTimer=null;
let finalTranscript="";
let audioContext, analyser, dataArray;

// =====================
// COLOR ENGINE
// =====================

function setGlow(r,g,b){
halo.style.background=
`radial-gradient(circle at center,
rgba(${r},${g},${b},0.35) 0%,
rgba(${r},${g},${b},0.20) 50%,
rgba(${r},${g},${b},0.10) 75%,
rgba(${r},${g},${b},0.05) 100%)`;

halo.style.boxShadow=
`0 0 140px rgba(${r},${g},${b},0.6),
0 0 280px rgba(${r},${g},${b},0.4),
0 0 400px rgba(${r},${g},${b},0.3)`;
}

setGlow(0,255,200);

// =====================
// BREATHING BASE PULSE
// =====================

function breathe(){
let baseIntensity=0.025;
if(state==="listening") baseIntensity=0.05;
if(state==="speaking") baseIntensity=0.06;

let scale=1+Math.sin(Date.now()*0.0012)*baseIntensity;
halo.style.transform=`scale(${scale})`;

requestAnimationFrame(breathe);
}
breathe();

// =====================
// MIC REACTIVE ENGINE
// =====================

async function initMic(){
audioContext=new(window.AudioContext||window.webkitAudioContext)();
const stream=await navigator.mediaDevices.getUserMedia({audio:true});
const source=audioContext.createMediaStreamSource(stream);
analyser=audioContext.createAnalyser();
analyser.fftSize=256;
source.connect(analyser);
dataArray=new Uint8Array(analyser.frequencyBinCount);
react();
}

function react(){
if(!analyser) return;
analyser.getByteFrequencyData(dataArray);
let volume=dataArray.reduce((a,b)=>a+b)/dataArray.length;

if(state==="listening"){
let scale=1+(volume/500);
halo.style.transform=`scale(${scale})`;
}

requestAnimationFrame(react);
}

// =====================
// PRODUCT LOGIC
// =====================

function chooseProduct(text){
text=text.toLowerCase();

if(/color|fade|brassy/.test(text))
return "Gotika restores vibrancy and protects pigment integrity. Price: $54.";

if(/oil|greasy/.test(text))
return "Gotero regulates excess oil while preserving hydration balance. Price: $42.";

if(/dry|frizz|rough/.test(text))
return "Laciador restores smoothness, moisture, and bounce. Price: $48.";

if(/damage|break|weak|thin|loss/.test(text))
return "Formula Exclusiva rebuilds structural strength and scalp health. Price: $65.";

return "Formula Exclusiva is your safest all-in-one restoration treatment. Price: $65.";
}

// =====================
// NATURAL VOICE SELECTION
// =====================

function getBestVoice(){
let voices=speechSynthesis.getVoices();
let lang=languageSelect.value;

let filtered=voices.filter(v=>v.lang===lang && !v.name.toLowerCase().includes("robot"));

return filtered[0] || voices.find(v=>v.lang===lang) || voices[0];
}

// =====================
// SPEAK
// =====================

function speak(text){

speechSynthesis.cancel();

const utter=new SpeechSynthesisUtterance(text);
utter.lang=languageSelect.value;
utter.voice=getBestVoice();
utter.rate=0.95;
utter.pitch=1;

state="speaking";
setGlow(0,255,220);

speechSynthesis.speak(utter);

utter.onend=()=>{
outroSound.play();
state="idle";
setGlow(0,255,200);
};
}

// =====================
// PROCESS TEXT
// =====================

function processText(text){

responseBox.innerText="Analyzing...";

setTimeout(()=>{
let result=chooseProduct(text);
responseBox.innerText=result;

setTimeout(()=>{
speak(result);
},2500); // 2.5 second true silence buffer

},1200);
}

// =====================
// START LISTENING
// =====================

function startListening(){

introSound.play();

const SpeechRecognition=
window.SpeechRecognition||window.webkitSpeechRecognition;

recognition=new SpeechRecognition();
recognition.lang=languageSelect.value;
recognition.continuous=true;
recognition.interimResults=false;

finalTranscript="";

state="listening";
setGlow(255,215,100);

recognition.onresult=function(event){

clearTimeout(silenceTimer);

for(let i=event.resultIndex;i<event.results.length;i++){
if(event.results[i].isFinal){
finalTranscript+=event.results[i][0].transcript+" ";
}
}

silenceTimer=setTimeout(()=>{
recognition.stop();
processText(finalTranscript.trim());
},2500);

};

recognition.start();
initMic();
}

// =====================
// MANUAL MODE
// =====================

let manual=false;
document.getElementById("modeToggle").onclick=function(){
manual=!manual;
document.getElementById("manualBox").style.display=manual?"block":"none";
this.innerText=manual?"Switch to Voice":"Switch to Manual";
};

function processManual(){
let text=document.getElementById("manualInput").value;
if(text.length<5) return;
processText(text);
}

// =====================
// CLICK CONTROL
// =====================

halo.addEventListener("click",()=>{

if(manual) return;

if(state==="listening"){
recognition.stop();
state="idle";
setGlow(0,255,200);
return;
}

if(state==="speaking"){
speechSynthesis.cancel();
state="idle";
setGlow(0,255,200);
return;
}

startListening();
});

</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
