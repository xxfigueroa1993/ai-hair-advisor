import os
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =====================================================
# PRODUCT DEFINITIONS
# =====================================================

PRODUCTS = {
    "Formula Exclusiva": "An advanced all-in-one natural professional salon treatment engineered to rebuild structure, repair damage, and restore elasticity and brilliance.",
    "Laciador": "A precision-crafted natural smoothing styler that deeply hydrates, eliminates dryness, and enhances manageability without heaviness.",
    "Gotero": "A lightweight natural gel system designed for oil balance, bounce restoration, and controlled structure without residue.",
    "Gotika": "A botanical-based color revitalizing treatment that restores vibrancy, shine, and reflective luminosity."
}

# =====================================================
# RULE ENGINE (NO ETHNICITY LOGIC)
# =====================================================

def select_product(issue: str, age: int):
    issue = issue.lower()

    # Under 16 safeguard
    if age < 16 and "color" in issue:
        return "Error"

    if "dry" in issue:
        return "Laciador"
    if "oily" in issue:
        return "Gotero"
    if "damaged" in issue:
        return "Formula Exclusiva"
    if "tangly" in issue:
        return "Formula Exclusiva"
    if "fall" in issue:
        return "Formula Exclusiva"
    if "not bouncy" in issue:
        return "Gotero"
    if "color" in issue:
        return "Gotika"

    # Guaranteed fallback
    return "Formula Exclusiva"

# =====================================================
# HTML (Stable Orb Version Restored)
# =====================================================

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>AI Hair Orb</title>

<style>
body{
    margin:0;
    background:black;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    height:100vh;
    overflow:hidden;
    color:white;
    font-family:Arial;
}

select{
    margin-bottom:20px;
    padding:8px;
    background:black;
    color:gold;
    border:1px solid gold;
}

.orb{
    width:220px;
    height:220px;
    border-radius:50%;
    background: radial-gradient(circle at center,
        rgba(255,215,0,0.18) 0%,
        rgba(255,215,0,0.08) 40%,
        rgba(0,0,0,0.9) 70%);
    box-shadow:
        0 0 60px rgba(255,215,0,0.25),
        0 0 120px rgba(255,215,0,0.15);
    animation: idlePulse 3s infinite ease-in-out;
    cursor:pointer;
}

@keyframes idlePulse{
    0%{transform:scale(1);}
    50%{transform:scale(1.05);}
    100%{transform:scale(1);}
}

.listening{animation:listeningPulse .8s infinite ease-in-out;}
@keyframes listeningPulse{
    0%{transform:scale(1);}
    50%{transform:scale(1.12);}
    100%{transform:scale(1);}
}

.speaking{animation:speakingPulse 1s infinite ease-in-out;}
@keyframes speakingPulse{
    0%{transform:scale(1);}
    50%{transform:scale(1.15);}
    100%{transform:scale(1);}
}
</style>
</head>
<body>

<select id="continent">
<option>Asia</option>
<option>Africa</option>
<option>North America</option>
<option>South America</option>
<option>Europe</option>
<option>Australia</option>
<option>Antarctica</option>
</select>

<div class="orb" id="orb"></div>

<audio id="clickSound" src="/static/click.mp3"></audio>
<audio id="completeSound" src="/static/complete.mp3"></audio>

<script>

const orb = document.getElementById("orb")
const clickSound = document.getElementById("clickSound")
const completeSound = document.getElementById("completeSound")

let recognition=null
let silenceTimer=null
let analyzingTimer=null
let transcriptFinal=""
let isListening=false
let isSpeaking=false

function fullReset(){
    if(recognition){
        recognition.stop()
        recognition=null
    }
    speechSynthesis.cancel()
    clearTimeout(silenceTimer)
    clearTimeout(analyzingTimer)
    transcriptFinal=""
    isListening=false
    isSpeaking=false
    orb.classList.remove("listening","speaking")
}

function startListening(){
    recognition=new(window.SpeechRecognition||window.webkitSpeechRecognition)()
    recognition.continuous=true
    recognition.interimResults=true

    recognition.onresult=(event)=>{
        clearTimeout(silenceTimer)
        transcriptFinal=Array.from(event.results)
            .map(r=>r[0].transcript)
            .join("")
        silenceTimer=setTimeout(()=>{
            recognition.stop()
            startAnalyzing(transcriptFinal)
        },2500)
    }

    recognition.start()
    isListening=true
    orb.classList.add("listening")
}

function startAnalyzing(text){
    orb.classList.remove("listening")
    analyzingTimer=setTimeout(()=>{
        fetch("/ask",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message:text})
        })
        .then(res=>res.json())
        .then(data=>speakResponse(data.reply))
    },3000)
}

function speakResponse(text){
    const utter=new SpeechSynthesisUtterance(text)
    utter.pitch=1.2
    utter.rate=1

    utter.onstart=()=>{
        isSpeaking=true
        orb.classList.add("speaking")
    }

    utter.onend=()=>{
        isSpeaking=false
        orb.classList.remove("speaking")
        completeSound.currentTime=0
        completeSound.play()
    }

    speechSynthesis.speak(utter)
}

orb.addEventListener("click",()=>{
    if(isListening||isSpeaking){
        fullReset()
        return
    }
    clickSound.currentTime=0
    clickSound.play()
    startListening()
})

</script>
</body>
</html>
"""

# =====================================================
# ROUTES
# =====================================================

@app.route("/")
def home():
    return HTML_PAGE

@app.route("/ask", methods=["POST"])
def ask():
    data=request.get_json()
    message=data.get("message","")
    age=30  # You can later replace with parsed input

    product=select_product(message, age)

    if product=="Error":
        return jsonify({"reply":"For clients under 16 experiencing pigment loss, we recommend consulting a medical professional before cosmetic treatment."})

    # OpenAI generates professional explanation but product is hard-set
    ai_response=client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"You are a confident, bright-toned professional salon hair expert."},
            {"role":"user","content":f"Client concern: {message}. Explain why {product} is the ideal solution in a professional salon FAQ tone."}
        ]
    )

    explanation=ai_response.choices[0].message.content

    return jsonify({"reply":explanation})

# =====================================================

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port)
