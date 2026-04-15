"""Aplicación de chat Aura Art Scanner con soporte multimodal en Streamlit.

Este módulo renderiza una interfaz conversacional en la que la persona usuaria puede:
- hacer preguntas sobre obras de arte,
- adjuntar una o varias imágenes,
- editar mensajes anteriores,
- regenerar la respuesta del asistente después de una edición,
- e interactuar con Gemini o OpenAI mediante sus API's.

El archivo también personaliza la interfaz de Streamlit con una imagen de fondo
y paneles translúcidos para mejorar la legibilidad.
"""
# --------------------------------------------
# Librerias y dependencias  
# --------------------------------------------

import base64
import html
import inspect
import json
import os
import re
import shutil
from pathlib import Path
import zipfile

import pandas as pd
from PIL import Image
from dotenv import load_dotenv
from openai import OpenAI
import requests
import streamlit as st

from prompts import stronger_prompt

# --------------------------------------------
# Entorno y clientes de API
# --------------------------------------------
load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# Se mantiene el cliente de OpenAI por si la app vuelve a usar modelos de OpenAI.
client_openai = OpenAI(api_key=OPENAI_API_KEY)
model_openai = "gpt-5.4-mini"

# Gemini se usa a través del endpoint compatible con OpenAI.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
client_google = OpenAI(api_key=GOOGLE_API_KEY, base_url=GEMINI_BASE_URL)
model_google = "gemini-2.5-flash"

# Imagen local usada como fondo de la aplicación.
# Fondo principal de la interfaz.
BACKGROUND_IMAGE_PATH = Path(__file__).resolve().parent / "assets" / "reflets_du_soir_echappee_belle.jpeg"
AURA_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "aura_gemini.png"
METADATA_CSV_PATH = Path(__file__).resolve().parent / "met_art_data2" / "metadata_cleaned_updated.csv"
MET_IMAGES_ZIP_PATH = Path(__file__).resolve().parent / "met_art_data2" / "images_updated.zip"
MET_IMAGES_DIR = Path(__file__).resolve().parent / "met_art_data2" / "images_extracted"
ARTISTS_CSV_PATH = Path(__file__).resolve().parent / "met_art_data" / "Artists2.csv"
ARTIST_IMAGES_DIR = Path(__file__).resolve().parent / "met_art_data" / "resized 3"
MET_PUBLIC_API_BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
AIC_API_BASE_URL = "https://api.artic.edu/api/v1"
CMA_API_BASE_URL = "https://openaccess-api.clevelandart.org/api"
SIMILAR_WEB_MATCH_LIMIT = 4
SIMILAR_WEB_SEARCH_TIMEOUT = 12
AIC_USER_AGENT = "aura-art-scanner (local-app)"

# Menú interactivo que se visualiza en la parte izquierda de la interfaz
AUDIENCE_PROFILES = [
    {
        "label": "Creative people",
        "icon": "🎨",
        "description": "Painters, illustrators, designers, photographers, musicians, and writers looking for visual inspiration and fresh ways to read an artwork.",
        "focus": "Great for exploring style, technique, composition, and visual references.",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/A_painter_at_work.jpg?width=900",
        "image_credit": "Image: 'A painter at work' - Wikimedia Commons",
    },
    {
        "label": "Students and teachers",
        "icon": "📚",
        "description": "People in art, history, humanities, design, or architecture who use art to learn, teach, and spark critical discussion.",
        "focus": "Useful for historical context, formal analysis, and classroom support.",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Architecture%20Students%20(5118388410).jpg?width=900",
        "image_credit": "Image: 'Architecture Students (5118388410)' - Wikimedia Commons",
    },
    {
        "label": "Culture lovers",
        "icon": "🏛️",
        "description": "People who enjoy museums, exhibitions, cinema, literature, and aesthetics, and want to connect art with broader cultural experiences.",
        "focus": "Perfect for discovering art movements and links to other disciplines.",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Visiting%20Museum.jpg?width=900",
        "image_credit": "Image: 'Visiting Museum' - Wikimedia Commons",
    },
    {
        "label": "Collectors and buyers",
        "icon": "🖼️",
        "description": "People interested in artworks, galleries, and the art market who want to sharpen their eye before buying or collecting.",
        "focus": "Helpful for discussing authorship, symbolic value, trends, and market context.",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Art%20Auction%20(1117409648).jpg?width=900",
        "image_credit": "Image: 'Art Auction (1117409648)' - Wikimedia Commons",
    },
    {
        "label": "Visually and emotionally driven people",
        "icon": "💫",
        "description": "People who connect with color, shape, symbolism, and narrative, even without formal art training.",
        "focus": "Helps read emotion, atmosphere, and visual language in a piece.",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Woman%20looking%20at%20painting%20(14168706910).jpg?width=900",
        "image_credit": "Image: 'Woman looking at painting (14168706910)' - Wikimedia Commons",
    },
    {
        "label": "Researchers and technologists",
        "icon": "🧠",
        "description": "People interested in computer vision, cultural heritage, digital museums, or AI applied to art.",
        "focus": "Very useful for discussing datasets, classification, embeddings, and multimodal analysis.",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Craft%20x%20Tech%20exhibition%20at%20V%26A%202024%20-%2013.jpg?width=900",
        "image_credit": "Image: 'Craft x Tech exhibition at V&A 2024 - 13' - Wikimedia Commons",
    },
    {
        "label": "General audience",
        "icon": "✨",
        "description": "Anyone who wants to better understand an artwork, an artist, or a movement without needing to be an expert.",
        "focus": "A great entry point for discovering art in a clear, accessible, guided way.",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/A%20Sunday%20crowd%20for%20'A%20Sunday%20on%20La%20Grande%20Jatte'%20at%20the%20Art%20Institute%20of%20Chicago.jpg?width=900",
        "image_credit": "Image: 'A Sunday crowd for A Sunday on La Grande Jatte at the Art Institute of Chicago' - Wikimedia Commons",
    },
]


@st.cache_data(show_spinner=False)
def get_background_image_data_url(image_path):
    """Devuelve una data URL en base64 para que CSS use una imagen local como fondo.

    El resultado se cachea porque el mismo archivo se lee en cada rerun de
    Streamlit. Si el archivo no existe, la función devuelve ``None`` y la app
    usa un fondo alternativo generado por CSS.
    """
    if not os.path.exists(image_path):
        return None

    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded_image}"


@st.cache_resource(show_spinner=False)
def ensure_met_images_extracted():
    """Extrae el zip del nuevo dataset en una carpeta local plana."""
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
    """Convierte una ruta del CSV a una ruta local absoluta si existe."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None

    ensure_met_images_extracted()

    candidate = Path(raw_path)
    if candidate.is_absolute() and candidate.exists():
        return candidate

    candidate = (Path(__file__).resolve().parent / raw_path).resolve()
    if candidate.exists():
        return candidate

    fallback = MET_IMAGES_DIR / Path(raw_path).name
    if fallback.exists():
        return fallback.resolve()

    return None


@st.cache_data(show_spinner=False)
def load_met_collection():
    """Carga la nueva colección curada del MET desde el CSV local."""
    if not METADATA_CSV_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(METADATA_CSV_PATH).copy()

    if "object_year" in df.columns:
        df["object_year"] = pd.to_numeric(df["object_year"], errors="coerce")

    if "artistDisplayName" in df.columns:
        df["artistDisplayName"] = df["artistDisplayName"].fillna("Unknown Artist")

    if "title" in df.columns:
        df["title"] = df["title"].fillna("Untitled")

    if "artistDisplayName" in df.columns:
        df["artistDisplayName"] = df["artistDisplayName"].fillna("Unknown Artist")

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
    """Prepara una imagen local para mostrarla como preview compacta."""
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
    """Convierte el nombre del artista al patrón usado por las imágenes locales."""
    if not isinstance(name, str):
        return ""

    cleaned = name.strip().replace(" ", "_")
    return cleaned


@st.cache_data(show_spinner=False)
def load_artists_collection():
    """Carga el dataset de artistas y enlaza sus imágenes locales."""
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
def count_artist_images(artist_key):
    """Cuenta cuantas previews locales hay para un artista."""
    if not artist_key or not ARTIST_IMAGES_DIR.exists():
        return 0

    return len(list(ARTIST_IMAGES_DIR.glob(f"{artist_key}_*.jpg")))


@st.cache_data(show_spinner=False)
def get_artist_image_paths(artist_key, limit=6):
    """Devuelve una lista corta de imágenes locales para un artista."""
    if not artist_key or not ARTIST_IMAGES_DIR.exists():
        return []

    image_paths = sorted(ARTIST_IMAGES_DIR.glob(f"{artist_key}_*.jpg"))
    return [path.resolve() for path in image_paths[:limit]]


def get_artist_record_by_name(artist_name):
    """Recupera una fila del dataset de artistas por nombre."""
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
    """Recupera una fila del nuevo dataset por objectID."""
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
    """Normaliza texto para comparaciones simples en el explorador del MET."""
    if not isinstance(value, str):
        value = str(value)

    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def split_artist_genres(genre_value):
    """Normaliza la lista de generos de un artista."""
    if not isinstance(genre_value, str):
        return set()

    return {genre.strip().lower() for genre in genre_value.split(",") if genre.strip()}


def get_related_artists(artist_name, limit=3):
    """Busca artistas relacionados por genero y nacionalidad dentro del dataset local."""
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
    """Busca objetos relacionados por artista, departamento, periodo y cultura."""
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


def build_artist_reference_message():
    """Construye un mensaje de sistema con el artista de referencia activo."""
    artist_name = st.session_state.get("selected_artist_context_name")
    artist = get_artist_record_by_name(artist_name)

    if artist is None:
        return None

    bio_text = str(artist.get("bio", "Biography unavailable.")).strip()
    bio_excerpt = bio_text[:900].rsplit(" ", 1)[0] + "..." if len(bio_text) > 900 else bio_text
    paintings_value = artist.get("paintings")
    paintings_label = int(paintings_value) if pd.notna(paintings_value) else "Unknown"
    preview_count = len(get_artist_image_paths(artist.get("artist_key", ""), limit=6))
    related_artists = get_related_artists(artist_name, limit=3)
    related_block = "\n".join(
        [
            f"- {candidate['name']} | {candidate['nationality']} | {candidate['genre']}"
            for candidate in related_artists
        ]
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


def build_met_object_reference_message():
    """Construye un mensaje de sistema con el objeto local activo como referencia."""
    object_id = st.session_state.get("selected_met_object_context_id")
    met_object = get_met_object_record_by_id(object_id)

    if met_object is None:
        return None

    related_objects = get_related_met_objects(met_object, limit=3)
    related_block = "\n".join(
        [
            f"- {candidate.get('title', 'Untitled')} | {candidate.get('artistDisplayName', 'Unknown Artist')} | {candidate.get('department', 'Unknown department')}"
            for candidate in related_objects
        ]
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


# --------------------------------------------
# Configuración de página y tema visual
# --------------------------------------------
st.set_page_config(
    page_title="Aura Art Scanner",
    page_icon=str(AURA_LOGO_PATH) if AURA_LOGO_PATH.exists() else "🎨",
)

background_image_url = get_background_image_data_url(BACKGROUND_IMAGE_PATH)
logo_image_url = get_background_image_data_url(str(AURA_LOGO_PATH)) if AURA_LOGO_PATH.exists() else None

if background_image_url:
    # Superpone un velo cálido suave para que los paneles de texto destaquen mejor.
    background_layers = (
        "linear-gradient(180deg, rgba(250, 245, 235, 0.36) 0%, "
        "rgba(231, 210, 163, 0.28) 100%), "
        f'url("{background_image_url}")'
    )
else:
    # Fondo alternativo cuando la imagen local no está disponible.
    background_layers = (
        "radial-gradient(circle at 16% 18%, rgba(255, 255, 255, 0.68) 0 7%, transparent 8%), "
        "radial-gradient(circle at 24% 16%, rgba(255, 255, 255, 0.68) 0 5%, transparent 6%), "
        "radial-gradient(circle at 73% 14%, rgba(255, 255, 255, 0.62) 0 8%, transparent 9%), "
        "radial-gradient(circle at 82% 18%, rgba(255, 255, 255, 0.58) 0 5%, transparent 6%), "
        "linear-gradient(180deg, #84c7ff 0%, #bfe6ff 45%, #f3fbff 100%)"
    )

css_background = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Quicksand&display=swap');

:root {
    --panel: rgba(255, 252, 247, 0.78);
    --panel-border: rgba(177, 135, 67, 0.22);
    --text-main: #3f2c1f;
}

.stApp {
    background-image: BACKGROUND_LAYERS_VALUE;
    background-size: cover;
    background-position: center center;
    background-repeat: no-repeat;
    background-attachment: fixed;
    color: var(--text-main);
}

.stApp [data-testid="stAppViewContainer"] {
    background: transparent;
}

.stApp [data-testid="stHeader"] {
    background: rgba(255, 249, 241, 0.18);
    backdrop-filter: blur(8px);
}

.stApp [data-testid="stAppViewBlockContainer"],
.stApp [data-testid="stMainBlockContainer"] {
    padding-top: clamp(6.5rem, 13vh, 8.75rem);
    scroll-padding-top: clamp(6.5rem, 13vh, 8.75rem);
}

.stApp [data-testid="stForm"],
.stApp [data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--panel);
    border: 1px solid var(--panel-border);
    backdrop-filter: blur(10px);
    border-radius: 18px;
    box-shadow: 0 18px 45px rgba(104, 72, 28, 0.12);
}

.stApp [data-testid="stChatMessage"] {
    border-radius: 24px;
    padding: 0.45rem 0.6rem;
    border: 1px solid rgba(255, 255, 255, 0.18);
    box-shadow: 0 18px 45px rgba(104, 72, 28, 0.1);
}

.stApp [data-testid="stChatMessage"]:has(.assistant-marker) {
    background: linear-gradient(
        135deg,
        rgba(227, 247, 241, 0.94) 0%,
        rgba(242, 253, 249, 0.9) 100%
    );
    border-left: 6px solid #3c9b8c;
}

.stApp [data-testid="stChatMessage"]:has(.user-marker) {
    background: linear-gradient(
        135deg,
        rgba(255, 242, 221, 0.95) 0%,
        rgba(255, 250, 240, 0.9) 100%
    );
    border-left: 6px solid #d6902f;
}

.stApp [data-testid="stMarkdownContainer"],
.stApp label,
.stApp p,
.stApp span,
.stApp h1,
.stApp h2,
.stApp h3 {
    color: var(--text-main);
}

.stApp [data-testid="stChatInput"] {
    background: rgba(255, 251, 246, 0.92);
    border-radius: 18px;
}

.stApp button {
    border-radius: 999px;
    border: 1px solid rgba(177, 135, 67, 0.28);
    background: rgba(255, 251, 246, 0.92);
    color: var(--text-main);
}

/* Let Streamlit select widgets use the full width of their columns so long labels are less likely to truncate. */
.stApp [data-baseweb="select"] {
    width: 100%;
    min-width: 0;
}

.stApp [data-baseweb="select"] > div {
    width: 100%;
    min-width: 0;
}

.stApp [data-baseweb="select"] div[role="combobox"] {
    min-width: 0;
}

.stApp [data-baseweb="select"] [class*="SingleValue"],
.stApp [data-baseweb="select"] [class*="Placeholder"] {
    max-width: 100% !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

.composer-flag {
    display: none;
}

.stApp [data-testid="stForm"]:has(.composer-flag) {
    width: min(100%, 54rem);
    margin: 0.2rem auto 0 auto;
    padding: 0.45rem 0.55rem 0.35rem;
    border-radius: 24px;
    background: rgba(255, 251, 246, 0.96);
    border: 1px solid rgba(177, 135, 67, 0.18);
    box-shadow: 0 14px 30px rgba(104, 72, 28, 0.08);
}

.stApp [data-testid="stForm"]:has(.composer-flag) [data-baseweb="input"] {
    background: rgba(240, 240, 244, 0.74);
    border-radius: 18px;
    border: 1px solid rgba(177, 135, 67, 0.12);
    min-height: 3.2rem;
}

.stApp [data-testid="stForm"]:has(.composer-flag) [data-baseweb="input"] > div {
    background: transparent;
}

.stApp [data-testid="stForm"]:has(.composer-flag) input {
    font-size: 1rem;
}

.stApp [data-testid="stForm"]:has(.composer-flag) .stTextInput,
.stApp [data-testid="stForm"]:has(.composer-flag) .stFormSubmitButton {
    margin-bottom: 0;
}

.stApp [data-testid="stForm"]:has(.composer-flag) .stExpander {
    margin-top: 0.3rem;
}

.stApp [data-testid="stForm"]:has(.composer-flag) .stExpander summary {
    font-size: 0.92rem;
}

.page-top-spacer {
    height: clamp(0.7rem, 2vh, 1.4rem);
    pointer-events: none;
}

.brand-mark {
    width: clamp(8.8rem, 15vw, 13.2rem);
    aspect-ratio: 1;
    background: transparent;
    border: none;
    box-shadow: none;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}

.brand-mark img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center center;
    display: block;
}

.app-title-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.8rem;
    width: 100%;
    flex-wrap: wrap;
    padding-top: 0;
    overflow: visible;
}

.app-title-icon {
    font-size: clamp(3.2rem, 4.2vw, 4.4rem);
    line-height: 1;
    filter: drop-shadow(0 5px 10px rgba(104, 72, 28, 0.1));
    transform: translateY(0.05rem);
}

.app-title {
    font-family: "Satisfy", "Brush Script MT", "Segoe Script",
        "Apple Chancery", cursive !important;
    font-size: clamp(3.45rem, 6vw, 5.2rem);
    line-height: 1.12;
    color: #5b3a1f;
    margin: 0;
    padding: 0.14em 0 0.08em;
    text-shadow: 0 7px 18px rgba(104, 72, 28, 0.14);
    font-weight: 400;
    letter-spacing: 0.01em;
    text-align: center;
    overflow: visible;
}

.app-subtitle {
    display: inline-block;
    width: fit-content;
    max-width: min(100%, 44rem);
    font-size: 1rem;
    font-weight: 700;
    color: #26412f;
    background: rgba(210, 236, 204, 0.92);
    border: 1px solid rgba(121, 170, 119, 0.24);
    border-radius: 999px;
    padding: 0.62rem 0.95rem;
    box-shadow: 0 9px 20px rgba(63, 114, 72, 0.08);
    backdrop-filter: blur(8px);
    margin: 0.55rem auto 1.1rem auto;
    text-align: center;
    line-height: 1.35;
}

.hero-shell {
    width: min(100%, 62rem);
    margin: -3.15rem auto 1.15rem auto;
    padding-top: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    overflow: visible;
}

.message-role {
    display: inline-flex;
    align-items: center;
    gap: 0.42rem;
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.38rem 0.75rem;
    border-radius: 999px;
    margin-bottom: 0.55rem;
}

.message-role.assistant-marker {
    color: #18554b;
    background: rgba(190, 236, 224, 0.9);
    border: 1px solid rgba(60, 155, 140, 0.28);
}

.message-role.user-marker {
    color: #7a4b10;
    background: rgba(255, 224, 178, 0.88);
    border: 1px solid rgba(214, 144, 47, 0.28);
}

.sidebar-profile-card {
    background: rgba(255, 250, 244, 0.82);
    border: 1px solid rgba(113, 154, 113, 0.2);
    border-radius: 22px;
    padding: 0.95rem 1rem;
    box-shadow: 0 14px 28px rgba(47, 82, 54, 0.08);
    margin-bottom: 0.85rem;
    backdrop-filter: blur(10px);
}

.sidebar-profile-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #2c5b42;
    background: rgba(215, 240, 222, 0.92);
    border: 1px solid rgba(104, 160, 118, 0.22);
    border-radius: 999px;
    padding: 0.34rem 0.65rem;
    margin-bottom: 0.65rem;
}

.sidebar-profile-title {
    font-size: 1.08rem;
    font-weight: 800;
    color: #2d2b28;
    margin-bottom: 0.45rem;
}

.sidebar-profile-copy {
    font-size: 0.96rem;
    line-height: 1.5;
    color: #4e473f;
}

.sidebar-profile-focus {
    margin-top: 0.75rem;
    padding: 0.7rem 0.8rem;
    border-radius: 16px;
    background: rgba(232, 246, 238, 0.95);
    border: 1px solid rgba(104, 160, 118, 0.2);
    color: #26412f;
    font-size: 0.93rem;
    line-height: 1.45;
}

.artist-browser-shell {
    width: min(100%, 78rem);
    margin: 0 auto 1.1rem auto;
    padding: 1rem 1rem 0.85rem;
    border-radius: 24px;
    background: rgba(255, 251, 246, 0.88);
    border: 1px solid rgba(177, 135, 67, 0.16);
    box-shadow: 0 14px 34px rgba(104, 72, 28, 0.08);
}

.artist-browser-title {
    font-size: 1.18rem;
    font-weight: 800;
    color: #3f2c1f;
    margin-bottom: 0.24rem;
}

.artist-browser-copy {
    color: rgba(63, 44, 31, 0.78);
    line-height: 1.45;
}

.met-browser-shell {
    width: min(100%, 78rem);
    margin: 0 auto 1.1rem auto;
    padding: 1rem 1rem 0.85rem;
    border-radius: 24px;
    background: rgba(248, 251, 255, 0.88);
    border: 1px solid rgba(63, 104, 150, 0.16);
    box-shadow: 0 14px 34px rgba(43, 67, 104, 0.08);
}

.met-browser-title {
    font-size: 1.18rem;
    font-weight: 800;
    color: #2f3f58;
    margin-bottom: 0.24rem;
}

.met-browser-copy {
    color: #4a3422;
    text-align: center;
    font-weight: 600;
    line-height: 1.45;
}

.section-caption-dark {
    color: #4a3422;
    font-weight: 600;
    margin: 0.2rem 0 0.7rem 0;
    text-align: center;
}

.quickstart-shell {
    width: min(100%, 68rem);
    margin: 0 auto 1rem auto;
    padding: 1rem 1rem 0.9rem;
    border-radius: 24px;
    background: linear-gradient(135deg, rgba(255, 248, 235, 0.92) 0%, rgba(239, 249, 245, 0.92) 100%);
    border: 1px solid rgba(177, 135, 67, 0.16);
    box-shadow: 0 14px 34px rgba(104, 72, 28, 0.08);
}

.quickstart-hero {
    display: grid;
    grid-template-columns: minmax(120px, 170px) 1fr;
    gap: 1rem;
    align-items: center;
    margin-bottom: 0.95rem;
}

.quickstart-logo-card {
    background: rgba(255, 255, 255, 0.84);
    border: 1px solid rgba(177, 135, 67, 0.14);
    border-radius: 24px;
    padding: 0.9rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.55);
}

.quickstart-logo-card img {
    width: 100%;
    max-width: 148px;
    display: block;
    margin: 0 auto;
    object-fit: contain;
}

.quickstart-text {
    min-width: 0;
}

.quickstart-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #2d5b44;
    background: rgba(214, 239, 225, 0.95);
    border: 1px solid rgba(99, 150, 120, 0.18);
    border-radius: 999px;
    padding: 0.32rem 0.68rem;
    margin-bottom: 0.75rem;
}

.quickstart-title {
    font-size: 1.28rem;
    font-weight: 800;
    color: #3a2c1e;
    margin-bottom: 0.28rem;
}

.quickstart-copy {
    color: rgba(58, 44, 30, 0.78);
    line-height: 1.55;
    margin-bottom: 0.85rem;
}

.quickstart-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.85rem;
}

.quickstart-card {
    background: rgba(255, 252, 247, 0.9);
    border: 1px solid rgba(177, 135, 67, 0.14);
    border-radius: 20px;
    padding: 0.9rem 0.95rem;
}

.quickstart-card-title {
    font-size: 0.95rem;
    font-weight: 800;
    color: #2e241a;
    margin-bottom: 0.28rem;
}

.quickstart-card-copy {
    font-size: 0.92rem;
    line-height: 1.5;
    color: #5a5147;
}

.context-summary-shell {
    width: min(100%, 68rem);
    margin: 0 auto 0.95rem auto;
    padding: 0.95rem 1rem;
    border-radius: 22px;
    background: rgba(245, 250, 255, 0.9);
    border: 1px solid rgba(63, 104, 150, 0.14);
    box-shadow: 0 12px 28px rgba(43, 67, 104, 0.07);
}

.context-summary-title {
    font-size: 0.95rem;
    font-weight: 800;
    color: #2f3f58;
    margin-bottom: 0.45rem;
}

.context-summary-copy {
    font-size: 0.92rem;
    line-height: 1.5;
    color: #49566a;
}

.right-rail-shell {
    width: 100%;
    padding: 0.95rem 1rem 0.85rem;
    border-radius: 22px;
    background: rgba(255, 251, 246, 0.92);
    border: 1px solid rgba(177, 135, 67, 0.16);
    box-shadow: 0 14px 32px rgba(104, 72, 28, 0.08);
}

.right-rail-brand {
    width: 100%;
    display: flex;
    justify-content: center;
    margin-bottom: 0.8rem;
}

.right-rail-brand img {
    width: min(100%, 124px);
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.84);
    border: 1px solid rgba(177, 135, 67, 0.14);
    box-shadow: 0 14px 28px rgba(43, 67, 104, 0.1);
    padding: 0.55rem;
}

.right-rail-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #2d5b44;
    background: rgba(214, 239, 225, 0.95);
    border: 1px solid rgba(99, 150, 120, 0.18);
    border-radius: 999px;
    padding: 0.32rem 0.68rem;
    margin-bottom: 0.72rem;
}

.right-rail-title {
    font-size: 1.06rem;
    font-weight: 800;
    color: #33271c;
    margin-bottom: 0.28rem;
}

.right-rail-copy {
    font-size: 0.92rem;
    line-height: 1.5;
    color: #5a5147;
    margin-bottom: 0.75rem;
}

.right-rail-note {
    margin-top: 0.8rem;
    font-size: 0.86rem;
    line-height: 1.45;
    color: #6a5d4f;
    padding-top: 0.7rem;
    border-top: 1px solid rgba(177, 135, 67, 0.14);
}

.right-rail-note-empty {
    color: #4a3422;
    text-align: center;
    font-weight: 600;
}

/* Make selected radio controls feel lighter and more aligned with the Aura palette. */
.stApp input[type="radio"] {
    accent-color: #6b7280;
}

.stApp [data-testid="stRadio"] [role="radio"][aria-checked="true"],
.stApp [data-testid="stRadio"] [role="radio"][aria-checked="true"] * {
    color: #6b7280 !important;
}

.stApp [data-testid="stRadio"] [role="radio"][aria-checked="true"]::before,
.stApp [data-testid="stRadio"] [role="radio"][aria-checked="true"]::after,
.stApp [data-testid="stRadio"] [role="radio"][aria-checked="true"] svg,
.stApp [data-testid="stRadio"] [role="radio"][aria-checked="true"] path {
    border-color: #6b7280 !important;
    background-color: #6b7280 !important;
    fill: #6b7280 !important;
    stroke: #6b7280 !important;
}

.stApp div[data-baseweb="radio"] input[type="radio"]:checked + div {
    border-color: #6b7280 !important;
}

.stApp div[data-baseweb="radio"] input[type="radio"]:checked + div > div {
    background-color: #6b7280 !important;
}

.stApp div[data-baseweb="radio"] [aria-checked="true"] {
    color: #2f3f58;
}

.stApp [data-testid="stVerticalBlockBorderWrapper"]:has(.right-rail-flag) {
    position: sticky;
    top: 7.2rem;
    align-self: flex-start;
}

.artist-hero-card {
    background: linear-gradient(135deg, rgba(235, 247, 243, 0.94) 0%, rgba(255, 249, 240, 0.94) 100%);
    border: 1px solid rgba(99, 150, 120, 0.18);
    border-radius: 24px;
    padding: 1rem;
    box-shadow: 0 14px 32px rgba(66, 98, 73, 0.08);
}

.artist-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #2d5b44;
    background: rgba(214, 239, 225, 0.95);
    border: 1px solid rgba(99, 150, 120, 0.18);
    border-radius: 999px;
    padding: 0.32rem 0.68rem;
    margin-bottom: 0.7rem;
}

.artist-name {
    font-size: 1.45rem;
    font-weight: 800;
    color: #2f2418;
    margin-bottom: 0.18rem;
}

.artist-years {
    font-size: 0.95rem;
    color: rgba(63, 44, 31, 0.76);
    margin-bottom: 0.7rem;
}

.artist-statline {
    font-size: 0.95rem;
    line-height: 1.55;
    color: #304635;
}

.artist-bio {
    margin-top: 0.85rem;
    font-size: 0.97rem;
    line-height: 1.65;
    color: #4b4338;
}

.artist-link {
    display: inline-block;
    margin-top: 0.8rem;
    font-size: 0.92rem;
    font-weight: 700;
    color: #25543f;
    text-decoration: none;
}

.online-match-shell {
    margin-top: 1rem;
    margin-bottom: 0.85rem;
    padding: 0.9rem 1rem 0.8rem;
    border-radius: 20px;
    background: rgba(255, 249, 241, 0.9);
    border: 1px solid rgba(177, 135, 67, 0.16);
}

.online-match-title {
    font-size: 1rem;
    font-weight: 800;
    color: #4a3422;
    text-align: center;
    margin-bottom: 0.18rem;
}

.online-match-copy {
    font-size: 0.9rem;
    line-height: 1.45;
    color: #6a5240;
    text-align: center;
}

.online-match-card {
    margin-top: 0.45rem;
    margin-bottom: 1rem;
    padding: 0.75rem 0.8rem;
    border-radius: 18px;
    background: rgba(255, 252, 247, 0.88);
    border: 1px solid rgba(177, 135, 67, 0.14);
}

.online-match-meta {
    font-size: 0.92rem;
    line-height: 1.5;
    color: #4a3422;
}

.app-signature {
    position: fixed;
    right: 1.15rem;
    bottom: 1rem;
    z-index: 999;
    text-align: right;
    font-size: 0.88rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: rgba(74, 60, 48, 0.86);
}

.app-signature span {
    display: inline-block;
    padding: 0.48rem 0.88rem;
    border-radius: 999px;
    background: rgba(255, 249, 241, 0.8);
    border: 1px solid rgba(177, 135, 67, 0.2);
    box-shadow: 0 10px 18px rgba(104, 72, 28, 0.08);
    backdrop-filter: blur(8px);
}
</style>
""".replace("BACKGROUND_LAYERS_VALUE", background_layers)

# Inyectamos el CSS generado en la página para que la app tenga su estilo completo al cargar.
st.markdown(css_background, unsafe_allow_html=True)

# Cabecera visual fija de la app: logo y subtítulo.
st.markdown(
    f"""<div class="page-top-spacer"></div>
    <div class="hero-shell">
        <div class="app-title-row">
            <div class="brand-mark">
                <img src="{logo_image_url or ''}" alt="Aura Gemini logo" />
            </div>
        </div>
        <div class="app-subtitle">
            This is a tool that helps you scan art and get information about it 🖌
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Tipos de archivo permitidos en el chat con imágenes.
SUPPORTED_IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"]


# --------------------------------------------
# Estado de sesión
# --------------------------------------------
if "messages" not in st.session_state:
    # La conversación empieza con un mensaje guía del asistente.
    st.session_state.messages = [{"role": "assistant", "content": "Upload an image to uncover its artistic style, influences, and connections. But first, tell me your name to personalize your experience"}]

if "editing_message_index" not in st.session_state:
    # Guarda el índice del mensaje del usuario que se está editando.
    st.session_state.editing_message_index = None

if "pending_regeneration" not in st.session_state:
    # Indica que debe regenerarse una respuesta después de guardar una edición.
    st.session_state.pending_regeneration = None

if "selected_artist_context_name" not in st.session_state:
    # Artista de referencia opcional para análisis de imágenes.
    st.session_state.selected_artist_context_name = None

if "selected_met_object_context_id" not in st.session_state:
    # Objeto del MET de referencia opcional para análisis de imágenes.
    st.session_state.selected_met_object_context_id = None

if "active_primary_panel" not in st.session_state:
    # Sección principal visible en el área central.
    st.session_state.active_primary_panel = "Chat Studio"

def serialize_uploaded_images(uploaded_files):
    """Convierte archivos subidos en Streamlit a una estructura serializable en memoria.

    Cada imagen conserva:
    - el nombre original del archivo,
    - el tipo MIME,
    - los bytes crudos para renderizarla en Streamlit,
    - y una data URL en base64 para enviarla al modelo multimodal.
    """
    # Guardamos los archivos como bytes y como data URL para reutilizarlos en UI y en el modelo.
    images = []

    for uploaded_file in uploaded_files or []:
        file_bytes = uploaded_file.getvalue()
        mime_type = uploaded_file.type or "application/octet-stream"
        data_url = f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode('utf-8')}"

        images.append(
            {
                "name": uploaded_file.name,
                "mime_type": mime_type,
                "bytes": file_bytes,
                "data_url": data_url,
            }
        )

    return images


def get_image_display_kwargs():
    """Devuelve argumentos de renderizado compatibles con varias versiones de Streamlit.

    Las versiones nuevas prefieren ``width="stretch"``, mientras que las más
    antiguas todavía usan ``use_column_width=True``.
    """
    # Streamlit cambia la API de imágenes entre versiones; detectamos qué opción soporta.
    image_signature = inspect.signature(st.image)

    if "use_container_width" in image_signature.parameters:
        return {"width": "stretch"}

    if "use_column_width" in image_signature.parameters:
        return {"use_column_width": True}

    return {}


def normalize_text_list(values, limit=6):
    """Normaliza una lista de strings cortos para usarla en UI o búsquedas."""
    # Quitamos duplicados, espacios sobrantes y limitamos el número de elementos.
    normalized = []

    for value in values or []:
        text = str(value).strip()
        if not text:
            continue
        if text.lower() in {item.lower() for item in normalized}:
            continue
        normalized.append(text)
        if len(normalized) >= limit:
            break

    return normalized


def render_images(message):
    """Renderiza todas las imágenes adjuntas a un mismo mensaje de chat."""
    # Cada imagen del mensaje se pinta en orden para conservar el contexto original.
    for image in message.get("images", []):
        st.image(
            image["bytes"],
            caption=image["name"],
            **get_image_display_kwargs(),
        )


@st.cache_data(show_spinner=False, ttl=60 * 60 * 8)
def fetch_remote_image_bytes(image_url, source_name=""):
    """Descarga una miniatura remota para mostrarla en Streamlit sin depender del navegador."""
    if not image_url:
        return None

    # Añadimos cabeceras básicas para evitar bloqueos por hotlinking en algunas fuentes.
    headers = {
        "User-Agent": AIC_USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    if source_name == "Art Institute of Chicago API":
        headers["AIC-User-Agent"] = AIC_USER_AGENT

    try:
        response = requests.get(
            image_url,
            headers=headers,
            timeout=SIMILAR_WEB_SEARCH_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    content_type = response.headers.get("content-type", "").lower()
    if "image" not in content_type and not response.content:
        return None

    return response.content


def render_online_matches(message):
    """Muestra una galería compacta con coincidencias encontradas en la web."""
    online_matches = message.get("online_matches") or []
    if not online_matches:
        return

    # Creamos un resumen de procedencia para que el usuario entienda de dónde vienen los resultados.
    source_labels = normalize_text_list(
        [match.get("source_name", "Online collection") for match in online_matches],
        limit=6,
    )
    source_summary = ", ".join(source_labels)

    st.markdown(
        f"""
        <div class="online-match-shell">
            <div class="online-match-title">Similar Works Found Online</div>
            <div class="online-match-copy">
                Possible visual matches from {html.escape(source_summary)}. Treat them as references, not definitive attributions.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Repartimos la galería en dos columnas para mantenerla compacta y legible.
    gallery_cols = st.columns(2)
    for index, match in enumerate(online_matches):
        with gallery_cols[index % 2]:
            # Intentamos usar bytes descargados; si no existen, los obtenemos en tiempo de render.
            image_url = match.get("image_url")
            image_bytes = match.get("image_bytes")
            if image_url and image_bytes is None:
                image_bytes = fetch_remote_image_bytes(
                    image_url,
                    source_name=str(match.get("source_name", "")),
                )

            if image_bytes:
                st.image(image_bytes, caption=match.get("title", "Untitled"), **get_image_display_kwargs())
            else:
                st.caption("Preview image unavailable for this source.")

            creator = match.get("creator", "Unknown artist")
            period = match.get("period", "Period unavailable")
            source_url = match.get("source_url", "")

            st.markdown(
                f"""
                <div class="online-match-card">
                    <div class="online-match-meta"><strong>Author:</strong> {html.escape(str(creator))}</div>
                    <div class="online-match-meta"><strong>Period:</strong> {html.escape(str(period))}</div>
                    <div class="online-match-meta"><strong>Source:</strong> {html.escape(str(match.get("source_name", "Online collection")))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if source_url:
                st.markdown(
                    f'[Open source page]({html.escape(source_url, quote=True)})'
                )


def render_role_marker(role):
    """Renderiza una pequeña etiqueta de rol usada como marca visual y hook de CSS."""
    if role == "assistant":
        st.markdown(
            """
            <div class="message-role assistant-marker">
                <span>Art Guide</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        """
        <div class="message-role user-marker">
            <span>Your Prompt</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_audience_menu():
    """Renderiza un menú lateral curado con perfiles a quienes puede interesar el arte."""
    with st.sidebar:
        # La barra lateral resume el propósito de la app y ofrece perfiles de uso.
        st.markdown("## Start Here")
        st.caption("Aura helps you explore art, compare references, and analyze uploaded images with guided context.")

        with st.expander("How to use Aura", expanded=True):
            st.markdown("**1. Chat with an artwork**")
            st.write("Upload an image or type a question to get an explanation, interpretation, or comparison.")
            st.markdown("**2. Browse references**")
            st.write("Open the Artist Explorer or MET Object Explorer to find a relevant reference.")
            st.markdown("**3. Activate context**")
            st.write("Use a selected artist or object as optional context so the chat can answer more precisely.")

        st.markdown("## Who Might Love Aura Art Scanner?")
        st.caption("A quick guide to the kinds of people this experience can speak to.")

        selected_label = st.radio(
            "Audience profile",
            options=[profile["label"] for profile in AUDIENCE_PROFILES],
            label_visibility="collapsed",
        )

        profile = next(
            item for item in AUDIENCE_PROFILES if item["label"] == selected_label
        )

        st.markdown(
            f"""
            <div class="sidebar-profile-card">
                <div class="sidebar-profile-kicker">
                    <span>{profile["icon"]}</span>
                    <span>Art Audience</span>
                </div>
                <div class="sidebar-profile-title">{profile["label"]}</div>
                <div class="sidebar-profile-copy">{profile["description"]}</div>
                <div class="sidebar-profile-focus"><strong>Why it fits:</strong> {profile["focus"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.image(profile["image_url"], **get_image_display_kwargs())
        st.caption(profile["image_credit"])

        with st.expander("See all profiles"):
            for item in AUDIENCE_PROFILES:
                st.markdown(f"**{item['icon']} {item['label']}**")
                st.write(item["description"])


def render_quick_start():
    """Muestra una guía breve para entender la app de un vistazo."""
    # Bloque de entrada para que el usuario entienda Aura sin leer documentación externa.
    st.markdown(
        """
        <div class="quickstart-shell">
            <div class="quickstart-kicker">How Aura Works</div>
            <div class="quickstart-title">Explore art in three simple ways</div>
            <div class="quickstart-copy">
                Ask questions, upload an artwork image, or activate a local reference from your datasets. Aura will use that context to make the conversation more grounded and easier to follow.
            </div>
            <div class="quickstart-grid">
                <div class="quickstart-card">
                    <div class="quickstart-card-title">Chat</div>
                    <div class="quickstart-card-copy">Ask about style, symbolism, influences, movements, or historical context.</div>
                </div>
                <div class="quickstart-card">
                    <div class="quickstart-card-title">Upload Images</div>
                    <div class="quickstart-card-copy">Send one or more artwork images so Aura can compare visual evidence with your prompt.</div>
                </div>
                <div class="quickstart-card">
                    <div class="quickstart-card-title">Use References</div>
                    <div class="quickstart-card-copy">Pick an artist or a museum object to guide the response without forcing a match.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_active_context_summary():
    """Resume el contexto activo para que el usuario entienda lo que guiara el chat."""
    active_artist = get_artist_record_by_name(
        st.session_state.get("selected_artist_context_name")
    )
    active_met_object = get_met_object_record_by_id(
        st.session_state.get("selected_met_object_context_id")
    )

    # Si no hay contexto local activo, se informa explícitamente y terminamos.
    if active_artist is None and active_met_object is None:
        st.markdown(
            """
            <div class="context-summary-shell">
                <div class="context-summary-title">Current Chat Mode</div>
                <div class="context-summary-copy">
                    No local reference is active. Aura will answer from your prompt and any uploaded images only.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    parts = []
    if active_artist is not None:
        parts.append(
            f"<strong>Artist reference:</strong> {html.escape(str(active_artist['name']))} | {html.escape(str(active_artist['nationality']))} | {html.escape(str(active_artist['genre']))}"
        )

    if active_met_object is not None:
        parts.append(
            f"<strong>Object reference:</strong> {html.escape(str(active_met_object['title']))} | {html.escape(str(active_met_object['artistDisplayName']))} | {html.escape(str(active_met_object['department']))}"
        )

    st.markdown(
        f"""
        <div class="context-summary-shell">
            <div class="context-summary-title">Current Chat Mode</div>
            <div class="context-summary-copy">
                {'<br/>'.join(parts)}<br/><br/>
                Aura will use this as optional context, but it should still check your image and prompt before making claims.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_right_navigation():
    """Renderiza un menú vertical a la derecha para navegar entre secciones."""
    st.markdown(
        """
        <div class="right-rail-flag"></div>
        <div class="right-rail-shell">
            <div class="right-rail-kicker">Navigate Aura</div>
            <div class="right-rail-title">Choose a workspace</div>
            <div class="right-rail-copy">
                Move between the conversation, your artist references, and the museum object dataset without leaving the current screen.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # El radio define qué workspace se muestra en el área principal.
    selected_panel = st.radio(
        "Navigate Aura",
        options=["Chat Studio", "Artist Explorer", "MET Object Explorer"],
        index=["Chat Studio", "Artist Explorer", "MET Object Explorer"].index(
            st.session_state.get("active_primary_panel", "Chat Studio")
        ),
        key="active_primary_panel",
        label_visibility="collapsed",
    )

    active_artist = get_artist_record_by_name(
        st.session_state.get("selected_artist_context_name")
    )
    active_met_object = get_met_object_record_by_id(
        st.session_state.get("selected_met_object_context_id")
    )

    # Resumen compacto del contexto activo para la navegación.
    note_parts = []
    note_is_empty = False
    if active_artist is not None:
        note_parts.append(f"Artist active: {active_artist['name']}")
    if active_met_object is not None:
        note_parts.append(f"Object active: {active_met_object['title']}")
    if not note_parts:
        note_parts.append("No local reference active yet.")
        note_is_empty = True

    note_class = "right-rail-note right-rail-note-empty" if note_is_empty else "right-rail-note"
    st.markdown(
        f"""
        <div class="{note_class}">
            {'<br/>'.join(note_parts)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    return selected_panel


def render_artist_browser():
    """Muestra un explorador filtrable de artistas con previews locales."""
    artists_df = load_artists_collection()

    st.markdown(
        """
        <div class="artist-browser-shell">
            <div class="artist-browser-title">Artist Explorer</div>
            <div class="artist-browser-copy">
                Browse your local artist dataset by name, genre, and nationality, then preview a small gallery of works already stored on disk.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if artists_df.empty:
        st.info("No pude cargar `met_art_data/Artists2.csv`.")
        return

    query = st.text_input(
        "Search artists",
        placeholder="Artist name or keyword from the bio",
        label_visibility="collapsed",
        key="artist_search_query",
    ).strip().lower()

    genre_col, nation_col = st.columns([1.2, 1.2])

    with genre_col:
        genre_options = sorted(
            {
                genre.strip()
                for value in artists_df["genre"].astype(str)
                for genre in value.split(",")
                if genre.strip()
            }
        )
        selected_genres = st.multiselect(
            "Genre",
            genre_options,
            default=[],
            placeholder="All genres",
            label_visibility="collapsed",
            key="artist_genres",
        )

    with nation_col:
        nationality_options = sorted(
            value for value in artists_df["nationality"].dropna().astype(str).unique() if value
        )
        selected_nationalities = st.multiselect(
            "Nationality",
            nationality_options,
            default=[],
            placeholder="All nationalities",
            label_visibility="collapsed",
            key="artist_nationalities",
        )

    # Partimos del dataset completo y reducimos por búsqueda/filtros.
    filtered_df = artists_df.copy()

    if query:
        filtered_df = filtered_df[
            filtered_df["name"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["bio"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["genre"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["nationality"].astype(str).str.lower().str.contains(query, na=False)
        ]

    if selected_genres:
        genre_pattern = "|".join(re.escape(genre) for genre in selected_genres)
        filtered_df = filtered_df[
            filtered_df["genre"].astype(str).str.contains(genre_pattern, case=False, na=False)
        ]

    if selected_nationalities:
        filtered_df = filtered_df[
            filtered_df["nationality"].isin(selected_nationalities)
        ]

    filtered_df = filtered_df.sort_values(
        by=["image_count", "paintings", "name"],
        ascending=[False, False, True],
        na_position="last",
    )

    st.markdown(
        f'<div class="section-caption-dark">{len(filtered_df)} artist(s) match your filters.</div>',
        unsafe_allow_html=True,
    )

    if filtered_df.empty:
        st.warning("No artists match those filters yet. Try broadening the search.")
        return

    # El selectbox se alimenta con los nombres ya filtrados.
    artist_names = filtered_df["name"].tolist()
    default_name = artist_names[0]

    selected_name = st.selectbox(
        "Select artist",
        options=artist_names,
        index=0,
        label_visibility="collapsed",
        key="artist_selectbox",
    )

    selected_artist = filtered_df[filtered_df["name"] == selected_name].iloc[0]
    artist_images = get_artist_image_paths(selected_artist["artist_key"], limit=6)
    is_active_context = st.session_state.get("selected_artist_context_name") == selected_name
    related_artists = get_related_artists(selected_name, limit=3)

    details_col, gallery_col = st.columns([1.2, 1.55], vertical_alignment="top")

    with details_col:
        bio_text = str(selected_artist.get("bio", "Biography unavailable.")).strip()
        bio_excerpt = bio_text[:620].rsplit(" ", 1)[0] + "..." if len(bio_text) > 620 else bio_text
        paintings_value = selected_artist.get("paintings")
        paintings_label = int(paintings_value) if pd.notna(paintings_value) else "Unknown"
        wikipedia_url = str(selected_artist.get("wikipedia", "")).strip()
        wikipedia_link = (
            f'<a class="artist-link" href="{html.escape(wikipedia_url, quote=True)}" target="_blank" rel="noopener noreferrer">Open artist reference</a>'
            if wikipedia_url and wikipedia_url.lower() != "nan"
            else ""
        )

        st.markdown(
            f"""
            <div class="artist-hero-card">
                <div class="artist-kicker">Dataset Profile</div>
                <div class="artist-name">{html.escape(str(selected_artist['name']))}</div>
                <div class="artist-years">{html.escape(str(selected_artist['years']))}</div>
                <div class="artist-statline">
                    <strong>Nationality:</strong> {html.escape(str(selected_artist['nationality']))}<br/>
                    <strong>Genres:</strong> {html.escape(str(selected_artist['genre']))}<br/>
                    <strong>Paintings in dataset:</strong> {paintings_label}<br/>
                    <strong>Local previews:</strong> {len(artist_images)}
                </div>
                <div class="artist-bio">{html.escape(bio_excerpt)}</div>
                {wikipedia_link}
            </div>
            """,
            unsafe_allow_html=True,
        )

        action_col, clear_col = st.columns([1.4, 1], vertical_alignment="center")
        with action_col:
            button_label = "Using this artist as reference" if is_active_context else "Use this artist for image analysis"
            if st.button(
                button_label,
                key=f"use_artist_context_{selected_artist['artist_key']}",
                disabled=is_active_context,
                use_container_width=True,
            ):
                st.session_state.selected_artist_context_name = selected_name
                st.rerun()

        with clear_col:
            if st.button(
                "Clear reference",
                key=f"clear_artist_context_{selected_artist['artist_key']}",
                disabled=st.session_state.get("selected_artist_context_name") is None,
                use_container_width=True,
            ):
                st.session_state.selected_artist_context_name = None
                st.rerun()

        if related_artists:
            related_names = ", ".join(candidate["name"] for candidate in related_artists)
            st.markdown(
                f'<div class="section-caption-dark">Nearby references in your dataset: {related_names}</div>',
                unsafe_allow_html=True,
            )

    with gallery_col:
        if not artist_images:
            st.info("No local previews found for this artist in `met_art_data/resized 3`.")
        else:
            image_cols = st.columns(3)
            for index, image_path in enumerate(artist_images):
                preview = load_met_thumbnail(image_path, max_size=(340, 340))
                with image_cols[index % 3]:
                    if preview is not None:
                        st.image(preview, width=210)
 


def render_met_object_browser():
    """Muestra un explorador filtrable de obras del MET con imagen local."""
    met_df = load_met_collection()

    st.markdown(
        """
        <div class="met-browser-shell">
            <div class="met-browser-title">MET Object Explorer</div>
            <div class="met-browser-copy">
                Browse the new museum object dataset by title, artist, department, period, and year, then preview the local image extracted from the archive.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if met_df.empty:
        st.info("No pude cargar `met_art_data2/metadata_cleaned_updated.csv`.")
        return

    query = st.text_input(
        "Search works",
        placeholder="Title, artist, medium, culture, or department",
        label_visibility="collapsed",
        key="met_search_query",
    ).strip().lower()

    dept_col, period_col, role_col = st.columns([1.2, 1.2, 1.0])

    with dept_col:
        department_options = sorted(
            value for value in met_df["department"].dropna().astype(str).unique() if value
        )
        selected_departments = st.multiselect(
            "Department",
            department_options,
            default=[],
            placeholder="All departments",
            label_visibility="collapsed",
            key="met_departments",
        )

    with period_col:
        period_options = sorted(
            value for value in met_df["period"].dropna().astype(str).unique() if value
        )
        selected_periods = st.multiselect(
            "Period",
            period_options,
            default=[],
            placeholder="All periods",
            label_visibility="collapsed",
            key="met_periods",
        )

    with role_col:
        role_options = sorted(
            value for value in met_df["artistRole"].dropna().astype(str).unique() if value
        )
        selected_roles = st.multiselect(
            "Role",
            role_options,
            default=[],
            placeholder="All roles",
            label_visibility="collapsed",
            key="met_roles",
        )

    # Aplicamos los filtros de texto, categoría y año sobre una copia del dataset.
    filtered_df = met_df.copy()

    if query:
        query_mask = (
            filtered_df["title"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["artistDisplayName"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["artistRole"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["objectDate"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["medium"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["department"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["culture"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["period"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["dimensions"].astype(str).str.lower().str.contains(query, na=False)
            | filtered_df["objectID"].astype(str).str.contains(query, na=False)
        )
        filtered_df = filtered_df[query_mask]

    if selected_departments:
        filtered_df = filtered_df[filtered_df["department"].isin(selected_departments)]

    if selected_periods:
        filtered_df = filtered_df[filtered_df["period"].isin(selected_periods)]

    if selected_roles:
        filtered_df = filtered_df[filtered_df["artistRole"].isin(selected_roles)]

    year_values = filtered_df["object_year"].dropna()
    if not year_values.empty:
        year_min = int(year_values.min())
        year_max = min(int(year_values.max()), 2026)
        year_min = min(year_min, year_max)
        if year_min < year_max:
            year_range = st.slider(
                "Object year",
                min_value=year_min,
                max_value=year_max,
                value=(year_min, year_max),
                key="met_year_range",
            )
            filtered_df = filtered_df[
                filtered_df["object_year"].isna()
                | filtered_df["object_year"].between(year_range[0], year_range[1])
            ]
        else:
            st.caption(f"Object year: {year_min}")

    filtered_df = filtered_df.sort_values(
        by=["object_year", "department", "artistDisplayName", "title"],
        ascending=[False, True, True, True],
        na_position="last",
    )

    st.markdown(
        f'<div class="section-caption-dark">{len(filtered_df)} object(s) match your filters.</div>',
        unsafe_allow_html=True,
    )

    if filtered_df.empty:
        st.warning("No objects match those filters yet. Try broadening the search.")
        return

    # Etiquetas largas para que el usuario identifique rápidamente cada obra.
    object_labels = {
        row["objectID"]: f"{row.get('title', 'Untitled')} — {row.get('artistDisplayName', 'Unknown Artist')} ({row.get('objectDate', 'Date unavailable')})"
        for _, row in filtered_df.iterrows()
    }

    selected_object_id = st.selectbox(
        "Select object",
        options=list(object_labels.keys()),
        format_func=lambda oid: object_labels.get(oid, str(oid)),
        label_visibility="collapsed",
        key="met_object_selectbox",
    )

    selected_object = filtered_df[filtered_df["objectID"] == selected_object_id].iloc[0]
    selected_image = selected_object.get("resolved_image_path")
    is_active_context = st.session_state.get("selected_met_object_context_id") == selected_object_id
    related_objects = get_related_met_objects(selected_object, limit=3)

    details_col, preview_col = st.columns([1.25, 1.45], vertical_alignment="top")

    with details_col:
        title_text = str(selected_object.get("title", "Untitled")).strip()
        artist_text = str(selected_object.get("artistDisplayName", "Unknown Artist")).strip()
        date_text = str(selected_object.get("objectDate", "Date unavailable")).strip()
        year_value = selected_object.get("object_year")
        year_label = int(year_value) if pd.notna(year_value) else "Unknown"
        object_url = str(selected_object.get("objectURL", "")).strip()
        object_link = (
            f'<a class="artist-link" href="{html.escape(object_url, quote=True)}" target="_blank" rel="noopener noreferrer">Open MET object page</a>'
            if object_url and object_url.lower() != "nan"
            else ""
        )

        st.markdown(
            f"""
            <div class="artist-hero-card">
                <div class="artist-kicker">Museum Object</div>
                <div class="artist-name">{html.escape(title_text)}</div>
                <div class="artist-years">{html.escape(artist_text)} | {html.escape(date_text)}</div>
                <div class="artist-statline">
                    <strong>Object ID:</strong> {selected_object.get('objectID', 'Unknown')}<br/>
                    <strong>Department:</strong> {html.escape(str(selected_object.get('department', 'Unknown department')))}<br/>
                    <strong>Period:</strong> {html.escape(str(selected_object.get('period', 'Unknown')) or 'Unknown')}<br/>
                    <strong>Culture:</strong> {html.escape(str(selected_object.get('culture', 'Unknown')) or 'Unknown')}<br/>
                    <strong>Medium:</strong> {html.escape(str(selected_object.get('medium', 'Unknown medium')))}<br/>
                    <strong>Dimensions:</strong> {html.escape(str(selected_object.get('dimensions', 'Dimensions unavailable')))}<br/>
                    <strong>Object year:</strong> {year_label}
                </div>
                {object_link}
            </div>
            """,
            unsafe_allow_html=True,
        )

        action_col, clear_col = st.columns([1.4, 1], vertical_alignment="center")
        with action_col:
            button_label = "Using this object as reference" if is_active_context else "Use this object for image analysis"
            if st.button(
                button_label,
                key=f"use_met_object_context_{selected_object_id}",
                disabled=is_active_context,
                use_container_width=True,
            ):
                st.session_state.selected_met_object_context_id = selected_object_id
                st.rerun()

        with clear_col:
            if st.button(
                "Clear reference",
                key=f"clear_met_object_context_{selected_object_id}",
                disabled=st.session_state.get("selected_met_object_context_id") is None,
                use_container_width=True,
            ):
                st.session_state.selected_met_object_context_id = None
                st.rerun()

        if related_objects:
            related_names = ", ".join(
                f"{candidate.get('title', 'Untitled')} ({candidate.get('artistDisplayName', 'Unknown Artist')})"
                for candidate in related_objects
            )
            st.markdown(
                f'<div class="section-caption-dark">Nearby references in your dataset: {related_names}</div>',
                unsafe_allow_html=True,
            )

    with preview_col:
        if not selected_image:
            st.info("No local preview found for this object in `met_art_data2/images_updated.zip`.")
        else:
            preview = load_met_thumbnail(selected_image, max_size=(440, 440))
            if preview is not None:
                st.image(preview, caption=title_text, **get_image_display_kwargs())
            else:
                st.info("The image file could not be opened locally.")


def save_edited_message(index, edited_text):
    """Guarda un mensaje editado y activa la regeneración de la respuesta.

    Cuando se modifica un mensaje anterior, el resto del historial puede dejar
    de ser coherente. Por eso se recorta la conversación hasta ese punto y se
    vuelve a generar la respuesta del asistente desde ahí.
    """
    # Recuperamos el mensaje original antes de reemplazarlo.
    current_message = st.session_state.messages[index]
    normalized_text = edited_text.strip()

    if not normalized_text and not current_message.get("images"):
        st.warning("Write a message or keep at least one attached image.")
        return

    current_message["content"] = normalized_text
    # Cortamos el historial posterior para que la regeneración parta desde un estado consistente.
    st.session_state.messages = st.session_state.messages[: index + 1]
    st.session_state.editing_message_index = None
    st.session_state.pending_regeneration = index
    st.rerun()


def extract_json_object(raw_text):
    """Intenta recuperar un objeto JSON incluso si el modelo lo envuelve en fences."""
    if not raw_text:
        return None

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Si el modelo añadió texto alrededor, intentamos extraer el primer bloque JSON.
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def build_similar_art_search_queries(search_hints, fallback_text=""):
    """Construye varias consultas cortas para recuperar obras similares en la web."""
    queries = []
    artists = normalize_text_list(search_hints.get("likely_artists", []), limit=3)
    terms = normalize_text_list(search_hints.get("search_terms", []), limit=6)
    style = str(search_hints.get("likely_style", "")).strip()
    period = str(search_hints.get("likely_period", "")).strip()
    object_type = str(search_hints.get("object_type", "")).strip()
    material_terms = normalize_text_list(search_hints.get("material_terms", []), limit=4)

    # Empezamos por combinaciones centradas en artista, tipo de objeto y estilo.
    if artists:
        queries.append(" ".join(part for part in [artists[0], object_type, style] if part))
        queries.append(" ".join(part for part in [artists[0]] + material_terms[:2] if part))

    if object_type and artists:
        queries.append(" ".join(part for part in [artists[0], object_type, period] if part))

    if style and terms:
        queries.append(" ".join([style, object_type] + terms[:2]).strip())

    if period and terms:
        queries.append(" ".join([period, object_type] + terms[:2]).strip())

    if terms:
        queries.append(" ".join(([object_type] if object_type else []) + terms[:4]).strip())

    fallback_text = re.sub(r"\s+", " ", str(fallback_text)).strip()
    # Si todo lo demás falla, reutilizamos el texto libre del usuario como respaldo.
    if fallback_text:
        queries.append(fallback_text[:120])

    deduped = []
    seen = set()
    for query in queries:
        normalized = query.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        deduped.append(normalized)
        seen.add(key)
        if len(deduped) >= 4:
            break

    return deduped


def normalize_object_type(value):
    """Reduce tipos de obra a unas pocas familias comparables entre APIs."""
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

    # Traducimos descripciones libres a categorías más estables entre fuentes.
    for canonical, keywords in mapping.items():
        if any(keyword in text for keyword in keywords):
            return canonical

    return text


def build_match_haystack(match):
    """Reune metadata textual de una coincidencia para scoring y filtros."""
    return " ".join(
        [
            str(match.get("title", "")),
            str(match.get("creator", "")),
            str(match.get("period", "")),
            str(match.get("department", "")),
            str(match.get("medium", "")),
            str(match.get("culture", "")),
            str(match.get("object_type", "")),
        ]
    ).lower()


def same_artist_match(match, search_hints):
    """Detecta coincidencia por artista de forma tolerante."""
    creator = str(match.get("creator", "")).strip().lower()
    if not creator or creator == "unknown artist":
        return False

    primary_artist = str(search_hints.get("primary_artist", "")).strip().lower()
    likely_artists = [artist.lower() for artist in search_hints.get("likely_artists", [])]
    artist_candidates = [artist for artist in [primary_artist] + likely_artists if artist]

    # Permitimos coincidencias parciales porque cada API escribe el autor de forma distinta.
    for artist in artist_candidates:
        if artist == creator or artist in creator or creator in artist:
            return True

    return False


def score_online_match(match, search_hints):
    """Asigna una puntuación simple a una coincidencia según pistas del modelo."""
    artists = [artist.lower() for artist in search_hints.get("likely_artists", [])]
    style = str(search_hints.get("likely_style", "")).lower()
    period = str(search_hints.get("likely_period", "")).lower()
    terms = [term.lower() for term in search_hints.get("search_terms", [])]
    material_terms = [term.lower() for term in search_hints.get("material_terms", [])]
    expected_object_type = normalize_object_type(search_hints.get("object_type", ""))
    match_object_type = normalize_object_type(match.get("object_type", ""))

    haystack = build_match_haystack(match)

    # El mismo artista pesa más que cualquier otra señal.
    score = 0
    if same_artist_match(match, search_hints):
        score += 12
    elif artists and any(artist in haystack for artist in artists):
        score += 5
    if expected_object_type and match_object_type == expected_object_type:
        score += 7
    elif expected_object_type and expected_object_type in haystack:
        score += 3
    if style and style in haystack:
        score += 3
    if period and period in haystack:
        score += 2
    score += sum(2 for term in material_terms if term in haystack)
    score += sum(1 for term in terms if term in haystack)
    return score


@st.cache_data(show_spinner=False, ttl=60 * 60 * 8)
def search_met_collection_online(query, has_images=True):
    """Busca IDs de objetos en la API pública del Met."""
    if not query:
        return []

    try:
        response = requests.get(
            f"{MET_PUBLIC_API_BASE_URL}/search",
            params={
                "q": query,
                "hasImages": str(bool(has_images)).lower(),
            },
            timeout=SIMILAR_WEB_SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    # Devolvemos solo IDs enteros válidos para las siguientes llamadas.
    object_ids = payload.get("objectIDs") or []
    return [object_id for object_id in object_ids if isinstance(object_id, int)]


@st.cache_data(show_spinner=False, ttl=60 * 60 * 8)
def fetch_met_object_online(object_id):
    """Recupera metadata de un objeto del Met desde la API pública."""
    try:
        response = requests.get(
            f"{MET_PUBLIC_API_BASE_URL}/objects/{object_id}",
            timeout=SIMILAR_WEB_SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    # Preferimos la miniatura pequeña, pero caemos a la imagen principal si hace falta.
    image_url = payload.get("primaryImageSmall") or payload.get("primaryImage")
    if not image_url:
        return None

    title = str(payload.get("title", "")).strip()
    if not title:
        return None

    creator = str(payload.get("artistDisplayName", "")).strip() or "Unknown artist"
    period = (
        str(payload.get("objectDate", "")).strip()
        or str(payload.get("period", "")).strip()
        or str(payload.get("culture", "")).strip()
        or "Period unavailable"
    )

    return {
        "object_id": object_id,
        "title": title,
        "creator": creator,
        "period": period,
        "image_url": image_url,
        "source_url": str(payload.get("objectURL", "")).strip(),
        "source_name": "The Met Collection API",
        "department": str(payload.get("department", "")).strip(),
        "medium": str(payload.get("medium", "")).strip(),
        "culture": str(payload.get("culture", "")).strip(),
        "object_type": normalize_object_type(
            payload.get("classification")
            or payload.get("objectName")
            or payload.get("medium")
            or ""
        ),
    }


@st.cache_data(show_spinner=False, ttl=60 * 60 * 8)
def search_aic_collection_online(query, limit=8):
    """Busca obras en la API del Art Institute of Chicago."""
    if not query:
        return []

    try:
        response = requests.get(
            f"{AIC_API_BASE_URL}/artworks/search",
            params={
                "q": query,
                "limit": limit,
                "fields": ",".join(
                    [
                        "id",
                        "title",
                        "artist_title",
                        "date_display",
                        "image_id",
                        "artwork_type_title",
                        "medium_display",
                        "classification_title",
                        "thumbnail",
                        "api_link",
                    ]
                ),
            },
            headers={"AIC-User-Agent": AIC_USER_AGENT},
            timeout=SIMILAR_WEB_SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    iiif_url = ""
    config = payload.get("config") or {}
    iiif_url = str(config.get("iiif_url", "")).strip()
    website_url = str(config.get("website_url", "https://www.artic.edu")).strip()
    results = []

    # Reconstruimos URLs IIIF y normalizamos metadatos para que encajen con el resto del pipeline.
    for item in payload.get("data") or []:
        title = str(item.get("title", "")).strip()
        image_id = str(item.get("image_id", "")).strip()
        if not title or not image_id:
            continue

        image_url = f"{iiif_url}/{image_id}/full/843,/0/default.jpg" if iiif_url else ""
        if not image_url:
            continue

        object_id = item.get("id")
        results.append(
            {
                "object_id": object_id,
                "title": title,
                "creator": str(item.get("artist_title", "")).strip() or "Unknown artist",
                "period": str(item.get("date_display", "")).strip() or "Period unavailable",
                "image_url": image_url,
                "source_url": (
                    f"{website_url}/artworks/{object_id}"
                    if object_id is not None
                    else str(item.get("api_link", "")).strip()
                ),
                "source_name": "Art Institute of Chicago API",
                "department": "",
                "medium": str(item.get("medium_display", "")).strip(),
                "culture": "",
                "object_type": normalize_object_type(
                    item.get("artwork_type_title")
                    or item.get("classification_title")
                    or item.get("medium_display")
                    or ""
                ),
            }
        )

    return results


@st.cache_data(show_spinner=False, ttl=60 * 60 * 8)
def search_cma_collection_online(query, limit=8):
    """Busca obras en la API abierta del Cleveland Museum of Art."""
    if not query:
        return []

    try:
        response = requests.get(
            f"{CMA_API_BASE_URL}/artworks/",
            params={
                "q": query,
                "has_image": 1,
                "limit": limit,
            },
            timeout=SIMILAR_WEB_SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
    # Esta API devuelve estructuras distintas, así que normalizamos autor, periodo e imagen.
    for item in payload.get("data") or []:
        title = str(item.get("title", "")).strip()
        images = item.get("images") or {}
        web_image = images.get("web") or {}
        image_url = str(web_image.get("url", "")).strip()
        if not title or not image_url:
            continue

        creators = item.get("creators") or []
        creator_names = []
        for creator in creators:
            if isinstance(creator, dict):
                name = str(creator.get("description") or creator.get("creator") or creator.get("name") or "").strip()
                if name:
                    creator_names.append(name)

        results.append(
            {
                "object_id": item.get("id"),
                "title": title,
                "creator": ", ".join(normalize_text_list(creator_names, limit=3)) or "Unknown artist",
                "period": (
                    str(item.get("date_text", "")).strip()
                    or str(item.get("creation_date", "")).strip()
                    or "Period unavailable"
                ),
                "image_url": image_url,
                "source_url": str(item.get("url", "")).strip(),
                "source_name": "Cleveland Museum of Art Open Access API",
                "department": str(item.get("department", "")).strip(),
                "medium": str(item.get("technique", "")).strip() or str(item.get("type", "")).strip(),
                "culture": str(item.get("culture", "")).strip(),
                "object_type": normalize_object_type(
                    item.get("type")
                    or item.get("technique")
                    or ""
                ),
            }
        )

    return results


def infer_similar_art_search_hints(latest_user_message, assistant_response):
    """Pide al modelo pistas estructuradas para buscar obras similares."""
    user_text = str(latest_user_message.get("content", "")).strip()
    prompt = """
Return JSON only. Do not add markdown.
Infer search hints to find visually similar artworks in museum collection APIs.
Use the uploaded image as the main signal and the assistant analysis only as a weak hint.

Schema:
{
  "primary_artist": "single best artist guess or empty string",
  "likely_artists": ["max 3 names"],
  "likely_period": "short period label",
  "likely_style": "short style label",
  "object_type": "painting, sculpture, ceramic, drawing, print, textile, photograph, decorative object, or empty string",
  "material_terms": ["up to 4 material or technique terms"],
  "search_terms": ["4 to 6 short visual keywords"]
}

Rules:
- If uncertain, return empty strings or an empty list.
- Keep search_terms short and concrete.
- Prefer identifying the kind of object before the style.
- If the image looks like a sculpture, utensil, vessel, ceramic object, or decorative object, say so.
- Do not invent exact artwork titles unless confidence is high.
""".strip()

    # Le pedimos al modelo que devuelva una estructura JSON compacta y fácil de consumir.
    try:
        completion = client_google.chat.completions.create(
            model=model_google,
            messages=[
                {"role": "system", "content": prompt},
                build_model_message(latest_user_message),
                {
                    "role": "user",
                    "content": (
                        "Assistant analysis hint:\n"
                        f"{assistant_response[:1800]}\n\n"
                        f"User text hint:\n{user_text or 'No extra user text.'}"
                    ),
                },
            ],
        )
    except Exception:
        return None

    raw_content = ""
    if completion and getattr(completion, "choices", None):
        raw_content = completion.choices[0].message.content or ""

    payload = extract_json_object(raw_content)
    if not isinstance(payload, dict):
        return None

    primary_artist = str(payload.get("primary_artist", "")).strip()
    likely_artists = normalize_text_list(payload.get("likely_artists", []), limit=3)
    if primary_artist and primary_artist.lower() not in {artist.lower() for artist in likely_artists}:
        likely_artists = normalize_text_list([primary_artist] + likely_artists, limit=3)

    return {
        "primary_artist": primary_artist,
        "likely_artists": likely_artists,
        "likely_period": str(payload.get("likely_period", "")).strip(),
        "likely_style": str(payload.get("likely_style", "")).strip(),
        "object_type": normalize_object_type(payload.get("object_type", "")),
        "material_terms": normalize_text_list(payload.get("material_terms", []), limit=4),
        "search_terms": normalize_text_list(payload.get("search_terms", []), limit=6),
    }


def find_online_similar_artworks(latest_user_message, assistant_response, limit=SIMILAR_WEB_MATCH_LIMIT):
    """Busca referencias visuales online sin interrumpir el flujo principal del chat."""
    if not latest_user_message or not latest_user_message.get("images"):
        return []

    if st.session_state.get("selected_artist_context_name") or st.session_state.get("selected_met_object_context_id"):
        return []

    # Primera capa: inferimos señales visuales y semánticas a partir de la imagen y la respuesta.
    search_hints = infer_similar_art_search_hints(latest_user_message, assistant_response)
    if not search_hints:
        return []

    # Segunda capa: construimos consultas más fuertes centradas en autor y tipo de objeto.
    artist_queries = []
    primary_artist = str(search_hints.get("primary_artist", "")).strip()
    object_type = str(search_hints.get("object_type", "")).strip()
    likely_period = str(search_hints.get("likely_period", "")).strip()
    material_terms = normalize_text_list(search_hints.get("material_terms", []), limit=3)
    if primary_artist:
        artist_queries.append(" ".join(part for part in [primary_artist, object_type] if part))
        artist_queries.append(" ".join(part for part in [primary_artist] + material_terms[:2] if part))
        artist_queries.append(" ".join(part for part in [primary_artist, likely_period] if part))

    queries = normalize_text_list(
        artist_queries + build_similar_art_search_queries(
            search_hints,
            fallback_text=latest_user_message.get("content", ""),
        ),
        limit=6,
    )
    if not queries:
        return []

    # Tercera capa: reunimos candidatos de varias fuentes públicas antes de puntuar.
    candidate_matches = []
    seen_keys = set()
    for query in queries:
        met_ids = search_met_collection_online(query)[:8]
        for object_id in met_ids:
            object_data = fetch_met_object_online(object_id)
            if object_data is None:
                continue
            key = (
                object_data.get("source_name", ""),
                object_data.get("title", "").strip().lower(),
                object_data.get("creator", "").strip().lower(),
            )
            if key in seen_keys:
                continue
            candidate_matches.append(object_data)
            seen_keys.add(key)

        for object_data in search_aic_collection_online(query, limit=6):
            key = (
                object_data.get("source_name", ""),
                object_data.get("title", "").strip().lower(),
                object_data.get("creator", "").strip().lower(),
            )
            if key in seen_keys:
                continue
            candidate_matches.append(object_data)
            seen_keys.add(key)

        for object_data in search_cma_collection_online(query, limit=6):
            key = (
                object_data.get("source_name", ""),
                object_data.get("title", "").strip().lower(),
                object_data.get("creator", "").strip().lower(),
            )
            if key in seen_keys:
                continue
            candidate_matches.append(object_data)
            seen_keys.add(key)

        if len(candidate_matches) >= 24:
            break

    if not candidate_matches:
        return []

    # Agrupamos por prioridad para que primero salgan las coincidencias más cercanas.
    grouped_matches = {
        "same_artist_same_type": [],
        "same_artist": [],
        "same_type": [],
        "general": [],
    }
    expected_object_type = normalize_object_type(search_hints.get("object_type", ""))

    for object_data in candidate_matches[:24]:
        score = score_online_match(object_data, search_hints)
        match_type = normalize_object_type(object_data.get("object_type", ""))
        is_same_artist = same_artist_match(object_data, search_hints)
        is_same_type = bool(expected_object_type) and match_type == expected_object_type
        if is_same_artist and is_same_type:
            grouped_matches["same_artist_same_type"].append((score, object_data))
        elif is_same_artist:
            grouped_matches["same_artist"].append((score, object_data))
        elif is_same_type:
            grouped_matches["same_type"].append((score, object_data))
        else:
            grouped_matches["general"].append((score, object_data))

    for bucket_name in grouped_matches:
        grouped_matches[bucket_name].sort(
            key=lambda item: (
                item[0],
                item[1].get("creator", "") != "Unknown artist",
                item[1].get("period", "") != "Period unavailable",
                bool(item[1].get("source_url", "")),
            ),
            reverse=True,
        )

    deduped = []
    seen_titles = set()
    source_buckets = {}

    for bucket_name in ["same_artist_same_type", "same_artist", "same_type", "general"]:
        for _, match in grouped_matches[bucket_name]:
            key = (match.get("title", "").strip().lower(), match.get("creator", "").strip().lower())
            if key in seen_titles:
                continue
            source_name = str(match.get("source_name", "Online collection")).strip() or "Online collection"
            source_buckets.setdefault((bucket_name, source_name), []).append(match)
            seen_titles.add(key)

    ordered_sources = sorted(
        source_buckets.keys(),
        key=lambda source_key: (
            ["same_artist_same_type", "same_artist", "same_type", "general"].index(source_key[0]),
            -max(
                score_online_match(candidate, search_hints) for candidate in source_buckets.get(source_key, [])
            ),
        ),
    )

    source_cycle = ordered_sources[:]
    while source_cycle and len(deduped) < limit:
        next_cycle = []
        for source_key in source_cycle:
            bucket = source_buckets.get(source_key, [])
            if not bucket:
                continue
            deduped.append(bucket.pop(0))
            if len(deduped) >= limit:
                break
            if bucket:
                next_cycle.append(source_key)
        source_cycle = next_cycle

    # Descargamos las miniaturas ya elegidas para que el render no dependa de hotlink directo.
    for match in deduped:
        match["image_bytes"] = fetch_remote_image_bytes(
            match.get("image_url", ""),
            source_name=str(match.get("source_name", "")),
        )

    return deduped


def render_message(message, index, container=None):
    """Renderiza un mensaje del chat, incluyendo imágenes y controles de edición."""
    target = container if container is not None else st
    is_editing = (
        message["role"] == "user"
        and st.session_state.editing_message_index == index
    )
    avatar = "🖌️" if message["role"] == "assistant" else "🎨"

    with target.chat_message(message["role"], avatar=avatar):
        render_role_marker(message["role"])

        # Si este mensaje está en edición, lo reemplazamos por un pequeño formulario.
        if is_editing:
            # Durante la edición, el cuerpo del mensaje se sustituye por un formulario.
            st.caption(
                "Edit the message and regenerate the conversation from this point."
            )
            render_images(message)

            with st.form(f"edit_message_form_{index}"):
                edited_text = st.text_area(
                    "Edit your message",
                    value=message.get("content", ""),
                    height=140,
                )
                save_clicked = st.form_submit_button("Save and regenerate")
                cancel_clicked = st.form_submit_button("Cancel")

            if save_clicked:
                save_edited_message(index, edited_text)

            if cancel_clicked:
                st.session_state.editing_message_index = None
                st.rerun()

            return

        # El texto del mensaje se muestra antes de las imágenes para mantener el flujo natural de lectura.
        if message.get("content"):
            st.write(message["content"])

        render_images(message)
        render_online_matches(message)

        # Solo los mensajes del usuario pueden reabrirse y editarse.
        if message["role"] == "user":
            # Solo los mensajes del usuario pueden editarse.
            if st.button("Edit message", key=f"edit_message_{index}"):
                st.session_state.editing_message_index = index
                st.rerun()


def build_model_message(message):
    """Convierte un mensaje interno al formato que espera la API del modelo.

    Los mensajes de solo texto se envían tal cual.
    Los mensajes con imágenes adjuntas se transforman en contenido multimodal:
    un bloque de texto y un bloque ``image_url`` por cada imagen.
    """
    # Si no hay imágenes, el mensaje se pasa tal cual.
    if message["role"] != "user" or not message.get("images"):
        return {"role": message["role"], "content": message["content"]}

    content = []
    text_content = message.get("content", "").strip()

    content.append(
        {
            "type": "text",
            "text": text_content or "Analyze the attached artwork image.",
        }
    )

    # Cada imagen se convierte en un bloque independiente para el modelo multimodal.
    for image in message["images"]:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": image["data_url"]},
            }
        )

    return {"role": "user", "content": content}


def get_messages_container_height(message_count):
    """Ajusta la altura del chat para evitar huecos grandes al inicio."""
    if message_count <= 1:
        return 360

    if message_count <= 3:
        return 500

    if message_count <= 6:
        return 600

    return 720


def get_user_submission(disabled=False):
    """Lee el envío actual desde un compositor estable basado en formulario.

    Se evita ``st.chat_input`` porque puede reposicionar la vista al montarse
    durante un refresh, lo que dificulta ver el encabezado al cargar la página.
    """
    # Si estamos editando un mensaje anterior, bloqueamos el envío nuevo.
    if disabled:
        st.info("Finish editing the selected message to continue chatting.")
        return None

    # Mostramos recordatorios del contexto activo para que el usuario sepa qué está guiando la respuesta.
    active_artist = get_artist_record_by_name(
        st.session_state.get("selected_artist_context_name")
    )

    if active_artist is not None:
        related_artists = get_related_artists(active_artist["name"], limit=3)
        alternatives_text = (
            " | Alternatives: "
            + ", ".join(candidate["name"] for candidate in related_artists)
            if related_artists
            else ""
        )
        st.info(
            "Image analysis reference active: "
            f"{active_artist['name']} | {active_artist['nationality']} | {active_artist['genre']}"
            f"{alternatives_text}"
        )

    active_met_object = get_met_object_record_by_id(
        st.session_state.get("selected_met_object_context_id")
    )

    if active_met_object is not None:
        related_met_objects = get_related_met_objects(active_met_object, limit=3)
        alternatives_text = (
            " | Alternatives: "
            + ", ".join(candidate.get("title", "Untitled") for candidate in related_met_objects)
            if related_met_objects
            else ""
        )
        st.info(
            "Object analysis reference active: "
            f"{active_met_object['title']} | {active_met_object['artistDisplayName']} | {active_met_object['department']}"
            f"{alternatives_text}"
        )

    # El formulario mantiene estable la interfaz y evita saltos de scroll innecesarios.
    with st.form("chat_with_image", clear_on_submit=True):
        st.markdown('<div class="composer-flag"></div>', unsafe_allow_html=True)

        input_col, send_col = st.columns([8.8, 1.2], vertical_alignment="center")

        with input_col:
            prompt_text = st.text_input(
                "Ask about art...",
                label_visibility="collapsed",
                placeholder="Upload an image of art and ask about it...",
            )

        with send_col:
            submitted = st.form_submit_button("↑", use_container_width=True)

        # El expander separa el texto del adjunto visual sin ocupar espacio fijo.
        with st.expander("Attach artwork images"):
            uploaded_files = st.file_uploader(
                "Attach artwork images",
                type=SUPPORTED_IMAGE_TYPES,
                accept_multiple_files=True,
                label_visibility="collapsed",
            )

        if uploaded_files:
            st.caption(f"{len(uploaded_files)} image(s) ready to send.")

    # Solo devolvemos un envío cuando hay texto o imágenes.
    if submitted and (prompt_text.strip() or uploaded_files):
        return {"text": prompt_text.strip(), "files": uploaded_files}

    return None


render_sidebar_audience_menu()

# Distribuimos la pantalla entre el contenido principal y la barra lateral derecha.
main_col, right_col = st.columns([5.1, 1.45], gap="large")
messages_container = None

with right_col:
    selected_panel = render_right_navigation()

with main_col:
    if selected_panel == "Chat Studio":
        # En la vista principal de chat mostramos ayuda rápida, contexto activo e historial.
        render_quick_start()
        render_active_context_summary()

        # Contenedor principal del historial de chat con scroll.
        messages_container = st.container(
            height=get_messages_container_height(len(st.session_state.messages)),
            border=True,
        )

        for index, msg in enumerate(st.session_state.messages):
            render_message(msg, index, container=messages_container)

    elif selected_panel == "Artist Explorer":
        # Explorador de artistas local con filtros y referencias de apoyo.
        st.markdown(
            '<div class="section-caption-dark">Browse artist profiles, preview works from your local dataset, and activate a reference for the chat.</div>',
            unsafe_allow_html=True,
        )
        render_artist_browser()

    elif selected_panel == "MET Object Explorer":
        # Explorador de objetos del MET con filtros y vista previa local.
        st.markdown(
            '<div class="section-caption-dark">Browse museum objects from your new dataset, inspect their metadata, and use them as grounded references.</div>',
            unsafe_allow_html=True,
        )
        render_met_object_browser()


def generate_assistant_reply(container):
    """Envía la conversación actual al modelo y muestra la respuesta en streaming."""
    conversation = [{"role": "system", "content": stronger_prompt}]

    latest_user_message = next(
        (message for message in reversed(st.session_state.messages) if message["role"] == "user"),
        None,
    )
    # Si hay un mensaje reciente del usuario, añadimos contexto local antes de responder.
    if latest_user_message is not None:
        artist_reference_message = build_artist_reference_message()
        if artist_reference_message is not None:
            conversation.append(artist_reference_message)

        met_object_reference_message = build_met_object_reference_message()
        if met_object_reference_message is not None:
            conversation.append(met_object_reference_message)

    conversation.extend(build_model_message(message) for message in st.session_state.messages)

    # Se acumulan aquí las coincidencias online que se van a mostrar al final.
    online_matches = []

    # El mensaje del asistente se renderiza en streaming para dar sensación de respuesta viva.
    with container.chat_message("assistant", avatar="🖌️"):
        render_role_marker("assistant")
        stream = client_google.chat.completions.create(
            model=model_google,
            messages=conversation,
            stream=True,
        )
        response = st.write_stream(stream)
        # Tras responder, intentamos enriquecer la salida con referencias externas si aplica.
        online_matches = find_online_similar_artworks(latest_user_message, response)
        if online_matches:
            render_online_matches({"online_matches": online_matches})

    # Guardamos también las coincidencias online para que persistan en reruns.
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response,
            "online_matches": online_matches,
        }
    )


if selected_panel == "Chat Studio" and messages_container is not None:
    # Si un mensaje anterior fue editado, regeneramos exactamente una vez.
    if st.session_state.pending_regeneration is not None:
        st.session_state.pending_regeneration = None
        generate_assistant_reply(messages_container)

    # Bloqueamos nuevos envíos mientras haya una edición pendiente.
    submission = get_user_submission(
        disabled=st.session_state.editing_message_index is not None
    )

    if submission:
        # Convertimos el envío del formulario en el formato de historial interno.
        user_message = {
            "role": "user",
            "content": submission["text"],
            "images": serialize_uploaded_images(submission["files"]),
        }

        st.session_state.messages.append(user_message)
        # Pintamos el nuevo mensaje antes de lanzar el streaming del asistente.
        render_message(
            user_message,
            len(st.session_state.messages) - 1,
            container=messages_container,
        )
        # Respuesta final basada en el historial ya actualizado.
        generate_assistant_reply(messages_container)

st.markdown(
    """
    <div class="app-signature">
        <span>Author: @andreavrob</span>
    </div>
    """,
    unsafe_allow_html=True,
)
