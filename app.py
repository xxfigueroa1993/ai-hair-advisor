import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load API Key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="AI Hair Expert Advisor", layout="centered")

st.title("💇🏽 AI Hair Expert Advisor")
st.subheader("Salon Professional | Organic | Caribbean Engineered")

# -------------------------
# USER INPUTS
# -------------------------

hair_problems = st.multiselect(
    "Select Hair Problem(s)",
    ["Dry", "Damaged", "Tangly", "Lost of Color", "Oily", "Not Bouncy", "Falling Out"]
)

race = st.multiselect(
    "Hair Race Background",
    [
        "American Indian",
        "Asian",
        "African",
        "Hispanic",
        "Pacific Islander",
        "Caucasian"
    ]
)

age_group = st.selectbox(
    "Age",
    ["5-15", "15-35", "35-50", "50+"]
)

allergic = st.selectbox(
    "Allergic to Fish Oil?",
    ["No", "Yes"]
)

season = st.selectbox(
    "Season",
    ["Cold/Winter", "Summer/Hot", "Fall/Cold", "Spring/Warm"]
)

temperature = st.selectbox(
    "Temperature",
    ["-64 - 40", "64 - 75", "75+"]
)

continent = st.selectbox(
    "Continent",
    ["Asia", "Africa", "North America", "South America", "Antarctica", "Europe", "Australia"]
)

# -------------------------
# GPT DECISION ENGINE
# -------------------------

def get_ai_recommendation():

    system_prompt = """
You are Hair Expert Advisor, a salon professional AI.

Mission:
Choose ONE of the following products:
- Formula Exclusiva
- Laciador
- Gotero
- Gotika
- Or return: "Go see medical professional"

Style:
Friendly, Direct, ROI-focused, Analytical.

You MUST prioritize preset rules first.
If no exact preset rule applies, use intelligent reasoning.

Product Definitions:
Formula Exclusiva – Full repair & restoration.
Laciador – Styling & dryness control.
Gotero – Oil control & bounce & strengthening.
Gotika – Color restoration.

Return format:
Product Name:
Reason:
"""

    user_prompt = f"""
Hair Problems: {hair_problems}
Race Background: {race}
Age Group: {age_group}
Allergic to Fish Oil: {allergic}
Season: {season}
Temperature: {temperature}
Continent: {continent}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.4
    )

    return response.choices[0].message.content


# -------------------------
# BUTTON ACTION
# -------------------------

if st.button("Generate AI Recommendation"):

    if not hair_problems or not race:
        st.warning("Please select at least one Hair Problem and one Race Background.")
    else:
        with st.spinner("AI analyzing hair profile..."):
            result = get_ai_recommendation()
            st.success("🎯 AI Recommendation Ready")
            st.write(result)

# -------------------------
# FAQ / CONTACT
# -------------------------

st.markdown("---")
st.subheader("Need Help?")

option = st.radio("Choose Option:", ["None", "FAQ", "Contact Us"])

if option == "FAQ":
    st.write("""
    ✔ Organic Salon Grade  
    ✔ Caribbean Climate Optimized  
    ✔ Professional Competitive Positioning  
    ✔ Designed for ROI-driven retail resale  
    """)

elif option == "Contact Us":
    st.write("""
    📧 support@hairexpertadvisor.com  
    🌎 Global Distribution  
    """)