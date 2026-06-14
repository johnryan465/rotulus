# Rotulus: Mortuary Rolls Database

A specialized system for digitizing, parsing, and researching medieval mortuary rolls, specifically based on Jean Dufour's *Recueil des rouleaux des morts*.

## 🏗️ Architecture

The project uses a **hybrid architecture** that combines a dynamic development environment with high-performance remote OCR capabilities and a static production deployment.

- **Frontend**: React 19 + Vite (Modern, mobile-responsive SPA).
- **Backend (Dev)**: FastAPI + SQLite (Local server for CRUD and verification).
- **OCR Pipeline**: Distributed between a local controller and a remote GPU-accelerated worker.
- **Static Hosting**: GitHub Pages (Data exported from SQLite to static JSON during build).

---

## 🛠️ Engineering Workflows

### 1. Hybrid Development Mode
To maintain a fast dev loop without a persistent database server in production:
- **Local Dev**: Run `python server.py` (API) and `npm run dev` (Vite). The frontend automatically detects `localhost` and routes API calls to the FastAPI server.
- **Production**: Run `npm run build`. This triggers `export_static_data.py`, which dumps the SQLite database into structured JSON files in `public/api/`. GitHub Pages then serves these as a static API.

### 2. Remote OCR Pipeline
The OCR pipeline is split to leverage high-performance hardware:
- **`ocr_pipeline.py`**: The local controller. It extracts PDF pages, performs layout analysis, and sends image segments to a remote worker.
- **Remote Worker**: A FastAPI service (e.g., using **DocTR**) running on a machine with a powerful GPU (like an RTX 3090). It handles high-accuracy text recognition.
- **`parser.py`**: A complex heuristic engine that turns raw OCR text into structured rolls, tituli, and entities.

### 3. Configuration
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
- `ocr_pipeline.py`: Orchestrates PDF -> Text.
- `parser.py`: The logic for identifying rolls and linking footnotes.
- `database.py`: SQLite schema definitions and initialization.
- `export_static_data.py`: The bridge between the SQLite DB and static hosting.

---

## 🛡️ Security
Standard Git hooks are implemented in `.pre-commit-config.yaml` to prevent committing PII or large binary files. Always keep PDFs out of the repository.
