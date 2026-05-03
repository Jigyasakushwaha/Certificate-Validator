import cv2
import numpy as np
import os
import pytesseract
import re


# ============================
# 🔍 IMAGE QUALITY CHECK
# ============================

def calculate_blur(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


# ============================
# 🔍 OCR PREPROCESSING
# ============================

def preprocess_for_ocr(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    return thresh


# ============================
# 🔍 ELA (OPTIONAL)
# ============================
def run_ela(image_path, quality=90):
    try:
        original = cv2.imread(image_path)
        if original is None:
            return None

        temp_path = "temp_ela.jpg"

        # Save compressed version
        cv2.imwrite(temp_path, original, [cv2.IMWRITE_JPEG_QUALITY, quality])
        compressed = cv2.imread(temp_path)

        # Compute difference
        diff = cv2.absdiff(original, compressed)

        # 🔥 BOOST VISIBILITY
        enhanced = cv2.convertScaleAbs(diff, alpha=25, beta=0)

        # Heatmap
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        heatmap = cv2.applyColorMap(gray, cv2.COLORMAP_JET)

        # ✅ FIXED PATH HANDLING
        filename = "ela_" + os.path.basename(image_path)
        output_path = os.path.join("static/uploads", filename)

        cv2.imwrite(output_path, heatmap)

        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # ✅ RETURN RELATIVE PATH (IMPORTANT)
        return f"uploads/{filename}"

    except Exception as e:
        print("ELA ERROR:", e)
        return None

# ============================
# 🔍 MAIN FUNCTION
# ============================
def extract_certificate_data(image_path):

    try:
        blur_score = calculate_blur(image_path)
        quality_status = "Good" if blur_score > 80 else "Low/Blurry"

        img = cv2.imread(image_path)
        if img is None:
            return "", "NOT_FOUND", "NOT FOUND", "LOW"

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 🔥 MULTI PREPROCESSING
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # 🔥 MULTI OCR (VERY IMPORTANT)
        text1 = pytesseract.image_to_string(thresh, config='--psm 6')
        text2 = pytesseract.image_to_string(gray, config='--psm 11')

        raw_text = (text1 + "\n" + text2).upper()

        # Preserve structure
        lines = [l.strip() for l in raw_text.split("\n") if len(l.strip()) > 2]

        # Clean version (for regex only)
        clean_text = re.sub(r'[^A-Z0-9\s\-\/]', ' ', raw_text)
        clean_text = re.sub(r'\s+', ' ', clean_text)

        # ============================
        # 🔥 ID DETECTION (FINAL)
        # ============================

        cert_id = "NOT_FOUND"

        id_patterns = [
            r'\bCERT[-\s]*\d{2,}[-\d]*\b',
            r'\b[A-Z]{2,}[-]?\d{3,}\b',
            r'\b\d{4}[-/]\d+\b',
            r'ROLL\s*(?:NO|NUMBER)?[:\-\s]*([A-Z0-9\-\/]{4,})',
            r'REGISTRATION\s*(?:NO|ID)?[:\-\s]*([A-Z0-9\-\/]{4,})'
        ]

        for pattern in id_patterns:
            match = re.search(pattern, clean_text)
            if match:
                cert_id = match.group(0)
                break

        # ❌ remove junk like IFICATION
        if cert_id.endswith("IFICATION"):
            cert_id = "NOT_FOUND"

        # ============================
        # 🔥 NAME DETECTION (FINAL)
        # ============================

        extracted_name = "NOT FOUND"
        name_candidates = []

        ignore_words = [
            "CERTIFICATE", "CERTIFICATION", "ONLINE",
            "ACADEMY", "COURSE", "DATA", "PYTHON",
            "SUMMARY", "PERFORMANCE", "SCORE",
            "OF", "THE", "IN", "NPTEL"
        ]

        for i, line in enumerate(lines):
            words = line.split()

            if 2 <= len(words) <= 3:

                if not all(w.isalpha() for w in words):
                    continue

                if any(w in ignore_words for w in words):
                    continue

                if any(char.isdigit() for char in line):
                    continue

                if len(line) < 8 or len(line) > 25:
                    continue

                # center bias
                score = abs(i - len(lines)//2)

                name_candidates.append((line, score))

        if name_candidates:
            extracted_name = sorted(name_candidates, key=lambda x: x[1])[0][0]

        if len(extracted_name) < 5:
            extracted_name = "NOT FOUND"

        # ============================
        # DEBUG
        # ============================

        print("\n===== OCR DEBUG =====")
        print(clean_text[:300])
        print("ID:", cert_id)
        print("NAME:", extracted_name)
        print("====================\n")

        return clean_text, cert_id, extracted_name, quality_status

    except Exception as e:
        print("ERROR:", e)
        return "", "NOT_FOUND", "NOT FOUND", "ERROR"