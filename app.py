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
<title>Hair Expert Advisor</title>

<style>
body{
margin:0;
background:#05080a;
color:white;
font-family:Arial,sans-serif;
text-align:center;
overflow:hidden;
}

#languageSelect{
margin-top:20px;
padding:8px;
border-radius:6px;
border:none;
}

.wrapper{
height:60vh;
display:flex;
justify-content:center;
align-items:center;
}

#halo{
width:280px;
height:280px;
border-radius:50%;
transition:background 1.4s ease, box-shadow 1.4s ease, transform 0.3s ease;
cursor:pointer;
}

#response{
margin-top:20px;
padding:20px;
min-height:80px;
}

</style>
</head>
<body>

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

<div id="response">Tap and describe your hair concern.</div>

<audio id="introSound" src="intro.mp3"></audio>
<audio id="outroSound" src="outro.mp3"></audio>

<script>

const halo=document.getElementById("halo");
const responseBox=document.getElementById("response");
const languageSelect=document.getElementById("languageSelect");
const introSound=document.getElementById("introSound");
const outroSound=document.getElementById("outroSound");

let state="idle";
let recognition=null;
let transcript="";
let silenceTimer=null;
let noSpeechTimer=null;

/* ================= COLOR ENGINE ================= */

function setGlow(r,g,b){
halo.style.boxShadow=`
0 0 100px rgba(${r},${g},${b},0.55),
0 0 220px rgba(${r},${g},${b},0.35),
0 0 320px rgba(${r},${g},${b},0.25)
`;

halo.style.background=`
radial-gradient(circle at center,
rgba(${r},${g},${b},0.35) 0%,
rgba(${r},${g},${b},0.20) 60%,
rgba(${r},${g},${b},0.10) 100%)
`;
}

setGlow(0,255,200);

/* ================= PULSE ================= */

function pulse(){
let intensity=0.04;
if(state==="listening") intensity=0.08;
if(state==="speaking") intensity=0.10;

let scale=1+Math.sin(Date.now()*0.002)*intensity;
halo.style.transform=`scale(${scale})`;
requestAnimationFrame(pulse);
}
pulse();

/* ================= PRODUCT ENGINE ================= */

function chooseProduct(text){

text=text.toLowerCase();

let dry=/dry|frizz|rough|brittle/.test(text);
let damaged=/damage|break|weak/.test(text);
let tangly=/tangle|knot|matted/.test(text);
let color=/color|fade|brassy/.test(text);
let oily=/oily|greasy/.test(text);
let flat=/flat|no bounce/.test(text);
let falling=/falling|thinning|shedding/.test(text);

let problems=[dry,damaged,tangly,color,oily,flat,falling].filter(Boolean).length;

if(problems===0) return null;

if(damaged || falling || problems>=3)
return "Formula Exclusiva restores structural strength, elasticity, moisture balance, and long-term scalp integrity. Price: $65.";

if(color)
return "Gotika restores vibrancy, corrects tone, and protects pigment longevity. Price: $54.";

if(oily && problems>=2)
return "Formula Exclusiva balances oil while repairing structural stress. Price: $65.";

if(oily)
return "Gotero regulates excess oil and supports scalp clarity. Price: $42.";

if(tangly && problems>=2)
return "Gotero smooths texture and reinforces resilience. Price: $42.";

if(tangly)
return "Laciador improves smoothness and manageability while restoring bounce. Price: $48.";

if(dry && problems>=2)
return "Formula Exclusiva deeply rehydrates and rebuilds dry multi-concern hair. Price: $65.";

if(dry)
return "Laciador restores moisture, softness, and natural movement. Price: $48.";

if(flat)
return "Laciador enhances body and natural volume. Price: $48.";

return null;
}

/* ================= SPEAK ================= */

function speak(text){

speechSynthesis.cancel();

const utter=new SpeechSynthesisUtterance(text);
utter.lang=languageSelect.value;
utter.rate=0.95;
utter.pitch=1.02;

state="speaking";
setGlow(0,200,255);

introSound.play();

setTimeout(()=>{
speechSynthesis.speak(utter);
},400);

utter.onend=()=>{
outroSound.play();
setGlow(0,255,200);
state="idle";
};
}

/* ================= LISTEN ================= */

function startListening(){

const SpeechRecognition=
window.SpeechRecognition||window.webkitSpeechRecognition;

recognition=new SpeechRecognition();
recognition.lang=languageSelect.value;
recognition.continuous=true;
recognition.interimResults=true;

transcript="";
state="listening";
setGlow(255,210,80);

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
speak("I didn’t hear anything. Please describe your hair concern.");
}
},3500);

}

/* ================= PROCESS ================= */

function processTranscript(text){

if(!text || text.length<5){
speak("Please describe dryness, oiliness, damage, tangling, color loss, volume issues, or shedding.");
return;
}

responseBox.innerText="Analyzing...";

setTimeout(()=>{

let result=chooseProduct(text);

if(!result){
speak("I couldn’t detect a clear concern. Please be more specific.");
return;
}

responseBox.innerText=result;

setTimeout(()=>{
speak(result);
},2500); // 2.5 second silence before speaking

},1200);
}

/* ================= CLICK ================= */

halo.addEventListener("click",()=>{

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

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
