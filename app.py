import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ======================================
# FRONTEND WITH GLOWING HALO
# ======================================

@app.route("/", methods=["GET"])
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Hair Advisor</title>
        <style>
            body {
                background: black;
                color: white;
                text-align: center;
                font-family: Arial;
                margin-top: 100px;
            }

            .halo {
                width: 150px;
                height: 150px;
                border-radius: 50%;
                border: 4px solid rgba(0,255,255,0.6);
                margin: 40px auto;
                box-shadow: 0 0 20px cyan;
                transition: all 0.3s ease;
            }

            .recording {
                animation: pulse 1.2s infinite;
                box-shadow: 0 0 40px cyan, 0 0 80px blue;
            }

            .speaking {
                animation: pulseSpeak 1s infinite;
                box-shadow: 0 0 40px lime, 0 0 80px green;
            }

            @keyframes pulse {
                0% { transform: scale(1); opacity: 0.8; }
                50% { transform: scale(1.15); opacity: 1; }
                100% { transform: scale(1); opacity: 0.8; }
            }

            @keyframes pulseSpeak {
                0% { transform: scale(1); opacity: 0.8; }
                50% { transform: scale(1.1); opacity: 1; }
                100% { transform: scale(1); opacity: 0.8; }
            }

            button {
                padding: 12px 25px;
                font-size: 18px;
                cursor: pointer;
                background: cyan;
                border: none;
                border-radius: 20px;
            }

        </style>
    </head>
    <body>

        <h1>AI Hair Advisor</h1>

        <div id="halo" class="halo"></div>

        <button onclick="record()">Ask About Your Hair</button>

        <p id="response"></p>

        <script>

        let recorder;
        let chunks = [];

        async function record() {

            const halo = document.getElementById("halo");
            halo.classList.remove("speaking");
            halo.classList.add("recording");

            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            recorder = new MediaRecorder(stream);
            chunks = [];

            recorder.ondataavailable = e => chunks.push(e.data);

            recorder.onstop = async () => {

                const blob = new Blob(chunks, { type: "audio/webm" });
                const form = new FormData();
                form.append("audio", blob);

                const res = await fetch("/voice", {
                    method: "POST",
                    body: form
                });

                const data = await res.json();

                document.getElementById("response").innerText = data.text;

                halo.classList.remove("recording");
                halo.classList.add("speaking");

                if (data.audio) {
                    const audio = new Audio("data:audio/mp3;base64," + data.audio);
                    audio.play();

                    audio.onended = () => {
                        halo.classList.remove("speaking");
                    };
                }
            };

            recorder.start();

            // 6 seconds recording (extra delay)
            setTimeout(() => {
                recorder.stop();
            }, 6000);
        }

        </script>
    </body>
    </html>
    """

# ======================================
# PRODUCT DATABASE
# ======================================

PRODUCTS = {
    "Laciador": {
        "description": "It deeply hydrates dry and brittle hair, restoring softness and shine.",
        "price": 34.99
    },
    "Gotero": {
        "description": "It balances excess oil while keeping your scalp fresh and clean.",
        "price": 29.99
    },
    "Formula Exclusiva": {
        "description": "It repairs damaged strands and strengthens hair from root to tip.",
        "price": 39.99
    },
    "Gotika": {
        "description": "It protects color-treated hair and enhances vibrancy and glow.",
        "price": 36.99
    }
}

# ======================================
# RULE ENGINE
# ======================================

def choose_product(text):
    text = text.lower()

    if "dry" in text:
        return "Laciador"
    if "damaged" in text:
        return "Formula Exclusiva"
    if "oily" in text:
        return "Gotero"
    if "color" in text:
        return "Gotika"

    return None

# ======================================
# VOICE ROUTE
# ======================================

@app.route("/voice", methods=["POST"])
def voice():

    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400

    file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        audio_path = temp_audio.name

    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    user_text = transcript.strip()

    print("Transcript:", user_text)

    if not user_text or len(user_text) < 3:
        return speak("I didn't hear anything. Please try again.")

    if not any(word in user_text.lower() for word in ["dry", "damaged", "oily", "color"]):
        return speak("Please tell me your hair concern like dry, damaged, oily, or color-treated.")

    product_name = choose_product(user_text)

    if product_name is None:
        return speak("I couldn't determine your hair concern. Please try again.")

    info = PRODUCTS[product_name]

    message = (
        f"I recommend {product_name}. "
        f"{info['description']} "
        f"With tax and shipping, you're looking at ${info['price']}."
    )

    return speak(message)

# ======================================
# SPEECH FUNCTION
# ======================================

def speak(message):

    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=message
    )

    audio_bytes = speech.read()
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({
        "text": message,
        "audio": audio_base64
    })

# ======================================
# RUN
# ======================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
