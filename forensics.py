import cv2
import numpy as np
import os
import pytesseract
import re
from pyzbar.pyzbar import decode

# --- YOUR EXISTING ELA CODE (UNTOUCHED) ---
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

# --- NEW: BLUR DETECTION (To prevent False Positives) ---

def calculate_blur(image_path):
    """Returns a score: higher is sharper, lower is blurrier"""
    img = cv2.imread(image_path)
    if img is None: return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Variance of Laplacian measures the 'sharpness' of edges
    return cv2.Laplacian(gray, cv2.CV_64F).var()

# --- OCR PREPROCESSING ---

def preprocess_for_ocr(image_path):
    img = cv2.imread(image_path)
    if img is None: return None
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Bilateral Filter removes noise while keeping edges (better than Gaussian for OCR)
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)
    
    processed_img = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    return processed_img

# --- QR CODE FEATURE ---

def scan_qr_code(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None: return None
        decoded_objects = decode(img)
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
        return None
    except Exception as e:
        print(f"QR Error: {e}")
        return None

# --- MAIN EXTRACTION LOGIC ---

def extract_certificate_data(image_path):
    """Main function to get results with quality checking"""
    
    # 1. Check Image Quality first
    blur_score = calculate_blur(image_path)
    quality_status = "Good" if blur_score > 100 else "Low/Blurry"
    
    # 2. QR/OCR Extraction
    qr_id = scan_qr_code(image_path)
    processed_img = preprocess_for_ocr(image_path)
    
    if processed_img is None:
        return "Error processing image", "N/A", "Critically Low"
    
    raw_text = pytesseract.image_to_string(processed_img)
    
    # 3. ID Priority
    if qr_id:
        cert_id = qr_id
    else:
        # Improved Regex to be more specific to IDs
        id_pattern = r'\b[A-Z0-9-]{6,}\b' 
        found_ids = re.findall(id_pattern, raw_text)
        cert_id = found_ids[0] if found_ids else "NOT_FOUND"
    
    # Returns: Raw Text, ID, and Quality Status for app.py to use
    return raw_text, cert_id, quality_status
