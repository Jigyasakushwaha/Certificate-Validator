import os
import cv2
import re
import pytesseract
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, redirect, url_for
from forensics import run_ela, extract_certificate_data

# 🔥 SET TESSERACT PATH (Windows)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Initialize Flask
app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'

# --- FIREBASE INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------- ROUTES ---------------- #

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/verify', methods=['POST'])
def verify():
    file = request.files.get('file')
    mode = request.form.get('mode', 'database')

    if not file:
        return redirect(url_for('index'))

    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)

    # 🔥 OCR + extraction
    raw_text, cert_id, quality = extract_certificate_data(path)

    print("MODE:", mode)
    print("CERT ID:", cert_id)
    print("TEXT:", raw_text[:200])

    # ---------------- ID NOT FOUND ---------------- #
    if cert_id == "NOT_FOUND":
        return render_template("results.html",
                               mode=mode.upper(),
                               status="INVALID",
                               info="Certificate ID not detected",
                               quality=quality)

    # ---------------- DATABASE CHECK ---------------- #
    doc = db.collection('certificates').document(cert_id).get()

    if not doc.exists:
        status = "FAKE"
        info = f"ID {cert_id} is not in the registry."
    else:
        db_data = doc.to_dict()

        # 🔥 Normalize DB values
        official_name = str(db_data.get('Name', '')).upper().strip()
        official_dob = str(db_data.get('DOB', '')).strip().replace('/', '-')

        # 🔥 Normalize OCR text
        ocr_clean = " ".join(raw_text.upper().split()).replace('/', '-')

        print(f"DEBUG: Name [{official_name}]")
        print(f"DEBUG: DOB [{official_dob}]")

        # ---------------- NAME MATCH ---------------- #
        name_parts = official_name.split()
        name_match_score = sum(1 for part in name_parts if part in ocr_clean)
        name_match = name_match_score >= max(1, len(name_parts)//2)

        # ---------------- DOB EXTRACTION ---------------- #
        dob_patterns = [
            r'\b\d{2}[-/]\d{2}[-/]\d{4}\b',
            r'\b\d{4}[-/]\d{2}[-/]\d{2}\b'
        ]

        ocr_dobs = []
        for pattern in dob_patterns:
            ocr_dobs.extend(re.findall(pattern, ocr_clean))

        # ---------------- DOB LOGIC ---------------- #
        dob_match = True  # default safe

        if official_dob:
            if len(ocr_dobs) == 0:
                dob_match = None  # no DOB detected
            else:
                normalized_ocr_dobs = [d.replace('/', '-') for d in ocr_dobs]

                if official_dob in normalized_ocr_dobs:
                    dob_match = True
                else:
                    dob_match = False  # ❌ real mismatch

        # ---------------- FINAL DECISION ---------------- #
        if name_match:
            if dob_match is False:
                status = "TAMPERED"
                info = f"DOB Mismatch! Registry says {official_dob}."
            else:
                status = "AUTHENTIC"
                info = f"Verified record for {official_name}"

                if dob_match is None:
                    info += " | DOB not clearly detected"
        else:
            status = "TAMPERED"
            info = f"Name Mismatch! Registry says {official_name}."

    # ---------------- QUALITY WARNING ---------------- #
    if quality == "Low/Blurry":
        info += " | Warning: Low image quality detected"

    # ---------------- FORENSIC MODE ---------------- #
    ela_path = None
    if mode == "forensic":
        ela_path = run_ela(path)

    return render_template("results.html",
                           mode=mode.upper(),
                           status=status,
                           info=info,
                           quality=quality,
                           cert_id=cert_id,
                           original_img=f"uploads/{file.filename}",
                           forensic_img=ela_path)


if __name__ == '__main__':
    app.run(debug=True, port=5000)