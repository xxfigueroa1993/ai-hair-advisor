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

/* ===== BASE SPHERE ===== */

#sphere{
width:280px;
height:280px;
border-radius:50%;
cursor:pointer;
transition:background 0.4s ease;
}

/* ===== IDLE BREATHING ===== */

.idle{
background:radial-gradient(circle,
rgba(0,255,200,0.95) 0%,
rgba(0,255,200,0.25) 60%,
rgba(0,255,200,0.08) 100%);
animation:breathe 7s ease-in-out infinite;
}

@keyframes breathe{
0%{transform:scale(1);}
50%{transform:scale(1.06);}
100%{transform:scale(1);}
}

/* ===== LISTENING ===== */

.listening{
background:radial-gradient(circle,
rgba(255,200,60,0.95) 0%,
rgba(255,200,60,0.3) 60%,
rgba(255,200,60,0.08) 100%);
animation:listenPulse 1.8s ease-in-out infinite;
}

@keyframes listenPulse{
0%{transform:scale(1);}
50%{transform:scale(1.12);}
100%{transform:scale(1);}
}

/* ===== SPEAKING ===== */

.speaking{
background:radial-gradient(circle,
rgba(0,200,255,0.95) 0%,
rgba(0,200,255,0.3) 60%,
rgba(0,200,255,0.08) 100%);
animation:speakPulse 1.5s ease-in-out infinite;
}

@keyframes speakPulse{
0%{transform:scale(1);}
50%{transform:scale(1.14);}
100%{transform:scale(1);}
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

<div id="sphere" class="idle"></div>
<div id="response">Tap the sphere and describe your hair concern.</div>

<script>

const sphere=document.getElementById("sphere");
const responseBox=document.getElementById("response");

let recognition;
let transcript="";
let silenceTimer;
let lastSpeechTime=0;
const SILENCE_DELAY=2500;

/* ===== STATE HANDLER ===== */

function setState(state){
sphere.classList.remove("idle","listening","speaking");
sphere.classList.add(state);
}

/* ===== LISTEN ===== */

function startListening(){

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;

if(!SR){
responseBox.innerText="Speech recognition not supported.";
return;
}

transcript="";
setState("listening");
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

let result=transcript.length>2
? "You said: "+transcript
: "I didn’t hear anything.";

responseBox.innerText=result;
speak(result);
}

/* ===== SPEAK ===== */

function speak(text){

setState("speaking");

let utter=new SpeechSynthesisUtterance(text);
utter.rate=0.95;

speechSynthesis.cancel();
speechSynthesis.speak(utter);

utter.onend=()=>{
setState("idle");
};
}

/* ===== CLICK ===== */

sphere.addEventListener("click",()=>{
startListening();
});

</script>
</body>
</html>
"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
