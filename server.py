import os
import re
import sqlite3
import subprocess
import tempfile
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from PIL import Image

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
    roll_num: str
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

GEOLOCATIONS = {
    "gent": [51.0543, 3.7174, "Ghent, Belgium"],
    "ghent": [51.0543, 3.7174, "Ghent, Belgium"],
    "vatican": [41.9022, 12.4539, "Vatican City"],
    "vaticano": [41.9022, 12.4539, "Vatican City"],
    "anglia": [52.5000, 1.0000, "East Anglia, England"],
    "angha": [52.5000, 1.0000, "East Anglia, England"],
    "wimborne": [50.8010, -1.9830, "Wimborne Minster, England"],
    "fulda": [50.5528, 9.6775, "Fulda Abbey, Germany"],
    "luxeuil": [47.8178, 6.3117, "Luxeuil Abbey, France"],
    "st. gall": [47.4245, 9.3767, "Abbey of Saint Gall, Switzerland"],
    "sankt gallen": [47.4245, 9.3767, "Abbey of Saint Gall, Switzerland"],
    "attigny": [49.4719, 4.5778, "Attigny, France"],
    "dingolfing": [48.6293, 12.4984, "Dingolfing, Germany"],
    "wien": [48.2082, 16.3738, "Vienna, Austria"],
    "vienna": [48.2082, 16.3738, "Vienna, Austria"],
    "karlsruhe": [49.0069, 8.4037, "Karlsruhe, Germany"],
    "rastatt": [48.8573, 8.2030, "Rastatt, Germany"],
    "montecassino": [41.4901, 13.8143, "Montecassino Abbey, Italy"],
    "mont cassin": [41.4901, 13.8143, "Montecassino Abbey, Italy"],
    "mainz": [49.9929, 8.2473, "Mainz, Germany"],
    "glastonbury": [51.1473, -2.7186, "Glastonbury, England"],
    "jumièges": [49.4326, 0.8211, "Jumièges Abbey, France"],
    "jumieges": [49.4326, 0.8211, "Jumièges Abbey, France"],
    "flavigny": [47.5126, 4.5312, "Flavigny Abbey, France"],
    "novalesa": [45.1897, 7.0142, "Novalesa Abbey, Italy"],
    "rebais": [48.8471, 3.2323, "Rebais Abbey, France"],
    "saint-wandrille": [49.5297, 0.7225, "Saint-Wandrille Abbey, France"],
    "wandrille": [49.5297, 0.7225, "Saint-Wandrille Abbey, France"],
    "corbie": [49.9085, 2.5089, "Corbie Abbey, France"],
    "niederaltaich": [48.7663, 13.0274, "Niederaltaich Abbey, Germany"],
    "altaich": [48.7663, 13.0274, "Niederaltaich Abbey, Germany"],
    "reichenau": [47.6994, 9.0601, "Reichenau Abbey, Germany"],
    "salzburg": [47.8095, 13.0550, "Salzburg, Austria"],
    "salzbourg": [47.8095, 13.0550, "Salzburg, Austria"],
    "saint-denis": [48.9358, 2.3598, "Saint-Denis Abbey, France"],
    "denis": [48.9358, 2.3598, "Saint-Denis Abbey, France"],
    "saint-germain": [48.8542, 2.3332, "Saint-Germain-des-Prés, France"],
    "germain": [48.8542, 2.3332, "Saint-Germain-des-Prés, France"],
    "saint-maurice": [46.2163, 7.0033, "Saint-Maurice Abbey, Switzerland"],
    "maurice": [46.2163, 7.0033, "Saint-Maurice Abbey, Switzerland"],
    "agaune": [46.2163, 7.0033, "Saint-Maurice Abbey, Switzerland"],
    "verdun": [49.1599, 5.3855, "Verdun, France"],
    "besançon": [47.2378, 6.0241, "Besançon, France"],
    "besancon": [47.2378, 6.0241, "Besançon, France"],
    "moosburg": [48.4682, 11.9360, "Moosburg, Germany"],
    "mondsee": [47.8566, 13.3516, "Mondsee Abbey, Austria"],
    "tegernsee": [47.7081, 11.7584, "Tegernsee Abbey, Germany"],
    "metten": [48.8576, 12.9133, "Metten Abbey, Germany"],
    "benediktbeuern": [47.7082, 11.4116, "Benediktbeuern Abbey, Germany"],
    "weltenburg": [48.8967, 11.8203, "Weltenburg Abbey, Germany"],
    "saint-cloud": [48.8413, 2.2185, "Saint-Cloud Abbey, France"],
    "cloud": [48.8413, 2.2185, "Saint-Cloud Abbey, France"],
    "eichstätt": [48.8920, 11.1830, "Eichstätt, Germany"],
    "eichstatt": [48.8920, 11.1830, "Eichstätt, Germany"],
    "würzburg": [49.7913, 9.9534, "Würzburg, Germany"],
    "wurzburg": [49.7913, 9.9534, "Würzburg, Germany"],
    "noyon": [49.5807, 2.9995, "Noyon, France"],
    "murbach": [47.9234, 7.1581, "Murbach Abbey, France"],
    "bayeux": [49.2794, -0.7028, "Bayeux, France"],
    "tours": [47.3941, 0.6848, "Tours, France"],
    "chur": [46.8508, 9.5320, "Chur, Switzerland"],
    "coire": [46.8508, 9.5320, "Chur, Switzerland"],
    "angers": [47.4784, -0.5635, "Angers, France"],
    "winchester": [51.0632, -1.3080, "Winchester, England"],
    "saint-riquier": [50.1347, 1.9472, "Saint-Riquier Abbey, France"],
    "centula": [50.1347, 1.9472, "Saint-Riquier Abbey, France"],
    "riquier": [50.1347, 1.9472, "Saint-Riquier Abbey, France"],
    "pfifers": [46.9934, 9.5028, "Pfäfers Abbey, Switzerland"],
    "pfäfers": [46.9934, 9.5028, "Pfäfers Abbey, Switzerland"],
    "nesle": [48.7619, 3.5683, "Nesle-la-Reposte, France"],
    "saint-evroult": [48.7903, 0.4627, "Saint-Evroult Abbey, France"],
    "evroult": [48.7903, 0.4627, "Saint-Evroult Abbey, France"],
    "scharnitz": [47.3889, 11.2642, "Scharnitz Abbey, Austria"],
    "isen": [48.2124, 12.0628, "Isen Abbey, Germany"],
    "oberaltaich": [48.9132, 12.6775, "Oberaltaich Abbey, Germany"],
    "berg": [48.9868, 12.0833, "Berg im Donaugau, Germany"],
    "schliersee": [47.7247, 11.8615, "Schliersee, Germany"],
    "northumbrie": [55.1000, -2.0000, "Northumbria, England"],
    "northumbria": [55.1000, -2.0000, "Northumbria, England"],
    "hautvillers": [49.0817, 3.9383, "Abbey of Hautvillers, France"],
    "rochester": [51.3900, 0.5050, "Rochester, England"],
    "anchinl": [50.3854, 3.2323, "Anchin Abbey, France"],
    "chalon": [46.7833, 4.8500, "Chalon-sur-Saône, France"],
    "nantcuil": [46.0022, 0.2818, "Nanteuil-en-Vallée Abbey, France"],
    "clermont": [45.7772, 3.0870, "Clermont-Ferrand, France"],
    "sever": [43.7600, -0.5739, "Saint-Sever Abbey, France"],
    "toulouse": [43.6047, 1.4442, "Toulouse, France"],
    "tourtoirac": [45.2706, 1.0594, "Tourtoirac Abbey, France"],
    "brioude": [45.2933, 3.3847, "Brioude Abbey, France"],
    "fleury": [47.8093, 2.3053, "Fleury Abbey, France"],
    "redon": [47.6534, -2.0850, "Redon Abbey, France"],
    "tournus": [46.5647, 4.9111, "Tournus Abbey, France"],
    "laon": [49.5642, 3.6199, "Laon, France"],
    "poitiers": [46.5802, 0.3404, "Poitiers, France"],
    "montierneuf": [46.5802, 0.3404, "Montierneuf Abbey, France"]
}

def geocode_location(name):
    if not name:
        return None
    s = name.strip().lower()
    if s in GEOLOCATIONS:
        return GEOLOCATIONS[s]
    for key, val in GEOLOCATIONS.items():
        if key in s:
            return val
    return None

@app.get("/api/rolls/{roll_id}/travels")
def get_roll_travels(roll_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get the roll to find its origin
    cursor.execute("SELECT * FROM rolls WHERE id = ?", (roll_id,))
    roll_row = cursor.fetchone()
    if not roll_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Roll not found")
    roll = dict(roll_row)
    
    # Try to geocode the roll title or manuscripts as origin
    origin_geo = None
    origin_name = "Origin"
    
    # Find any geocodable name in the title/manuscripts
    for word in re.findall(r'\b[A-Za-zÀ-ÿ\-]+\b', roll["title"] + " " + roll["manuscripts"]):
        geo = geocode_location(word)
        if geo:
            origin_geo = geo
            origin_name = geo[2]
            break
            
    travels = []
    if origin_geo:
        travels.append({
            "step": 0,
            "type": "origin",
            "name": origin_name,
            "coords": origin_geo[:2],
            "description": f"Origin: {roll['title'][:50]}..."
        })
    else:
        # Fallback to first non-common capitalized word in the title/manuscripts as origin name
        words = re.findall(r'\b[A-Z][a-zA-ZÀ-ÿ\-]+\b', roll["title"] + " " + roll["manuscripts"])
        exclude = {
            "T", "S", "Sancti", "Sancte", "Sanctorum", "Sanctique", "Sanctus", "Sanctis",
            "Anima", "Amen", "Orate", "Oravimus", "Abbas", "Abbatis", "Titulus", "Implicit",
            "Deus", "Domini", "Domino", "Dominus", "Christo", "Christi", "Maria", "Marie",
            "Petri", "Martyris", "Apostolorum", "Pauli", "Johannis", "Trinitatis", "Ecclesie",
            "Monasterii", "Cenobii", "Cujus", "Vitalis", "Vitali", "Hospitalitatis",
            "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
            "Original", "Communication", "Wien", "Paris", "Bibliotheque", "Nationalbibl", "Briefe", "Brief", "EpP", "M", "G", "H", "R", "Rau", "Lul"
        }
        exclude_lower = {e.lower() for e in exclude}
        filtered = [w for w in words if w.lower() not in exclude_lower]
        if filtered:
            travels.append({
                "step": 0,
                "type": "origin",
                "name": filtered[0],
                "coords": None,
                "description": f"Origin: {roll['title'][:50]}..."
            })
        
    # Get all tituli and their entities
    cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (roll_id,))
    tituli = [dict(row) for row in cursor.fetchall()]
    
    step = len(travels)
    for tit in tituli:
        cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
        entities = [dict(row) for row in cursor.fetchall()]
        
        # Collect any entities with a location_name
        entity_locations = [ent for ent in entities if ent["location_name"]]
        
        if entity_locations:
            for ent in entity_locations:
                geo = geocode_location(ent["location_name"])
                tit_loc_name = geo[2] if geo else ent["location_name"]
                coords = geo[:2] if geo else None
                tit_desc = f"{ent['normalized_name']} ({ent['normalized_role']})"
                
                # Avoid adding duplicate consecutive locations
                is_duplicate = False
                if travels:
                    last_travel = travels[-1]
                    if coords is not None and last_travel["coords"] is not None:
                        is_duplicate = (last_travel["coords"] == coords)
                    else:
                        is_duplicate = (last_travel["name"].lower() == tit_loc_name.lower())
                        
                if not is_duplicate:
                    travels.append({
                        "step": step,
                        "type": "stop",
                        "name": tit_loc_name,
                        "coords": coords,
                        "description": f"Visited: {tit_desc}"
                    })
                    step += 1
        else:
            tit_geo = None
            tit_loc_name = ""
            tit_desc = ""
            
            # Check titulus title for a geocodable word
            for word in re.findall(r'\b[A-Za-zÀ-ÿ\-]+\b', tit["title"]):
                geo = geocode_location(word)
                if geo:
                    tit_geo = geo
                    tit_loc_name = geo[2]
                    tit_desc = tit["title"]
                    break
                    
            # Fall back to any non-common capitalized words in titulus title
            if not tit_geo:
                words = re.findall(r'\b[A-Z][a-zA-ZÀ-ÿ\-]+\b', tit["title"])
                exclude = {
                    "T", "S", "Sancti", "Sancte", "Sanctorum", "Sanctique", "Sanctus", "Sanctis",
                    "Anima", "Amen", "Orate", "Oravimus", "Abbas", "Abbatis", "Titulus", "Implicit",
                    "Deus", "Domini", "Domino", "Dominus", "Christo", "Christi", "Maria", "Marie",
                    "Petri", "Martyris", "Apostolorum", "Pauli", "Johannis", "Trinitatis", "Ecclesie",
                    "Monasterii", "Cenobii", "Cujus", "Vitalis", "Vitali", "Hospitalitatis",
                    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"
                }
                exclude_lower = {e.lower() for e in exclude}
                filtered = [w for w in words if w.lower() not in exclude_lower]
                if filtered:
                    tit_loc_name = filtered[0]
                    tit_desc = tit["title"]
                    
            if tit_geo or tit_loc_name:
                coords = tit_geo[:2] if tit_geo else None
                
                is_duplicate = False
                if travels:
                    last_travel = travels[-1]
                    if coords is not None and last_travel["coords"] is not None:
                        is_duplicate = (last_travel["coords"] == coords)
                    else:
                        is_duplicate = (last_travel["name"].lower() == tit_loc_name.lower())
                        
                if not is_duplicate:
                    travels.append({
                        "step": step,
                        "type": "stop",
                        "name": tit_loc_name,
                        "coords": coords,
                        "description": f"Visited: {tit_desc}"
                    })
                    step += 1
                    
    conn.close()
    return travels

@app.get("/api/travels")
def get_all_travels():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, roll_num, title, date_str FROM rolls ORDER BY id")
    rolls = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    all_travels = {}
    for r in rolls:
        travels = get_roll_travels(r["id"])
        if travels:
            all_travels[r["id"]] = {
                "roll_num": r["roll_num"],
                "title": r["title"],
                "date_str": r["date_str"],
                "travels": travels
            }
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
        w, h = img.size
        
        if w > h:
            if half == "left":
                cropped = img.crop((0, 0, w // 2 + 30, h))
            elif half == "right":
                cropped = img.crop((w // 2 - 30, 0, w, h))
            else:
                cropped = img
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
