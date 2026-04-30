import cv2
import numpy as np
import os

def run_ela(image_path, quality=90):
    try:
        # Load the image
        original = cv2.imread(image_path)
        if original is None:
            return "error: image not found"

        # Save with lower quality
        temp_path = "temp_ela.jpg"
        cv2.imwrite(temp_path, original, [cv2.IMWRITE_JPEG_QUALITY, quality])
        
        # Calculate difference
        compressed = cv2.imread(temp_path)
        diff = cv2.absdiff(original, compressed)
        
        # Scale the difference
        enhanced_diff = diff * 15
        
        # Save to static folder
        result_filename = "ela_result.png"
        output_path = os.path.join('static', result_filename)
        
        # Ensure static folder exists
        if not os.path.exists('static'):
            os.makedirs('static')
            
        cv2.imwrite(output_path, enhanced_diff)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return result_filename
    except Exception as e:
        print(f"Forensic Error: {e}")
        return None

if __name__ == "__main__":
    print("Forensics module is ready!")