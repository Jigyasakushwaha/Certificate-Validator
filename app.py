import os
import re
import pytesseract
from PIL import Image
from flask import Flask, render_template, request
import firebase_admin
from firebase_admin import credentials, firestore

# Import your forensic engine
from forensics import run_ela

app = Flask(__name__)

# --- 1. SETTINGS & FOLDERS ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Ensure the static/uploads folder exists for the images to show on web
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Firebase initialization
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- 2. ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    if 'file' not in request.files:
        return "No file part"
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file"

    # A. Save the file
    img_filename = "latest_check.jpg"
    img_path = os.path.join(UPLOAD_FOLDER, img_filename)
    file.save(img_path)

    # B. Run Forensic Test
    ela_filename = run_ela(img_path)

    # C. OCR Step (Read the text)
    extracted_text = pytesseract.image_to_string(Image.open(img_path))
    print(f"DEBUG: AI found this text -> {extracted_text}")

    # D. Define Pattern & Search (IMPORTANT: Define the pattern FIRST)
    # This pattern catches the '-1' at the end!
    id_pattern = r'[A-Z]{3,4}-\d{4}(?:-\d+)?' 
    
    found_ids = re.findall(id_pattern, extracted_text)

    # E. Logic & Database Check
    status = "❌ INVALID FORMAT"
    details = "No valid Certificate ID pattern recognized."
    
    if found_ids:
        detected_id = found_ids[0].strip()
        print(f"DEBUG: AI extracted this ID -> {detected_id}")
        
        # Check Firebase for the ID
        doc = db.collection('certificates').document(detected_id).get()
        
        if doc.exists:
            data = doc.to_dict()
            status = f"✅ VERIFIED: {detected_id}"
            details = f"Certificate belongs to: {data.get('Name')}"
        else:
            status = "⚠️ UNREGISTERED ID"
            details = f"ID {detected_id} found on paper, but not in official records."

    # F. Render Results
    return render_template('results.html', 
                           status=status, 
                           info=details,
                           original_img='uploads/' + img_filename, 
                           forensic_img=ela_filename)
if __name__ == "__main__":
    app.run(debug=True)