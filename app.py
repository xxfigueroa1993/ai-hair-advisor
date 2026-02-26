from flask import Flask, request, jsonify, render_template_string
import openai
import os

app = Flask(__name__)

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/")
def index():

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Luxury AI Voice Assistant</title>
        <style>
            body {
                background: #f8fafc;
                text-align: center;
                font-family: Arial, sans-serif;
                padding-top: 150px;
            }

            #halo {
                width: 200px;
                height: 200px;
                border-radius: 50%;
                border: 6px solid rgba(0, 150, 255, 0.4);
                margin: auto;
                cursor: pointer;
                transition: 0.3s ease;
            }

            #halo.listening {
                border-color: red;
                box-shadow: 0 0 40px red;
            }
        </style>
    </head>
    <body>

        <div id="halo"></div>
        <p id="status">Click to Speak</p>

        <script>
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();

        recognition.lang = "en-US";
        recognition.continuous = false;
        recognition.interimResults = false;

        let isListening = false;

        const halo = document.getElementById("halo");
        const statusText = document.getElementById("status");

        halo.addEventListener("click", () => {
            if (!isListening) {
                startListening();
            }
        });

        function startListening() {
            isListening = true;
            statusText.innerText = "Listening...";
            halo.classList.add("listening");
            recognition.start();
        }

        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            stopListening();
            sendToAI(transcript);
        };

        recognition.onerror = function(event) {
            stopListening();
        };

        recognition.onend = function() {
            if (isListening) stopListening();
        };

        function stopListening() {
            isListening = false;
            statusText.innerText = "Processing...";
            halo.classList.remove("listening");
        }

        function sendToAI(text) {
            fetch("/ask", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({message: text})
            })
            .then(res => res.json())
            .then(data => {
                statusText.innerText = data.reply;

                const utter = new SpeechSynthesisUtterance(data.reply);
                speechSynthesis.speak(utter);
            });
        }
        </script>

    </body>
    </html>
    """

    return render_template_string(html)

@app.route("/ask", methods=["POST"])
def ask():
    user_message = request.json["message"]

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional salon hair expert."},
            {"role": "user", "content": user_message}
        ]
    )

    return jsonify({"reply": response.choices[0].message.content})

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

