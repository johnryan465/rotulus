import os
import sqlite3
import json
import re
import sys
import shutil

DB_PATH = "rolls.db"
OUTPUT_DIR = "public/api"

GEOLOCATIONS = {
    "montecassino": [41.4900, 13.8140, "Montecassino, Italy", False],
    "mainz": [50.0000, 8.2667, "Mainz, Germany", False],
    "maguntiaci": [50.0000, 8.2667, "Mainz, Germany", False],
    "fulda": [50.5528, 9.6775, "Fulda, Germany", False],
    "st. gallen": [47.4239, 9.3747, "St. Gallen, Switzerland", False],
    "sanctigallensis": [47.4239, 9.3747, "St. Gallen, Switzerland", False],
    "cluny": [46.4351, 4.6592, "Cluny, France", False],
    "cluniacensis": [46.4351, 4.6592, "Cluny, France", False],
    "fleury": [47.8100, 2.3050, "Fleury / Saint-Benoît-sur-Loire, France", False],
    "floriacensis": [47.8100, 2.3050, "Fleury / Saint-Benoît-sur-Loire, France", False],
    "st. denis": [48.9356, 2.3539, "Saint-Denis, France", False],
    "dionysii": [48.9356, 2.3539, "Saint-Denis, France", False],
    "marmoutier": [47.4022, 0.7033, "Marmoutier, Tours, France", False],
    "majoris monasterii": [47.4022, 0.7033, "Marmoutier, Tours, France", False],
    "st. remi": [49.2431, 4.0417, "Saint-Remi, Reims, France", False],
    "remigii": [49.2431, 4.0417, "Saint-Remi, Reims, France", False],
    "corbie": [49.9089, 2.5117, "Corbie, France", False],
    "corbeiensis": [49.9089, 2.5117, "Corbie, France", False],
    "ripoll": [42.1997, 2.1911, "Ripoll, Spain", False],
    "rivipollentis": [42.1997, 2.1911, "Ripoll, Spain", False],
    "st. michel": [48.6361, -1.5114, "Mont-Saint-Michel, France", False],
    "michel": [48.6361, -1.5114, "Mont-Saint-Michel, France", False],
    "canigou": [42.5850, 2.4567, "Saint-Martin-du-Canigou, France", False],
    "canigonensis": [42.5850, 2.4567, "Saint-Martin-du-Canigou, France", False],
    "cuxà": [42.5958, 2.4178, "Saint-Michel-de-Cuxà, France", False],
    "besalú": [42.1994, 2.6967, "Besalú, Spain", False],
    "bisuldunensis": [42.1994, 2.6967, "Besalú, Spain", False],
    "girona": [41.9833, 2.8233, "Girona, Spain", False],
    "gerundensis": [41.9833, 2.8233, "Girona, Spain", False],
    "vic": [41.9300, 2.2544, "Vic, Spain", False],
    "ausonensis": [41.9300, 2.2544, "Vic, Spain", False],
    "barcelona": [41.3833, 2.1833, "Barcelona, Spain", False],
    "barcinonensis": [41.3833, 2.1833, "Barcelona, Spain", False],
    "narbonne": [43.1833, 3.0000, "Narbonne, France", False],
    "narbonensis": [43.1833, 3.0000, "Narbonne, France", False],
    "arles-sur-tech": [42.4564, 2.6347, "Arles-sur-Tech, France", False],
    "arulensis": [42.4564, 2.6347, "Arles-sur-Tech, France", False],
    "elne": [42.6000, 2.9714, "Elne, France", False],
    "elenensis": [42.6000, 2.9714, "Elne, France", False],
    "carcassonne": [43.2167, 2.3500, "Carcassonne, France", False],
    "carcassonensis": [43.2167, 2.3500, "Carcassonne, France", False],
    "beziers": [43.3444, 3.2158, "Béziers, France", False],
    "biterris": [43.3444, 3.2158, "Béziers, France", False],
    "agde": [43.3108, 3.4758, "Agde, France", False],
    "agathensis": [43.3108, 3.4758, "Agde, France", False],
    "maguelone": [43.5119, 3.8831, "Maguelone, France", False],
    "magalonensis": [43.5119, 3.8831, "Maguelone, France", False],
    "nîmes": [43.8333, 4.3500, "Nîmes, France", False],
    "nemausensis": [43.8333, 4.3500, "Nîmes, France", False],
    "uzès": [44.0122, 4.4194, "Uzès, France", False],
    "viviensis": [44.4819, 4.6889, "Viviers, France", False],
    "valence": [44.9333, 4.8917, "Valence, France", False],
    "valentia": [44.9333, 4.8917, "Valence, France", False],
    "vienne": [45.5244, 4.8761, "Vienne, France", False],
    "viennensis": [45.5244, 4.8761, "Vienne, France", False],
    "lyon": [45.7597, 4.8422, "Lyon, France", False],
    "lugdunensis": [45.7597, 4.8422, "Lyon, France", False],
    "macon": [46.3000, 4.8333, "Mâcon, France", False],
    "matiscensis": [46.3000, 4.8333, "Mâcon, France", False],
    "chalon": [46.7833, 4.8500, "Chalon-sur-Saône, France", False],
    "cabillonensis": [46.7833, 4.8500, "Chalon-sur-Saône, France", False],
    "dijon": [47.3167, 5.0167, "Dijon, France", False],
    "divionensis": [47.3167, 5.0167, "Dijon, France", False],
    "langres": [47.8667, 5.3333, "Langres, France", False],
    "lingonensis": [47.8667, 5.3333, "Langres, France", False],
    "troyes": [48.3000, 4.0833, "Troyes, France", False],
    "trecas": [48.3000, 4.0833, "Troyes, France", False],
    "sens": [48.2000, 3.2833, "Sens, France", False],
    "senonensis": [48.2000, 3.2833, "Sens, France", False],
    "auxerre": [47.8000, 3.5667, "Auxerre, France", False],
    "autissiodorensis": [47.8000, 3.5667, "Auxerre, France", False],
    "nevers": [46.9936, 3.1592, "Nevers, France", False],
    "nivernensis": [46.9936, 3.1592, "Nevers, France", False],
    "bourges": [47.0833, 2.4000, "Bourges, France", False],
    "bituricensis": [47.0833, 2.4000, "Bourges, France", False],
    "tours": [47.3833, 0.6833, "Tours, France", False],
    "turonensis": [47.3833, 0.6833, "Tours, France", False],
    "angers": [47.4736, -0.5542, "Angers, France", False],
    "andecavensis": [47.4736, -0.5542, "Angers, France", False],
    "le mans": [48.0000, 0.2000, "Le Mans, France", False],
    "cenomanensis": [48.0000, 0.2000, "Le Mans, France", False],
    "chartres": [48.4472, 1.4875, "Chartres, France", False],
    "carnotensis": [48.4472, 1.4875, "Chartres, France", False],
    "orléans": [47.9025, 1.9090, "Orléans, France", False],
    "aurelianensis": [47.9025, 1.9090, "Orléans, France", False],
    "paris": [48.8566, 2.3522, "Paris, France", False],
    "parisiensis": [48.8566, 2.3522, "Paris, France", False],
    "meaux": [48.9500, 2.9000, "Meaux, France", False],
    "meldis": [48.9500, 2.9000, "Meaux, France", False],
    "beauvais": [49.4333, 2.0833, "Beauvais, France", False],
    "bellovacensis": [49.4333, 2.0833, "Beauvais, France", False],
    "amiens": [49.8944, 2.2958, "Amiens, France", False],
    "ambianensis": [49.8944, 2.2958, "Amiens, France", False],
    "laon": [49.5667, 3.6167, "Laon, France", False],
    "laudunensis": [49.5667, 3.6167, "Laon, France", False],
    "reims": [49.2500, 4.0333, "Reims, France", False],
    "remensis": [49.2500, 4.0333, "Reims, France", False],
    "châlons": [48.9539, 4.3644, "Châlons-en-Champagne, France", False],
    "catalaunensis": [48.9539, 4.3644, "Châlons-en-Champagne, France", False],
    "verdun": [49.1603, 5.3811, "Verdun, France", False],
    "virdunensis": [49.1603, 5.3811, "Verdun, France", False],
    "metz": [49.1203, 6.1778, "Metz, France", False],
    "mettensis": [49.1203, 6.1778, "Metz, France", False],
    "toul": [48.6750, 5.8917, "Toul, France", False],
    "tullensis": [48.6750, 5.8917, "Toul, France", False],
    "trier": [49.7590, 6.6440, "Trier, Germany", False],
    "trèves": [49.7590, 6.6440, "Trier, Germany", False],
    "worms": [49.6340, 8.3580, "Worms, Germany", False],
    "spire": [49.3170, 8.4390, "Speyer, Germany", False],
    "strasbourg": [48.5730, 7.7520, "Strasbourg, France", False],
    "bâle": [47.5596, 7.5886, "Basel, Switzerland", False],
    "genève": [46.2044, 6.1432, "Geneva, Switzerland", False],
    "lausanne": [46.5197, 6.6323, "Lausanne, Switzerland", False],
    "sion": [46.2330, 7.3600, "Sion, Switzerland", False],
    "aoste": [45.7370, 7.3200, "Aosta, Italy", False],
    "turin": [45.0703, 7.6869, "Turin, Italy", False],
    "milan": [45.4642, 9.1900, "Milan, Italy", False],
    "pavie": [45.1850, 9.1550, "Pavia, Italy", False],
    "gênes": [44.4056, 8.9463, "Genoa, Italy", False],
    "lucques": [43.8429, 10.5027, "Lucca, Italy", False],
    "pise": [43.7228, 10.4017, "Pisa, Italy", False],
    "florence": [43.7696, 11.2558, "Florence, Italy", False],
    "rome": [41.9028, 12.4964, "Rome, Italy", False],
    "naples": [40.8518, 14.2681, "Naples, Italy", False],
    "messine": [38.1939, 15.5552, "Messina, Italy", False],
    "palerme": [38.1157, 13.3615, "Palermo, Italy", False],
}

ROMAN_CENTURIES = {'VII': 650, 'VIII': 750, 'IX': 850, 'X': 950, 'XI': 1050, 'XII': 1150, 'XIII': 1250, 'XIV': 1350, 'XV': 1450, 'XVI': 1550}

def extract_year(date_str):
    if not date_str: return None
    years = re.findall(r'\b(5\d{2}|[6-9]\d{2}|1\d{3})\b', date_str)
    if years: return int(years[0])
    for rom, yr in ROMAN_CENTURIES.items():
        if f"{rom}'" in date_str or f"{rom}\"" in date_str or f"{rom} " in date_str: return yr
    return None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; return conn

def geocode_location(name):
    if not name: return None
    s = name.strip().lower()
    if s in GEOLOCATIONS: return GEOLOCATIONS[s]
    for key, val in GEOLOCATIONS.items():
        if key in s or s in key: return val
    return None

def get_roll_travels(conn, db_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rolls WHERE id = ?", (db_id,))
    row = cursor.fetchone()
    if not row: return []
    roll = dict(row); roll_year = extract_year(roll["date_str"])
    travels = []
    
    # Origin logic
    origin_geo = None; origin_name = "Origin"
    for word in re.findall(r'\b[A-Za-zÀ-ÿ\-]{3,}\b', roll["title"] + " " + roll["manuscripts"]):
        geo = geocode_location(word)
        if geo: origin_geo = geo; origin_name = geo[2]; break
    if origin_geo:
        travels.append({"step": 0, "type": "origin", "name": origin_name, "coords": origin_geo[:2], "year": roll_year, "date_str": roll["date_str"], "is_approximate": origin_geo[3], "description": f"Origin: {roll['title'][:50]}..."})

    cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (db_id,))
    tituli = [dict(r) for r in cursor.fetchall()]
    step = len(travels)
    for tit in tituli:
        loc_str = tit.get("location_name")
        if not loc_str: continue
        geo = geocode_location(loc_str)
        if geo: loc_name = geo[2]; coords = geo[:2]; approx = geo[3]
        else: loc_name = loc_str.strip(); coords = None; approx = True
        is_dup = False
        if travels:
            last = travels[-1]
            is_dup = (last["coords"] == coords) if coords and last["coords"] else (last["name"].lower() == loc_name.lower())
        if not is_dup:
            travels.append({"step": step, "type": "stop", "name": loc_name, "coords": coords, "year": roll_year, "date_str": roll["date_str"], "is_approximate": approx, "description": f"Titulus Header: {loc_str}"})
            step += 1
    return travels

def export_data():
    conn = get_db_connection(); cursor = conn.cursor()
    if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR); roll_dir = os.path.join(OUTPUT_DIR, "rolls"); os.makedirs(roll_dir, exist_ok=True)
    
    cursor.execute("SELECT * FROM rolls ORDER BY CAST(roll_num AS INTEGER)")
    rolls = [dict(row) for row in cursor.fetchall()]
    all_travels = {}; rolls_with_stops = []

    for roll in rolls:
        db_id = roll['id']; r_num = roll['roll_num']
        cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (db_id,))
        tituli = [dict(row) for row in cursor.fetchall()]
        for tit in tituli:
            cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
            tit["entities"] = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM footnotes WHERE roll_id = ? ORDER BY pdf_page, pdf_half, CAST(footnote_num AS INTEGER)", (db_id,))
        detail = {"roll": roll, "tituli": tituli, "footnotes": [dict(row) for row in cursor.fetchall()]}
        
        # KEY CHANGE: Filename is now roll_num
        with open(os.path.join(roll_dir, f"{r_num}.json"), "w") as f: json.dump(detail, f, indent=2)

        travels = get_roll_travels(conn, db_id)
        num_stops = len([t for t in travels if t['type'] == 'stop'])
        year = extract_year(roll["date_str"])
        
        # KEY CHANGE: Key is now roll_num
        all_travels[r_num] = {"id": r_num, "roll_num": r_num, "title": roll["title"], "date_str": roll["date_str"], "year": year, "travels": travels, "num_stops": num_stops, "manuscripts": roll["manuscripts"]}
        
        roll_dict = dict(roll); roll_dict["num_stops"] = num_stops; roll_dict["year"] = year
        rolls_with_stops.append(roll_dict)

    with open(os.path.join(OUTPUT_DIR, "rolls.json"), "w") as f: json.dump(rolls_with_stops, f, indent=2)
    with open(os.path.join(OUTPUT_DIR, "travels.json"), "w") as f: json.dump(all_travels, f, indent=2)
    
    conn.close(); print(f"✅ Database exported to static JSON using ROLL_NUM as keys.")

if __name__ == "__main__":
    export_data()
