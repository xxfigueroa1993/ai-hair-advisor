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
    background:#05080a;
    font-family:Arial;
    color:white;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    height:100vh;
}

#continentSelect{
    position:absolute;
    top:20px;
    right:20px;
    padding:8px;
    font-size:14px;
}

.wrapper{
    width:400px;
    height:400px;
    display:flex;
    justify-content:center;
    align-items:center;
}

#halo{
    width:280px;
    height:280px;
    border-radius:50%;
    background:rgba(0,255,200,0.22);
    backdrop-filter:blur(60px);
    cursor:pointer;
    transition:transform 1.2s ease;
}

#response{
    margin-top:30px;
    width:80%;
    text-align:center;
}
</style>
</head>
<body>

<select id="continentSelect">
<option>North America</option>
<option>South America</option>
<option>Europe</option>
<option>Africa</option>
<option>Asia</option>
<option>Australia</option>
<option>Antarctica</option>
</select>

<div class="wrapper">
<div id="halo"></div>
</div>

<div id="response">Tap and describe your hair concern.</div>

<script>

const halo=document.getElementById("halo");
const responseBox=document.getElementById("response");

let recognition;
let silenceTimer;
let state="idle";

// ================= PRODUCT ENGINE =================

function chooseProduct(text){

text=text.toLowerCase();

let ageUnder16 = text.includes("under 16") || text.includes("15") || text.includes("14");

if(ageUnder16 && text.includes("loss") && text.includes("color")){
    return {
        product:"Medical Advisory",
        description:"For individuals under 16 experiencing sudden color loss, we recommend consulting a medical professional before using any treatment."
    };
}

// ===== MAIN LOGIC =====

if(text.includes("dry"))
    return productResponse("Laciador",
    "Dry hair lacks moisture retention. Laciador replenishes hydration while smoothing the hair cuticle for long-lasting manageability.");

if(text.includes("oily"))
    return productResponse("Gotero",
    "Excess oil production requires lightweight control. Gotero balances scalp oils without stripping essential hydration.");

if(text.includes("damaged"))
    return productResponse("Formula Exclusiva",
    "Damage typically affects the protein structure of the hair shaft. Formula Exclusiva restores strength, elasticity, and shine.");

if(text.includes("tangly"))
    return productResponse("Laciador",
    "Tangles are caused by raised cuticles and friction. Laciador smooths and detangles while improving comb-through efficiency.");

if(text.includes("falling"))
    return productResponse("Formula Exclusiva",
    "Hair shedding concerns require strengthening and scalp stimulation. Formula Exclusiva supports healthier growth cycles.");

if(text.includes("not bouncy"))
    return productResponse("Gotero",
    "Lack of bounce often indicates product buildup or imbalance. Gotero provides structure and lightweight lift.");

if(text.includes("loss") || text.includes("color"))
    return productResponse("Gotika",
    "Color fading results from oxidation and cuticle wear. Gotika enhances vibrancy while protecting pigment longevity.");

// ===== FALLBACK =====
return productResponse("Formula Exclusiva",
"Based on industry research from leading professional salons, your concern indicates a need for structural restoration and moisture balance.");

}

function productResponse(name,desc){
return {
    product:name,
    description:desc
};
}

// ================= SPEECH =================

function speak(text){
const utter=new SpeechSynthesisUtterance(text);
utter.rate=1;
utter.pitch=1.1;
utter.volume=1;

const voices=speechSynthesis.getVoices();
const brightVoice=voices.find(v=>v.name.toLowerCase().includes("female"));
if(brightVoice) utter.voice=brightVoice;

speechSynthesis.speak(utter);

utter.onend=function(){
responseBox.innerHTML="<b>Recommendation:</b><br>"+text;
state="idle";
};
}

// ================= LISTENING =================

function setupRecognition(){

const SpeechRecognition =
window.SpeechRecognition || window.webkitSpeechRecognition;

recognition=new SpeechRecognition();
recognition.continuous=true;
recognition.interimResults=true;
recognition.lang="en-US";

let finalTranscript="";

recognition.onresult=function(event){

clearTimeout(silenceTimer);

for(let i=event.resultIndex;i<event.results.length;i++){
if(event.results[i].isFinal){
finalTranscript+=event.results[i][0].transcript+" ";
}
}

silenceTimer=setTimeout(()=>{
recognition.stop();
processSpeech(finalTranscript.trim());
},2000);

};

recognition.onend=function(){
if(!finalTranscript){
processSpeech("");
}
};

}

function processSpeech(text){

if(!text){
speak("I didn’t hear anything. Please describe your hair concern.");
return;
}

responseBox.innerText="Analyzing...";

setTimeout(()=>{
const result=chooseProduct(text);
if(result.product==="Medical Advisory"){
speak(result.description);
}else{
speak(result.product + ". " + result.description);
}
},1000);

}

// ================= CLICK =================

halo.addEventListener("click",()=>{

if(state!=="idle"){
recognition?.stop();
state="idle";
responseBox.innerText="Tap and describe your hair concern.";
return;
}

state="listening";
responseBox.innerText="Listening...";
setupRecognition();
recognition.start();

});

</script>
</body>
</html>
"""

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
