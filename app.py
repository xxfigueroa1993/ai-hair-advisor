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

/* ===== SPHERE BASE ===== */

#sphere{
width:280px;
height:280px;
border-radius:50%;
cursor:pointer;

/* Soft teal luxury tone */
background:radial-gradient(circle,
rgba(0,255,200,0.95) 0%,
rgba(0,255,200,0.25) 60%,
rgba(0,255,200,0.08) 100%);

box-shadow:
0 0 90px rgba(0,255,200,0.8),
0 0 180px rgba(0,255,200,0.5),
0 0 260px rgba(0,255,200,0.2);

/* SLOW BREATHING */
animation: breathe 6.5s ease-in-out infinite;
}

/* ===== SLOW BREATHING ===== */

@keyframes breathe{

0%{
transform:scale(1);
box-shadow:
0 0 90px rgba(0,255,200,0.8),
0 0 180px rgba(0,255,200,0.5),
0 0 260px rgba(0,255,200,0.2);
}

50%{
transform:scale(1.06);
box-shadow:
0 0 140px rgba(0,255,200,0.9),
0 0 260px rgba(0,255,200,0.6),
0 0 360px rgba(0,255,200,0.3);
}

100%{
transform:scale(1);
box-shadow:
0 0 90px rgba(0,255,200,0.8),
0 0 180px rgba(0,255,200,0.5),
0 0 260px rgba(0,255,200,0.2);
}
}

/* ===== LISTENING (slightly faster, but still smooth) ===== */

.listening{
background:radial-gradient(circle,
rgba(255,200,60,0.95) 0%,
rgba(255,200,60,0.25) 60%,
rgba(255,200,60,0.08) 100%);
animation: listeningPulse 2s ease-in-out infinite;
}

@keyframes listeningPulse{
0%{transform:scale(1);}
50%{transform:scale(1.1);}
100%{transform:scale(1);}
}

/* ===== SPEAKING ===== */

.speaking{
background:radial-gradient(circle,
rgba(0,200,255,0.95) 0%,
rgba(0,200,255,0.25) 60%,
rgba(0,200,255,0.08) 100%);
animation: speakingPulse 1.8s ease-in-out infinite;
}

@keyframes speakingPulse{
0%{transform:scale(1);}
50%{transform:scale(1.12);}
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

<div id="sphere"></div>
<div id="response">Tap the sphere and describe your hair concern.</div>

<script>

const sphere = document.getElementById("sphere");
const responseBox = document.getElementById("response");

let recognition;
let transcript="";
let silenceTimer;
let lastSpeechTime=0;
const SILENCE_DELAY=2500;

/* ===== LISTEN ===== */

function startListening(){

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;

if(!SR){
responseBox.innerText="Speech recognition not supported.";
return;
}

transcript="";
sphere.className="listening";
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

/* ===== SPEAK ===== */

function speak(text){

sphere.className="speaking";

let utter=new SpeechSynthesisUtterance(text);
utter.rate=0.95;

speechSynthesis.cancel();
speechSynthesis.speak(utter);

utter.onend=()=>{
sphere.className="";
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
