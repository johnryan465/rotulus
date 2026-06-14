from abc import ABC, abstractmethod
from typing import List, Dict, Any
from .models import PageContent

class PageProcessor(ABC):
    """Base class for processing a page of the mortuary rolls edition."""
    
    @abstractmethod
    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        """
        Takes OCR text and metadata, returns structured PageContent.
        metadata should include: pdf_idx, page_num, half, expected_next_roll
        """
        pass

class LegacyRegexProcessor(PageProcessor):
    """
    Implementation using the refined regex logic from the previous parser.py.
    This serves as the fallback/baseline.
    """
    def __init__(self):
        import re
        self.re = re

    def is_latin_text(self, text):
        if not text or len(text.strip()) < 15: return False
        fr_de_stop_words = {" de ", " la ", " le ", " les ", " des ", " dans ", " pour ", " qui ", " que ", " et ", " est ", " au ", " aux ", " cf", " und ", " der ", " die ", " das ", " von ", " une "}
        la_stop_words = {" et ", " in ", " est ", " qui ", " quod ", " non ", " ad ", " cum ", " ut ", " per ", " pro ", " sed ", " quia ", " deus ", " sancti ", " episcopus ", " abbas ", " ecclesie "}
        t = " " + text.lower() + " "
        fr_de = sum(t.count(w) for w in fr_de_stop_words)
        la = sum(t.count(w) for w in la_stop_words)
        return la > fr_de

    def get_roll_numbers(self, line, expected_next, pdf_idx, line_idx):
        if line_idx < 3 and self.re.match(r'^(?:N[oO°\?]*\s*)?\d+(?:\s*-\s*\d+)?\s*$', line.strip()):
            return None
        bounds = {1: (1, 74), 2: (74, 105), 3: (106, 121), 4: (122, 200)}
        min_r, max_roll = bounds.get(pdf_idx, (1, 200))
        m = self.re.match(r'^(?:N[oO°\?]*\s*)?(\d+)(?:\s*[\-\/]\s*(\d+))?', line.strip())
        if m:
            nums = [int(m.group(1))]
            if m.group(2): nums.extend(range(int(m.group(1)) + 1, int(m.group(2)) + 1))
            if any(min_r <= n <= max_roll for n in nums):
                if any(expected_next - 2 <= n <= expected_next + 10 for n in nums):
                    if not line.strip()[m.end():].strip().startswith("["):
                        return nums
        return None

    def get_titulus_info(self, line):
        s = line.strip()
        m1 = self.re.match(r'^(\d+)\s*\[(\d+)\]\s*(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,40})', s)
        if m1: return m1.group(4).strip(" ."), s
        m2 = self.re.match(r'^(\d+)\s+(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,40})', s)
        if m2 and int(m2.group(1)) < 500: return m2.group(3).strip(" ."), s
        if self.re.match(r'^T[T]?\.\s+([^0-9,;:\.\n\r]{3,40})', s):
            loc = s.split(".", 1)[1].split(".")[0].strip() if "." in s else s
            return loc, s
        return None, None

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        from .models import Roll, Titulus, Footnote, PageContent
        
        pdf_idx = metadata.get('pdf_idx', 1)
        page_num = metadata.get('page_num', 1)
        half = metadata.get('half', 'full')
        expected_next = metadata.get('expected_next_roll', 1)
        
        lines = text.split('\n')
        f_idx = next((idx for idx, l in enumerate(lines) if "=== FOOTNOTES ===" in l), -1)
        main_lines = lines[:f_idx] if f_idx != -1 else lines
        
        content = PageContent()
        i = 0
        while i < len(main_lines):
            r_nums = self.get_roll_numbers(main_lines[i], expected_next, pdf_idx, i)
            if r_nums:
                title_parts = []
                ms_parts = []
                j = i + 1
                while j < len(main_lines):
                    l = main_lines[j].strip()
                    if not l or "=== FOOTNOTES ===" in l: j += 1; continue
                    if self.get_titulus_info(l)[0] or self.is_latin_text(l) or self.get_roll_numbers(l, expected_next, pdf_idx, j): break
                    if self.re.match(r'^[A-E]\.\s+|^Original\s+|^B\.\s+|^C\.\s+|^London;|^Paris;|^München;', l):
                        ms_parts.append(l)
                    else: title_parts.append(l)
                    j += 1
                
                header_clean = self.re.sub(r'^(?:N[oO°\?]*\s*)?[\d\s\-\/]+', '', main_lines[i].strip()).strip()
                if header_clean: title_parts.insert(0, header_clean)

                for n in r_nums:
                    content.rolls.append(Roll(
                        roll_num=n,
                        title=" ".join(title_parts),
                        manuscripts=" ".join(ms_parts),
                        pdf_source=f"Dufour T1 ({pdf_idx})",
                        pdf_pages=[page_num]
                    ))
                expected_next = max(r_nums) + 1
                i = j; continue
            
            loc, h_text = self.get_titulus_info(main_lines[i])
            if loc:
                text_parts = []
                j = i + 1
                while j < len(main_lines):
                    l = main_lines[j].strip()
                    if not l or "=== FOOTNOTES ===" in l: j += 1; continue
                    if self.get_titulus_info(l)[0] or self.get_roll_numbers(l, expected_next, pdf_idx, j): break
                    text_parts.append(l); j += 1
                
                tit = Titulus(
                    title=h_text[:100],
                    location_name=loc,
                    latin_text=" ".join(text_parts),
                    page_num=page_num,
                    half=half
                )
                if content.rolls:
                    content.rolls[-1].tituli.append(tit)
                else:
                    content.orphaned_tituli.append(tit)
                i = j; continue
            i += 1
            
        if f_idx != -1:
            for idx, fn in enumerate(lines[f_idx+1:], 1):
                fn_s = fn.strip()
                if not fn_s: continue
                fm = self.re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', fn_s)
                fn_obj = Footnote(
                    footnote_num=self.re.findall(r'\d+', fm.group(1))[0] if fm and self.re.findall(r'\d+', fm.group(1)) else str(idx),
                    text=fm.group(2) if fm else fn_s,
                    page_num=page_num,
                    half=half
                )
                if content.rolls:
                    content.rolls[-1].footnotes.append(fn_obj)
                else:
                    content.orphaned_footnotes.append(fn_obj)
                    
        return content

class VLLMProcessor(PageProcessor):
    """
    Processor that uses Gemini Vision to extract structured data directly from page images.
    """
    def __init__(self, model_name="gemini-1.5-flash"):
        import google.generativeai as genai
        import os
        self.genai = genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(model_name)

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        # Note: In a real implementation, 'text' would be replaced by or supplemented with an 'image_path'
        # provided via metadata.
        image_path = metadata.get('image_path')
        if not image_path:
            raise ValueError("VLLMProcessor requires 'image_path' in metadata")
            
        import PIL.Image
        img = PIL.Image.open(image_path)
        
        prompt = f"""
        Extract structured data from this page image of a medieval mortuary rolls edition.
        ... (same logic as LLMStructuredProcessor but using image context) ...
        """
        # (Implementation details for multi-modal call)
        pass
