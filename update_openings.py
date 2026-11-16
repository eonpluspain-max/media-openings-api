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
    r = requests.get(url, params={"api_key": TMDB_API_KEY, "language": "en-US"}, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()

    cred_url = (
        f"https://api.themoviedb.org/3/tv/{item_id}/season/1/credits"
        if media_type == "tv"
        else f"https://api.themoviedb.org/3/movie/{item_id}/credits"
    )
    cred_r = requests.get(cred_url, params={"api_key": TMDB_API_KEY}, timeout=10)

    composers = []
    top_cast = []
    if cred_r.status_code == 200:
        cred_json = cred_r.json()
        crew = cred_json.get("crew", [])
        composers = [c["name"] for c in crew if c.get("job") == "Original Music Composer"][:3]
        top_cast = [c["name"] for c in cred_json.get("cast", [])[:2]]

    return {
        "id": item_id,
        "media_type": media_type,
        "original_name": data.get("original_name") or data.get("original_title", ""),
        "english_name": data.get("name") or data.get("title", ""),
        "release_date": data.get("first_air_date") or data.get("release_date", ""),
        "origin_countries": data.get("origin_country") or [c["iso_3166_1"] for c in data.get("production_countries", [])],
        "genre_ids": [g["id"] for g in data.get("genres", [])],
        "composers": composers,
        "top_cast": top_cast,
    }

def generate_search_titles(media):
    """Genera variantes limpias del título (maneja subtítulos separados por ':' o '-')"""
    raw_titles = [media["original_name"], media["english_name"]]
    expanded = set()
    for t in raw_titles:
        if not t:
            continue
        expanded.add(t.strip())
        for sep in [":", " - ", " – "]:
            if sep in t:
                parts = [p.strip() for p in t.split(sep) if len(p.strip()) >= 3]
                expanded.update(parts)
    return list(expanded)

def search_deezer(query, limit=15):
    time.sleep(0.15)
    r = requests.get("https://api.deezer.com/search", params={"q": query, "limit": limit}, timeout=10)
    if r.status_code == 200:
        return r.json().get("data", [])
    return []

def get_deezer_track_details(track_id):
    time.sleep(0.15)
    r = requests.get(f"https://api.deezer.com/track/{track_id}", timeout=10)
    if r.status_code == 200 and "error" not in r.json():
        return r.json()
    return None

def strip_own_title(text, titles):
    res = text.lower()
    for name in titles:
        if name:
            res = res.replace(name.lower(), "")
    return res

def calculate_score(track, media, search_titles):
    score = 10
    title = track.get("title", "")
    title_lower = title.lower()
    album_title = track.get("album", {}).get("title", "")
    album_lower = album_title.lower()
    artist_lower = track.get("artist", {}).get("name", "").lower()

    is_tv = media["media_type"] == "tv"
    is_anime = is_tv and "JP" in media["origin_countries"] and 16 in media["genre_ids"]
    is_music_doc = 10402 in media["genre_ids"]
    duration = track.get("duration", 0)

    # 1. Control de duración
    if is_anime and not (75 <= duration <= 300):
        return -1
    elif is_tv and not is_anime and not (30 <= duration <= 240):
        return -1
    elif not is_tv and not (45 <= duration <= 420):
        return -1

    # 2. Validación de Compositor o Artista Protagonista
    matches_composer = any(c.lower() in artist_lower for c in media["composers"])
    matches_music_artist = is_music_doc and any(a.lower() in artist_lower for a in media["top_cast"])

    if matches_composer or matches_music_artist:
        score += 35

    # 3. Protección contra títulos genéricos de 1 palabra
    primary_title = media["english_name"] or media["original_name"]
    is_short_generic = len(primary_title.split()) == 1 or len(primary_title) < 5
    has_soundtrack_tag = bool(SOUNDTRACK_ALBUM_REGEX.search(album_title) or SOUNDTRACK_ALBUM_REGEX.search(title))

    if is_short_generic and not (matches_composer or matches_music_artist) and not has_soundtrack_tag:
        return -1

    # 4. Palabras clave y coincidencia de título
    keywords_regex = TV_KEYWORDS_REGEX if is_tv else MOVIE_KEYWORDS_REGEX
    has_keyword = bool(keywords_regex.search(title))
    names_lower = [t.lower() for t in search_titles]
    matches_exact_title = any(title_lower == n or title_lower.startswith(f"{n} (") for n in names_lower)

    if has_keyword:
        score += 25
    elif matches_exact_title:
        score += 20

    # 5. Validación de año de estreno (Flexible para clásicos / antiguos anteriores a 2005)
    release_date = track.get("album", {}).get("release_date", "")
    media_year = int(media["release_date"][:4]) if len(media["release_date"]) >= 4 else None
    rel_year = int(release_date[:4]) if len(release_date) >= 4 else None

    if media_year and rel_year:
        if media_year >= 2005:
            if (media_year - 1) <= rel_year <= (media_year + 1):
                score += 50
            elif not matches_composer and not matches_music_artist and not has_keyword:
                score -= 45
        else:
            if rel_year >= media_year:
                score += 20

    # 6. Bonus de álbum/single oficial, K-Dramas y pista 1
    if any(n in album_lower or n in title_lower for n in names_lower):
        score += 10
    if is_tv and "KR" in media["origin_countries"] and re.search(r"\bost\s?part\.?\s?1\b", album_lower):
        score += 20
    if track.get("track_position") == 1:
        score += 15

    return score

def find_best_audio(media):
    candidates = {}
    titles = generate_search_titles(media)
    is_tv = media["media_type"] == "tv"
    is_anime = is_tv and "JP" in media["origin_countries"] and 16 in media["genre_ids"]
    is_music_doc = 10402 in media["genre_ids"]

    # Nivel 1A: Conciertos / Documentales Musicales
    if is_music_doc and media["top_cast"]:
        for lead_artist in media["top_cast"]:
            for t in titles:
                for item in search_deezer(f'artist:"{lead_artist}" "{t}"', 10):
                    candidates[item["id"]] = item
        if not candidates:
            for lead_artist in media["top_cast"]:
                for item in search_deezer(f'artist:"{lead_artist}"', 10):
                    candidates[item["id"]] = item

    # Nivel 1B: Todos los compositores acreditados (hasta 3)
    if not candidates and media["composers"]:
        for comp in media["composers"]:
            for t in titles:
                for item in search_deezer(f'track:"{t}" artist:"{comp}"', 10):
                    candidates[item["id"]] = item
                if not candidates:
                    for item in search_deezer(f'album:"{t}" artist:"{comp}"', 10):
                        candidates[item["id"]] = item

    # Nivel 2: Palabras clave internacionales y en español (BSO, Cabecera, Sintonía, Main Theme)
    if not candidates:
        for t in titles:
            if is_anime:
                q = f'"{t}" opening'
            elif is_tv:
                q = f'"{t}" "Main Title" OR "{t}" "Cabecera" OR "{t}" "Sintonía" OR "{t}" "BSO"'
            else:
                q = f'"{t}" "Main Theme" OR "{t}" "Main Title" OR "{t}" "Tema Principal" OR "{t}" "BSO"'
            for item in search_deezer(q, 15):
                candidates[item["id"]] = item

    # Nivel 3: Búsqueda general por título
    if not candidates:
        for t in titles:
            q = f'"{t}" OP' if is_anime else f'"{t}"'
            for item in search_deezer(q, 20):
                candidates[item["id"]] = item

    pre_filtered = []
    for tr in candidates.values():
        if not tr.get("readable") or not tr.get("preview") or tr.get("duration", 0) < 30:
            continue
        if BLACKLIST_STANDARD.search(tr.get("title", "")) or BLACKLIST_STANDARD.search(tr.get("artist", {}).get("name", "")):
            continue
        if is_tv and TV_ENDING_BLACKLIST.search(tr.get("title", "")):
            continue

        clean_title = strip_own_title(tr.get("title", ""), titles)
        clean_album = strip_own_title(tr.get("album", {}).get("title", ""), titles)

        if LATER_SEASONS_REGEX.search(clean_title) or LATER_SEASONS_REGEX.search(clean_album):
            continue
        pre_filtered.append(tr)

    top_5 = sorted(pre_filtered, key=lambda x: x.get("rank", 0), reverse=True)[:5]
    best_track = None
    best_score = 44  # Umbral mínimo de seguridad

    for item in top_5:
        details = get_deezer_track_details(item["id"])
        if not details:
            continue
        score = calculate_score(details, media, titles)
        if score > best_score or (score == best_score and best_track and details.get("rank", 0) > best_track.get("rank", 0)):
            best_score = score
            best_track = details

    # =========================================================================
    # NIVEL DE RESCATE (FALLBACK DE SEGURIDAD):
    # Si las reglas estrictas no encuentran nada, busca por título + compositor 
    # o soundtrack y toma el primer resultado válido para evitar silencios.
    # =========================================================================
    if not best_track:
        fallback_queries = []
        primary_title = media["english_name"] or media["original_name"]
        
        for comp in media["composers"]:
            fallback_queries.append(f'{primary_title} {comp}')
            
        fallback_queries.append(f'{primary_title} soundtrack')
        fallback_queries.append(primary_title)

        for fq in fallback_queries:
            fallback_items = search_deezer(fq, limit=5)
            for f_item in fallback_items:
                if f_item.get("readable") and f_item.get("preview") and f_item.get("duration", 0) >= 30:
                    details = get_deezer_track_details(f_item["id"])
                    if details:
                        best_track = details
                        print(f"🛟 [RESCATE/FALLBACK] Aplicado para '{primary_title}' usando query: '{fq}'")
                        break
            if best_track:
                break

    return best_track["id"] if best_track else None

def main():
    if not TMDB_API_KEY:
        print("Error: Falta la variable de entorno TMDB_API_KEY.")
        return

    catalog = load_existing_catalog()
    added_count = 0
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    ninety_days_ago = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")

    search_configs = [
        ("tv", "tv/popular", {}),
        ("tv", "tv/top_rated", {}),
        ("tv", "discover/tv", {"with_origin_country": "ES", "sort_by": "popularity.desc"}),
        ("tv", "discover/tv", {
            "first_air_date.gte": ninety_days_ago,
            "first_air_date.lte": today_str,
            "vote_count.gte": 5,
            "sort_by": "first_air_date.desc"
        }),
        ("tv", "discover/tv", {
            "with_origin_country": "ES",
            "first_air_date.gte": ninety_days_ago,
            "first_air_date.lte": today_str,
            "sort_by": "first_air_date.desc"
        }),
        ("movie", "movie/popular", {}),
        ("movie", "movie/top_rated", {}),
        ("movie", "discover/movie", {"with_origin_country": "ES", "sort_by": "popularity.desc"}),
        ("movie", "discover/movie", {"with_genres": "99", "sort_by": "popularity.desc"}),
        ("movie", "discover/movie", {"with_genres": "10402", "sort_by": "popularity.desc"}),
        ("movie", "discover/movie", {
            "primary_release_date.gte": ninety_days_ago,
            "primary_release_date.lte": today_str,
            "vote_count.gte": 5,
            "sort_by": "primary_release_date.desc"
        }),
        ("movie", "discover/movie", {
            "with_origin_country": "ES",
            "primary_release_date.gte": ninety_days_ago,
            "primary_release_date.lte": today_str,
            "sort_by": "primary_release_date.desc"
        }),
    ]

    for media_type, endpoint, extra_params in search_configs:
        target_dict = catalog["tv"] if media_type == "tv" else catalog["movies"]
        for page in range(1, PAGES_TO_SCAN + 1):
            params = {"api_key": TMDB_API_KEY, "page": page, **extra_params}
            r = requests.get(f"https://api.themoviedb.org/3/{endpoint}", params=params, timeout=10)
            if r.status_code != 200:
                continue
            for item in r.json().get("results", []):
                tmdb_id = str(item["id"])
                if tmdb_id in target_dict:
                    continue
                details = get_tmdb_details(media_type, item["id"])
                if not details:
                    continue
                deezer_id = find_best_audio(details)
                if deezer_id:
                    target_dict[tmdb_id] = deezer_id
                    added_count += 1
                    print(f"[+] [{media_type.upper()}] {details['english_name']} ({tmdb_id}) -> {deezer_id}")

    if added_count > 0:
        catalog["version"] = catalog.get("version", 0) + 1
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        print(f"Catálogo v{catalog['version']} guardado. Series: {len(catalog['tv'])} | Películas/Docs: {len(catalog['movies'])}")
    else:
        print("No se encontraron títulos nuevos.")

if __name__ == "__main__":
    main()
