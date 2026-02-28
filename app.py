import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

# =========================================
# CONFIG
# =========================================

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =========================================
# HOME ROUTE (Health Check)
# =========================================

@app.route("/", methods=["GET"])
def home():
    return """
    <h1>AI Hair Advisor is Running</h1>
    <p>Use POST /voice to send audio.</p>
    """

# =========================================
# INPUT NORMALIZATION
# =========================================

def normalize_input(text):
    print("Raw transcript:", text)

    text = text.lower()

    # RESET EACH REQUEST
    hair_problem = None
    race = None
    age_group = "15-35"
    allergic = False

    # -------- Hair Problems --------
    if "dry" in text:
        hair_problem = "Dry"
    elif "damaged" in text:
        hair_problem = "Damaged"
    elif "tangly" in text:
        hair_problem = "Tangly"
    elif "lost of color" in text or "lost color" in text:
        hair_problem = "Lost of Color"
    elif "oily" in text:
        hair_problem = "Oily"
    elif "not bouncy" in text:
        hair_problem = "Not Bouncy"
    elif "falling out" in text:
        hair_problem = "Falling Out"

    # -------- Race --------
    if "hispanic" in text:
        race = "Hispanic"
    elif "caucasian" in text or "white" in text:
        race = "Caucasian"
    elif "african" in text or "black" in text:
        race = "African"
    elif "asian" in text:
        race = "Asian"
    elif "pacific islander" in text or "island pacific" in text:
        race = "Island Pacific"
    elif "american indian" in text:
        race = "American Indian"

    # -------- Age --------
    if any(word in text for word in ["5", "6", "7", "8", "9", "10", "child"]):
        age_group = "5-15"
    elif any(word in text for word in ["50", "60", "70"]):
        age_group = "50+"
    elif any(word in text for word in ["35", "40"]):
        age_group = "35-50"

    # -------- Allergy --------
    if "allergic" in text:
        allergic = True

    print("Mapped:")
    print("Hair:", hair_problem)
    print("Race:", race)
    print("Age:", age_group)
    print("Allergic:", allergic)

    return hair_problem, race, age_group, allergic


# =========================================
# RULE ENGINE (DETERMINISTIC)
# =========================================

def choose_product(hair_problem, race, age_group, allergic):

    # Allergy override
    if allergic:
        return "Error / Go see medical"

    under_16 = age_group == "5-15"

    # Medical blocking
    if under_16 and hair_problem == "Lost of Color":
        return "Error / Go see medical"

    # Deterministic preset matrix
    preset_rules = {

        ("Lost of Color","Hispanic"): "Gotika",
        ("Dry","African"): "Laciador",
        ("Damaged","Caucasian"): "Formula Exclusiva",
        ("Oily","Asian"): "Gotero",
        ("Dry","Caucasian"): "Laciador",
        ("Dry","Asian"): "Formula Exclusiva",
        ("Damaged","Hispanic"): "Formula Exclusiva",
        ("Oily","African"): "Gotero",
        ("Damaged","Asian"): "Formula Exclusiva",
        ("Not Bouncy","Caucasian"): "Gotero",
        ("Tangly","Hispanic"): "Laciador",
        ("Tangly","Caucasian"): "Formula Exclusiva",
        ("Tangly","Asian"): "Formula Exclusiva",
        ("Tangly","African"): "Laciador",
        ("Falling Out","African"): "Gotero",
        ("Falling Out","Caucasian"): "Formula Exclusiva",
        ("Falling Out","Asian"): "Formula Exclusiva",
        ("Falling Out","Hispanic"): "Formula Exclusiva",
        ("Lost of Color","Caucasian"): "Gotika",
        ("Lost of Color","African"): "Gotero",
        ("Not Bouncy","Hispanic"): "Laciador",
        ("Not Bouncy","Asian"): "Gotero",
        ("Damaged","African"): "Formula Exclusiva",
        ("Oily","Caucasian"): "Gotero",
        ("Oily","Hispanic"): "Formula Exclusiva",
        ("Lost of Color","Asian"): "Gotika",
        ("Dry","Hispanic"): "Laciador",
        ("Lost of Color","Island Pacific"): "Formula Exclusiva",
        ("Dry","Island Pacific"): "Laciador",
        ("Oily","Island Pacific"): "Formula Exclusiva",
        ("Damaged","Island Pacific"): "Gotero",
        ("Not Bouncy","Island Pacific"): "Laciador",
        ("Falling Out","Island Pacific"): "Formula Exclusiva",
        ("Lost of Color","American Indian"): "Gotika",
        ("Dry","American Indian"): "Gotero",
        ("Oily","American Indian"): "Formula Exclusiva",
        ("Damaged","American Indian"): "Laciador",
        ("Not Bouncy","American Indian"): "Gotero",
        ("Falling Out","American Indian"): "Formula Exclusiva",
    }

    # Exact match
    if (hair_problem, race) in preset_rules:
        return preset_rules[(hair_problem, race)]

    # Controlled fallback (still deterministic)
    if hair_problem in ["Damaged", "Falling Out"]:
        return "Formula Exclusiva"
    if hair_problem == "Oily":
        return "Gotero"
    if hair_problem in ["Dry", "Tangly", "Not Bouncy"]:
        return "Laciador"
    if hair_problem == "Lost of Color":
        return "Gotika"

    return "Formula Exclusiva"


# =========================================
# VOICE ROUTE
# =========================================

@app.route("/voice", methods=["POST"])
def voice():

    print("===== VOICE ROUTE HIT =====")

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        audio_path = temp_audio.name

    print("Audio saved:", audio_path)

    # Transcription
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    user_text = transcript.strip()

    hair_problem, race, age_group, allergic = normalize_input(user_text)

    product = choose_product(hair_problem, race, age_group, allergic)

    print("Final Product:", product)

    # Voice response
    speech = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=f"I recommend {product}."
    )

    audio_bytes = speech.read()
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    return jsonify({
        "text": product,
        "audio": audio_base64
    })


# =========================================
# RUN SERVER
# =========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
