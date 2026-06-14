import os
import re
from typing import Iterator, Dict, Any, Tuple

class PageProvider:
    """Provides OCR text and metadata for pages."""
    
    def __init__(self, raw_text_dir: str):
        self.raw_text_dir = raw_text_dir

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
                
            yield text, {
                "pdf_idx": pdf_idx,
                "page_num": page_num,
                "half": half,
                "filename": fname
            }
