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
    return cv2.Laplacian(gray, cv2.CV_64F).var()

# --- OCR PREPROCESSING ---

def preprocess_for_ocr(image_path):
    img = cv2.imread(image_path)
    if img is None: return None
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
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
    
    # 1. Check Image Quality
    blur_score = calculate_blur(image_path)
    quality_status = "Good" if blur_score > 100 else "Low/Blurry"
    
    # 2. QR/OCR Extraction
    qr_id = scan_qr_code(image_path)
    processed_img = preprocess_for_ocr(image_path)
    
    if processed_img is None:
        return "Error processing image", "NOT_FOUND", "Critically Low"
    
    # Use PSM 11 to find text regardless of layout (helps broad certificates)
    raw_text = pytesseract.image_to_string(processed_img, config='--psm 11').upper()
    
    # 3. ID Priority Logic (The "Universal" Fix)
    if qr_id:
        cert_id = qr_id
    else:
        # Broad Alphanumeric Search: 8-20 chars long
        id_pattern = r'\b[A-Z0-9-]{8,20}\b' 
        found_ids = re.findall(id_pattern, raw_text)
        
        # Filter out common header words that OCR might misidentify as an ID
        blacklist = ["CERTIFICATE", "COMPLETION", "PRESENTED", "SUCCESSFULLY", "UNIVERSITY"]
        potential_ids = [uid for uid in found_ids if uid not in blacklist]
        
        # Pick the first potential ID that isn't blacklisted
        cert_id = potential_ids[0] if potential_ids else "NOT_FOUND"
    
    return raw_text, cert_id, quality_status