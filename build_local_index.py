"""Construye el índice local de similitud visual para Aura Art Scanner.

Este script recorre las imágenes precargadas del proyecto, genera un embedding
visual para cada una y guarda en disco:
- un archivo `embeddings.npy` con los vectores numéricos,
- y un `metadata.json` con la información descriptiva de cada imagen.

El resultado final se usa después en la interfaz principal para buscar las
obras visualmente más cercanas a una imagen subida por el usuario.
"""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from local_similarity import encode_image_paths, save_local_index


BASE_DIR = Path(__file__).resolve().parent
# Dataset curado del MET con metadatos y miniaturas extraídas localmente.
METADATA_CSV_PATH = BASE_DIR / "met_art_data2" / "metadata_cleaned_updated.csv"
MET_IMAGES_DIR = BASE_DIR / "met_art_data2" / "images_extracted"
# Dataset histórico de artistas y sus previews ya redimensionadas.
ARTISTS_CSV_PATH = BASE_DIR / "met_art_data" / "Artists2.csv"
ARTIST_IMAGES_DIR = BASE_DIR / "met_art_data" / "resized 3"


def normalize_artist_key(name):
    """Convierte un nombre de artista al patrón usado por los archivos locales."""
    return str(name or "").strip().replace(" ", "_")


def normalize_object_type(value):
    """Agrupa descripciones libres en familias de objeto comparables.

    Esto evita que el índice trate como categorías distintas etiquetas muy
    parecidas, por ejemplo `oil on canvas` y `painting`.
    """
    text = str(value or "").strip().lower()
    if not text:
        return ""

    mapping = {
        "painting": ["painting", "oil", "canvas", "tempera", "panel"],
        "sculpture": ["sculpture", "statue", "bronze", "marble", "stone", "carving", "statuette"],
        "drawing": ["drawing", "sketch", "graphite", "chalk", "ink drawing"],
        "print": ["print", "etching", "engraving", "lithograph", "woodcut", "screenprint"],
        "ceramic": ["ceramic", "pottery", "vase", "porcelain", "earthenware", "stoneware", "terracotta"],
        "textile": ["textile", "tapestry", "fabric", "weaving", "embroidery"],
        "photograph": ["photograph", "photo", "albumen", "gelatin silver"],
        "decorative object": ["utensil", "vessel", "bowl", "cup", "plate", "furniture", "decorative", "object"],
    }

    for canonical, keywords in mapping.items():
        if any(keyword in text for keyword in keywords):
            return canonical
    return text


def collect_met_records():
    """Prepara registros a partir del dataset local del MET.

    Cada registro contiene la ruta de la imagen y la metadata mínima necesaria
    para mostrar el resultado luego en la interfaz.
    """
    if not METADATA_CSV_PATH.exists():
        return []

    # Leemos el CSV y lo convertimos en una lista homogénea de diccionarios.
    df = pd.read_csv(METADATA_CSV_PATH).copy()
    records = []
    for _, row in df.iterrows():
        # `localImageFileName` enlaza la fila del CSV con una imagen en disco.
        image_name = str(row.get("localImageFileName", "")).strip()
        if not image_name:
            continue

        image_path = MET_IMAGES_DIR / Path(image_name).name
        if not image_path.exists():
            continue

        # Guardamos la información mínima que luego será útil en el buscador.
        records.append(
            {
                "image_path": str(image_path.resolve()),
                "title": str(row.get("title", "Untitled")).strip() or "Untitled",
                "creator": str(row.get("artistDisplayName", "Unknown artist")).strip() or "Unknown artist",
                "period": str(row.get("objectDate", "")).strip() or str(row.get("period", "")).strip() or "Period unavailable",
                "source_name": "Local MET dataset",
                "source_url": str(row.get("objectURL", "")).strip(),
                "medium": str(row.get("medium", "")).strip(),
                "culture": str(row.get("culture", "")).strip(),
                "object_type": normalize_object_type(row.get("medium", "") or row.get("department", "")),
            }
        )
    return records


def collect_artist_preview_records():
    """Prepara registros a partir de `met_art_data/resized 3`.

    Estas imágenes no vienen de un CSV de obras individuales, así que las
    tratamos como previews representativas de cada artista.
    """
    if not ARTIST_IMAGES_DIR.exists():
        return []

    # Construimos un pequeño lookup para enriquecer las imágenes con metadata.
    artist_lookup = {}
    if ARTISTS_CSV_PATH.exists():
        artists_df = pd.read_csv(ARTISTS_CSV_PATH).copy()
        for _, row in artists_df.iterrows():
            artist_lookup[normalize_artist_key(row.get("name", ""))] = row

    records = []
    for image_path in sorted(ARTIST_IMAGES_DIR.glob("*.*")):
        # Solo indexamos formatos de imagen útiles para OpenCLIP.
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue

        # El nombre del archivo suele terminar en `_numero`; lo quitamos para
        # volver a la clave estable del artista.
        artist_key = re.sub(r"_\d+$", "", image_path.stem)
        artist_row = artist_lookup.get(artist_key)
        artist_name = str(artist_row.get("name", "")).strip() if artist_row is not None else artist_key.replace("_", " ")
        records.append(
            {
                "image_path": str(image_path.resolve()),
                "title": f"{artist_name} preview",
                "creator": artist_name or "Unknown artist",
                "period": str(artist_row.get("years", "")).strip() if artist_row is not None else "Period unavailable",
                "source_name": "Local artist previews",
                "source_url": str(artist_row.get("wikipedia", "")).strip() if artist_row is not None else "",
                "medium": str(artist_row.get("genre", "")).strip() if artist_row is not None else "",
                "culture": str(artist_row.get("nationality", "")).strip() if artist_row is not None else "",
                "object_type": "painting",
            }
        )
    return records


def main():
    """Orquesta la construcción del índice visual local."""
    # Unimos ambos orígenes para que Aura busque en todo lo precargado.
    records = collect_met_records() + collect_artist_preview_records()
    if not records:
        raise SystemExit("No local image records were found to index.")

    # Convertimos cada ruta de imagen a un embedding visual.
    image_paths = [Path(record["image_path"]) for record in records]
    embeddings = encode_image_paths(image_paths)
    if embeddings is None or len(embeddings) != len(records):
        raise SystemExit("Could not build embeddings. Install torch + open-clip-torch and try again.")

    # Persistimos embeddings y metadata para reutilizarlos desde Streamlit.
    save_local_index(embeddings, records)
    print(f"Indexed {len(records)} local images into local_similarity_index/.")


if __name__ == "__main__":
    # Punto de entrada cuando el archivo se ejecuta directamente.
    main()
