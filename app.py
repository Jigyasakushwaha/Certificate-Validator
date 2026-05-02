import os
import re
import pytesseract
from PIL import Image
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

from forensics import run_ela

app = Flask(__name__)
CORS(app)


# OCR setup
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Firebase init
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    # Matches the 'file' key appended in your index.html JS
    files = request.files.getlist('file')

    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    results = []

    for file in files:
        if file.filename == '':
            continue

        safe_name = file.filename.replace(" ", "_")
        img_path = os.path.join(UPLOAD_FOLDER, safe_name)
        file.save(img_path)

        # Forensic analysis
        ela_filename = run_ela(img_path)

        # OCR
        try:
            extracted_text = pytesseract.image_to_string(Image.open(img_path))
        except:
            extracted_text = ""
        
        # Regex for ID (e.g., ABC-1234)
        id_pattern = r'[A-Z]{3,4}-\d{4}(?:-\d+)?'
        found_ids = re.findall(id_pattern, extracted_text)

        status = "❌ INVALID FORMAT"
        details = "No valid Certificate ID found on document"

        if found_ids:
            detected_id = found_ids[0].strip()
            doc = db.collection('certificates').document(detected_id).get()

            if doc.exists:
                data = doc.to_dict()
                status = f"✅ VERIFIED"
                details = f"ID: {detected_id} | Owner: {data.get('Name', 'Unknown')}"
            else:
                status = "⚠️ UNREGISTERED"
                details = f"ID {detected_id} not found in database"

        results.append({
            "name": file.filename,
            "status": status,
            "info": details,
            "original_img": f"uploads/{safe_name}",
            "forensic_img": ela_filename
        })

    # Return as JSON for the index.html to process
    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)