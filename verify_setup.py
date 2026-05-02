import pytesseract
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore

# 1. PATH SETUP
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

print("--- System Diagnostic ---")

# 2. FIREBASE CHECK
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ SUCCESS: Firebase Connected.")
except Exception as e:
    print(f"❌ ERROR: Firebase Failed: {e}")

# 3. OCR CHECK
try:
    version = pytesseract.get_tesseract_version()
    print(f"✅ SUCCESS: OCR Engine Detected (v{version}).")
except Exception as e:
    print(f"❌ ERROR: OCR Engine not found at specified path.")
    