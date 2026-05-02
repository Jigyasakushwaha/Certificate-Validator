import os
import re
import pytesseract
from PIL import Image
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

# Import extraction functions from forensics.py
from forensics import run_ela, extract_certificate_data, scan_qr_code

app = Flask(__name__)
CORS(app)

# OCR engine path setup
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Firebase initialization
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

        # Sanitize filename and save locally
        safe_name = file.filename.replace(" ", "_")
        img_path = os.path.join(UPLOAD_FOLDER, safe_name)
        file.save(img_path)

        # 1. Forensic ELA analysis
        ela_filename = run_ela(img_path)

        # 2. Multi-Vector Extraction (Quality + QR + OCR)
        try:
            # extract_certificate_data now returns: text, id, and quality_status
            raw_text, detected_id, quality = extract_certificate_data(img_path)
            
            # Check if QR was the source for the ID
            qr_check = scan_qr_code(img_path)
            source_tag = "[QR Detected]" if qr_check else "[OCR Extracted]"
        except Exception as e:
            print(f"Extraction Engine Error: {e}")
            raw_text, detected_id, quality, source_tag = "", "Not Found", "Unknown", ""
        
        # Default status for unrecognized or poor quality formats
        status = "INVALID FORMAT"
        details = "Operational Failure: Unique Identifier (UID) could not be anchored."

        # --- QUALITY GATE LOGIC ---
        # If the image is blurry, we stop the check to prevent false 'Forger' flags
        if quality == "Low/Blurry":
            status = "⚠️ QUALITY ALERT"
            details = "Signal interference or low resolution detected. Please re-upload a clear photograph."
        
        # 3. Database Validation (Only proceed if quality is 'Good' and ID exists)
        elif detected_id != "Not Found" and detected_id != "NOT_FOUND":
            clean_id = detected_id.strip()
            doc = db.collection('certificates').document(clean_id).get()

            if doc.exists:
                data = doc.to_dict()
                db_name = data.get('Name', 'Unknown')
                
                # Secondary validation: Cross-reference DB name against OCR text
                if db_name.lower() in raw_text.lower():
                    status = "✅ VERIFIED"
                    details = f"Authenticated for: {db_name} {source_tag}"
                else:
                    status = "⚠️ TAMPERED"
                    details = f"Security Mismatch: Record for {db_name} found, but image data differs."
            else:
                status = "⚠️ UNREGISTERED"
                details = f"Identifier {clean_id} {source_tag} not found in central repository."

        results.append({
            "name": file.filename,
            "status": status,
            "info": details,
            "original_img": f"uploads/{safe_name}",
            "forensic_img": ela_filename
        })

    return jsonify(results)

if __name__ == "__main__":
    # Running in debug mode for the hackathon development phase
    app.run(debug=True)
    
