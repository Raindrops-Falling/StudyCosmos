from flask import Flask, request, render_template, redirect, url_for, session, flash
import os
import requests
import fitz  # PyMuPDF for PDF text extraction
import time
import re

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key")  # Set securely in prod

AI_API_KEY = "9569c154abea1ae413f654aefac871282908ff62652d92b15ce4ffb7126baa5e"


def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    return text


def chunk_text(text, max_length=1000):
    words = text.split()
    chunks = []
    current_chunk = ""

    for word in words:
        if len(current_chunk) + len(word) + 1 <= max_length:
            current_chunk += (" " if current_chunk else "") + word
        else:
            chunks.append(current_chunk)
            current_chunk = word

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def call_together_ai(api_key, prompt):
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",  # ✅ Correct full model name
        "messages": [
            {"role": "system", "content": "You are a helpful AI tutor."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.7
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    uploaded_file = request.files.get('file')

    if uploaded_file:
        try:
           
            text = extract_text_from_pdf(uploaded_file)
            if not text.strip():
                flash("The uploaded file contains no readable text.")
                return redirect(url_for('home'))
            
            
            session['text_chunks'] =chunk_text(text)
            return redirect(url_for('options'))
        except Exception as e:
            flash(f"Failed to process file: {e}")
            return redirect(url_for('home'))
    flash("No file uploaded.")
    return redirect(url_for('home'))


@app.route('/options')
def options():
    if 'text_chunks' not in session:
        flash("Please upload a file first.")
        return redirect(url_for('home'))
    return render_template('options.html')


@app.route('/practice_quiz', methods=['GET', 'POST'])
def practice_quiz():
    return render_template('practice_quiz.html')
@app.route('/generate_quiz', methods=['POST'])
def generate_quiz():
    import re

    question_count = int(request.form.get('question_count', 10))

    # Get text from session
    text_chunks = session.get('text_chunks')
    if not text_chunks:
        flash("Please upload a file before generating a quiz.")
        return redirect(url_for('home'))

    file_text = ' '.join(text_chunks)

    # Compose the AI prompt
    prompt = (
        f"Generate {question_count} quiz questions and answers from the following study material. If math is present, use LaTeX formatting.:\n\n"
        f"{file_text}\n\n"
        "Use this format exactly:\n"
        "1. What is X? Or How is X related to something? Or insert a question based on previous questions in the notes.\n"
        "Answer: It is Y.\n\n"
        "2. What is ...?\n"
        "Answer: ...\n\n"
        "Be consistent and make sure every question is followed by its answer."
    )

    try:
        ai_response = call_together_ai(AI_API_KEY, prompt)
    except Exception as e:
        flash(f"Error communicating with AI: {e}")
        return redirect(url_for('practice_quiz'))

    print("=== AI RESPONSE ===")
    print(ai_response)

    # Match using a relaxed but robust regex
    pattern = r"\d+[.)]\s*(.+?)\s*Answer:\s*(.+?)(?=\n\d+[.)]|\Z)"
    matches = re.findall(pattern, ai_response, re.DOTALL)

    qa_pairs = []
    for q, a in matches:
        question = q.strip()
        answer = a.strip()
        if question and answer:
            qa_pairs.append({'question': question, 'answer': answer})

    if not qa_pairs:
        flash("No quiz content could be parsed. Try rephrasing your file or re-uploading.")
        return redirect(url_for('practice_quiz'))

    # Store answers and pass only questions to template
    session['quiz_answers'] = [pair['answer'] for pair in qa_pairs]
    return render_template('generate_quiz.html', questions=[pair['question'] for pair in qa_pairs])






# Add stubs for simulation, dashboard save, etc., as needed

if __name__ == '__main__':
    app.run(debug=True, port=5002)  # Change port if 5000 busy