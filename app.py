from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a Professional Salon Hair Expert.
Only answer hair-related questions.
If asked anything outside hair, respond:
"I am a Professional Salon Hair Expert. How may I assist you with your hair needs today?"
"""

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# FRONTEND (Embedded)
# ==============================

html = """
<!DOCTYPE html>
<html>
<head>
<title>Professional Hair AI</title>
<style>
body {
    background: #0f172a;
    font-family: Arial;
    text-align: center;
    color: white;
    margin-top: 100px;
}
.halo {
    width: 160px;
    height: 160px;
    border-radius: 50%;
    border: none;
    background: radial-gradient(circle, #3b82f6, #1e3a8a);
    box-shadow: 0 0 40px #3b82f6;
    animation: pulse 2s infinite;
    cursor: pointer;
}
@keyframes pulse {
    0% { box-shadow: 0 0 20px #3b82f6; }
    50% { box-shadow: 0 0 60px #60a5fa; }
    100% { box-shadow: 0 0 20px #3b82f6; }
}
select {
    margin-top: 40px;
    padding: 10px;
    font-size: 16px;
}
#response {
    margin-top: 40px;
    width: 60%;
    margin-left: auto;
    margin-right: auto;
    font-size: 18px;
}
</style>
</head>
<body>

<h1>Professional Hair AI</h1>

<select id="language">
<option>English</option>
<option>Spanish</option>
<option>French</option>
<option>Portuguese</option>
</select>

<br><br>

<button class="halo" onclick="startChat()"></button>

<div id="response"></div>

<script>
let ws;

function startChat() {
    document.getElementById("response").innerHTML = "";
    ws = new WebSocket("wss://" + location.host + "/ws");

    ws.onmessage = function(event) {
        document.getElementById("response").innerHTML += event.data;
    };

    ws.onopen = function() {
        let question = prompt("Ask your hair question:");
        let language = document.getElementById("language").value;
        ws.send(JSON.stringify({
            question: question,
            language: language
        }));
    };
}
</script>

</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

# ==============================
# WEBSOCKET BACKEND
# ==============================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()

    user_question = data["question"]
    language = data["language"]

    final_prompt = SYSTEM_PROMPT + f"\nRespond in {language}."

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
            await websocket.send_text(chunk.choices[0].delta.content)
