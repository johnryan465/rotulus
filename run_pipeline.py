import os
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.provider import PageProvider
from pipeline.processor import LegacyRegexProcessor, LLMStructuredProcessor, LocalOllamaProcessor

def main():
    # Setup
    RAW_TEXT_DIR = "/home/john/rolls/raw_text"
    DB_PATH = "rolls.db"
    
    provider = PageProvider(RAW_TEXT_DIR)
    
    # Processor Selection Logic
    ollama_host = os.getenv("OLLAMA_HOST", "http://192.168.0.116:11434")
    
    if os.getenv("USE_LOCAL_LLM") == "true":
        print(f"Using Local Ollama Processor (Llama 3 8B) at {ollama_host}...")
        processor = LocalOllamaProcessor(host=ollama_host)
    elif os.getenv("GEMINI_API_KEY"):
        print("Using Gemini Structured Processor (Cloud)...")
        processor = LLMStructuredProcessor()
    else:
        print("No LLM keys found. Using Legacy Regex Processor...")
        processor = LegacyRegexProcessor()
        
    orchestrator = PipelineOrchestrator(DB_PATH, provider, processor)
    
    # Run
    # Warning: orchestrator.reset_db() will clear the database!
    orchestrator.run(dry_run=True) 

if __name__ == "__main__":
    main()
