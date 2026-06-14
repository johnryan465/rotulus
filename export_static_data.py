import os
import json
import sqlite3
import shutil
import re
import sys

DB_PATH = "rolls.db"
OUTPUT_DIR = "public/api"

# Format: "key": [lat, lon, "Display Name", is_approximate]
GEOLOCATIONS = {
    # Existing Precise
    "gent": [51.0543, 3.7174, "Ghent, Belgium", False],
    "ghent": [51.0543, 3.7174, "Ghent, Belgium", False],
    "vatican": [41.9022, 12.4539, "Vatican City", False],
    "vaticano": [41.9022, 12.4539, "Vatican City", False],
    "wimborne": [50.8010, -1.9830, "Wimborne Minster, England", False],
    "fulda": [50.5528, 9.6775, "Fulda Abbey, Germany", False],
    "luxeuil": [47.8178, 6.3117, "Luxeuil Abbey, France", False],
    "st. gall": [47.4245, 9.3767, "Abbey of Saint Gall, Switzerland", False],
    "sankt gallen": [47.4245, 9.3767, "Abbey of Saint Gall, Switzerland", False],
    "attigny": [49.4719, 4.5778, "Attigny, France", False],
    "dingolfing": [48.6293, 12.4984, "Dingolfing, Germany", False],
    "wien": [48.2082, 16.3738, "Vienna, Austria", False],
    "vienna": [48.2082, 16.3738, "Vienna, Austria", False],
    "karlsruhe": [49.0069, 8.4037, "Karlsruhe, Germany", False],
    "rastatt": [48.8573, 8.2030, "Rastatt, Germany", False],
    "montecassino": [41.4901, 13.8143, "Montecassino Abbey, Italy", False],
    "mont cassin": [41.4901, 13.8143, "Montecassino Abbey, Italy", False],
    "mainz": [49.9929, 8.2473, "Mainz, Germany", False],
    "mayence": [49.9929, 8.2473, "Mainz, Germany", False],
    "glastonbury": [51.1473, -2.7186, "Glastonbury, England", False],
    "jumièges": [49.4326, 0.8211, "Jumièges Abbey, France", False],
    "jumieges": [49.4326, 0.8211, "Jumièges Abbey, France", False],
    "flavigny": [47.5126, 4.5312, "Flavigny Abbey, France", False],
    "novalesa": [45.1897, 7.0142, "Novalesa Abbey, Italy", False],
    "rebais": [48.8471, 3.2323, "Rebais Abbey, France", False],
    "saint-wandrille": [49.5297, 0.7225, "Saint-Wandrille Abbey, France", False],
    "wandrille": [49.5297, 0.7225, "Saint-Wandrille Abbey, France", False],
    "corbie": [49.9085, 2.5089, "Corbie Abbey, France", False],
    "niederaltaich": [48.7663, 13.0274, "Niederaltaich Abbey, Germany", False],
    "altaich": [48.7663, 13.0274, "Niederaltaich Abbey, Germany", False],
    "reichenau": [47.6994, 9.0601, "Reichenau Abbey, Germany", False],
    "salzburg": [47.8095, 13.0550, "Salzburg, Austria", False],
    "salzbourg": [47.8095, 13.0550, "Salzburg, Austria", False],
    "saint-denis": [48.9358, 2.3598, "Saint-Denis Abbey, France", False],
    "denis": [48.9358, 2.3598, "Saint-Denis Abbey, France", False],
    "saint-germain": [48.8542, 2.3332, "Saint-Germain-des-Prés, France", False],
    "germain": [48.8542, 2.3332, "Saint-Germain-des-Prés, France", False],
    "saint-maurice": [46.2163, 7.0033, "Saint-Maurice Abbey, Switzerland", False],
    "maurice": [46.2163, 7.0033, "Saint-Maurice Abbey, Switzerland", False],
    "agaune": [46.2163, 7.0033, "Saint-Maurice Abbey, Switzerland", False],
    "verdun": [49.1599, 5.3855, "Verdun, France", False],
    "besançon": [47.2378, 6.0241, "Besançon, France", False],
    "besancon": [47.2378, 6.0241, "Besançon, France", False],
    "moosburg": [48.4682, 11.9360, "Moosburg, Germany", False],
    "mondsee": [47.8566, 13.3516, "Mondsee Abbey, Austria", False],
    "tegernsee": [47.7081, 11.7584, "Tegernsee Abbey, Germany", False],
    "metten": [48.8576, 12.9133, "Metten Abbey, Germany", False],
    "benediktbeuern": [47.7082, 11.4116, "Benediktbeuern Abbey, Germany", False],
    "weltenburg": [48.8967, 11.8203, "Weltenburg Abbey, Germany", False],
    "saint-cloud": [48.8413, 2.2185, "Saint-Cloud Abbey, France", False],
    "cloud": [48.8413, 2.2185, "Saint-Cloud Abbey, France", False],
    "eichstätt": [48.8920, 11.1830, "Eichstätt, Germany", False],
    "eichstatt": [48.8920, 11.1830, "Eichstätt, Germany", False],
    "würzburg": [49.7913, 9.9534, "Würzburg, Germany", False],
    "wurzburg": [49.7913, 9.9534, "Würzburg, Germany", False],
    "noyon": [49.5807, 2.9995, "Noyon, France", False],
    "murbach": [47.9234, 7.1581, "Murbach Abbey, France", False],
    "bayeux": [49.2794, -0.7028, "Bayeux, France", False],
    "tours": [47.3941, 0.6848, "Tours, France", False],
    "chur": [46.8508, 9.5320, "Chur, Switzerland", False],
    "coire": [46.8508, 9.5320, "Chur, Switzerland", False],
    "angers": [47.4784, -0.5635, "Angers, France", False],
    "winchester": [51.0632, -1.3080, "Winchester, England", False],
    "saint-riquier": [50.1347, 1.9472, "Saint-Riquier Abbey, France", False],
    "centula": [50.1347, 1.9472, "Saint-Riquier Abbey, France", False],
    "riquier": [50.1347, 1.9472, "Saint-Riquier Abbey, France", False],
    "pfifers": [46.9934, 9.5028, "Pfäfers Abbey, Switzerland", False],
    "pfäfers": [46.9934, 9.5028, "Pfäfers Abbey, Switzerland", False],
    "nesle": [48.7619, 3.5683, "Nesle-la-Reposte, France", False],
    "saint-evroult": [48.7903, 0.4627, "Saint-Evroult Abbey, France", False],
    "evroult": [48.7903, 0.4627, "Saint-Evroult Abbey, France", False],
    "scharnitz": [47.3889, 11.2642, "Scharnitz Abbey, Austria", False],
    "isen": [48.2124, 12.0628, "Isen Abbey, Germany", False],
    "oberaltaich": [48.9132, 12.6775, "Oberaltaich Abbey, Germany", False],
    "berg": [48.9868, 12.0833, "Berg im Donaugau, Germany", False],
    "schliersee": [47.7247, 11.8615, "Schliersee, Germany", False],
    "hautvillers": [49.0817, 3.9383, "Abbey of Hautvillers, France", False],
    "rochester": [51.3900, 0.5050, "Rochester, England", False],
    "anchinl": [50.3854, 3.2323, "Anchin Abbey, France", False],
    "chalon": [46.7833, 4.8500, "Chalon-sur-Saône, France", False],
    "nantcuil": [46.0022, 0.2818, "Nanteuil-en-Vallée Abbey, France", False],
    "clermont": [45.7772, 3.0870, "Clermont-Ferrand, France", False],
    "sever": [43.7600, -0.5739, "Saint-Sever Abbey, France", False],
    "toulouse": [43.6047, 1.4442, "Toulouse, France", False],
    "tourtoirac": [45.2706, 1.0594, "Tourtoirac Abbey, France", False],
    "brioude": [45.2933, 3.3847, "Brioude Abbey, France", False],
    "fleury": [47.8093, 2.3053, "Fleury Abbey, France", False],
    "redon": [47.6534, -2.0850, "Redon Abbey, France", False],
    "tournus": [46.5647, 4.9111, "Tournus Abbey, France", False],
    "laon": [49.5642, 3.6199, "Laon, France", False],
    "poitiers": [46.5802, 0.3404, "Poitiers, France", False],
    "montierneuf": [46.5802, 0.3404, "Montierneuf Abbey, France", False],
    "reims": [49.2583, 4.0317, "Reims, France", False],
    "paris": [48.8566, 2.3522, "Paris, France", False],
    "limoges": [45.8336, 1.2611, "Limoges, France", False],
    "ripoll": [42.2014, 2.1901, "Santa Maria de Ripoll, Spain", False],
    "lobbes": [50.3481, 4.2611, "Lobbes Abbey, Belgium", False],
    "cluny": [46.4350, 4.6583, "Cluny Abbey, France", False],
    "cîteaux": [47.1294, 5.0889, "Cîteaux Abbey, France", False],
    "clairvaux": [48.1469, 4.6500, "Clairvaux Abbey, France", False],
    "bec": [49.2294, 0.7208, "Bec Abbey, France", False],
    "fécamp": [49.7589, 0.3800, "Fécamp Abbey, France", False],
    "caen": [49.1829, -0.3707, "Caen, France", False],
    "rouen": [49.4431, 1.0992, "Rouen, France", False],
    "chartres": [48.4472, 1.4877, "Chartres, France", False],
    "orléans": [47.9030, 1.9090, "Orléans, France", False],
    "bourges": [47.0810, 2.3980, "Bourges, France", False],
    "sens": [48.1970, 3.2840, "Sens, France", False],
    "auxerre": [47.7980, 3.5730, "Auxerre, France", False],
    "troyes": [48.2970, 4.0740, "Troyes, France", False],
    "langres": [47.8630, 5.3330, "Langres, France", False],
    "metz": [49.1190, 6.1750, "Metz, France", False],
    "toul": [48.6750, 5.8910, "Toul, France", False],
    "liège": [50.6330, 5.5670, "Liège, Belgium", False],
    "utrecht": [52.0907, 5.1214, "Utrecht, Netherlands", False],
    "cologne": [50.9375, 6.9603, "Cologne, Germany", False],
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

    # Regional / Approximate
    "anglia": [52.5000, 1.0000, "East Anglia, England", True],
    "northumbrie": [55.1000, -2.0000, "Northumbria, England", True],
    "northumbria": [55.1000, -2.0000, "Northumbria, England", True],
    "bavaria": [48.7904, 11.4979, "Bavaria, Germany", True],
    "normandy": [49.1829, -0.3707, "Normandy, France", True],
    "normandie": [49.1829, -0.3707, "Normandy, France", True],
    "aquitaine": [44.8378, -0.5792, "Aquitaine, France", True],
    "france": [46.2276, 2.2137, "France (General)", True],
    "germany": [51.1657, 10.4515, "Germany (General)", True],
    "italy": [41.8719, 12.5674, "Italy (General)", True],
    "gallia": [46.2276, 2.2137, "Gaul / France", True],
    "bretagne": [48.2020, -2.9326, "Brittany, France", True],
    "bourgogne": [47.2805, 4.4126, "Burgundy, France", True],
    "provence": [43.9352, 6.0679, "Provence, France", True],
    "lombardie": [45.4791, 9.8452, "Lombardy, Italy", True],
    "toscane": [43.7711, 11.2486, "Tuscany, Italy", True],
    "sicile": [37.5990, 14.0154, "Sicily, Italy", True],
    "espagne": [40.4637, -3.7492, "Spain (General)", True],
    "hispania": [40.4637, -3.7492, "Hispania", True],
    "belgium": [50.5039, 4.4699, "Belgium (General)", True],
    "flandre": [51.0500, 3.7333, "Flanders", True],
}

ROMAN_CENTURIES = {
    'VII': 650, 'VIII': 750, 'IX': 850, 'X': 950, 'XI': 1050, 'XII': 1150, 'XIII': 1250, 'XIV': 1350, 'XV': 1450, 'XVI': 1550
}

def extract_year(date_str):
    if not date_str: return None
    years = re.findall(r'\b(5\d{2}|[6-9]\d{2}|1\d{3})\b', date_str)
    if years: return int(years[0])
    for rom, yr in ROMAN_CENTURIES.items():
        if f"{rom}'" in date_str or f"{rom}\"" in date_str or f"{rom} " in date_str:
            return yr
    return None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; return conn

def geocode_location(name):
    if not name: return None
    s = name.strip().lower()
    if s in GEOLOCATIONS: return GEOLOCATIONS[s]
    # Partial match
    for key, val in GEOLOCATIONS.items():
        if key in s or s in key: return val
    return None

def get_roll_travels(conn, roll_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rolls WHERE id = ?", (roll_id,))
    row = cursor.fetchone()
    if not row: return []
    roll = dict(row); roll_year = extract_year(roll["date_str"])
    
    origin_geo = None; origin_name = "Origin"
    for word in re.findall(r'\b[A-Za-zÀ-ÿ\-]{3,}\b', roll["title"] + " " + roll["manuscripts"]):
        geo = geocode_location(word)
        if geo: origin_geo = geo; origin_name = geo[2]; break
            
    travels = []
    if origin_geo:
        travels.append({
            "step": 0, "type": "origin", "name": origin_name, "coords": origin_geo[:2],
            "year": roll_year, "date_str": roll["date_str"], "is_approximate": origin_geo[3],
            "description": f"Origin: {roll['title'][:50]}..."
        })
    else:
        words = re.findall(r'\b[A-Z][a-zA-ZÀ-ÿ\-]+\b', roll["title"] + " " + roll["manuscripts"])
        exclude = {"T", "S", "Sancti", "Sancte", "Sanctorum", "Sanctique", "Sanctus", "Sanctis", "Anima", "Amen", "Orate", "Oravimus", "Abbas", "Abbatis", "Titulus", "Implicit", "Deus", "Domini", "Domino", "Dominus", "Christo", "Christi", "Maria", "Marie", "Petri", "Martyris", "Apostolorum", "Pauli", "Johannis", "Trinitatis", "Ecclesie", "Monasterii", "Cenobii", "Cujus", "Vitalis", "Vitali", "Hospitalitatis", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "Original", "Communication", "Wien", "Paris", "Bibliotheque", "Nationalbibl", "Briefe", "Brief", "EpP", "M", "G", "H", "R", "Rau", "Lul"}
        filtered = [w for w in words if w.lower() not in {e.lower() for e in exclude}]
        if filtered:
            travels.append({
                "step": 0, "type": "origin", "name": filtered[0], "coords": None,
                "year": roll_year, "date_str": roll["date_str"], "is_approximate": True,
                "description": f"Origin: {roll['title'][:50]}..."
            })
        
    cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (roll_id,))
    tituli = [dict(r) for r in cursor.fetchall()]
    
    step = len(travels)
    for tit in tituli:
        cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
        entities = [dict(r) for r in cursor.fetchall()]
        tit_year = roll_year; tit_date_str = roll["date_str"]
        for ent in entities:
            if ent["normalized_dates"]:
                ey = extract_year(ent["normalized_dates"])
                if ey: tit_year = ey; tit_date_str = ent["normalized_dates"]; break
        
        entity_locations = [ent for ent in entities if ent["location_name"]]
        if entity_locations:
            for ent in entity_locations:
                geo = geocode_location(ent["location_name"])
                loc_name = geo[2] if geo else ent["location_name"]
                coords = geo[:2] if geo else None
                approx = geo[3] if geo else True
                is_dup = False
                if travels:
                    last = travels[-1]
                    is_dup = (last["coords"] == coords) if coords and last["coords"] else (last["name"].lower() == loc_name.lower())
                if not is_dup:
                    travels.append({
                        "step": step, "type": "stop", "name": loc_name, "coords": coords,
                        "year": tit_year, "date_str": tit_date_str, "is_approximate": approx,
                        "description": f"Visited: {ent['normalized_name']} ({ent['normalized_role']})"
                    })
                    step += 1
        else:
            tit_geo = None; loc_name = ""
            for word in re.findall(r'\b[A-Za-zÀ-ÿ\-]+\b', tit["title"]):
                geo = geocode_location(word)
                if geo: tit_geo = geo; loc_name = geo[2]; break
            if not tit_geo:
                words = re.findall(r'\b[A-Z][a-zA-ZÀ-ÿ\-]+\b', tit["title"])
                exclude = {"T", "S", "Sancti", "Sancte", "Sanctorum", "Sanctique", "Sanctus", "Sanctis", "Anima", "Amen", "Orate", "Oravimus", "Abbas", "Abbatis", "Titulus", "Implicit", "Deus", "Domini", "Domino", "Dominus", "Christo", "Christi", "Maria", "Marie", "Petri", "Martyris", "Apostolorum", "Pauli", "Johannis", "Trinitatis", "Ecclesie", "Monasterii", "Cenobii", "Cujus", "Vitalis", "Vitali", "Hospitalitatis", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"}
                filtered = [w for w in words if w.lower() not in {e.lower() for e in exclude}]
                if filtered: loc_name = filtered[0]
            if tit_geo or loc_name:
                coords = tit_geo[:2] if tit_geo else None
                approx = tit_geo[3] if tit_geo else True
                is_dup = False
                if travels:
                    last = travels[-1]
                    is_dup = (last["coords"] == coords) if coords and last["coords"] else (last["name"].lower() == loc_name.lower())
                if not is_dup:
                    travels.append({
                        "step": step, "type": "stop", "name": loc_name, "coords": coords,
                        "year": tit_year, "date_str": tit_date_str, "is_approximate": approx,
                        "description": f"Visited: {tit['title']}"
                    })
                    step += 1
    return travels

def export_data():
    if not os.path.exists(DB_PATH): sys.exit(1)
    conn = get_db_connection(); cursor = conn.cursor()
    if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)
    
    cursor.execute("SELECT * FROM rolls ORDER BY id")
    rolls = [dict(row) for row in cursor.fetchall()]
    for r in rolls: r["year"] = extract_year(r["date_str"])
    with open(os.path.join(OUTPUT_DIR, "rolls.json"), "w") as f: json.dump(rolls, f, indent=2)

    roll_dir = os.path.join(OUTPUT_DIR, "rolls"); os.makedirs(roll_dir, exist_ok=True)
    all_travels = {}
    for roll in rolls:
        roll_id = roll['id']
        cursor.execute("SELECT * FROM tituli WHERE roll_id = ? ORDER BY id", (roll_id,))
        tituli = [dict(row) for row in cursor.fetchall()]
        for tit in tituli:
            cursor.execute("SELECT * FROM entities WHERE titulus_id = ? ORDER BY id", (tit["id"],))
            tit["entities"] = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT * FROM footnotes WHERE roll_id = ? ORDER BY pdf_page, pdf_half, CAST(footnote_num AS INTEGER)", (roll_id,))
        detail = {"roll": roll, "tituli": tituli, "footnotes": [dict(row) for row in cursor.fetchall()]}
        with open(os.path.join(roll_dir, f"{roll_id}.json"), "w") as f: json.dump(detail, f, indent=2)

        travels = get_roll_travels(conn, roll_id)
        if travels:
            roll_travel_dir = os.path.join(roll_dir, str(roll_id)); os.makedirs(roll_travel_dir, exist_ok=True)
            with open(os.path.join(roll_travel_dir, "travels.json"), "w") as f: json.dump(travels, f, indent=2)
            all_travels[roll_id] = {"roll_num": roll["roll_num"], "title": roll["title"], "date_str": roll["date_str"], "year": roll["year"], "travels": travels}

    with open(os.path.join(OUTPUT_DIR, "travels.json"), "w") as f: json.dump(all_travels, f, indent=2)
    conn.close(); print(f"✅ Database exported to static JSON in {OUTPUT_DIR}")

if __name__ == "__main__":
    export_data()
