from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_session import Session
from werkzeug.utils import secure_filename
import os
import re
import json
from transformers import pipeline
import PyPDF2
from docx import Document
from io import BytesIO
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)

# Configure server-side session
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_FILE_DIR'] = './flask_session'
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
Session(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load job roles and keywords
JOB_ROLES_FILE = "job_roles.json"
with open(JOB_ROLES_FILE, "r") as file:
    JOB_ROLES = json.load(file)

# Load classifier
classifier = pipeline('zero-shot-classification', model='facebook/bart-large-mnli')

def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, "rb") as f:
        pdf_reader = PyPDF2.PdfReader(f)
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
    return text.strip()

def extract_text_from_docx(file_path):
    document = Document(file_path)
    return " ".join([p.text for p in document.paragraphs]).strip()

def match_keywords(resume_text, job_keywords):
    return [kw for kw in job_keywords if re.search(rf"\b{kw}\b", resume_text.lower())]

def create_bar_chart(keyword_results):
    roles = list(keyword_results.keys())
    scores = [keyword_results[role]['score'] for role in roles]

    plt.figure(figsize=(10, 6))
    plt.barh(roles, scores, color='skyblue')
    plt.xlabel('Matching Score (%)')
    plt.ylabel('Job Roles')
    plt.title('Keyword Matching Scores by Job Role')
    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()
    return plot_url

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if "resume" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["resume"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Extract resume text
        if filename.endswith(".pdf"):
            resume_text = extract_text_from_pdf(file_path)
        elif filename.endswith(".docx"):
            resume_text = extract_text_from_docx(file_path)
        else:
            return jsonify({"error": "Unsupported file format. Please upload a PDF or DOCX file."}), 400

        # Keyword matching
        keyword_results = {}
        for role, keywords in JOB_ROLES.items():
            matched_keywords = match_keywords(resume_text, keywords)
            keyword_results[role] = {
                "matched_keywords": matched_keywords,
                "total_keywords": len(keywords),
                "score": round(len(matched_keywords) / len(keywords) * 100, 2) if keywords else 0
            }

        # Generate bar chart
        plot_url = create_bar_chart(keyword_results)

        # BERT classification
        bert_results = classifier(resume_text, list(JOB_ROLES.keys()), multi_label=True)

        # Save to session
        session["resume_text"] = resume_text[:5000]
        session["keyword_results"] = keyword_results
        session["bert_results"] = bert_results
        session["plot_url"] = plot_url

        return jsonify({"success": "File uploaded successfully", "redirect": url_for("results_page")})

    except Exception as e:
        import traceback
        traceback.print_exc()  # Logs the error for debugging
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/results")
def results_page():
    if "resume_text" not in session:
        return redirect(url_for("index"))

    return render_template(
        "results.html",
        resume_text=session["resume_text"],
        keyword_results=session["keyword_results"],
        bert_results=session["bert_results"],
        plot_url=session["plot_url"],
        zip=zip
    )

# Optional: Handle missing favicon.ico requests to avoid console warnings
@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)