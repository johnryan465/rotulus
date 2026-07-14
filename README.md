# Rotulus: Mortuary Rolls Database

A specialized system for digitizing, parsing, and researching medieval mortuary rolls, specifically based on Jean Dufour's *Recueil des rouleaux des morts*.

## 🏗️ Architecture

The project uses a **hybrid architecture** that combines a dynamic development environment with a local vision-LLM extraction pipeline and a static production deployment.

- **Frontend**: React 19 + Vite (Modern, mobile-responsive SPA).
- **Backend (Dev)**: FastAPI + SQLite (Local server for CRUD and verification).
- **Extraction pipeline**: `pipeline/` - VLM-primary (page images sent directly to a local vision LLM), with text-based and regex fallback processors. See below.
- **Static Hosting**: GitHub Pages (Data exported from SQLite to static JSON during build).

---

## 🛠️ Engineering Workflows

### 1. Hybrid Development Mode
To maintain a fast dev loop without a persistent database server in production:
- **Local Dev**: Run `python server.py` (API) and `npm run dev` (Vite). The frontend automatically detects `localhost` and routes API calls to the FastAPI server.
- **Production**: Run `npm run build`. This triggers `export_static_data.py`, which dumps the SQLite database into structured JSON files in `public/api/`. GitHub Pages then serves these as a static API.

### 2. Extraction Pipeline
Run via `python run_pipeline.py --mode {vlm,local_llm,gemini,regex} [--live] [--reset]`. Defaults to a dry run in `vlm` mode.

- **`vlm` (default, primary path)**: `pipeline/provider.py`'s `PDFImageProvider` extracts page images directly from the source PDFs and `pipeline/processor.py`'s `LocalVLLMProcessor` sends them to a vision LLM (gemma3:27b via Ollama, on Stanley at `192.168.0.116:11434`). This bypasses the OCR text pipeline entirely, since `raw_text/` is known to be missing content on a meaningful fraction of pages.
- **`local_llm`**: text-based extraction from `raw_text/` (see below) via the same local Ollama server - faster per page, but inherits any gaps already present in the OCR text.
- **`gemini`** / **`regex`**: cloud LLM and legacy heuristic fallbacks.
- All processors share one prompt/schema (`pipeline/processor.py`) and are validated against known per-PDF roll-number ranges (`pipeline/validation.py`) before being accepted, so a single hallucinated roll number can't silently corrupt the extraction sequence.
- Runs are resumable: `pipeline/orchestrator.py` records finished pages in `processed_pages` and skips them on restart. Pass `--reset` to wipe the database and start over.
- Entities (named people/places mentioned within a titulus) are extracted as part of the same schema and linked to their titulus/footnote - see `pipeline/models.py`'s `Entity`.
- Citations (references to external catalogs/editions, e.g. Delisle's earlier "Rouleaux des morts" catalog) are extracted per-roll - see `pipeline/models.py`'s `Citation`. This is the primary signal for the project's research goal: finding evidence of mortuary rolls not referenced in this edition. Run `python audit_rolls.py` for a citations report, including a dedicated Delisle cross-reference list.

### 3. Remote OCR Pipeline (legacy text extraction, feeds `local_llm`/`regex` modes)
- **`ocr_pipeline.py`**: Extracts PDF pages, splits them (via the shared `pipeline/imaging.py` spine/footnote-splitting logic - also used by the VLM image provider and `server.py`'s image endpoint, so crops line up everywhere), and sends image segments to a remote DocTR OCR worker.
- **Remote Worker**: A FastAPI service (using **DocTR**) running on a machine with a powerful GPU (Stanley, an RTX 3090). It handles high-accuracy text recognition, writing `raw_text/*.txt`.

### 4. Configuration
Sensitive configuration (like remote OCR URLs) is managed via a `.env` file (which is ignored by Git).
```bash
# Example .env
REMOTE_OCR_URL=http://<remote-host-ip>:8000/ocr
```

---

## 🚀 Getting Started

### Prerequisites
- Node.js 20+
- Python 3.10+
- `pdftoppm` (poppler-utils) for PDF image extraction.

### Local Setup
1. **Frontend**:
   ```bash
   npm install
   npm run dev
   ```
2. **Backend**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   uv sync # Or pip install fastapi uvicorn pillow httpx python-dotenv
   python server.py
   ```

---

## 📂 Project Structure

- `src/`: React source code.
- `public/api/`: Static JSON data (Generated at build time).
- `pipeline/`: extraction pipeline - `provider.py` (page/image sources), `processor.py` (LLM/VLM/regex extraction + shared prompt schema), `orchestrator.py` (DB writes, validation, resumability), `imaging.py` (shared page-splitting), `geo.py` (travels/origin logic) + `geocoding.py` (Wikidata-backed place-name resolution, cached in the `locations` table - not a hardcoded list), `validation.py` (roll-number sanity checks), `models.py` (pydantic schema).
- `run_pipeline.py`: CLI entrypoint for the extraction pipeline.
- `ocr_pipeline.py`: Legacy OCR text extraction (PDF -> `raw_text/*.txt`), feeds the `local_llm`/`regex` modes.
- `database.py`: Single source of truth for the SQLite schema.
- `export_static_data.py`: The bridge between the SQLite DB and static hosting.

---

## 🛡️ Security
Standard Git hooks are implemented in `.pre-commit-config.yaml` to prevent committing PII or large binary files. Always keep PDFs out of the repository.
