import os
import io
import subprocess
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import httpx
from dotenv import load_dotenv

from pipeline.imaging import split_page_halves, split_footnotes

load_dotenv()

# Project configurations
WORKSPACE = "/home/john/rolls"
PDF_FILES = [
    {"name": "Dufour T1 p. 3-157 (1).pdf", "pages": 80},
    {"name": "Dufour T1 p. 157-351 (1).pdf", "pages": 99},
    {"name": "Dufour T1 p. 351-529 (2).pdf", "pages": 91},
    {"name": "Dufour T1 p. 529-714 (4).pdf", "pages": 94}
]

RAW_TEXT_DIR = os.path.join(WORKSPACE, "raw_text")
TEMP_DIR = "/var/tmp/rolls/temp_ocr"
REMOTE_OCR_URL = os.getenv("REMOTE_OCR_URL")

os.makedirs(RAW_TEXT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def call_remote_ocr(img):
    """Sends image to the 3090 machine for DocTR processing."""
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    
    try:
        with httpx.Client(timeout=60.0) as client:
            files = {'file': ('image.png', img_byte_arr.getvalue(), 'image/png')}
            response = client.post(REMOTE_OCR_URL, files=files)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Remote OCR failed: {e}")
        return None

def process_sub_image(img, pdf_idx, page_num, half, region_type, offset_x=0, offset_y=0):
    """Sends a sub-image to the remote 3090 and saves structured results."""
    data = call_remote_ocr(img)
    if not data: return ""

    results_text = []
    conn = sqlite3.connect(os.path.join(WORKSPACE, "rolls.db"))
    cursor = conn.cursor()
    
    # DocTR output: data['pages'][0]['blocks']...
    for page in data.get('pages', []):
        page_w, page_h = img.size
        for block in page.get('blocks', []):
            for line in block.get('lines', []):
                line_text = " ".join([w['value'] for w in line.get('words', [])])
                results_text.append(line_text)
                
                # Get line-level bounding box (DocTR words have geometry [[x_min, y_min], [x_max, y_max]])
                # Geometry is relative (0 to 1)
                all_words = line.get('words', [])
                if not all_words: continue
                
                x_min = min(w['geometry'][0][0] for w in all_words) * page_w + offset_x
                y_min = min(w['geometry'][0][1] for w in all_words) * page_h + offset_y
                x_max = max(w['geometry'][1][0] for w in all_words) * page_w + offset_x
                y_max = max(w['geometry'][1][1] for w in all_words) * page_h + offset_y
                
                conf = sum(w['confidence'] for w in all_words) / len(all_words)
                
                cursor.execute("""
                INSERT INTO spatial_regions (pdf_idx, page_num, half, region_type, x_min, y_min, x_max, y_max, text, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (pdf_idx, page_num, half, region_type, int(x_min), int(y_min), int(x_max), int(y_max), line_text, conf))
                
    conn.commit()
    conn.close()
    return "\n".join(results_text)

def process_page_section(img, page_txt_path, pdf_idx, page_num, half):
    """Processes a page/half, splitting main text & footnotes, using remote GPU OCR."""
    w, h = img.size
    main_img, fn_left_img, fn_right_img, split_y, fn_split_x = split_footnotes(img)

    main_text = process_sub_image(main_img, pdf_idx, page_num, half, "main_text", 0, 0)
    fn_left_text = process_sub_image(fn_left_img, pdf_idx, page_num, half, "footnote_left", 0, split_y)
    fn_right_text = process_sub_image(fn_right_img, pdf_idx, page_num, half, "footnote_right", fn_split_x, split_y)
    
    combined = [main_text]
    if fn_left_text.strip() or fn_right_text.strip():
        combined.append("=== FOOTNOTES ===")
        if fn_left_text.strip(): combined.append(fn_left_text)
        if fn_right_text.strip(): combined.append(fn_right_text)
            
    with open(page_txt_path, "w") as f:
        f.write("\n".join(combined))

def process_page(pdf_idx, pdf_name, page_num):
    pdf_path = os.path.join(WORKSPACE, pdf_name)
    left_txt_path = os.path.join(RAW_TEXT_DIR, f"pdf{pdf_idx}_p{page_num}_left.txt")
    right_txt_path = os.path.join(RAW_TEXT_DIR, f"pdf{pdf_idx}_p{page_num}_right.txt")
    full_txt_path = os.path.join(RAW_TEXT_DIR, f"pdf{pdf_idx}_p{page_num}_full.txt")
    img_prefix = os.path.join(TEMP_DIR, f"temp_pdf{pdf_idx}_p{page_num}")
    
    if os.path.exists(full_txt_path) or (os.path.exists(left_txt_path) and os.path.exists(right_txt_path)):
        return
        
    print(f"🚀 Processing PDF {pdf_idx} page {page_num} on 3090...")
    subprocess.run(["pdftoppm", "-png", "-f", str(page_num), "-l", str(page_num), pdf_path, img_prefix])
    
    ext_file = None
    for f in os.listdir(TEMP_DIR):
        if f.startswith(f"temp_pdf{pdf_idx}_p{page_num}-") and f.endswith(".png"):
            ext_file = os.path.join(TEMP_DIR, f); break
            
    if not ext_file: return
        
    try:
        img = Image.open(ext_file)
        left_img, right_img = split_page_halves(img)
        if right_img is not None:
            process_page_section(left_img, left_txt_path, pdf_idx, page_num, "left")
            process_page_section(right_img, right_txt_path, pdf_idx, page_num, "right")
        else:
            process_page_section(left_img, full_txt_path, pdf_idx, page_num, "full")
    except Exception as e:
        print(f"Error on page {page_num}: {e}")
    finally:
        if ext_file and os.path.exists(ext_file): os.remove(ext_file)

def run_pipeline():
    tasks = []
    for idx, pdf in enumerate(PDF_FILES, 1):
        for page in range(1, pdf["pages"] + 1):
            tasks.append((idx, pdf["name"], page))
    
    # Increase workers slightly since remote network latency is the bottleneck, not local CPU
    with ThreadPoolExecutor(max_workers=4) as executor:
        for idx, name, page in tasks:
            executor.submit(process_page, idx, name, page)
            
    print("OCR Pipeline completed successfully via 3090!")

if __name__ == "__main__":
    run_pipeline()
