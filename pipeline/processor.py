import os
import json
import httpx
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .models import PageContent, Roll, Titulus, Footnote

class PageProcessor(ABC):
    """Base class for processing a page of the mortuary rolls edition."""
    
    @abstractmethod
    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        pass

class LegacyRegexProcessor(PageProcessor):
    """Fallback implementation using refined regex logic."""
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
        if line_idx < 3 and self.re.match(r'^(?:N[oO°\?]*\s*)?\d+(?:\s*-\s*\d+)?\s*$', line.strip()): return None
        bounds = {1: (1, 74), 2: (74, 105), 3: (106, 121), 4: (122, 200)}
        min_r, max_roll = bounds.get(pdf_idx, (1, 200))
        m = self.re.match(r'^(?:N[oO°\?]*\s*)?(\d+)(?:\s*[\-\/]\s*(\d+))?', line.strip())
        if m:
            nums = [int(m.group(1))]
            if m.group(2): nums.extend(range(int(m.group(1)) + 1, int(m.group(2)) + 1))
            if any(min_r <= n <= max_roll for n in nums) and any(expected_next - 2 <= n <= expected_next + 10 for n in nums):
                if not line.strip()[m.end():].strip().startswith("["): return nums
        return None

    def get_titulus_info(self, line):
        s = line.strip()
        m1 = self.re.match(r'^(\d+)\s*\[(\d+)\]\s*(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,40})', s)
        if m1: return m1.group(4).strip(" ."), s
        m2 = self.re.match(r'^(\d+)\s+(?:S\.?d\.?|\[?[\d\w\s]+\]?)\s*([-~]\s*)?([^0-9,;:\.\n\r]{3,40})', s)
        if m2 and int(m2.group(1)) < 500: return m2.group(3).strip(" ."), s
        if self.re.match(r'^T[T]?\.\s+([^0-9,;:\.\n\r]{3,40})', s):
            return (s.split(".", 1)[1].split(".")[0].strip() if "." in s else s), s
        return None, None

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        pdf_idx, page_num, half, expected_next = metadata.get('pdf_idx', 1), metadata.get('page_num', 1), metadata.get('half', 'full'), metadata.get('expected_next_roll', 1)
        lines = text.split('\n'); f_idx = next((idx for idx, l in enumerate(lines) if "=== FOOTNOTES ===" in l), -1)
        main_lines = lines[:f_idx] if f_idx != -1 else lines; content = PageContent()
        i = 0
        while i < len(main_lines):
            r_nums = self.get_roll_numbers(main_lines[i], expected_next, pdf_idx, i)
            if r_nums:
                title_parts, ms_parts, j = [], [], i + 1
                while j < len(main_lines):
                    l = main_lines[j].strip()
                    if not l or "=== FOOTNOTES ===" in l or self.get_titulus_info(l)[0] or self.is_latin_text(l) or self.get_roll_numbers(l, expected_next, pdf_idx, j): break
                    if self.re.match(r'^[A-E]\.\s+|^Original\s+|^B\.\s+|^C\.\s+|^London;|^Paris;|^München;', l): ms_parts.append(l)
                    else: title_parts.append(l)
                    j += 1
                h_clean = self.re.sub(r'^(?:N[oO°\?]*\s*)?[\d\s\-\/]+', '', main_lines[i].strip()).strip()
                if h_clean: title_parts.insert(0, h_clean)
                for n in r_nums:
                    content.rolls.append(Roll(roll_num=n, title=" ".join(title_parts), manuscripts=" ".join(ms_parts), pdf_source=f"Dufour T1 ({pdf_idx})", pdf_pages=[page_num]))
                expected_next, i = max(r_nums) + 1, j; continue
            loc, h_text = self.get_titulus_info(main_lines[i])
            if loc:
                text_parts, j = [], i + 1
                while j < len(main_lines):
                    l = main_lines[j].strip()
                    if not l or "=== FOOTNOTES ===" in l or self.get_titulus_info(l)[0] or self.get_roll_numbers(l, expected_next, pdf_idx, j): break
                    text_parts.append(l); j += 1
                tit = Titulus(title=h_text[:100], location_name=loc, latin_text=" ".join(text_parts), page_num=page_num, half=half)
                if content.rolls: content.rolls[-1].tituli.append(tit)
                else: content.orphaned_tituli.append(tit)
                i = j; continue
            i += 1
        if f_idx != -1:
            for idx, fn in enumerate(lines[f_idx+1:], 1):
                fn_s = fn.strip()
                if not fn_s: continue
                fm = self.re.match(r'^\s*([®©§%#@\d\w\(\)\]\[\-]+|\b\w\b)\s+(.+)$', fn_s)
                fn_obj = Footnote(footnote_num=self.re.findall(r'\d+', fm.group(1))[0] if fm and self.re.findall(r'\d+', fm.group(1)) else str(idx), text=fm.group(2) if fm else fn_s, page_num=page_num, half=half)
                if content.rolls: content.rolls[-1].footnotes.append(fn_obj)
                else: content.orphaned_footnotes.append(fn_obj)
        return content

class LocalOllamaProcessor(PageProcessor):
    """
    Processor using Ollama on the remote 3090 machine.
    Expects OLLAMA_HOST environment variable (e.g. http://192.168.0.116:11434).
    """
    def __init__(self, model="gemma4:26b", host=None):
        self.model = model
        self.host = host or os.getenv("OLLAMA_HOST", "http://192.168.0.116:11434")

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        prompt = f"""
        Extract structured data from the medieval mortuary rolls text below.
        Follow the exact JSON schema provided.
        Metadata: {metadata}
        Text: {text}
        
        Return ONLY valid JSON.
        """
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(f"{self.host}/api/generate", json={
                    "model": self.model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False
                })
                response.raise_for_status()
                data = response.json().get("response", "{}")
                return PageContent(**json.loads(data))
        except Exception as e:
            print(f"Local Ollama failed: {e}. Falling back to Regex.")
            return LegacyRegexProcessor().process_page(text, metadata)

class LLMStructuredProcessor(PageProcessor):
    """Cloud-based structured extraction using Gemini 1.5 Pro."""
    def __init__(self, model_name="gemini-1.5-pro"):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(model_name)

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        prompt = f"Extract mortuary roll data from this text into JSON: {text}. Metadata: {metadata}"
        response = self.model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return PageContent(**json.loads(response.text))

class LocalVLLMProcessor(PageProcessor):
    """
    Vision-based extraction using LLaVA (13B) via Ollama on the 3090.
    """
    def __init__(self, model="llava:13b", host=None):
        self.model = model
        self.host = host or os.getenv("OLLAMA_HOST", "http://192.168.0.116:11434")

    def process_page(self, text: str, metadata: Dict[str, Any]) -> PageContent:
        import base64
        image_path = metadata.get('image_path')
        if not image_path or not os.path.exists(image_path):
            return LegacyRegexProcessor().process_page(text, metadata)
            
        with open(image_path, "rb") as img_file:
            img_b64 = base64.b64encode(img_file.read()).decode('utf-8')
            
        prompt = "Analyze this medieval edition page image and extract all rolls and tituli into structured JSON."
        try:
            with httpx.Client(timeout=180.0) as client:
                response = client.post(f"{self.host}/api/generate", json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [img_b64],
                    "format": "json",
                    "stream": False
                })
                response.raise_for_status()
                data = response.json().get("response", "{}")
                return PageContent(**json.loads(data))
        except Exception as e:
            print(f"Local VLLM failed: {e}")
            return LegacyRegexProcessor().process_page(text, metadata)
