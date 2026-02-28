import os
import tempfile
import base64
from flask import Flask, request, jsonify
from openai import OpenAI

os.environ["PYTHONUNBUFFERED"] = "1"

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# =========================
# CATEGORY NORMALIZATION
# =========================

def normalize_input(text):
    text = text.lower()

    hair_problem = None
    race = None
    age_group = None
    allergic = False
    season = None
    temperature = None
    continent = None

    # Hair Problems
    if "dry" in text: hair_problem = "Dry"
    if "damaged" in text: hair_problem = "Damaged"
    if "tangly" in text: hair_problem = "Tangly"
    if "lost of color" in text or "lost color" in text: hair_problem = "Lost of Color"
    if "oily" in text: hair_problem = "Oily"
    if "not bouncy" in text: hair_problem = "Not Bouncy"
    if "falling out" in text: hair_problem = "Falling Out"

    # Race
    if "hispanic" in text: race = "Hispanic"
    if "caucasian" in text or "white" in text: race = "Caucasian"
    if "african" in text or "black" in text: race = "African"
    if "asian" in text: race = "Asian"
    if "island pacific" in text or "pacific islander" in text: race = "Island Pacific"
    if "american indian" in text or "alaska native" in text: race = "American Indian"

    # Age
    if "5" in text or "10" in text or "15" in text or "child" in text:
        age_group = "5-15"
    elif "50" in text or "60" in text or "70" in text:
        age_group = "50+"
    elif "35" in text or "40" in text:
        age_group = "35-50"
    else:
        age_group = "15-35"

    # Allergy
    if "allergic" in text and "fish" in text:
        allergic = True

    return hair_problem, race, age_group, allergic, season, temperature, continent


# =========================
# RULE ENGINE
# =========================

def choose_product(hair_problem, race, age_group, allergic):

    if allergic:
        return "Error / Go see medical"

    under_16 = age_group == "5-15"

    # ---- PRESET RULES ----

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

    # Under 16 medical blocks
    if under_16 and hair_problem == "Lost of Color":
        return "Error / Go see medical"

    if under_16 and race in ["Asian","Pacific Islander","Hispanic"] and hair_problem == "Lost of Color":
        return "Error / Go see medical"

    # Preset exact match
    if (hair_problem, race) in preset_rules:
        return preset_rules[(hair_problem, race)]

    # ---- AI FALLBACK ----
    # Only if no preset matched

    if hair_problem in ["Damaged","Falling Out"]:
        return "Formula Exclusiva"

    if hair_problem == "Oily":
        return "Gotero"

    if hair_problem in ["Dry","Tangly","Not Bouncy"]:
        return "Laciador"

    if hair_problem == "Lost of Color":
        return "Gotika"

    return "Formula Exclusiva"


# =========================
# ROUTES
# =========================

@app.route("/voice", methods=["POST"])
def voice():

    file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        path = temp_audio.name

    # Transcribe
    with open(path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    user_text = transcript.strip()

    hair_problem, race, age_group, allergic, season, temperature, continent = normalize_input(user_text)

    product = choose_product(hair_problem, race, age_group, allergic)

    # Generate natural sounding voice output
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
