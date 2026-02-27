import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>Bright Clinical AI</h1>
    <button onclick="test()">Test JS</button>
    <p id="status">Idle</p>

    <script>
    function test(){
        document.getElementById("status").innerText = "JavaScript working";
    }
    </script>
    """

port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)
