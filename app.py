import streamlit as st
import os
import google.generativeai as genai
from dotenv import load_dotenv
import re
import pandas as pd
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# --- FEATURE 2: Data Persistence Setup ---
DATA_FILE = Path("candidate_data.csv")

def save_data(data):
    """Appends a new candidate's data to a CSV file."""
    new_data_df = pd.DataFrame([data])
    if DATA_FILE.is_file():
        existing_df = pd.read_csv(DATA_FILE)
        combined_df = pd.concat([existing_df, new_data_df], ignore_index=True)
    else:
        combined_df = new_data_df
    combined_df.to_csv(DATA_FILE, index=False)

# --- Page Configuration & UI Setup ---
st.set_page_config(
    page_title="TalentScout Assistant",
    page_icon="🤖",
    layout="centered"
)

# --- AI Model Configuration ---
try:
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
except Exception as e:
    st.error(f"Error configuring the AI model: {e}")
    st.stop()

# --- FEATURE 3: Sidebar for Layout ---
with st.sidebar:
    st.image("logo.jpg", width=70) # Placeholder logo
    st.title("TalentScout Screening")
    st.write("Welcome to the initial screening process. Please follow the instructions from our AI assistant.")
    # --- FEATURE 1: Progress Bar ---
    st.session_state.progress_bar = st.progress(0, text="Screening Progress")

# --- Input Validation Functions ---
def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)
def validate_phone(phone):
    return re.match(r"^\+?\d{10,15}$", phone)
def validate_experience(experience):
    return experience.isdigit()

VALIDATION_RULES = {
    "Email Address": (validate_email, "That doesn't look like a valid email. Please try again."),
    "Phone Number": (validate_phone, "Please enter a valid phone number (10-15 digits)."),
    "Years of Experience": (validate_experience, "Please enter a number for your years of experience.")
}

# --- State Management and Application Logic ---
INFO_SEQUENCE = ["Full Name", "Email Address", "Phone Number", "Years of Experience", "Desired Position(s)", "Current Location", "Tech Stack"]
# --- REMOVED: TOTAL_STEPS constant is no longer needed ---

# --- FIXED: The update_progress function is now more robust ---
def update_progress():
    """Updates the progress bar based on the dynamic current state."""
    total_questions = len(st.session_state.get('questions', []))
    # If questions haven't been generated yet, assume 4 for a smooth initial progress
    if total_questions == 0:
        total_questions = 4 
    
    total_steps = len(INFO_SEQUENCE) + total_questions
    
    current_step = 0
    if st.session_state.stage == 'info_gathering':
        current_step = len(st.session_state.candidate_data)
    elif st.session_state.stage == 'asking_questions':
        current_step = len(INFO_SEQUENCE) + st.session_state.question_index
    elif st.session_state.stage == 'completed':
        current_step = total_steps

    # Calculate progress and use min() as a safeguard
    progress = min(current_step / total_steps, 1.0)
    
    st.session_state.progress_bar.progress(progress, text=f"Step {current_step} / {total_steps}")


# Initialize session state
if 'stage' not in st.session_state:
    st.session_state.stage = 'info_gathering'
    st.session_state.chat_history = [{"role": "assistant", "content": "Hello! I'm an AI hiring assistant. I'll be conducting your initial screening. Let's start with your **Full Name**, please."}]
    st.session_state.candidate_data = {}
    st.session_state.current_info_needed = "Full Name"
    st.session_state.questions = []
    st.session_state.question_index = 0
    st.session_state.answers = []

# --- Main App Interface ---
st.header("🤖 Your AI Hiring Assistant")
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Main Logic ---
if st.session_state.stage != 'completed':
    if prompt := st.chat_input("Your response..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        current_stage = st.session_state.stage
        
        if current_stage == 'info_gathering':
            info_key = st.session_state.current_info_needed
            is_valid = True
            if info_key in VALIDATION_RULES:
                validator, error_message = VALIDATION_RULES[info_key]
                if not validator(prompt):
                    is_valid = False
                    response = error_message
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    with st.chat_message("assistant"): st.markdown(response)
            
            if is_valid:
                st.session_state.candidate_data[info_key] = prompt
                update_progress()
                current_index = INFO_SEQUENCE.index(info_key)
                if current_index + 1 < len(INFO_SEQUENCE):
                    next_info_key = INFO_SEQUENCE[current_index + 1]
                    st.session_state.current_info_needed = next_info_key
                    response = f"Thank you. Now, could you please provide your **{next_info_key}**?"
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    with st.chat_message("assistant"): st.markdown(response)
                else:
                    st.session_state.stage = 'question_generation'
                    st.rerun()

        elif current_stage == 'asking_questions':
            st.session_state.answers.append(prompt)
            st.session_state.question_index += 1
            update_progress()
            if st.session_state.question_index < len(st.session_state.questions):
                next_question = st.session_state.questions[st.session_state.question_index]
                st.session_state.chat_history.append({"role": "assistant", "content": next_question})
                with st.chat_message("assistant"): st.markdown(next_question)
            else:
                st.session_state.candidate_data["Technical Answers"] = " | ".join(st.session_state.answers)
                response = "Thank you for your answers. A recruiter will review your profile and be in touch soon. Have a great day!"
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                with st.chat_message("assistant"): st.markdown(response)
                st.session_state.stage = 'completed'
                st.rerun()

if st.session_state.stage == 'question_generation':
    with st.chat_message("assistant"):
        with st.spinner("Analyzing your tech stack and generating questions..."):
            tech_stack = st.session_state.candidate_data.get("Tech Stack")
            question_prompt = f"Generate a numbered list of exactly 4 technical screening questions for a candidate with the tech stack: {tech_stack}."
            response_model = model.generate_content(question_prompt)
            questions = [q.strip() for q in response_model.text.strip().split('\n') if q.strip()]
            st.session_state.questions = questions
            first_question = questions[0]
            response = f"Great, thank you. I have a few technical questions for you.\n\n{first_question}"
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.markdown(response)
            st.session_state.stage = 'asking_questions'
            update_progress()

if st.session_state.stage == 'completed':
    st.success("Screening process completed!")
    st.balloons()
    save_data(st.session_state.candidate_data)
    update_progress()
    st.subheader("Your Submitted Information")
    for key, value in st.session_state.candidate_data.items():
        if key == "Technical Answers":
            st.markdown(f"**{key}:**")
            answers_list = value.split(" | ")
            for i, answer in enumerate(answers_list, 1):
                st.markdown(f"{i}. {answer}")
        else:
            st.markdown(f"**{key}:** {value}")