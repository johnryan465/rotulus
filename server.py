import os
import sqlite3
import subprocess
import tempfile
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from PIL import Image

from pipeline.imaging import split_page_halves
from pipeline.geo import get_roll_travels as _get_roll_travels, get_roll_movements as _get_roll_movements

WORKSPACE = "/home/john/rolls"
DB_PATH = os.path.join(WORKSPACE, "rolls.db")
CACHE_DIR = os.path.join(WORKSPACE, "image_cache")
PDF_DIR = WORKSPACE

os.makedirs(CACHE_DIR, exist_ok=True)

app = FastAPI(title="Mortuary Rolls API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Pydantic models for updates
class RollUpdate(BaseModel):
    roll_num: int
    date_str: str
    title: str
    manuscripts: str

class TitulusUpdate(BaseModel):
    title: str
    latin_text: str

class EntityUpdate(BaseModel):
    normalized_name: str
    normalized_role: str
    normalized_dates: str
    location_name: str

@app.get("/api/rolls")
def get_rolls(q: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if q:
        search_query = f"%{q}%"
        cursor.execute("""
        SELECT DISTINCT r.* FROM rolls r
        LEFT JOIN tituli t ON t.roll_id = r.id
        LEFT JOIN entities e ON e.titulus_id = t.id
        WHERE r.title LIKE ? OR r.roll_num LIKE ? OR r.date_str LIKE ? 
           OR t.title LIKE ? OR t.latin_text LIKE ?
           OR e.original_name LIKE ? OR e.normalized_name LIKE ? OR e.location_name LIKE ?
        """, (search_query, search_query, search_query, search_query, search_query, search_query, search_query, search_query))
    else:
        cursor.execute("SELECT * FROM rolls ORDER BY id")
        
    rolls = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rolls

@app.get("/api/rolls/{roll_id}")
def get_roll_details(roll_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM rolls WHERE id = ?", (roll_id,))
    roll_row = cursor.fetchone()
    if not roll_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Roll not found")
    roll = dict(roll_row)
    
    cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (roll_id,))
    tituli = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM footnotes WHERE roll_id = ? ORDER BY pdf_page, pdf_half, CAST(footnote_num AS INTEGER)", (roll_id,))
    footnotes = [dict(row) for row in cursor.fetchall()]
    
    for tit in tituli:
        cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
        tit["entities"] = [dict(row) for row in cursor.fetchall()]
        
    conn.close()
    
    return {
        "roll": roll,
        "tituli": tituli,
        "footnotes": footnotes
    }

@app.get("/api/rolls/{roll_id}/travels")
def get_roll_travels(roll_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rolls WHERE id = ?", (roll_id,))
    roll_row = cursor.fetchone()
    if not roll_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Roll not found")
    travels = _get_roll_travels(cursor, roll_row)
    conn.close()
    return travels

@app.get("/api/rolls/{roll_id}/movements")
def get_roll_movements(roll_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rolls WHERE id = ?", (roll_id,))
    roll_row = cursor.fetchone()
    if not roll_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Roll not found")
    movements = _get_roll_movements(cursor, roll_row)
    conn.close()
    return movements

@app.get("/api/travels")
def get_all_travels():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rolls ORDER BY id")
    rolls = [dict(row) for row in cursor.fetchall()]

    all_travels = {}
    for r in rolls:
        cursor.execute("SELECT * FROM rolls WHERE id = ?", (r["id"],))
        roll_row = cursor.fetchone()
        travels = _get_roll_travels(cursor, roll_row)
        if travels:
            all_travels[r["id"]] = {
                "roll_num": r["roll_num"],
                "title": r["title"],
                "date_str": r["date_str"],
                "travels": travels
            }
    conn.close()
    return all_travels

@app.put("/api/rolls/{roll_id}")
def update_roll(roll_id: int, data: RollUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE rolls SET roll_num = ?, date_str = ?, title = ?, manuscripts = ?
    WHERE id = ?
    """, (data.roll_num, data.date_str, data.title, data.manuscripts, roll_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.put("/api/tituli/{tit_id}")
def update_titulus(tit_id: int, data: TitulusUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE tituli SET title = ?, latin_text = ? WHERE id = ?
    """, (data.title, data.latin_text, tit_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.put("/api/entities/{ent_id}")
def update_entity(ent_id: int, data: EntityUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE entities SET normalized_name = ?, normalized_role = ?, normalized_dates = ?, location_name = ?
    WHERE id = ?
    """, (data.normalized_name, data.normalized_role, data.normalized_dates, data.location_name, ent_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/rolls/{roll_id}/verify")
def toggle_verify(roll_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified FROM rolls WHERE id = ?", (roll_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Roll not found")
        
    new_status = 1 if row["is_verified"] == 0 else 0
    cursor.execute("UPDATE rolls SET is_verified = ? WHERE id = ?", (new_status, roll_id))
    conn.commit()
    conn.close()
    return {"status": "success", "is_verified": new_status}

@app.get("/api/image/{pdf_idx}/{page_num}/{half}")
def get_page_image(pdf_idx: int, page_num: int, half: str):
    """Serve cropped page image dynamically, with local caching."""
    cache_filename = f"pdf{pdf_idx}_p{page_num}_{half}.png"
    cache_path = os.path.join(CACHE_DIR, cache_filename)
    
    if os.path.exists(cache_path):
        return FileResponse(cache_path, media_type="image/png")
        
    pdf_files = [
        "Dufour T1 p. 3-157 (1).pdf",
        "Dufour T1 p. 157-351 (1).pdf",
        "Dufour T1 p. 351-529 (2).pdf",
        "Dufour T1 p. 529-714 (4).pdf"
    ]
    
    if pdf_idx < 1 or pdf_idx > len(pdf_files):
        raise HTTPException(status_code=400, detail="Invalid PDF index")
        
    pdf_name = pdf_files[pdf_idx - 1]
    pdf_path = os.path.join(PDF_DIR, pdf_name)
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Source PDF file not found")
        
    with tempfile.TemporaryDirectory() as tmpdir:
        prefix = os.path.join(tmpdir, "page")
        cmd = ["pdftoppm", "-png", "-f", str(page_num), "-l", str(page_num), pdf_path, prefix]
        subprocess.run(cmd, check=True)
        
        extracted_file = None
        for f in os.listdir(tmpdir):
            if f.startswith("page-") and f.endswith(".png"):
                extracted_file = os.path.join(tmpdir, f)
                break
                
        if not extracted_file or not os.path.exists(extracted_file):
            raise HTTPException(status_code=500, detail="Failed to extract page image")
            
        img = Image.open(extracted_file)
        left_img, right_img = split_page_halves(img)

        if right_img is not None and half == "left":
            cropped = left_img
        elif right_img is not None and half == "right":
            cropped = right_img
        else:
            cropped = img
            
        cropped.save(cache_path, "PNG")
        
    return FileResponse(cache_path, media_type="image/png")

@app.get("/api/image/{pdf_idx}/{page_num}/{half}/bounds")
def get_page_bounds(pdf_idx: int, page_num: int, half: str):
    """Retrieve text bounding box coordinates and content for a specific page half."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT x_min, y_min, x_max, y_max, text, confidence, region_type 
    FROM spatial_regions 
    WHERE pdf_idx = ? AND page_num = ? AND half = ?
    """, (pdf_idx, page_num, half))
    bounds = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return bounds

@app.get("/api/export/json")
def export_json():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM rolls")
    rolls = [dict(row) for row in cursor.fetchall()]
    
    for r in rolls:
        cursor.execute("SELECT * FROM tituli WHERE roll_id = ?", (r["id"],))
        tituli = [dict(row) for row in cursor.fetchall()]
        for t in tituli:
            cursor.execute("SELECT * FROM entities WHERE titulus_id = ?", (t["id"],))
            t["entities"] = [dict(row) for row in cursor.fetchall()]
        r["tituli"] = tituli
        
        cursor.execute("SELECT * FROM footnotes WHERE roll_id = ?", (r["id"],))
        r["footnotes"] = [dict(row) for row in cursor.fetchall()]
        
    conn.close()
    return JSONResponse(content=rolls)

@app.get("/api/export/csv")
def export_csv():
    import csv
    import io
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT r.roll_num, r.date_str as roll_date, r.title as roll_title,
           t.title as titulus_title, t.latin_text,
           e.original_name, e.original_title, e.normalized_name, e.normalized_role, e.normalized_dates, e.location_name
    FROM rolls r
    LEFT JOIN tituli t ON t.roll_id = r.id
    LEFT JOIN entities e ON e.titulus_id = t.id
    ORDER BY r.id, t.id, e.id
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Roll Number", "Roll Date", "Roll Title",
        "Titulus Title", "Latin Text",
        "Original Name", "Original Title", "Normalized Name", "Normalized Role", "Normalized Dates", "Location Name"
    ])
    
    for row in rows:
        writer.writerow(list(row))
        
    headers = {
        'Content-Disposition': 'attachment; filename="mortuary_rolls_export.csv"',
        'Content-Type': 'text/csv'
    }
    return Response(content=output.getvalue(), headers=headers)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
