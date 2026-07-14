import os
import json
from pipeline.provider import PageProvider
from pipeline.processor import LocalVLLMProcessor

def test_vllm_page():
    # Setup
    IMAGE_CACHE_DIR = "/home/john/rolls/image_cache"
    ollama_host = os.getenv("OLLAMA_HOST", "http://192.168.0.116:11434")
    local_model = os.getenv("LOCAL_MODEL", "gemma4:26b")
    
    print(f"Testing Local VLLM Processor ({local_model}) at {ollama_host}...")
    processor = LocalVLLMProcessor(model=local_model, host=ollama_host)
    
    # Mock metadata for the test image we just created
    metadata = {
        "pdf_idx": 1,
        "page_num": 1,
        "half": "full",
        "image_path": "image_cache/pdf1_p1_full.png",
        "expected_next_roll": 1
    }
    
    content = processor.process_page("", metadata)
    print("\n--- VLLM EXTRACTED CONTENT ---")
    print(content.model_dump_json(indent=2))

if __name__ == "__main__":
    test_vllm_page()
