import pytesseract
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore

# 1. TELL PYTHON WHERE THE OCR ENGINE IS
# Ensure this path matches exactly where you installed the .exe
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 2. CONNECT TO THE BRAIN (FIREBASE)
try:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ SUCCESS: Firebase is connected!")
except Exception as e:
    print(f"❌ ERROR: Firebase failed. Did you move the .json file? {e}")
try:
    # This just asks Tesseract for its version number
    version = pytesseract.get_tesseract_version()
    print(f"✅ SUCCESS: OCR is connected! (Version {version})")
except Exception as e:
    print(f"❌ ERROR: OCR failed. Check the path in line 7! {e}")