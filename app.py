import os
import re
import pytesseract
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, redirect, url_for
from forensics import run_ela, extract_certificate_data

# Tesseract path (Windows)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'

# --- FIREBASE INIT ---
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


# --- HOME ROUTE ---
@app.route('/')
def index():
    return render_template('index.html')


# --- VERIFY ROUTE ---
@app.route('/verify', methods=['POST'])
def verify():

    file = request.files.get('file')
    mode = request.form.get('mode', 'verify')

    if not file:
        return redirect(url_for('index'))

    # Save file
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)

    # OCR + extraction
    
    result = extract_certificate_data(path)

    if result:
     raw_text, cert_id, extracted_name, quality = result
    else:
     raw_text, cert_id, extracted_name, quality = "", "NOT_FOUND", "NOT FOUND", "ERROR"

    print("MODE:", mode)
    print("CERT ID:", cert_id)
    print("NAME:", extracted_name)

    # =========================
    # 🚨 QUALITY CHECK FIRST
    # =========================
    if quality == "Low/Blurry":
        return render_template("results.html",
                               mode="QUALITY CHECK",
                               status="INVALID",
                               info="Please upload a clearer image for accurate analysis.",
                               quality=quality,
                               cert_id="N/A",
                               extracted_name="N/A",
                               score=0,
                               report=["Image quality too low for reliable OCR."])

    # =========================
    # 🔹 MODE: QUALITY ONLY
    # =========================
    if mode == "quality":

        ela_path = run_ela(path)

        return render_template("results.html",
                               mode="QUALITY ANALYSIS",
                               status="ANALYZED",
                               info="Image analyzed for quality and tampering.",
                               quality=quality,
                               cert_id="N/A",
                               extracted_name="N/A",
                               score=20,
                               report=[
                                   "Image processed successfully.",
                                   "ELA forensic scan applied.",
                                   "No strong tampering indicators detected."
                               ],
                               original_img=f"uploads/{file.filename}",
                               forensic_img = ela_path if ela_path else None)
    
    # =========================
    # 🔹 VALIDATION MODE
    # =========================

    if cert_id == "NOT_FOUND":
        return render_template("results.html",
                               mode="VERIFICATION",
                               status="INVALID",
                               info="Certificate ID not detected",
                               quality=quality,
                               cert_id="NOT FOUND",
                               extracted_name=extracted_name,
                               score=20,
                               report=["OCR failed to detect certificate ID."])

    # --- DATABASE CHECK ---
    doc = db.collection('certificates').document(cert_id).get()

    if not doc.exists:
        status = "NOT REGISTERED"
        info = f"ID {cert_id} not found in registry."

    else:
        db_data = doc.to_dict()

        official_name = str(db_data.get('Name', '')).upper().strip()
        official_dob = str(db_data.get('DOB', '')).strip().replace("/", "-")

        # Normalize OCR
        ocr_clean = " ".join(raw_text.upper().split()).replace("/", "-")

        # --- NAME MATCH ---
        name_parts = official_name.split()
        name_match = sum(1 for p in name_parts if p in ocr_clean) >= max(1, len(name_parts)//2)

        # --- DOB CHECK ---
        dob_pattern = r'\b\d{2}-\d{2}-\d{4}\b'
        found_dobs = re.findall(dob_pattern, ocr_clean)

        dob_present_in_cert = len(found_dobs) > 0
        dob_match = official_dob in found_dobs

        # --- FINAL DECISION ---
        if not name_match:
            status = "MISMATCH"
            info = f"Name mismatch with registry ({official_name})"

        else:
            if dob_present_in_cert:
                if dob_match:
                    status = "AUTHENTIC"
                    info = f"Verified: {official_name} (DOB matched)"
                else:
                    status = "TAMPERED"
                    info = f"DOB mismatch! Expected {official_dob}"
            else:
                status = "AUTHENTIC"
                info = f"Verified: {official_name} (No DOB found)"

    # =========================
    # 🔥 TAMPER ANALYSIS
    # =========================

    tamper_score = 0
    report = []

    if status == "NOT REGISTERED":
        tamper_score += 50
        report.append("Certificate ID not found in database.")

    if status == "MISMATCH":
        tamper_score += 40
        report.append("Name mismatch detected.")

    if status == "TAMPERED":
        tamper_score += 40
        report.append("DOB mismatch detected.")
        # Only block if EXTREMELY bad
    if quality == "Low/Blurry" and cert_id == "NOT_FOUND" and extracted_name == "NOT FOUND":
      status = "INVALID"
    report.append("Image too blurry for reliable detection.")

    tamper_score = min(tamper_score, 100)

    if tamper_score > 60:
        report.append("High probability of tampering.")
    else:
        report.append("No strong tampering evidence.")

    # Always run forensic scan
    ela_path = run_ela(path)
    report.append("Forensic scan applied (ELA).")
    print("ELA PATH:", ela_path)

    # =========================
    # FINAL OUTPUT
    # =========================

    return render_template("results.html",
                           mode="VERIFICATION",
                           status=status,
                           info=info,
                           quality=quality,
                           cert_id=cert_id,
                           extracted_name=extracted_name,
                           score=tamper_score,
                           report=report,
                           original_img=f"uploads/{file.filename}",
                           forensic_img = ela_path if ela_path else None)


# --- RUN SERVER ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)