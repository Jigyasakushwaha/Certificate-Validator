import cv2
import numpy as np
import os
import pytesseract
import re
from pyzbar.pyzbar import decode  # New import for QR detection

# --- YOUR EXISTING ELA CODE (DO NOT TOUCH) ---
def run_ela(image_path, quality=90):
    try:
        original = cv2.imread(image_path)
        if original is None:
            return None

        temp_path = "temp_ela.jpg"
        cv2.imwrite(temp_path, original, [cv2.IMWRITE_JPEG_QUALITY, quality])
        compressed = cv2.imread(temp_path)
        
        diff = cv2.absdiff(original, compressed)
        enhanced = diff * 15

        static_dir = os.path.join('static', 'uploads')
        os.makedirs(static_dir, exist_ok=True)

        result_filename = "ela_" + os.path.basename(image_path)
        output_path = os.path.join(static_dir, result_filename)

        cv2.imwrite(output_path, enhanced)

        if os.path.exists(temp_path):
            os.remove(temp_path)

        return f"uploads/{result_filename}"

    except Exception as e:
        print(f"ELA ERROR: {e}")
        return None

# --- NEW NECESSARY ADDITIONS FOR OCR ACCURACY ---

def preprocess_for_ocr(image_path):
    """Cleans the image to make text pop for Tesseract"""
    img = cv2.imread(image_path)
    if img is None:
        return None
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Use Adaptive Thresholding to handle uneven lighting/shadows
    processed_img = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    return processed_img

# --- NEW QR CODE FEATURE ---

def scan_qr_code(image_path):
    """Detects and decodes QR codes from the image"""
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        
        # Detect and decode
        decoded_objects = decode(img)
        
        if decoded_objects:
            # Return the data from the first QR code found
            return decoded_objects[0].data.decode('utf-8')
        return None
    except Exception as e:
        print(f"QR Error: {e}")
        return None

def extract_certificate_data(image_path):
    """Main function to be called from app.py to get text results"""
    
    # 1. First, attempt to get ID from QR code (Highest Accuracy)
    qr_id = scan_qr_code(image_path)
    
    # 2. Run OCR Preprocessing for full text extraction
    processed_img = preprocess_for_ocr(image_path)
    if processed_img is None:
        return "Error processing image", None
    
    # OCR Extraction
    raw_text = pytesseract.image_to_string(processed_img)
    
    # 3. Handle ID Logic: Prioritize QR, Fallback to Regex
    if qr_id:
        cert_id = qr_id
    else:
        # Find Certificate ID using Regex if QR is not found
        id_pattern = r'[A-Z0-9]{4,}' 
        found_ids = re.findall(id_pattern, raw_text)
        cert_id = found_ids[0] if found_ids else "Not Found"
    
    return raw_text, cert_id
