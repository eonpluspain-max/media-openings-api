import json
import os

OUTPUT_FILE = "media_openings.json"

def main():
    print("========================================")
    print(" 🛠️ AÑADIDOR MANUAL RÁPIDO DE OPENINGS")
    print("========================================")
    
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    else:
        catalog = {"version": 0, "tv": {}, "movies": {}}

    catalog.setdefault("tv", {})
    catalog.setdefault("movies", {})

    while True:
        print("\n--- Nuevo registro ---")
        media_type = input("¿Es serie (tv) o película (movie)? [Escribe 'q' para salir]: ").strip().lower()
        
        if media_type == 'q':
            print("Saliendo... ¡Guarda y sube tu archivo JSON actualizado a GitHub!")
            break
            
        if media_type in ['peli', 'pelicula', 'movies']:
            media_type = 'movies'
            
        if media_type not in ['tv', 'movies']:
            print("❌ Error: Escribe 'tv' para series o 'movie' para películas.")
            continue

        tmdb_id = input("Introduce el ID de TMDB: ").strip()
        if not tmdb_id:
            print("❌ El ID de TMDB no puede estar vacío.")
            continue

        deezer_id = input("Introduce el ID de la canción en Deezer (ej: 12345678): ").strip()
        if not deezer_id:
            print("❌ El ID de Deezer no puede estar vacío.")
            continue

        try:
            deezer_id = int(deezer_id)
        except ValueError:
            print("❌ El ID de Deezer debe ser un número entero.")
            continue

        # Si ya existe, lo sobrescribe; si no, lo añade
        catalog[media_type][tmdb_id] = deezer_id
        catalog["version"] = catalog.get("version", 0) + 1

        # Guardar inmediatamente en el archivo local
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

        print(f"✅ ¡Actualizado con éxito! [{media_type.upper()}] TMDB ID: {tmdb_id} ➔ Deezer ID: {deezer_id}")
        print(f"📦 Versión del catálogo incrementada a: {catalog['version']}")

if __name__ == "__main__":
    main()
