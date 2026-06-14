import os
import subprocess
import numpy as np
from PIL import Image, ImageFilter, ImageOps
from concurrent.futures import ThreadPoolExecutor
import easyocr
import sqlite3

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

os.makedirs(RAW_TEXT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Initialize global EasyOCR Reader
reader = easyocr.Reader(['la', 'fr', 'en'], gpu=True)

# preprocess_and_save has been deprecated; preprocessing is now handled in-memory in process_sub_image.

def find_split_point(img):
    """Find horizontal split point between main text and footnotes."""
    w, h = img.size
    
    # Convert to grayscale
    gray = img.convert('L')
    arr = np.array(gray, dtype=np.float32)
    mean_img = gray.filter(ImageFilter.BoxBlur(15))
    mean_arr = np.array(mean_img, dtype=np.float32)
    binary_arr = np.where(arr > (mean_arr - 15), 255, 0).astype(np.uint8)
    
    start_y = int(0.72 * h)
    end_y = int(0.92 * h)
    
    # 1. Look for a solid horizontal separator line
    line_y = None
    min_mean = 255
    for y in range(start_y, end_y):
        row = binary_arr[y, int(0.2*w):int(0.8*w)]
        m = row.mean()
        if m < 180 and m < min_mean:
            above = binary_arr[max(0, y-10):y, int(0.2*w):int(0.8*w)].mean()
            below = binary_arr[y+1:min(h, y+11), int(0.2*w):int(0.8*w)].mean()
            if m < above - 40 and m < below - 40:
                min_mean = m
                line_y = y
                
    if line_y is not None:
        return line_y
        
    # 2. Look for the widest white gap (all 255s)
    bright_rows = []
    for y in range(start_y, end_y):
        row = binary_arr[y, int(0.2*w):int(0.8*w)]
        if row.min() == 255:
            bright_rows.append(y)
            
    if bright_rows:
        runs = []
        current_run = [bright_rows[0]]
        for y_val in bright_rows[1:]:
            if y_val == current_run[-1] + 1:
                current_run.append(y_val)
            else:
                runs.append(current_run)
                current_run = [y_val]
        runs.append(current_run)
        
        longest_run = max(runs, key=len)
        if len(longest_run) > 10:
            return longest_run[len(longest_run) // 2]
            
    # 3. Fallback: split at 0.85 * h
    return int(0.85 * h)

def find_vertical_split(img):
    """Find vertical gutter splitting the footnote columns."""
    w, h = img.size
    if h < 50:
        return w // 2
        
    gray = img.convert('L')
    arr = np.array(gray, dtype=np.float32)
    mean_img = gray.filter(ImageFilter.BoxBlur(15))
    mean_arr = np.array(mean_img, dtype=np.float32)
    binary_arr = np.where(arr > (mean_arr - 15), 255, 0).astype(np.uint8)
    
    x1 = int(0.25 * w)
    x2 = int(0.75 * w)
    col_means = binary_arr.mean(axis=0)[x1:x2]
    
    # Find columns that are very bright (almost pure white, > 238)
    bright_indices = np.where(col_means > 238)[0]
    if len(bright_indices) > 0:
        runs = []
        current_run = [bright_indices[0]]
        for idx in bright_indices[1:]:
            if idx == current_run[-1] + 1:
                current_run.append(idx)
            else:
                runs.append(current_run)
                current_run = [idx]
        runs.append(current_run)
        
        longest_run = max(runs, key=len)
        if len(longest_run) >= 8:
            return x1 + longest_run[len(longest_run) // 2]
            
    # Fallback
    return w // 2

def process_sub_image(img, prefix_name, pdf_idx, page_num, half, region_type, offset_x=0, offset_y=0):
    """Preprocess a sub-image (upscale 2x, convert to grayscale) and run EasyOCR."""
    w, h = img.size
    upscaled = img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    gray = upscaled.convert('L')
    arr = np.array(gray)
    
    # Run EasyOCR with detail (getting coordinates and confidence)
    results = reader.readtext(arr, paragraph=True)
    
    # Save regions to database
    conn = sqlite3.connect(os.path.join(WORKSPACE, "rolls.db"))
    cursor = conn.cursor()
    for bbox, text in results:
        x_min = int(min(p[0] for p in bbox) / 2) + int(offset_x)
        y_min = int(min(p[1] for p in bbox) / 2) + int(offset_y)
        x_max = int(max(p[0] for p in bbox) / 2) + int(offset_x)
        y_max = int(max(p[1] for p in bbox) / 2) + int(offset_y)
        
        cursor.execute("""
        INSERT INTO spatial_regions (pdf_idx, page_num, half, region_type, x_min, y_min, x_max, y_max, text, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pdf_idx, page_num, half, region_type, x_min, y_min, x_max, y_max, text, 1.0))
    conn.commit()
    conn.close()
    
    return "\n".join([r[1] for r in results])

def process_page_section(img, page_txt_path, prefix_name, pdf_idx, page_num, half):
    """Processes a portrait page or half of landscape page, splitting main text & footnotes."""
    w, h = img.size
    split_y = find_split_point(img)
    
    # Crop main text (top part)
    main_img = img.crop((0, 0, w, split_y))
    main_text = process_sub_image(main_img, f"{prefix_name}_main", pdf_idx, page_num, half, "main_text", offset_x=0, offset_y=0)
    
    # Crop footnotes (bottom part)
    fn_img = img.crop((0, split_y, w, h))
    
    # Dynamically split footnotes vertically into two columns
    fn_split_x = find_vertical_split(fn_img)
    fn_left_img = fn_img.crop((0, 0, fn_split_x, fn_img.height))
    fn_right_img = fn_img.crop((fn_split_x, 0, w, fn_img.height))
    
    fn_left_text = process_sub_image(fn_left_img, f"{prefix_name}_fn_left", pdf_idx, page_num, half, "footnote_left", offset_x=0, offset_y=split_y)
    fn_right_text = process_sub_image(fn_right_img, f"{prefix_name}_fn_right", pdf_idx, page_num, half, "footnote_right", offset_x=fn_split_x, offset_y=split_y)
    
    # Combine outputs with clean separator
    combined_lines = [main_text]
    if fn_left_text.strip() or fn_right_text.strip():
        combined_lines.append("=== FOOTNOTES ===")
        if fn_left_text.strip():
            combined_lines.append(fn_left_text)
        if fn_right_text.strip():
            combined_lines.append(fn_right_text)
            
    with open(page_txt_path, "w") as f:
        f.write("\n".join(combined_lines))

def process_page(pdf_idx, pdf_name, page_num):
    """Extract a PDF page, split if landscape, preprocess, OCR, and save text."""
    pdf_path = os.path.join(WORKSPACE, pdf_name)
    
    left_txt_path = os.path.join(RAW_TEXT_DIR, f"pdf{pdf_idx}_p{page_num}_left.txt")
    right_txt_path = os.path.join(RAW_TEXT_DIR, f"pdf{pdf_idx}_p{page_num}_right.txt")
    full_txt_path = os.path.join(RAW_TEXT_DIR, f"pdf{pdf_idx}_p{page_num}_full.txt")
    
    img_prefix = os.path.join(TEMP_DIR, f"temp_pdf{pdf_idx}_p{page_num}")
    
    # Check if text files already exist
    if os.path.exists(full_txt_path) and os.path.getsize(full_txt_path) > 0:
        return
    if os.path.exists(left_txt_path) and os.path.getsize(left_txt_path) > 0 and os.path.exists(right_txt_path) and os.path.getsize(right_txt_path) > 0:
        return
        
    print(f"Processing PDF {pdf_idx} page {page_num}...")
    
    # Run pdftoppm to extract the page
    subprocess.run(["pdftoppm", "-png", "-f", str(page_num), "-l", str(page_num), pdf_path, img_prefix])
    
    # Find the extracted file
    extracted_file = None
    for f in os.listdir(TEMP_DIR):
        if f.startswith(f"temp_pdf{pdf_idx}_p{page_num}-") and f.endswith(".png"):
            extracted_file = os.path.join(TEMP_DIR, f)
            break
            
    if not extracted_file or not os.path.exists(extracted_file):
        print(f"Error: Could not extract page {page_num} from PDF {pdf_name}")
        return
        
    try:
        img = Image.open(extracted_file)
        w, h = img.size
        
        # Check if page is landscape (double-page spread) or portrait
        if w > h:
            # Dynamic spine detection: find the darkest vertical line in the middle 20%
            gray = img.convert('L')
            arr = np.array(gray)
            start_x = int(0.4 * w)
            end_x = int(0.6 * w)
            col_sums = arr[:, start_x:end_x].mean(axis=0)
            spine_x = start_x + np.argmin(col_sums)
            
            # Crop left and right halves using the spine position
            left_img = img.crop((0, 0, spine_x + 15, h))
            right_img = img.crop((spine_x - 15, 0, w, h))
            
            # Process Left half
            process_page_section(left_img, left_txt_path, f"pdf{pdf_idx}_p{page_num}_left", pdf_idx, page_num, "left")
            
            # Process Right half
            process_page_section(right_img, right_txt_path, f"pdf{pdf_idx}_p{page_num}_right", pdf_idx, page_num, "right")
                
            print(f"Completed PDF {pdf_idx} page {page_num} (Landscape - Split).")
        else:
            # Process Full page (portrait)
            process_page_section(img, full_txt_path, f"pdf{pdf_idx}_p{page_num}_full", pdf_idx, page_num, "full")
                
            print(f"Completed PDF {pdf_idx} page {page_num} (Portrait - Full).")
            
    except Exception as e:
        print(f"Error processing PDF {pdf_idx} page {page_num}: {e}")
    finally:
        # Clean up original extracted page image
        if extracted_file and os.path.exists(extracted_file):
            os.remove(extracted_file)

def run_pipeline():
    tasks = []
    for idx, pdf in enumerate(PDF_FILES, 1):
        for page in range(1, pdf["pages"] + 1):
            tasks.append((idx, pdf["name"], page))
            
    print(f"Starting OCR Pipeline for {len(tasks)} pages...")
    
    # We use a ThreadPoolExecutor with 2 workers to prevent GPU memory/concurrency contention
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(process_page, idx, name, page) for idx, name, page in tasks]
        # Wait for all to complete
        for future in futures:
            future.result()
            
    print("OCR Pipeline completed successfully!")

if __name__ == "__main__":
    run_pipeline()
