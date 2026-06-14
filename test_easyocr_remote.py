import sys
import easyocr
from PIL import Image
import numpy as np

# Load reader
reader = easyocr.Reader(['la', 'fr', 'en'])

# Test on original extracted image (only upscaled, no binarization)
img = Image.open("test_verify-05.png")
w, h = img.size
spine_x = w // 2
left_img = img.crop((0, 0, spine_x + 15, h))

w, h = left_img.size
upscaled = left_img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
arr = np.array(upscaled)

print("Running EasyOCR...")
results = reader.readtext(arr, paragraph=True)

for bbox, text in results:
    print(text)
