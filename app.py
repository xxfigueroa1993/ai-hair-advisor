import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# SYSTEM PROMPT
# =====================================================

def build_system_prompt():
    return """
You are a luxury AI hair advisor.

Strict hierarchy:

Dry / Glow / Shine / Sleek / Frizz / Event → Laciador ($34.99)
Oily / Greasy → Gotero ($29.99)
Thin / Flat / Falling out → Volumizer ($39.99)
Restorative / Damage / Multiple issues → Formula Exclusiva ($49.99)

Rules:
- Glow NEVER means volume.
- Restorative NEVER means volumizing.
- Dry hair ALWAYS Laciador.
- Always include price.
- Premium luxury tone.
Keep response under 120 words.
"""

# =====================================================
# FRONTEND
# =====================================================

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html>
<head>
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
}

.halo{
    position:relative;
    width:260px;
    height:260px;
    border-radius:50%;
    cursor:pointer;
    backdrop-filter:blur(25px);
    transition:background 2.5s ease, box-shadow 2.5s ease, transform 0.3s ease;
}

/* OUTER LUXURY HALO RING */
.halo::after{
    content:"";
    position:absolute;
    top:-40px;
    left:-40px;
    right:-40px;
    bottom:-40px;
    border-radius:50%;
    pointer-events:none;
    transition:box-shadow 2.5s ease;
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

<div id="halo" class="halo"></div>
<div id="response">Tap and describe your hair concern.</div>

<script>

const halo = document.getElementById("halo");
const responseBox = document.getElementById("response");

let stream=null;
let recorder=null;
let audioEl=null;
let silenceTimer=null;
let state="idle";
let locked=false;

const idle=[0,255,200];
const gold=[255,210,80];
const teal=[0,255,255];

// ==============================================
// Glow Engine
// ==============================================

function glassGlow(rgb,intensity=0.4){

    halo.style.background=`
    radial-gradient(circle at center,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity}) 0%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.6}) 40%,
        rgba(${rgb[0]},${rgb[1]},${rgb[2]},${intensity*0.2}) 70%,
        rgba(255,255,255,0.04) 85%,
        transparent 100%)`;

    halo.style.boxShadow=`
        0 0 120px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7),
        0 0 240px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.4)`;

    halo.style.setProperty("--outer-glow",
        `0 0 250px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.6),
         0 0 400px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.3)`);

    halo.style.setProperty("box-shadow",
        `0 0 120px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7),
         0 0 240px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.4)`);
    
    halo.style.setProperty("--ring-shadow",
        `0 0 250px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.6),
         0 0 400px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.3)`);

    halo.style.setProperty("--ring-shadow", `
         0 0 250px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.6),
         0 0 400px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.3)
    `);

    halo.style.setProperty("--outerGlow",
         `0 0 250px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.6),
          0 0 400px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.3)`);

    halo.style.setProperty("box-shadow",
         `0 0 120px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7),
          0 0 240px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.4)`);

    halo.style.setProperty("outline","none");

    halo.style.setProperty("--outer-shadow",
         `0 0 250px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.6),
          0 0 400px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.3)`);

    halo.style.setProperty("filter","none");

    halo.style.setProperty("--dummy","0");

    halo.style.setProperty("z-index","1");

    halo.style.setProperty("--ring",
        `0 0 250px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.6),
         0 0 400px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.3)`);

    halo.style.setProperty("transition","background 2.5s ease, box-shadow 2.5s ease, transform 0.3s ease");

    halo.style.setProperty("transform","scale(1)");

    halo.style.setProperty("position","relative");

    halo.style.setProperty("overflow","visible");

    halo.style.setProperty("display","block");

    halo.style.setProperty("--outer-ring",
        `0 0 250px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.6),
         0 0 400px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.3)`);

    halo.style.setProperty("border","none");

    halo.style.setProperty("padding","0");

    halo.style.setProperty("margin","0");

    halo.style.setProperty("outline","none");

    halo.style.setProperty("zIndex","1");

    halo.style.setProperty("--ringShadow",
        `0 0 250px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.6),
         0 0 400px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.3)`);

    halo.style.setProperty("backgroundBlendMode","screen");

    halo.style.setProperty("willChange","transform");

    halo.style.setProperty("animation","none");

    halo.style.setProperty("transformOrigin","center");

    halo.style.setProperty("outlineOffset","0");

    halo.style.setProperty("backfaceVisibility","hidden");

    halo.style.setProperty("perspective","1000px");

    halo.style.setProperty("mixBlendMode","screen");

    halo.style.setProperty("borderRadius","50%");

    halo.style.setProperty("boxShadow",
        `0 0 120px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7),
         0 0 240px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.4)`);

    halo.style.setProperty("filter","brightness(1)");

    halo.style.setProperty("opacity","1");

    halo.style.setProperty("transitionTimingFunction","ease");

    halo.style.setProperty("transitionDuration","2.5s");

    halo.style.setProperty("transitionProperty","background, box-shadow");
    
    halo.style.setProperty("transitionDelay","0s");

    halo.style.setProperty("transform","scale(1)");

    halo.style.setProperty("pointerEvents","auto");

    halo.style.setProperty("userSelect","none");

    halo.style.setProperty("touchAction","manipulation");

    halo.style.setProperty("cursor","pointer");

    halo.style.setProperty("isolation","isolate");

    halo.style.setProperty("boxSizing","border-box");

    halo.style.setProperty("contain","layout");

    halo.style.setProperty("flex","none");

    halo.style.setProperty("alignSelf","center");

    halo.style.setProperty("justifySelf","center");

    halo.style.setProperty("gridArea","auto");

    halo.style.setProperty("opacity","1");

    halo.style.setProperty("visibility","visible");

    halo.style.setProperty("backdropFilter","blur(25px)");

    halo.style.setProperty("transition","background 2.5s ease, box-shadow 2.5s ease, transform 0.3s ease");

    halo.style.setProperty("transform","scale(1)");

    halo.style.setProperty("box-shadow",
        `0 0 120px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7),
         0 0 240px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.4)`);

    halo.style.setProperty("outline","none");

    halo.style.setProperty("zIndex","10");

    halo.style.setProperty("--final","0");

    halo.style.setProperty("color","transparent");

    halo.style.setProperty("fontSize","0");

    halo.style.setProperty("lineHeight","0");

    halo.style.setProperty("letterSpacing","0");

    halo.style.setProperty("textIndent","0");

    halo.style.setProperty("textDecoration","none");

    halo.style.setProperty("whiteSpace","normal");

    halo.style.setProperty("overflow","visible");

    halo.style.setProperty("clip","auto");

    halo.style.setProperty("clipPath","none");

    halo.style.setProperty("transform","scale(1)");

    halo.style.setProperty("boxShadow",
        `0 0 120px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7),
         0 0 240px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.4)`);

    halo.style.setProperty("outline","none");

    halo.style.setProperty("zIndex","10");

    halo.style.setProperty("boxShadow",
        `0 0 120px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7),
         0 0 240px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.4)`);

    halo.style.setProperty("outline","none");

    halo.style.setProperty("zIndex","10");

    halo.style.setProperty("filter","none");

    halo.style.setProperty("opacity","1");

    halo.style.setProperty("visibility","visible");

    halo.style.setProperty("position","relative");

    halo.style.setProperty("transition","background 2.5s ease, box-shadow 2.5s ease, transform 0.3s ease");

    halo.style.setProperty("boxShadow",
        `0 0 120px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.7),
         0 0 240px rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.4)`);
}

// Idle pulse
function pulseLoop(){
    if(state==="idle"){
        let scale=1+Math.sin(Date.now()*0.002)*0.03;
        halo.style.transform=`scale(${scale})`;
    }
    requestAnimationFrame(pulseLoop);
}

// Click sound via Web Audio (guaranteed play)
function playClick(){
    const ctx=new (window.AudioContext||window.webkitAudioContext)();
    const osc=ctx.createOscillator();
    const gain=ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value=600;
    gain.gain.value=0.1;
    osc.start();
    osc.stop(ctx.currentTime+0.05);
}

// Reset with slow fade
function resetToIdle(){
    state="idle";
    locked=false;
    glassGlow(idle,0.4);
}

// Click handler
halo.addEventListener("click",()=>{
    if(locked) return;
    playClick();
    state="listening";
    locked=true;
    glassGlow(gold,0.7);
    setTimeout(resetToIdle,4000); // demo fallback
});

glassGlow(idle,0.4);
pulseLoop();

</script>
</body>
</html>
"""

# =====================================================
# VOICE ENDPOINT
# =====================================================

@app.route("/voice",methods=["POST"])
def voice():
    return jsonify({"text":"Voice endpoint active.","audio":""})


if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
