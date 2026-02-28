import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =====================================================
# FRONTEND (UNCHANGED – YOUR PERFECT VERSION)
# =====================================================

@app.route("/", methods=["GET"])
def home():
    return open("frontend.html").read() if os.path.exists("frontend.html") else "Frontend Loaded Separately"


# =====================================================
# PRODUCT DATABASE (ONLY YOUR PRODUCTS)
# =====================================================

PRODUCTS = {
    "Laciador": {
        "price": 34.99,
        "tags": ["frizz","frizzy","dry","damaged","tangly","tangle","split ends","puffy"]
    },
    "Gotero": {
        "price": 29.99,
        "tags": ["oily","greasy","itchy scalp","oil buildup"]
    },
    "Volumizer": {
        "price": 39.99,
        "tags": ["flat","not bouncy","thin","falling","falling out","hair loss","no volume"]
    },
    "Color Protect": {
        "price": 36.99,
        "tags": ["color","lost color","fading","dull color","dyed hair"]
    },
    "Formula Exclusiva": {
        "price": 49.99,
        "tags": [
            "all in one",
            "all-in-one",
            "everything",
            "complete care",
            "full treatment",
            "total repair",
            "all problems",
            "combo solution"
        ]
    }
}

# =====================================================
# SMART MATCHER
# =====================================================

def match_product(text):
    text = text.lower()

    # First priority: Formula Exclusiva direct match
    for tag in PRODUCTS["Formula Exclusiva"]["tags"]:
        if tag in text:
            return "Formula Exclusiva", PRODUCTS["Formula Exclusiva"]["price"]

    # Check other products
    for product, data in PRODUCTS.items():
        if product == "Formula Exclusiva":
            continue
        for tag in data["tags"]:
            if tag in text:
                return product, data["price"]

    return None, None


# =====================================================
# GLOBAL LANGUAGE SUPPORT PROMPT
# =====================================================

SYSTEM_PROMPT = """
You are a luxury hair care AI advisor.

IMPORTANT RULES:
- Only recommend one of these exact products:
  Laciador, Gotero, Volumizer, Color Protect, Formula Exclusiva.
- NEVER invent product names.
- ALWAYS include the price in the recommendation.
- If user asks for an all-in-one solution → recommend Formula Exclusiva.
- If user mentions frizz → recommend Laciador.
- If oily → Gotero.
- If flat or falling out → Volumizer.
- If color fading → Color Protect.

If you do NOT understand the user:
Politely guide them by saying something like:
"I didn’t quite understand. You can say things like Frizz, Dry, Oily, Falling Out, or Lost Color."

Respond in the SAME language the user speaks.
Support all global languages automatically.
Keep responses premium and confident.
"""


# =====================================================
# VOICE ENDPOINT
# =====================================================

@app.route("/voice", methods=["POST"])
def voice():
    file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp:
        file.save(temp.name)
        temp_path = temp.name

    # Transcribe (auto language detection global)
    with open(temp_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    user_text = transcript.strip()

    product, price = match_product(user_text)

    if product:
        ai_message = f"I recommend {product}. It is perfect for your concern. The price is ${price}."
    else:
        ai_message = (
            "I didn’t quite understand your concern. "
            "You can say things like Frizz, Dry, Oily, Falling Out, Lost Color, "
            "or ask for an All-In-One solution."
        )

    return speak(ai_message)


# =====================================================
# TEXT TO SPEECH
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
# RUN SERVER
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
