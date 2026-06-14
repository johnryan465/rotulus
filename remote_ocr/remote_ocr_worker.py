import os
import io
import numpy as np
from PIL import Image
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
import uvicorn
from doctr.models import ocr_predictor
import torch

app = FastAPI(title="Remote DocTR OCR Worker")

# Initialize DocTR with PyTorch backend and GPU
# We use standard high-res models
model = ocr_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True).cuda()

@app.post("/ocr")
async def perform_ocr(file: UploadFile = File(...)):
    contents = await file.read()
    img = Image.open(io.BytesIO(contents)).convert('RGB')
    
    # Convert PIL to numpy for DocTR
    img_arr = np.array(img)
    
    # DocTR expects a list of images
    result = model([img_arr])
    
    # Export to JSON-like structure
    # result.export() returns a dict with pages, blocks, lines, words
    return result.export()

@app.get("/status")
async def get_status():
    return {
        "status": "ready",
        "gpu": torch.cuda.get_device_name(0),
        "cuda_available": torch.cuda.is_available()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
