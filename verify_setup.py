import pytesseract
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore
import cv2  # New: Check OpenCV
import os   # New: Check Directories

# 1. PATH SETUP
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

print("--- AI Alchemists: System Diagnostic ---")

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

# 4. OPENCV & DIRECTORY CHECK (New Necessary Additions)
try:
    # Test OpenCV version
    print(f"✅ SUCCESS: OpenCV detected (v{cv2.__version__}).")
    
    # Check if 'static/uploads' exists for saving ELA images
    upload_path = os.path.join('static', 'uploads')
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
        print(f"📁 INFO: Created missing directory: {upload_path}")
    else:
        print(f"✅ SUCCESS: Upload directory ready.")
        
except Exception as e:
    print(f"❌ ERROR: System environment check failed: {e}")

print("--- Diagnostic Complete ---") 
