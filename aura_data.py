"""Utilidades de datos y referencias locales para Aura Art Scanner.

Este módulo concentra todo lo relacionado con:
- rutas de datasets e imágenes locales,
- carga y normalización de colecciones,
- búsqueda de artistas y objetos relacionados,
- y construcción de mensajes de referencia para el chat.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
from pathlib import Path
import zipfile

import pandas as pd
from PIL import Image
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
BACKGROUND_IMAGE_PATH = BASE_DIR / "assets" / "reflets_du_soir_echappee_belle.jpeg"
AURA_LOGO_PATH = BASE_DIR / "assets" / "aura_gemini_transparent_v2.png"
METADATA_CSV_PATH = BASE_DIR / "met_art_data2" / "metadata_cleaned_updated.csv"
MET_IMAGES_ZIP_PATH = BASE_DIR / "met_art_data2" / "images_updated.zip"
MET_IMAGES_DIR = BASE_DIR / "met_art_data2" / "images_extracted"
ARTISTS_CSV_PATH = BASE_DIR / "met_art_data" / "Artists2.csv"
ARTIST_IMAGES_DIR = BASE_DIR / "met_art_data" / "resized 3"


@st.cache_data(show_spinner=False)
def get_background_image_data_url(image_path):
    """Devuelve una data URL en base64 para usar una imagen local en CSS."""
    if not os.path.exists(image_path):
        return None

    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded_image}"


@st.cache_resource(show_spinner=False)
def ensure_met_images_extracted():
    """Extrae el zip del dataset del MET a una carpeta plana local."""
    MET_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    if not MET_IMAGES_ZIP_PATH.exists():
        return MET_IMAGES_DIR

    with zipfile.ZipFile(MET_IMAGES_ZIP_PATH) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            filename = Path(member.filename).name
            if not filename:
                continue

            target_path = MET_IMAGES_DIR / filename
            if target_path.exists() and target_path.stat().st_size > 0:
                continue

            with archive.open(member) as source, open(target_path, "wb") as destination:
                shutil.copyfileobj(source, destination)

    return MET_IMAGES_DIR


def resolve_met_image_path(raw_path):
    """Convierte una ruta del CSV del MET a una ruta local válida si existe."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None

    ensure_met_images_extracted()

    candidate = Path(raw_path)
    if candidate.is_absolute() and candidate.exists():
        return candidate

    candidate = (BASE_DIR / raw_path).resolve()
    if candidate.exists():
        return candidate

    fallback = MET_IMAGES_DIR / Path(raw_path).name
    if fallback.exists():
        return fallback.resolve()

    return None


@st.cache_data(show_spinner=False)
def load_met_collection():
    """Carga la colección curada del MET desde el CSV local."""
    if not METADATA_CSV_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(METADATA_CSV_PATH).copy()

    if "object_year" in df.columns:
        df["object_year"] = pd.to_numeric(df["object_year"], errors="coerce")

    if "artistDisplayName" in df.columns:
        df["artistDisplayName"] = df["artistDisplayName"].fillna("Unknown Artist")
    if "title" in df.columns:
        df["title"] = df["title"].fillna("Untitled")
    if "artistRole" in df.columns:
        df["artistRole"] = df["artistRole"].fillna("Unknown role")
    if "objectDate" in df.columns:
        df["objectDate"] = df["objectDate"].fillna("Date unavailable")
    if "department" in df.columns:
        df["department"] = df["department"].fillna("Unknown department")
    if "medium" in df.columns:
        df["medium"] = df["medium"].fillna("Unknown medium")
    if "dimensions" in df.columns:
        df["dimensions"] = df["dimensions"].fillna("Dimensions unavailable")
    if "culture" in df.columns:
        df["culture"] = df["culture"].fillna("")
    if "period" in df.columns:
        df["period"] = df["period"].fillna("")
    if "artist_slug" in df.columns:
        df["artist_slug"] = df["artist_slug"].fillna("")

    if "localImageFileName" in df.columns:
        df["resolved_image_path"] = df["localImageFileName"].apply(resolve_met_image_path)
    elif "image_path" in df.columns:
        df["resolved_image_path"] = df["image_path"].apply(resolve_met_image_path)
    else:
        df["resolved_image_path"] = None

    return df


@st.cache_data(show_spinner=False)
def load_met_thumbnail(image_path, max_size=(440, 440)):
    """Abre una imagen local y la reduce para usarla como preview."""
    if not image_path:
        return None

    path = Path(image_path)
    if not path.exists():
        return None

    with Image.open(path) as img:
        preview = img.convert("RGB")
        preview.thumbnail(max_size)
        return preview.copy()


def normalize_artist_key(name):
    """Convierte el nombre del artista al patrón usado por archivos locales."""
    if not isinstance(name, str):
        return ""
    return name.strip().replace(" ", "_")


@st.cache_data(show_spinner=False)
def count_artist_images(artist_key):
    """Cuenta cuántas previews locales tiene un artista."""
    if not artist_key or not ARTIST_IMAGES_DIR.exists():
        return 0
    return len(list(ARTIST_IMAGES_DIR.glob(f"{artist_key}_*.jpg")))


@st.cache_data(show_spinner=False)
def load_artists_collection():
    """Carga el dataset local de artistas y enlaza sus previews."""
    if not ARTISTS_CSV_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(ARTISTS_CSV_PATH).copy()
    df["name"] = df["name"].fillna("Unknown Artist")
    df["genre"] = df["genre"].fillna("Unknown genre")
    df["nationality"] = df["nationality"].fillna("Unknown nationality")
    df["years"] = df["years"].fillna("Dates unavailable")
    df["bio"] = df["bio"].fillna("Biography unavailable.")
    df["paintings"] = pd.to_numeric(df["paintings"], errors="coerce")
    df["artist_key"] = df["name"].map(normalize_artist_key)
    df["image_count"] = df["artist_key"].map(count_artist_images)
    return df


@st.cache_data(show_spinner=False)
def get_artist_image_paths(artist_key, limit=6):
    """Devuelve una lista corta de imágenes locales para un artista."""
    if not artist_key or not ARTIST_IMAGES_DIR.exists():
        return []

    image_paths = sorted(ARTIST_IMAGES_DIR.glob(f"{artist_key}_*.jpg"))
    return [path.resolve() for path in image_paths[:limit]]


def get_artist_record_by_name(artist_name):
    """Recupera un artista del dataset local por nombre exacto."""
    if not artist_name:
        return None

    artists_df = load_artists_collection()
    if artists_df.empty:
        return None

    matches = artists_df[artists_df["name"] == artist_name]
    if matches.empty:
        return None

    return matches.iloc[0]


def get_met_object_record_by_id(object_id):
    """Recupera un objeto del dataset local del MET por `objectID`."""
    if object_id is None:
        return None

    met_df = load_met_collection()
    if met_df.empty:
        return None

    matches = met_df[met_df["objectID"].astype(str) == str(object_id)]
    if matches.empty:
        return None

    return matches.iloc[0]


def normalize_lookup_value(value):
    """Normaliza texto para comparaciones robustas."""
    if not isinstance(value, str):
        value = str(value)

    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def split_artist_genres(genre_value):
    """Convierte el campo de géneros en un conjunto normalizado."""
    if not isinstance(genre_value, str):
        return set()

    return {genre.strip().lower() for genre in genre_value.split(",") if genre.strip()}


def get_related_artists(artist_name, limit=3):
    """Busca artistas cercanos por género, nacionalidad y riqueza local."""
    artist = get_artist_record_by_name(artist_name)
    artists_df = load_artists_collection()

    if artist is None or artists_df.empty:
        return []

    base_genres = split_artist_genres(artist.get("genre", ""))
    base_nationality = str(artist.get("nationality", "")).strip().lower()

    candidates = artists_df[artists_df["name"] != artist_name].copy()
    if candidates.empty:
        return []

    def score_candidate(row):
        score = 0
        candidate_genres = split_artist_genres(row.get("genre", ""))
        score += len(base_genres.intersection(candidate_genres)) * 4

        candidate_nationality = str(row.get("nationality", "")).strip().lower()
        if base_nationality and candidate_nationality == base_nationality:
            score += 3

        image_count = row.get("image_count")
        if pd.notna(image_count):
            score += min(int(image_count), 6) * 0.2

        paintings_count = row.get("paintings")
        if pd.notna(paintings_count):
            score += min(int(paintings_count), 250) * 0.01

        return score

    candidates["related_score"] = candidates.apply(score_candidate, axis=1)
    candidates = candidates.sort_values(
        by=["related_score", "image_count", "paintings", "name"],
        ascending=[False, False, False, True],
        na_position="last",
    )

    top_candidates = candidates.head(limit)
    return [row for _, row in top_candidates.iterrows() if row["related_score"] > 0]


def get_related_met_objects(object_row, limit=3):
    """Busca objetos relacionados por autor, contexto y cercanía temporal."""
    met_df = load_met_collection()
    if object_row is None or met_df.empty:
        return []

    base_object_id = object_row.get("objectID")
    candidates = met_df[met_df["objectID"] != base_object_id].copy()
    if candidates.empty:
        return []

    base_artist = normalize_lookup_value(object_row.get("artistDisplayName", ""))
    base_department = normalize_lookup_value(object_row.get("department", ""))
    base_period = normalize_lookup_value(object_row.get("period", ""))
    base_culture = normalize_lookup_value(object_row.get("culture", ""))
    base_year = object_row.get("object_year")

    def score_candidate(row):
        score = 0
        candidate_artist = normalize_lookup_value(row.get("artistDisplayName", ""))
        candidate_department = normalize_lookup_value(row.get("department", ""))
        candidate_period = normalize_lookup_value(row.get("period", ""))
        candidate_culture = normalize_lookup_value(row.get("culture", ""))

        if base_artist and base_artist != "unknown artist" and candidate_artist == base_artist:
            score += 4
        if base_department and candidate_department == base_department:
            score += 3
        if base_period and candidate_period == base_period:
            score += 2
        if base_culture and candidate_culture == base_culture:
            score += 1.5

        candidate_year = row.get("object_year")
        if pd.notna(base_year) and pd.notna(candidate_year):
            score += max(0, 2 - (abs(float(candidate_year) - float(base_year)) / 25))

        if bool(row.get("has_local_image", False)):
            score += 0.2

        return score

    candidates["related_score"] = candidates.apply(score_candidate, axis=1)
    candidates = candidates.sort_values(
        by=["related_score", "object_year", "title", "artistDisplayName"],
        ascending=[False, False, True, True],
        na_position="last",
    )

    top_candidates = candidates.head(limit)
    return [row for _, row in top_candidates.iterrows() if row["related_score"] > 0]


def build_artist_reference_message(selected_artist_context_name):
    """Construye el mensaje de sistema para el artista local activo."""
    artist = get_artist_record_by_name(selected_artist_context_name)
    if artist is None:
        return None

    bio_text = str(artist.get("bio", "Biography unavailable.")).strip()
    bio_excerpt = bio_text[:900].rsplit(" ", 1)[0] + "..." if len(bio_text) > 900 else bio_text
    paintings_value = artist.get("paintings")
    paintings_label = int(paintings_value) if pd.notna(paintings_value) else "Unknown"
    preview_count = len(get_artist_image_paths(artist.get("artist_key", ""), limit=6))
    related_artists = get_related_artists(selected_artist_context_name, limit=3)
    related_block = "\n".join(
        f"- {candidate['name']} | {candidate['nationality']} | {candidate['genre']}"
        for candidate in related_artists
    ) or "- No close alternatives found in the local artist dataset."

    context = f"""
Use the following local artist profile as optional reference context for image analysis.
Do not assume the uploaded artwork is by this artist. Treat it as a hypothesis anchor only.

Artist reference:
- Name: {artist.get('name', 'Unknown Artist')}
- Years: {artist.get('years', 'Dates unavailable')}
- Nationality: {artist.get('nationality', 'Unknown nationality')}
- Genres: {artist.get('genre', 'Unknown genre')}
- Paintings in local dataset: {paintings_label}
- Local preview images available: {preview_count}
- Bio summary: {bio_excerpt}

Possible alternative artist references from the same local dataset:
{related_block}

When the user uploads an artwork image, compare the visual evidence against this profile.
If the match feels weak, say so clearly and use the alternatives above when they fit better.
"""
    return {"role": "system", "content": context.strip()}


def build_met_object_reference_message(selected_met_object_context_id):
    """Construye el mensaje de sistema para el objeto local activo."""
    met_object = get_met_object_record_by_id(selected_met_object_context_id)
    if met_object is None:
        return None

    related_objects = get_related_met_objects(met_object, limit=3)
    related_block = "\n".join(
        f"- {candidate.get('title', 'Untitled')} | {candidate.get('artistDisplayName', 'Unknown Artist')} | {candidate.get('department', 'Unknown department')}"
        for candidate in related_objects
    ) or "- No close alternatives found in the local object dataset."

    object_year = met_object.get("object_year")
    object_year_label = int(object_year) if pd.notna(object_year) else "Unknown"
    image_preview = met_object.get("resolved_image_path")
    image_label = "Yes" if image_preview else "No"

    context = f"""
Use the following local museum object as optional reference context for image analysis.
Do not assume the uploaded artwork is this object. Treat it as a hypothesis anchor only.

Selected object:
- Object ID: {met_object.get('objectID', 'Unknown')}
- Title: {met_object.get('title', 'Untitled')}
- Artist: {met_object.get('artistDisplayName', 'Unknown Artist')}
- Artist role: {met_object.get('artistRole', 'Unknown role')}
- Date: {met_object.get('objectDate', 'Date unavailable')}
- Object year: {object_year_label}
- Department: {met_object.get('department', 'Unknown department')}
- Culture: {met_object.get('culture', 'Unknown')}
- Period: {met_object.get('period', 'Unknown')}
- Medium: {met_object.get('medium', 'Unknown medium')}
- Dimensions: {met_object.get('dimensions', 'Dimensions unavailable')}
- Local image available: {image_label}

Possible alternative objects from the same local dataset:
{related_block}

When the user uploads an artwork image, compare the visual evidence against this object profile.
If the match feels weak, say so clearly and use the alternatives above when they fit better.
"""
    return {"role": "system", "content": context.strip()}
