import os
import io
import numpy as np
from PIL import Image
from fastapi import FastAPI, UploadFile, File
import uvicorn
from doctr.models import ocr_predictor
import torch

app = FastAPI(title="Remote DocTR OCR Worker")

# Fallback: if DocTR fails to load, we can use EasyOCR
try:
    # Try a different detection architecture to avoid the corrupted ResNet50 download
    model = ocr_predictor(det_arch='db_mobilenet_v3_large', reco_arch='crnn_vgg16_bn', pretrained=True).cuda()
    print("DocTR initialized successfully.")
except Exception as e:
    print(f"DocTR failed to initialize: {e}")
    import easyocr
    reader = easyocr.Reader(['la', 'fr', 'en'], gpu=True)
    model = None
    print("EasyOCR fallback initialized.")

@app.post("/ocr")
async def perform_ocr(file: UploadFile = File(...)):
    contents = await file.read()
    img = Image.open(io.BytesIO(contents)).convert('RGB')

    if model:
        img_arr = np.array(img)
        result = model([img_arr])
        return result.export()
    else:
        # EasyOCR Fallback logic
        import easyocr
        img_arr = np.array(img)
        results = reader.readtext(img_arr, paragraph=True)
        # Mock DocTR output structure for the pipeline
        pages = [{
            "blocks": [{
                "lines": [{
                    "words": [{"value": r[1], "confidence": 1.0, "geometry": [[p[0]/img.width, p[1]/img.height] for p in r[0]]} for r in results]
                }]
            }]
        }]
        return {"pages": pages}

@app.get("/status")
async def get_status():
    return {
        "status": "ready",
        "engine": "DocTR" if model else "EasyOCR",
        "gpu": torch.cuda.get_device_name(0),
        "cuda_available": torch.cuda.is_available()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
