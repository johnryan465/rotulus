import os
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.provider import PageProvider
from pipeline.processor import LegacyRegexProcessor, LLMStructuredProcessor

def main():
    # Setup
    RAW_TEXT_DIR = "/home/john/rolls/raw_text"
    DB_PATH = "rolls.db"
    
    provider = PageProvider(RAW_TEXT_DIR)
    
    # Choose processor: LegacyRegex or LLM
    # processor = LegacyRegexProcessor()
    
    # If GEMINI_API_KEY is present, we can use the LLM processor
    if os.getenv("GEMINI_API_KEY"):
        print("Using LLM Structured Processor...")
        processor = LLMStructuredProcessor()
    else:
        print("GEMINI_API_KEY not found. Using Legacy Regex Processor...")
        processor = LegacyRegexProcessor()
        
    orchestrator = PipelineOrchestrator(DB_PATH, provider, processor)
    
    # Run
    # Warning: orchestrator.reset_db() will clear the database!
    orchestrator.run(dry_run=True) # Start with dry_run to test

if __name__ == "__main__":
    main()
