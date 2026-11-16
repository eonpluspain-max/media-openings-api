import os
import re
import json

OUTPUT_FILE = "media_openings.json"

def main():
    issue_body = os.environ.get("ISSUE_BODY", "")
    if not issue_body:
        print("Error: No se recibió el cuerpo del formulario.")
        return

    # Cargar catálogo existente
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    else:
        catalog = {"version": 0, "tv": {}, "movies": {}}

    catalog.setdefault("tv", {})
    catalog.setdefault("movies", {})

    nuevos_procesados = 0

    # 1. Procesar Películas (1 a 5)
    for i in range(1, 6):
        tmdb_match = re.search(rf"### \[Peli {i}\] ID de TMDB.*?\n+([^\n]+)", issue_body)
        deezer_match = re.search(rf"### \[Peli {i}\] ID de la pista en Deezer\s*\n+([^\n]+)", issue_body)

        if not tmdb_match or not deezer_match:
            continue

        tmdb_id = tmdb_match.group(1).strip()
        raw_deezer = deezer_match.group(1).strip()

        if not tmdb_id or not raw_deezer:
            continue

        try:
            deezer_id = int(raw_deezer)
        except ValueError:
            continue

        accion = "Sustituido" if tmdb_id in catalog["movies"] else "Añadido"
        catalog["movies"][tmdb_id] = deezer_id
        nuevos_procesados += 1
        print(f"✅ [{accion}] [MOVIES] TMDB: {tmdb_id} -> Deezer: {deezer_id}")

    # 2. Procesar Series (1 a 5)
    for i in range(1, 6):
        tmdb_match = re.search(rf"### \[Serie {i}\] ID de TMDB.*?\n+([^\n]+)", issue_body)
        deezer_match = re.search(rf"### \[Serie {i}\] ID de la pista en Deezer\s*\n+([^\n]+)", issue_body)

        if not tmdb_match or not deezer_match:
            continue

        tmdb_id = tmdb_match.group(1).strip()
        raw_deezer = deezer_match.group(1).strip()

        if not tmdb_id or not raw_deezer:
            continue

        try:
            deezer_id = int(raw_deezer)
        except ValueError:
            continue

        accion = "Sustituido" if tmdb_id in catalog["tv"] else "Añadido"
        catalog["tv"][tmdb_id] = deezer_id
        nuevos_procesados += 1
        print(f"✅ [{accion}] [TV] TMDB: {tmdb_id} -> Deezer: {deezer_id}")

    if nuevos_procesados > 0:
        catalog["version"] = catalog.get("version", 0) + 1
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        print(f"📦 Catálogo actualizado con éxito. Total procesados: {nuevos_procesados}. Nueva versión: {catalog['version']}")
    else:
        print("⚠️ No se encontraron elementos válidos para procesar en el formulario.")

if __name__ == "__main__":
    main()
