import os
import re
import json
import time
from datetime import datetime, timedelta
import requests

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
OUTPUT_FILE = "media_openings.json"
PAGES_TO_SCAN = 10  # 20 títulos por página = 200 títulos por categoría

# Listas negras de control
BLACKLIST_STANDARD = re.compile(
    r"\b(karaoke|8-bit|8 bit|lullaby|cover|tribute|ringtone|remix|instrumental version|piano version|interview|dialogue|commentary)\b",
    re.IGNORECASE,
)
TV_ENDING_BLACKLIST = re.compile(
    r"\b(end title|end credits|ending|closing|outro|créditos finales|creditos finales|ed\s?1|ed1)\b",
    re.IGNORECASE,
)

# Bloqueo de temporadas o secuelas posteriores
LATER_SEASONS_REGEX = re.compile(
    r"\b(season\s?([2-9]|[1-9]\d)|s0?([2-9]|[1-9]\d)|([2-9]|[1-9]\d)(nd|rd|th)\s?season|temporada\s?([2-9]|[1-9]\d)|op\s?([2-9]|[1-9]\d)|opening\s?([2-9]|[1-9]\d)|part\s?([2-9])|part\s?(ii|iii|iv|v)|vol\.?\s?([2-9])|chapter\s?([2-9]))\b",
    re.IGNORECASE,
)

# Palabras clave positivas por formato
TV_KEYWORDS_REGEX = re.compile(
    r"\b(main title|main titles|main theme|opening|intro|theme from|cabecera|sintonía|sintonia|tema principal|op\s?1|op1)\b",
    re.IGNORECASE,
)
MOVIE_KEYWORDS_REGEX = re.compile(
    r"\b(main title|main titles|main theme|theme from|suite|overture|end credits|end titles|tema principal|títulos de crédito|titulos de credito|opening)\b",
    re.IGNORECASE,
)

# Palabras de control para evitar falsos positivos en títulos de una sola palabra
SOUNDTRACK_ALBUM_REGEX = re.compile(
    r"\b(soundtrack|score|original|bso|banda sonora|television|motion picture|season|ost)\b",
    re.IGNORECASE,
)

def load_existing_catalog():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("tv", {})
            data.setdefault("movies", {})
            return data
    return {"version": 0, "tv": {}, "movies": {}}

def get_tmdb_details(media_type, item_id):
    url = f"https://api.themoviedb.org/3/{media_type}/{item_id}"
    try:
        r = requests.get(url, params={"api_key": TMDB_API_KEY, "language": "en-US"}, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
    except requests.exceptions.RequestException:
        return None

    cred_url = (
        f"https://api.themoviedb.org/3/tv/{item_id}/season/1/credits"
        if media_type == "tv"
        else f"https://api.themoviedb.org/3/movie/{item_id}/credits"
    )
    
    composers = []
    top_cast = []
    try:
        cred_r = requests.get(cred_url, params={"api_key": TMDB_API_KEY}, timeout=10)
        if cred_r.status_code == 200:
            cred_json = cred_r.json()
            crew = cred_json.get("crew", [])
            composers = [c["name"] for c in crew if c.get("job") == "Original Music Composer"][:3]
            top_cast = [c["name"] for c in cred_json.get("cast", [])[:2]]
    except requests.exceptions.RequestException:
        pass

    return {
        "id": item_id,
        "media_type": media_type,
        "original_name": data.get("original_name") or data.get("original_title", ""),
        "english_name": data.get("name") or data.
