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
font-family:Arial;
color:white;
overflow:hidden;
}
.wrapper{
width:380px;
height:380px;
display:flex;
justify-content:center;
align-items:center;
}
#halo{
width:280px;
height:280px;
border-radius:50%;
cursor:pointer;
transition:transform 0.05s linear;
}
#response{
margin-top:30px;
width:75%;
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
let micStream=null;
let dataArray=null;

let premiumVoice=null;

// ================= FORCE VOICE LOAD =================

function loadVoices(){
return new Promise(resolve=>{
let voices=speechSynthesis.getVoices();
if(voices.length!==0){
resolve(voices);
}else{
speechSynthesis.onvoiceschanged=()=>{
resolve(speechSynthesis.getVoices());
};
}
});
}

async function initVoice(){
let voices=await loadVoices();

let preferredOrder=[
"Google US English",
"Microsoft Jenny",
"Microsoft Aria",
"Samantha"
];

for(let name of preferredOrder){
let found=voices.find(v=>v.name.includes(name));
if(found){
premiumVoice=found;
return;
}
}

// fallback to any natural US voice
premiumVoice=voices.find(v=>v.lang==="en-US") || voices[0];
}

// ================= COLOR =================

function setColor(r,g,b){
halo.style.boxShadow=`
0 0 120px rgba(${r},${g},${b},0.9),
0 0 260px rgba(${r},${g},${b},0.6),
0 0 380px rgba(${r},${g},${b},0.4)
`;
halo.style.background=
`radial-gradient(circle, rgba(${r},${g},${b},0.65) 0%, rgba(${r},${g},${b},0.2) 70%)`;
}
setColor(0,255,200);

// ================= PULSE =================

function pulse(){
let scale=1;

if(state==="idle"){
scale=1+Math.sin(Date.now()*0.002)*0.04;
}

if(state==="listening" && analyser){
analyser.getByteTimeDomainData(dataArray);
let sum=0;
for(let i=0;i<dataArray.length;i++){
let val=(dataArray[i]-128)/128;
sum+=val*val;
}
let rms=Math.sqrt(sum/dataArray.length);
scale=1+Math.min(rms*4,0.35);
}

if(state==="speaking"){
scale=1+Math.sin(Date.now()*0.0035)*0.10;
}

halo.style.transform=`scale(${scale})`;
requestAnimationFrame(pulse);
}
pulse();

// ================= MIC =================

async function initMic(){
if(audioCtx) return;

audioCtx=new (window.AudioContext||window.webkitAudioContext)();
micStream=await navigator.mediaDevices.getUserMedia({audio:true});
let source=audioCtx.createMediaStreamSource(micStream);
analyser=audioCtx.createAnalyser();
analyser.fftSize=1024;
source.connect(analyser);
dataArray=new Uint8Array(analyser.fftSize);
}

// ================= SPEAK =================

function speak(text){
state="speaking";
setColor(0,200,255);

let utter=new SpeechSynthesisUtterance(text);
if(premiumVoice) utter.voice=premiumVoice;

// premium pacing
utter.rate=0.90;
utter.pitch=1.05;
utter.volume=1;

speechSynthesis.speak(utter);

utter.onend=()=>{
setColor(0,255,200);
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

await initMic();
await initVoice();

state="listening";
setColor(255,210,80);
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
setColor(0,255,200);
state="idle";
}
});

</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
