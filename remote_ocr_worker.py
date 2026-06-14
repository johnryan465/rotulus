from fastapi import FastAPI, UploadFile, File
import easyocr
import numpy as np
from PIL import Image
import io
import uvicorn

app = FastAPI()

# Initialize EasyOCR with GPU
# 'la' for Latin, 'fr' for French, 'en' for English
reader = easyocr.Reader(['la', 'fr', 'en'], gpu=True)

@app.post("/ocr")
async def perform_ocr(file: UploadFile = File(...)):
    contents = await file.read()
    img = Image.open(io.BytesIO(contents))
    
    # Preprocessing: convert to grayscale if needed, but EasyOCR handles it
    # We can also upscale here if the 3090 has enough VRAM
    img_arr = np.array(img)
    
    # Run EasyOCR
    # paragraph=True helps grouping text lines
    results = reader.readtext(img_arr, paragraph=True)
    
    # Format results: [([[x,y], ...], text), ...]
    # We convert numpy types to native python types for JSON serialization
    formatted_results = []
    for bbox, text in results:
        # bbox is a list of 4 lists [x,y]
        clean_bbox = [[int(coord[0]), int(coord[1])] for coord in bbox]
        formatted_results.append({
            "bbox": clean_bbox,
            "text": text
        })
        
    return {"results": formatted_results}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
