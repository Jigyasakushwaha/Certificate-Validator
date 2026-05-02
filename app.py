import os
import re
import pytesseract
from PIL import Image
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

# Ensure you import the new extraction function from your forensics.py
from forensics import run_ela, extract_certificate_data

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

        # 1. Forensic analysis (Existing)
        ela_filename = run_ela(img_path)

        # 2. Improved OCR & ID Extraction (Now includes QR)
        # Using the helper from forensics.py to handle image cleaning and ID regex
        try:
            raw_text, detected_id = extract_certificate_data(img_path)
            from forensics import scan_qr_code
            qr_check = scan_qr_code(img_path)
            source_tag = "[QR Detected]" if qr_check else "[OCR Extracted]"
        except Exception as e:
            print(f"Extraction Error: {e}")
            raw_text, detected_id, source_tag = "", "Not Found", ""
        
        status = "INVALID FORMAT"
        details = "No valid Certificate ID found on document"

        # 3. Database Validation
        if detected_id != "Not Found":
            # Strip extra whitespace or characters
            clean_id = detected_id.strip()
            doc = db.collection('certificates').document(clean_id).get()

            if doc.exists:
                data = doc.to_dict()
                # Secondary check: See if owner name from DB exists in OCR text
                db_name = data.get('Name', 'Unknown')
                if db_name.lower() in raw_text.lower():
                    status = "✅ VERIFIED"
                    details = f"Authenticated for: {db_name} {source_tag}"
                else:
                    status = "⚠️ TAMPERED"
                    details = f"Identity Mismatch: DB shows {db_name}, but image differs."
            else:
                status = "⚠️ UNREGISTERED"
                details = f"ID {clean_id} {source_tag} not found in central repository"

        results.append({
            "name": file.filename,
            "status": status,
            "info": details,
            "original_img": f"uploads/{safe_name}",
            "forensic_img": ela_filename
        })

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)
