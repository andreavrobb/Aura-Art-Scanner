"""Extrae obras del MET y guarda metadatos e imágenes locales.

Este script consulta la API pública del MET, filtra artistas no deseados,
descarga imágenes principales y construye un dataset local con:
- metadatos en Excel,
- imágenes descargadas a disco,
- y un contador por artista para nombrar archivos de forma consistente.
"""

import os
import re
import time
from collections import defaultdict  # Lleva el conteo de imágenes por artista.

import pandas as pd
import requests

# --- 1. Configuración ---
# Lista de artistas a omitir. Se normaliza a minúsculas para comparar de forma robusta.
OMIT_ARTISTS = {
    "amedeo modigliani", "vasiliy kandinskiy", "diego rivera", "claude monet", 
    "rene magritte", "salvador dali", "edouard manet", "andrei rublev", 
    "vincent van gogh", "gustav klimt", "hieronymus bosch", "kazimir malevich", 
    "mikhail vrubel", "pablo picasso", "peter paul rubens", "pierre-auguste renoir", 
    "francisco goya", "frida kahlo", "el greco", "albrecht dürer", "alfred sisley", 
    "pieter bruegel", "marc chagall", "giotto di bondone", "sandro botticelli", 
    "caravaggio", "leonardo da vinci", "diego velazquez", "henri matisse", 
    "jan van eyck", "edgar degas", "rembrandt", "titian", 
    "henri de toulouse-lautrec", "gustave courbet", "camille pissarro", 
    "william turner", "edvard munch", "paul cezanne", "eugene delacroix", 
    "henri rousseau", "georges seurat", "paul klee", "piet mondrian", 
    "joan miro", "andy warhol", "paul gauguin", "raphael", "michelangelo", 
    "jackson pollock", "konstantinos grammatopoulos", "kiyohara yukinobu"
}

# Rutas de salida donde se almacenan metadata e imágenes.
OUTPUT_DIR = "met_art_data"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
METADATA_FILE = os.path.join(OUTPUT_DIR, "metadata.xlsx")

# URL base de la API del MET.
MET_COLLECTION_API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"

# Nos aseguramos de que las carpetas de salida existan antes de guardar archivos.
os.makedirs(IMAGES_DIR, exist_ok=True)

# Diccionario para llevar la cuenta de imágenes por artista.
# La clave es el nombre sanitizado del artista y el valor es su contador.
artist_image_counts = defaultdict(int)

# --- 2. Funciones de Ayuda ---

def sanitize_filename(name):
    """Convierte un nombre en una cadena segura para usarla como archivo."""
    if not name:
        return ""
    # Reemplaza espacios con guiones bajos para mantener un patrón estable.
    sanitized = name.replace(" ", "_")
    # Elimina caracteres que podrían romper el nombre del archivo.
    sanitized = re.sub(r'[^\w.-]', '', sanitized)
    # Limpia guiones bajos redundantes para que el nombre quede más legible.
    sanitized = re.sub(r'_{2,}', '_', sanitized).strip('_')
    # Limitamos la longitud para no generar rutas incómodas o muy largas.
    return sanitized[:100]

def get_object_ids(query="painting", has_images=True, top_n=500):
    """Busca objectIDs en la API del MET usando una consulta dada."""
    search_url = f"{MET_COLLECTION_API_BASE}/search"
    params = {"q": query}
    if has_images:
        params["hasImages"] = True
    # Informamos al usuario qué consulta se lanzará antes de llamar a la API.
    print(f"Buscando objectIDs para la consulta: '{query}' (con imágenes={has_images})...")
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        object_ids = data.get("objectIDs", [])
        if top_n and len(object_ids) > top_n:
            print(f"Limitando a los primeros {top_n} objectIDs de un total de {len(object_ids)}.")
            return object_ids[:top_n]
        print(f"Encontrados {len(object_ids)} objectIDs.")
        return object_ids
    except requests.exceptions.RequestException as e:
        print(f"Error al buscar objectIDs: {e}")
        return []

def get_object_details(object_id):
    """Obtiene la ficha completa de una obra a partir de su objectID."""
    object_url = f"{MET_COLLECTION_API_BASE}/objects/{object_id}"
    try:
        response = requests.get(object_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener detalles para objectID {object_id}: {e}")
        return None

def download_image(image_url, object_id, artist_display_name, folder_path, artist_counts_dict):
    """Descarga una imagen y la guarda usando un nombre derivado del artista."""
    if not image_url:
        return None

    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()

        # Determinamos la extensión según el content-type recibido.
        content_type = response.headers.get('content-type', '').lower()
        if 'jpeg' in content_type or 'jpg' in content_type:
            ext = 'jpg'
        elif 'png' in content_type:
            ext = 'png'
        else:
            # Si el servidor no informa bien el tipo, usamos jpg como respaldo.
            ext = 'jpg'

        # Construimos un nombre de archivo estable y legible.
        sanitized_artist_name = sanitize_filename(artist_display_name)

        if sanitized_artist_name:
            # Incrementamos el contador por artista para evitar colisiones.
            artist_counts_dict[sanitized_artist_name] += 1
            count = artist_counts_dict[sanitized_artist_name]
            filename = f"{sanitized_artist_name}_{count}.{ext}"
        else:
            # Si no hay artista válido, usamos un nombre de respaldo con objectID.
            filename = f"unknown_artist_{object_id}.{ext}"
            print(f"  Advertencia: No se pudo usar nombre de artista para {object_id}. Usando '{filename}'")

        filepath = os.path.join(folder_path, filename)

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return filename
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar imagen {image_url} para objectID {object_id}: {e}")
        return None

# --- 3. Proceso Principal ---

def extract_and_save_art_data(query="painting", max_objects_to_fetch=500, delay_seconds=0.1):
    """Orquesta la descarga de metadatos e imágenes del MET."""
    # Aquí acumulamos todas las fichas de las obras procesadas correctamente.
    all_art_metadata = []

    object_ids = get_object_ids(query=query, has_images=True, top_n=max_objects_to_fetch)

    if not object_ids:
        print("No se encontraron objectIDs para procesar. Saliendo.")
        return

    print(f"\nIniciando procesamiento de {len(object_ids)} obras...")

    for i, object_id in enumerate(object_ids):
        print(f"[{i+1}/{len(object_ids)}] Procesando objectID: {object_id}")
        details = get_object_details(object_id)

        if details:
            # Tomamos el nombre del artista tal como lo devuelve el MET.
            artist_name_raw = details.get("artistDisplayName", "").strip()

            # Normalizamos el nombre del artista para compararlo con la lista de omitidos.
            normalized_artist_name_for_filter = artist_name_raw.lower()

            if normalized_artist_name_for_filter in OMIT_ARTISTS:
                print(f"  --> Omitiendo obra del artista '{artist_name_raw}' (objectID: {object_id})")
                continue 

            metadata = {
                "objectID": object_id,
                "title": details.get("title"),
                "artistDisplayName": artist_name_raw,
                "artistRole": details.get("artistRole"),
                "objectDate": details.get("objectDate"),
                "period": details.get("period"),
                "culture": details.get("culture"),
                "medium": details.get("medium"),
                "dimensions": details.get("dimensions"),
                "department": details.get("department"),
                "objectURL": details.get("objectURL"),
                "primaryImage": details.get("primaryImage"),
                "primaryImageSmall": details.get("primaryImageSmall"),
                "isPublicDomain": details.get("isPublicDomain")
            }

            # Si hay imagen principal, intentamos descargarla y enlazarla.
            primary_image_url = metadata["primaryImage"]
            if primary_image_url:
                print(f"  Descargando imagen para {object_id}...")
                # Guardamos la imagen usando el contador por artista.
                image_filename = download_image(primary_image_url, object_id, artist_name_raw, IMAGES_DIR, artist_image_counts)
                if image_filename:
                    metadata["localImageFileName"] = image_filename 
                else:
                    metadata["localImageFileName"] = None
            else:
                metadata["localImageFileName"] = None
                print(f"  No hay imagen principal disponible para {object_id}.")

            # Añadimos la fila aunque no siempre tenga imagen local disponible.
            all_art_metadata.append(metadata)

        # Pequeña pausa para no saturar la API.
        time.sleep(delay_seconds)

    if all_art_metadata:
        # Convertimos la lista de diccionarios en una tabla y la exportamos a Excel.
        df = pd.DataFrame(all_art_metadata)
        df.to_excel(METADATA_FILE, index=False)
        print(f"\n--- Extracción y guardado completados ---")
        print(f"Metadata de {len(df)} obras guardada en: '{METADATA_FILE}'")
        print(f"Imágenes de las obras guardadas en: '{IMAGES_DIR}'")
    else:
        print("\nNo se extrajo ninguna obra después de aplicar los filtros y procesar.")

# --- Ejecución Principal ---
if __name__ == "__main__":
    # Entrada principal del script cuando se ejecuta de forma directa.
    extract_and_save_art_data(query="painting", max_objects_to_fetch=500, delay_seconds=0.1)
