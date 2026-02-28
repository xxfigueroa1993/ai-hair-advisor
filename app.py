import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# ======================
# OPENAI CLIENT
# ======================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ======================
# ROUTES
# ======================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_message = data.get("message", "")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a confident, bright-toned, professional salon hair expert. Give clear, specific recommendations."
                },
                {"role": "user", "content": user_message}
            ]
        )

        reply = response.choices[0].message.content
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": "I'm having a temporary connection issue. Please try again."})


# ======================
# RUN (Render Compatible)
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
