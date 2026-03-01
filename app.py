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
font-family:Arial,sans-serif;
color:white;
overflow:hidden;
}

#sphere{
width:280px;
height:280px;
border-radius:50%;
cursor:pointer;
will-change: transform, box-shadow;
}

#response{
margin-top:30px;
width:75%;
text-align:center;
font-size:18px;
min-height:60px;
}
</style>
</head>
<body>

<div id="sphere"></div>
<div id="response">Tap the sphere and describe your hair concern.</div>

<script>

const sphere = document.getElementById("sphere");
const responseBox = document.getElementById("response");

let state="idle";
let transcript="";
let recognition=null;
let silenceTimer=null;
let lastSpeechTime=0;
const SILENCE_DELAY=2500;

/* ================= VISUAL ENGINE ================= */

let baseColor=[0,255,200];
let pulse=0;
let direction=1;

function render(){

sphere.style.background=
`radial-gradient(circle,
rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.95) 0%,
rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.25) 60%,
rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.08) 100%)`;

sphere.style.boxShadow=
`0 0 ${120+pulse}px rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.9),
 0 0 ${240+pulse}px rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.6),
 0 0 ${360+pulse}px rgba(${baseColor[0]},${baseColor[1]},${baseColor[2]},0.3)`;

sphere.style.transform = `scale(${1 + pulse/200})`;
}

function animate(){

// IDLE BREATHING
if(state==="idle"){
pulse += 0.35*direction;
if(pulse>18||pulse<0) direction*=-1;
}

// LISTENING REACTIVE
if(state==="listening"){
pulse = 10 + Math.random()*25;
}

// AI SPEAKING STRONGER
if(state==="speaking"){
pulse = 25 + Math.random()*35;
}

render();
requestAnimationFrame(animate);
}

requestAnimationFrame(animate); // FORCE LOOP START

/* ================= SPEAK ================= */

function speak(text){

state="speaking";
baseColor=[0,200,255];

let utter=new SpeechSynthesisUtterance(text);
utter.rate=0.92;

speechSynthesis.cancel();
speechSynthesis.speak(utter);

utter.onend=()=>{
state="idle";
baseColor=[0,255,200];
};
}

/* ================= LISTEN ================= */

function startListening(){

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;

if(!SR){
responseBox.innerText="Speech recognition not supported.";
return;
}

transcript="";
state="listening";
baseColor=[255,200,60];
lastSpeechTime=Date.now();

recognition=new SR();
recognition.lang="en-US";
recognition.continuous=true;
recognition.interimResults=true;

recognition.onresult=(e)=>{
transcript="";
for(let i=0;i<e.results.length;i++){
transcript+=e.results[i][0].transcript;
}
lastSpeechTime=Date.now();
clearTimeout(silenceTimer);
silenceTimer=setTimeout(checkSilence,SILENCE_DELAY);
};

recognition.start();
}

function checkSilence(){
if(Date.now()-lastSpeechTime>=SILENCE_DELAY){
recognition.stop();
process();
}
}

function process(){

let result = transcript.length>2
? "You said: "+transcript
: "I didn’t hear anything.";

responseBox.innerText=result;
speak(result);
}

/* ================= CLICK ================= */

sphere.addEventListener("click",()=>{
if(state==="idle"){
startListening();
}else if(state==="listening"){
recognition.stop();
state="idle";
baseColor=[0,255,200];
}
});

/* ================= INITIAL FORCE RENDER ================= */

render(); // ensure first paint

</script>
</body>
</html>
"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
