from flask import Flask, render_template, request, jsonify
import openai
import os

app = Flask(__name__)

# =========================
# CONFIG
# =========================
openai.api_key = os.getenv("OPENAI_API_KEY")

# =========================
# ROUTES
# =========================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_message = request.json.get("message")

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional bright toned salon hair expert giving confident recommendations."},
            {"role": "user", "content": user_message}
        ]
    )

    return jsonify({"reply": response.choices[0].message.content})


if __name__ == "__main__":
    app.run(debug=True)
