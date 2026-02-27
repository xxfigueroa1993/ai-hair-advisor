import os
from flask import Flask, request

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>Bright Clinical AI</h1>
    <button onclick="send()">Test Backend</button>
    <p id="status">Idle</p>

    <script>
    async function send(){
        const res = await fetch("/voice", { method:"POST" });
        const text = await res.text();
        document.getElementById("status").innerText = text;
    }
    </script>
    """

@app.route("/voice", methods=["POST"])
def voice():
    print("VOICE ROUTE HIT")
    return "Backend reached successfully"

port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)
