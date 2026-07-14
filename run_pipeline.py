import argparse
import os
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.provider import PageProvider, PDFImageProvider
from pipeline.processor import LegacyRegexProcessor, LLMStructuredProcessor, LocalOllamaProcessor, LocalVLLMProcessor

RAW_TEXT_DIR = "/home/john/rolls/raw_text"
IMAGE_CACHE_DIR = "/home/john/rolls/image_cache"
DB_PATH = "rolls.db"
PDF_FILES = [
    {"name": "Dufour T1 p. 3-157 (1).pdf", "pages": 80},
    {"name": "Dufour T1 p. 157-351 (1).pdf", "pages": 99},
    {"name": "Dufour T1 p. 351-529 (2).pdf", "pages": 91},
    {"name": "Dufour T1 p. 529-714 (4).pdf", "pages": 94},
]


def build_provider_and_processor(mode, ollama_host, local_model):
    if mode == "vlm":
        print(f"Using PDF Image Provider + Local VLM Processor ({local_model}) at {ollama_host} (End-to-End VLM)...")
        return PDFImageProvider(PDF_FILES, IMAGE_CACHE_DIR), LocalVLLMProcessor(model=local_model, host=ollama_host)

    provider = PageProvider(RAW_TEXT_DIR, IMAGE_CACHE_DIR)
    if mode == "local_llm":
        print(f"Using standard Page Provider + Local Ollama Processor ({local_model}) at {ollama_host}...")
        return provider, LocalOllamaProcessor(model=local_model, host=ollama_host)
    if mode == "gemini":
        print("Using standard Page Provider + Gemini Structured Processor (Cloud)...")
        return provider, LLMStructuredProcessor()

    print("Using standard Page Provider + Legacy Regex Processor...")
    return provider, LegacyRegexProcessor()


def main():
    parser = argparse.ArgumentParser(description="Run the Rotulus extraction pipeline.")
    parser.add_argument("--mode", choices=["vlm", "local_llm", "gemini", "regex"], default="vlm",
                         help="Extraction path to use (default: vlm, the primary path - reads page "
                              "images directly instead of relying on the OCR text pipeline).")
    parser.add_argument("--live", action="store_true",
                         help="Actually write to the database. Default is a dry run (process and print only).")
    parser.add_argument("--reset", action="store_true",
                         help="Wipe the database and start from page 1. Default resumes, skipping "
                              "pages already recorded in processed_pages.")
    args = parser.parse_args()

    ollama_host = os.getenv("OLLAMA_HOST", "http://192.168.0.116:11434")
    local_model = os.getenv("LOCAL_MODEL", "gemma4:26b")

    provider, processor = build_provider_and_processor(args.mode, ollama_host, local_model)
    orchestrator = PipelineOrchestrator(DB_PATH, provider, processor)
    orchestrator.run(dry_run=not args.live, reset=args.reset)


if __name__ == "__main__":
    main()
