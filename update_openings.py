import os
import requests
import json

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
OUTPUT_FILE = "media_openings.json"

def get_tmdb_details(media_type, item_id):
    url = f"https://api.themoviedb.org/3/{media_type}/{item_id}"
    try:
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
    except requests.exceptions.RequestException:
        return None

def main():
    if not os.path.exists(OUTPUT_FILE):
        print(f"No se encontró el archivo {OUTPUT_FILE}")
        return

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    print("Comprobando actualizaciones en el catálogo existente...")
    # Aquí puedes mantener la lógica que ya tuvieses para recorrer o validar tu JSON, 
    # asegurando que los diccionarios estén listos.
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    
    print("¡Proceso de update finalizado correctamente!")

if __name__ == "__main__":
    main()
