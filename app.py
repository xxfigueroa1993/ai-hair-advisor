import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# FRONTEND
# =====================================================

@app.route("/", methods=["GET"])
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Hair Advisor</title>
        <style>
            body {
                margin: 0;
                height: 100vh;
                background: radial-gradient(circle at center, #0f0f0f 0%, #000000 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                font-family: Arial;
                color: white;
                overflow: hidden;
            }

            .halo {
                width: 180px;
                height: 180px;
                border-radius: 50%;
                cursor: pointer;
                position: relative;
                background: rgba(255,255,255,0.02);
                backdrop-filter: blur(4px);
                box-shadow:
                    0 0 30px rgba(0,255,255,0.25),
                    inset 0 0 40px rgba(0,255,255,0.15);
                transition: all 0.3s ease;
            }

            /* Seamless outer glow ring */
            .halo::before {
                content: "";
                position: absolute;
                inset: -8px;
                border-radius: 50%;
                background: radial-gradient(circle,
                    rgba(0,255,255,0.4) 0%,
                    rgba(0,255,255,0.2) 40%,
                    rgba(0,255,255,0.05) 70%,
                    transparent 80%);
                opacity: 0.6;
            }

            .idle {
                animation: idlePulse 2.5s infinite ease-in-out;
            }

            .recording {
                animation: recordPulse 1.2s infinite ease-in-out;
            }

            .speaking {
                animation: speakPulse 1s infinite ease-in-out;
            }

            @keyframes idlePulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.05); }
                100% { transform: scale(1); }
            }

            @keyframes recordPulse {
                0% { transform: scale(1); box-shadow: 0 0 40px cyan; }
                50% { transform: scale(1.15); box-shadow: 0 0 70px cyan; }
                100% { transform: scale(1); box-shadow: 0 0 40px cyan; }
            }

            @keyframes speakPulse {
                0% { transform: scale(1); box-shadow: 0 0 40px lime; }
                50% { transform: scale(1.12); box-shadow: 0 0 70px lime; }
                100% { transform: scale(1); box-shadow: 0 0 40px lime; }
            }

            #response {
                margin-top: 40px;
                font-size: 18px;
                width: 70%;
                text-align: center;
                line-height: 1.6;
            }
        </style>
    </head>
    <body>

        <div id="halo" class="halo idle"></div>
        <div id="response">Tap the ring and ask about your hair.</div>

        <script>

        let recorder;
        let chunks = [];

        const halo = document.getElementById("halo");

        halo.addEventListener("click", record);

        async function record() {

            halo.classList.remove("idle", "speaking");
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
                        halo.classList.add("idle");
                    };
                }
            };

            recorder.start();

            // 6 seconds = speaking time + 2-3 sec grace delay
            setTimeout(() => {
                recorder.stop();
            }, 6000);
        }

        </script>

    </body>
    </html>
    """

# =====================================================
# PRODUCT DATABASE
# =====================================================

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

# =====================================================
# RULE ENGINE
# =====================================================

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

# =====================================================
# VOICE ROUTE
# =====================================================

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

# =====================================================
# SPEECH
# =====================================================

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

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
