import os
import re
from typing import Iterator, Dict, Any, Tuple, Optional, List

from .imaging import split_page_halves

class PageProvider:
    """Provides OCR text and metadata for pages, including image paths if available."""
    
    def __init__(self, raw_text_dir: str, image_cache_dir: Optional[str] = None):
        self.raw_text_dir = raw_text_dir
        self.image_cache_dir = image_cache_dir or "image_cache"

    def get_pages(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        files = sorted([f for f in os.listdir(self.raw_text_dir) if f.endswith(".txt") and "_full" not in f], 
                       key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
        
        for fname in files:
            m = re.match(r'^pdf(\d+)_p(\d+)_(\w+)\.txt$', fname)
            if not m: continue
            
            pdf_idx = int(m.group(1))
            page_num = int(m.group(2))
            half = m.group(3)
            
            path = os.path.join(self.raw_text_dir, fname)
            with open(path, "r", encoding='utf-8') as f:
                text = f.read()
            
            # Check for corresponding image
            image_filename = fname.replace(".txt", ".png")
            image_path = os.path.join(self.image_cache_dir, image_filename)
            if not os.path.exists(image_path):
                image_path = None
                
            yield text, {
                "pdf_idx": pdf_idx,
                "page_num": page_num,
                "half": half,
                "filename": fname,
                "image_path": image_path
            }

class PDFImageProvider(PageProvider):
    """
    Provides pages by extracting them from PDFs on the fly.
    """
    def __init__(self, pdf_files: List[Dict[str, Any]], image_cache_dir: str = "image_cache"):
        self.pdf_files = pdf_files
        self.image_cache_dir = image_cache_dir
        os.makedirs(image_cache_dir, exist_ok=True)

    def get_pages(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        import subprocess
        for idx, pdf_info in enumerate(self.pdf_files, 1):
            pdf_name = pdf_info["name"]
            num_pages = pdf_info["pages"]
            
            for p in range(1, num_pages + 1):
                # Extract page image using pdftoppm (efficient and high quality)
                base_name = f"pdf{idx}_p{p}"

                full_image_path = os.path.join(self.image_cache_dir, f"{base_name}_full_raw.png")
                if not os.path.exists(full_image_path):
                    subprocess.run([
                        "pdftoppm", "-png", "-f", str(p), "-l", str(p), "-singlefile",
                        pdf_name, os.path.join(self.image_cache_dir, f"{base_name}_full_raw")
                    ])

                # Split at the detected spine, same logic used by the OCR text
                # pipeline, so VLM crops line up with anything indexed from raw_text/.
                from PIL import Image
                img = Image.open(full_image_path)
                left_img, right_img = split_page_halves(img)

                if right_img is None:
                    # Not a double-page spread: single "full" page.
                    half_path = os.path.join(self.image_cache_dir, f"{base_name}_full.png")
                    left_img.save(half_path)
                    yield "", {
                        "pdf_idx": idx,
                        "page_num": p,
                        "half": "full",
                        "image_path": half_path,
                        "filename": f"{base_name}_full.txt"
                    }
                else:
                    for half, half_img in [("left", left_img), ("right", right_img)]:
                        half_path = os.path.join(self.image_cache_dir, f"{base_name}_{half}.png")
                        half_img.save(half_path)

                        # Yield empty text as it's a VLLM-first provider
                        yield "", {
                            "pdf_idx": idx,
                            "page_num": p,
                            "half": half,
                            "image_path": half_path,
                            "filename": f"{base_name}_{half}.txt"
                        }
