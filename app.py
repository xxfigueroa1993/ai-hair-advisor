from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os
import base64

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are an Elite Professional Salon Hair Consultant.
Only answer hair-related questions.
If asked anything outside hair, respond:
"I am a Professional Salon Hair Consultant. How may I assist you with your hair needs today?"
"""

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# FRONTEND (FULL ELITE UI)
# ================================

html = """
<!DOCTYPE html>
<html>
<head>
<title>Global Professional Hair Intelligence</title>

<style>
body {
    background: radial-gradient(circle at center, #0b1220 0%, #050a14 100%);
    font-family: 'Segoe UI', sans-serif;
    text-align: center;
    color: white;
    margin-top: 80px;
}

h1 {
    font-size: 38px;
    font-weight: 500;
    letter-spacing: 1px;
}

select {
    margin-top: 30px;
    padding: 10px 20px;
    font-size: 15px;
    background: rgba(31,41,55,0.8);
    color: white;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
}

.halo-container {
    position: relative;
    width: 220px;
    height: 220px;
    margin: 70px auto;
}

.halo-ring {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    border: 4px solid rgba(59,130,246,0.35);
    background: transparent;
    transition: all 0.3s ease;
    cursor: pointer;
    z-index: 2;
}

.halo-glow {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(59,130,246,0.35) 0%, transparent 70%);
    animation: breathe 2.5s infinite ease-in-out;
    z-index: 1;
    transition: all 0.3s ease;
}

@keyframes breathe {
    0% { transform: scale(1); opacity: 0.6; }
    50% { transform: scale(1.15); opacity: 1; }
    100% { transform: scale(1); opacity: 0.6; }
}

.listening .halo-ring {
    border-color: rgba(239,68,68,0.7);
}

.listening .halo-glow {
    background: radial-gradient(circle, rgba(239,68,68,0.4) 0%, transparent 70%);
}

.thinking .halo-ring {
    animation: rotate 1.2s linear infinite;
}

@keyframes rotate {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

.waveform {
    margin-top: 30px;
    height: 20px;
    display: flex;
    justify-content: center;
    gap: 4px;
}

.bar {
    width: 4px;
    height: 5px;
    background: #3b82f6;
    animation: wave 1s infinite ease-in-out;
}

.bar:nth-child(2) { animation-delay: 0.1s; }
.bar:nth-child(3) { animation-delay: 0.2s; }
.bar:nth-child(4) { animation-delay: 0.3s; }
.bar:nth-child(5) { animation-delay: 0.4s; }

@keyframes wave {
    0%, 100% { height: 5px; }
    50% { height: 20px; }
}

#response {
    margin-top: 40px;
    width: 60%;
    margin-left: auto;
    margin-right: auto;
    font-size: 18px;
    line-height: 1.6;
}

.status {
    margin-top: 20px;
    font-size: 14px;
    color: #9ca3af;
}
</style>
</head>

<body>

<h1>Global Professional Hair Intelligence</h1>

<select id="language">
<option>English</option>
<option>Spanish</option>
<option>French</option>
<option>Portuguese</option>
<option>German</option>
<option>Arabic</option>
<option>Hindi</option>
<option>Mandarin Chinese</option>
<option>Japanese</option>
<option>Korean</option>
<option>Russian</option>
</select>

<div id="halo" class="halo-container" onclick="startListening()">
    <div class="halo-glow"></div>
    <div class="halo-ring"></div>
</div>

<div class="status" id="status">Click the halo to speak</div>

<div class="waveform" id="waveform" style="display:none;">
    <div class="bar"></div>
    <div class="bar"></div>
    <div class="bar"></div>
    <div class="bar"></div>
    <div class="bar"></div>
</div>

<div id="response"></div>

<audio id="ttsAudio"></audio>

<script>
let recognition;
let ws;

function playStartupSound() {
    let audio = new Audio("https://actions.google.com/sounds/v1/cartoon/wood_plank_flicks.ogg");
    audio.volume = 0.2;
    audio.play();
}

function startListening() {

    if (!('webkitSpeechRecognition' in window)) {
        alert("Use Chrome browser.");
        return;
    }

    playStartupSound();

    const halo = document.getElementById("halo");
    halo.classList.add("listening");

    recognition = new webkitSpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    document.getElementById("status").innerText = "Listening...";
    recognition.start();

    recognition.onresult = function(event) {
        let transcript = event.results[0][0].transcript;
        recognition.stop();
        halo.classList.remove("listening");
        connectWebSocket(transcript);
    };

    recognition.onend = function() {
        halo.classList.remove("listening");
    };
}

function connectWebSocket(question) {

    const halo = document.getElementById("halo");
    document.getElementById("response").innerHTML = "";
    halo.classList.add("thinking");

    ws = new WebSocket("wss://" + location.host + "/ws");

    ws.onmessage = function(event) {
        if(event.data.startsWith("AUDIO:")) {
            let audioData = event.data.replace("AUDIO:", "");
            let audio = document.getElementById("ttsAudio");
            audio.src = "data:audio/mp3;base64," + audioData;
            document.getElementById("waveform").style.display = "flex";
            audio.play();
            audio.onended = () => {
                document.getElementById("waveform").style.display = "none";
            };
        } else {
            document.getElementById("response").innerHTML += event.data;
        }
    };

    ws.onopen = function() {
        let language = document.getElementById("language").value;
        ws.send(JSON.stringify({question: question, language: language}));
    };

    ws.onclose = function() {
        halo.classList.remove("thinking");
        document.getElementById("status").innerText = "Click the halo to speak";
    };
}
</script>

</body>
</html>
"""

@app.get("/")
async def home():
    return HTMLResponse(html)

# ================================
# BACKEND
# ================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()

    user_question = data["question"]
    language = data["language"]

    final_prompt = SYSTEM_PROMPT + f"\nRespond in {language}."

    response_text = ""

    response = client.chat.completions.create(
        model="gpt-4o",
        stream=True,
        messages=[
            {"role": "system", "content": final_prompt},
            {"role": "user", "content": user_question}
        ]
    )

    for chunk in response:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            response_text += content
            await websocket.send_text(content)

    # Generate TTS after full response
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=response_text
    )

    audio_bytes = speech.read()
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    await websocket.send_text("AUDIO:" + audio_base64)
