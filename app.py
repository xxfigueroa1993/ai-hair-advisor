from flask import Flask, request, jsonify, render_template_string
import os

app = Flask(__name__)

@app.route("/")
def index():

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Global Professional Hair Intelligence</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                margin: 0;
                background: #0b1220;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                flex-direction: column;
                font-family: Arial, sans-serif;
                color: white;
            }

            #halo {
                width: 220px;
                height: 220px;
                border-radius: 50%;
                border: 6px solid rgba(0, 170, 255, 0.35);
                box-shadow: 0 0 40px rgba(0,170,255,0.4);
                cursor: pointer;
                transition: all 0.3s ease;
            }

            #halo.listening {
                border-color: red;
                box-shadow: 0 0 60px red;
            }

            #halo.thinking {
                animation: rotate 2s linear infinite;
            }

            @keyframes rotate {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            #status {
                margin-top: 30px;
                font-size: 18px;
                opacity: 0.8;
            }
        </style>
    </head>
    <body>

        <div id="halo"></div>
        <div id="status">Click Halo to Speak</div>

        <script>
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();

        recognition.lang = "en-US";
        recognition.continuous = false;
        recognition.interimResults = false;

        let isListening = false;

        const halo = document.getElementById("halo");
        const status = document.getElementById("status");

        halo.addEventListener("click", () => {
            if (!isListening) startListening();
        });

        function startListening() {
            isListening = true;
            halo.classList.add("listening");
            status.innerText = "Listening...";
            recognition.start();
        }

        function stopListening() {
            isListening = false;
            halo.classList.remove("listening");
        }

        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            stopListening();
            sendToAI(transcript);
        };

        recognition.onerror = function(event) {
            stopListening();
            status.innerText = "Speech error.";
        };

        recognition.onend = function() {
            if (isListening) stopListening();
        };

        function sendToAI(text) {
            halo.classList.add("thinking");
            status.innerText = "Processing...";

            fetch("/ask", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ message: text })
            })
            .then(res => res.json())
            .then(data => {
                halo.classList.remove("thinking");
                status.innerText = data.reply;

                const speech = new SpeechSynthesisUtterance(data.reply);
                speechSynthesis.speak(speech);
            })
            .catch(err => {
                halo.classList.remove("thinking");
                status.innerText = "Server error.";
                console.error(err);
            });
        }
        </script>

    </body>
    </html>
    """

    return render_template_string(html)

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_message = data.get("message", "")

    # TEMP SAFE RESPONSE (no OpenAI yet)
    return jsonify({"reply": f"You said: {user_message}"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
