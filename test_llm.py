import os
import json
from pipeline.provider import PageProvider
from pipeline.processor import LocalOllamaProcessor

def test_single_page():
    # Setup
    RAW_TEXT_DIR = "/home/john/rolls/raw_text"
    provider = PageProvider(RAW_TEXT_DIR)
    
    ollama_host = os.getenv("OLLAMA_HOST", "http://192.168.0.116:11434")
    local_model = os.getenv("LOCAL_MODEL", "gemma4:26b")
    
    print(f"Testing Local Ollama Processor ({local_model}) at {ollama_host}...")
    processor = LocalOllamaProcessor(model=local_model, host=ollama_host)
    
    # Get just the first page
    pages = provider.get_pages()
    for _ in range(5): # Skip to a page with interesting content (Roll 2)
        text, metadata = next(pages)
        
    print(f"Processing {metadata['filename']}...")
    metadata['expected_next_roll'] = 2
    
    content = processor.process_page(text, metadata)
    print("\n--- EXTRACTED CONTENT ---")
    print(content.model_dump_json(indent=2))

if __name__ == "__main__":
    test_single_page()
