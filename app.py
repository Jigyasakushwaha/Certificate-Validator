import os
import re
import pytesseract
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, render_template, request, redirect, url_for, session
from forensics import run_ela, extract_certificate_data
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from forensics import draw_detected_boxes

# Tesseract path (Windows)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


app = Flask(__name__)
app.secret_key = "hackathon_secret_key"
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
    decision_points = []

    file = request.files.get('file')
    mode = request.form.get('mode', 'verify')

    if not file:
        return redirect(url_for('index'))

    # Save file
    import time

    filename = f"{int(time.time())}_{file.filename}"
    path = os.path.join(UPLOAD_FOLDER, filename)

    file.save(path)

    # OCR + extraction
    
    result = extract_certificate_data(path)
   

    if result:
     raw_text, cert_id, extracted_name, quality = result
    else:
     raw_text, cert_id, extracted_name, quality = "", "NOT_FOUND", "NOT FOUND", "ERROR"

    boxed_img = draw_detected_boxes(path, extracted_name, cert_id)

     # =========================
# 🔥 CONFIDENCE SCORE
# =========================
    confidence = 100

    if cert_id == "NOT_FOUND":
       confidence -= 30

    if extracted_name == "NOT FOUND":
      confidence -= 30

    if quality == "Low/Blurry":
      confidence -= 20


     

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
                               confidence=confidence,
                               boxed_img=boxed_img,
                               decision_points=decision_points,
                               report=["Image quality too low for reliable OCR."])

    # =========================
    # 🔹 MODE: QUALITY ONLY
    # =========================
    
    if mode == "quality":

     ela_path = run_ela(path)

    # 🔥 ONLY QUALITY LOGIC
     if quality == "Low/Blurry":
        status = "INVALID"
        info = "Image is blurry. Please upload a clearer image."
        score = 0
        report = ["Low clarity detected.", "Results may be unreliable."]
     else:
        status = "ANALYZED"
        info = "Image quality is sufficient for analysis."
        score = 20
        report = ["Image is clear.", "No major blur detected."]

     return render_template("results.html",
                           mode="QUALITY ANALYSIS",
                           status=status,
                           info=info,
                           quality=quality,
                           score=score,
                           report=report,
                           original_img=f"uploads/{file.filename}",
                           forensic_img=ela_path if ela_path else None)


    
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
                               confidence=confidence,
                               boxed_img=boxed_img,
                               decision_points=decision_points,
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
    decision_points = []

# ID check
    if cert_id != "NOT_FOUND":
     decision_points.append("✔ Certificate ID detected")
    else:
     decision_points.append("❌ Certificate ID missing")

# Name check
    if extracted_name != "NOT FOUND":
     decision_points.append("✔ Identity extracted successfully")
    else:
      decision_points.append("⚠ Name extraction uncertain")

# DB validation
    if status == "AUTHENTIC":
     decision_points.append("✔ Record matched with registry")
    elif status == "MISMATCH":
     decision_points.append("❌ Identity mismatch with database")
    elif status == "NOT REGISTERED":
     decision_points.append("❌ Certificate not found in registry")

# Quality
    if quality == "Low/Blurry":
     decision_points.append("⚠ Low image clarity may affect results")

# Tampering
    if tamper_score > 60:
     decision_points.append("❌ High probability of tampering")
    else:
     decision_points.append("✔ No strong tampering evidence"  )
   

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
    if quality == "Low/Blurry":
     report.append("Image too blurry for reliable detection.")

    if cert_id == "NOT_FOUND" and extracted_name == "NOT FOUND":
        status = "INVALID"
    # =========================
# 🚨 QUALITY CHECK FIRST
# =========================
    # 🚨 FINAL OCR RELIABILITY GATE
    if quality == "Low/Blurry" or confidence < 50: 
       cert_id = "NOT_FOUND"
       extracted_name = "NOT FOUND"

    tamper_score = min(tamper_score, 100)
    confidence = 100 - tamper_score
    confidence = max(0, min(confidence, 100))

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
    session['status'] = status
    session['cert_id'] = cert_id
    session['extracted_name'] = extracted_name
    session['score'] = tamper_score
    session['confidence'] = confidence
    session['quality'] = quality
    return render_template("results.html",
                           mode="VERIFICATION",
                           status=status,
                           info=info,
                           quality=quality,
                           cert_id=cert_id,
                           extracted_name=extracted_name,
                           score=tamper_score,
                           report=report,
                           original_img=f"uploads/{filename}",
                           confidence=confidence, 
                           boxed_img=boxed_img,
                           decision_points=decision_points,
                           forensic_img = ela_path if ela_path else None)

@app.route("/download-report")
def download_report():
    from flask import send_file
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from datetime import datetime

    file_path = "report.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()

    content = []

    # 🔥 TITLE
    content.append(Paragraph("Certificate Authenticity  Report", styles['Title']))
    content.append(Spacer(1, 10))

    content.append(Paragraph("Certificate Analysis Summary", styles['Heading2']))
    content.append(Spacer(1, 15))


    # 🔥 DATA TABLE
    data = [
        ["Field", "Value"],
        ["Status", session.get('status', 'N/A')],
        ["Detected ID", session.get('cert_id', 'N/A')],
        ["Extracted Name", session.get('extracted_name', 'N/A')],
        ["Forgery Risk", f"{session.get('score', 'N/A')}%"],
        ["Confidence", f"{session.get('confidence', 'N/A')}%"],
        ["Image Quality", session.get('quality', 'N/A')],
    ]

    table = Table(data, colWidths=[150, 300])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),

        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),

        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
    ]))

    content.append(table)
    content.append(Spacer(1, 20))

    # 🔥 INTERPRETATION SECTION
    content.append(Paragraph("System Interpretation:", styles['Heading3']))
    content.append(Spacer(1, 8))

    interpretation = f"""
    The certificate was analyzed using OCR and forensic techniques.
    Based on extracted data and anomaly detection, the system classified
    the document as <b>{session.get('status', 'N/A')}</b>.
    """

    content.append(Paragraph(interpretation, styles['Normal']))
    content.append(Spacer(1, 20))

    # 🔥 FOOTER
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    content.append(Paragraph(f"Generated on: {timestamp}", styles['Normal']))
    content.append(Spacer(1, 5))
    content.append(Paragraph("Powered by Alchemist AI System", styles['Italic']))

    # BUILD PDF
    doc.build(content)

    return send_file(file_path, as_attachment=True)

# --- RUN SERVER ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)