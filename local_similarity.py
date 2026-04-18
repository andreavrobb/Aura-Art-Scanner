"""Búsqueda de similitud visual local usando embeddings CLIP/OpenCLIP.

Este módulo encapsula toda la parte de recuperación visual local:
- cargar el modelo de embeddings,
- convertir imágenes en vectores numéricos,
- leer y escribir el índice local,
- y buscar vecinos cercanos para una imagen subida por el usuario.

La idea es que la interfaz principal no tenga que conocer los detalles de
OpenCLIP; solo llama a funciones de alto nivel como
`search_local_similar_artworks`.
"""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import json
import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    import open_clip
except ImportError:  # pragma: no cover
    open_clip = None

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None

from PIL import Image


# Cargamos variables de entorno para poder tomar credenciales desde `.env`.
load_dotenv(override=False)
# Si el proyecto ya guarda el token de Hugging Face en `AURA`, lo reutilizamos
# como `HF_TOKEN` para que OpenCLIP pueda descargar pesos con autenticación.
if os.getenv("AURA") and not os.getenv("HF_TOKEN"):
    os.environ["HF_TOKEN"] = os.environ["AURA"]


BASE_DIR = Path(__file__).resolve().parent
# Carpeta donde se persiste el índice visual una vez construido.
LOCAL_INDEX_DIR = BASE_DIR / "local_similarity_index"
INDEX_EMBEDDINGS_PATH = LOCAL_INDEX_DIR / "embeddings.npy"
INDEX_METADATA_PATH = LOCAL_INDEX_DIR / "metadata.json"
# Modelo base y checkpoint usados para generar embeddings compatibles.
DEFAULT_MODEL_NAME = "ViT-B-32"
DEFAULT_PRETRAINED_NAME = "laion2b_s34b_b79k"


def local_similarity_dependencies_ready() -> bool:
    """Comprueba si el entorno tiene instaladas las dependencias opcionales."""
    return np is not None and open_clip is not None and torch is not None


def local_similarity_index_ready() -> bool:
    """Comprueba si ya existe un índice persistido en disco."""
    return INDEX_EMBEDDINGS_PATH.exists() and INDEX_METADATA_PATH.exists()


@lru_cache(maxsize=1)
def get_model_bundle():
    """Carga el modelo de embeddings una sola vez por proceso.

    Usamos caché para evitar volver a instanciar el modelo en cada consulta.
    """
    if not local_similarity_dependencies_ready():
        return None

    model, _, preprocess = open_clip.create_model_and_transforms(
        DEFAULT_MODEL_NAME,
        pretrained=DEFAULT_PRETRAINED_NAME,
    )
    model.eval()
    return {"model": model, "preprocess": preprocess}


def _normalize_embeddings(embeddings):
    """Normaliza embeddings con norma L2 para poder usar coseno."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return embeddings / norms


def _encode_pil_images(images: Iterable[Image.Image]):
    """Transforma una lista de imágenes PIL en embeddings normalizados."""
    bundle = get_model_bundle()
    if bundle is None:
        return None

    # Preprocesamos todas las imágenes con la misma receta del modelo.
    tensors = [bundle["preprocess"](image.convert("RGB")) for image in images]
    if not tensors:
        return None

    # El modelo devuelve un vector por imagen; luego lo normalizamos.
    image_batch = torch.stack(tensors)
    with torch.no_grad():
        features = bundle["model"].encode_image(image_batch)
    embeddings = features.detach().cpu().numpy().astype("float32")
    return _normalize_embeddings(embeddings)


def encode_image_paths(image_paths: Iterable[Path]):
    """Genera embeddings para imágenes ya guardadas en disco."""
    if not local_similarity_dependencies_ready():
        return None

    images = []
    for image_path in image_paths:
        try:
            # Copiamos la imagen a memoria para cerrar el archivo enseguida.
            with Image.open(image_path) as image:
                images.append(image.copy())
        except (FileNotFoundError, OSError):
            continue

    return _encode_pil_images(images)


def encode_uploaded_images(uploaded_images: list[dict]):
    """Genera un embedding medio para las imágenes subidas por el usuario.

    Si el usuario adjunta varias imágenes, promediamos sus embeddings para
    obtener una sola consulta visual más estable.
    """
    if not local_similarity_dependencies_ready():
        return None

    images = []
    for image in uploaded_images or []:
        # `bytes` es la representación binaria que ya conserva Streamlit.
        raw_bytes = image.get("bytes")
        if not raw_bytes:
            continue
        try:
            with Image.open(BytesIO(raw_bytes)) as pil_image:
                images.append(pil_image.copy())
        except OSError:
            continue

    encoded = _encode_pil_images(images)
    if encoded is None or len(encoded) == 0:
        return None

    averaged = encoded.mean(axis=0, keepdims=True).astype("float32")
    return _normalize_embeddings(averaged)[0]


def save_local_index(embeddings, metadata: list[dict]):
    """Guarda en disco el índice visual y su metadata asociada."""
    LOCAL_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(INDEX_EMBEDDINGS_PATH, embeddings.astype("float32"))
    INDEX_METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    load_local_index.cache_clear()


@lru_cache(maxsize=1)
def load_local_index():
    """Carga el índice local persistido y lo cachea en memoria."""
    if not local_similarity_dependencies_ready() or not local_similarity_index_ready():
        return None

    embeddings = np.load(INDEX_EMBEDDINGS_PATH).astype("float32")
    metadata = json.loads(INDEX_METADATA_PATH.read_text(encoding="utf-8"))
    # Validamos que el número de vectores coincida con el número de registros.
    if embeddings.ndim != 2 or len(metadata) != len(embeddings):
        return None
    return embeddings, metadata


def _build_match_result(meta: dict, similarity: float):
    """Convierte metadata cruda del índice al formato que usa la UI."""
    image_path = str(meta.get("image_path", "")).strip()
    image_bytes = None
    if image_path:
        try:
            # Leemos la miniatura local para mostrarla directamente en Streamlit.
            image_bytes = Path(image_path).read_bytes()
        except OSError:
            image_bytes = None

    return {
        "title": str(meta.get("title", "Untitled")).strip() or "Untitled",
        "creator": str(meta.get("creator", "Unknown artist")).strip() or "Unknown artist",
        "period": str(meta.get("period", "Period unavailable")).strip() or "Period unavailable",
        "source_name": str(meta.get("source_name", "Local visual index")).strip() or "Local visual index",
        "source_url": str(meta.get("source_url", "")).strip(),
        "image_path": image_path,
        "image_bytes": image_bytes,
        "medium": str(meta.get("medium", "")).strip(),
        "culture": str(meta.get("culture", "")).strip(),
        "object_type": str(meta.get("object_type", "")).strip(),
        "similarity": float(similarity),
    }


def search_local_similar_artworks(uploaded_images: list[dict], limit: int = 6):
    """Busca vecinos cercanos en el índice local a partir de una imagen subida."""
    index_bundle = load_local_index()
    query_embedding = encode_uploaded_images(uploaded_images)
    if index_bundle is None or query_embedding is None:
        return []

    embeddings, metadata = index_bundle
    # Como todos los embeddings están normalizados, el producto punto equivale
    # a la similitud coseno.
    scores = embeddings @ query_embedding
    ordered_indices = np.argsort(scores)[::-1]

    matches = []
    seen_paths = set()
    for idx in ordered_indices:
        # Saltamos duplicados por ruta para no repetir la misma obra.
        meta = metadata[int(idx)]
        image_path = str(meta.get("image_path", "")).strip()
        if not image_path or image_path in seen_paths:
            continue
        seen_paths.add(image_path)
        matches.append(_build_match_result(meta, float(scores[int(idx)])))
        if len(matches) >= limit:
            break

    return matches


def build_local_similarity_context_message(matches: list[dict]):
    """Convierte vecinos visuales en un mensaje de sistema para el LLM.

    Esto permite que Aura no solo vea la imagen, sino que además sepa cuáles
    son las obras locales más cercanas antes de redactar la explicación final.
    """
    if not matches:
        return None

    lines = []
    for match in matches[:5]:
        similarity_pct = round(match.get("similarity", 0.0) * 100, 1)
        lines.append(
            "- "
            f"{match.get('title', 'Untitled')} | "
            f"{match.get('creator', 'Unknown artist')} | "
            f"{match.get('period', 'Period unavailable')} | "
            f"{match.get('object_type', 'Unknown type')} | "
            f"visual similarity {similarity_pct}%"
        )

    content = (
        "Use the following local visual-nearest-neighbor results as evidence.\n"
        "These are approximate visual matches from the local image index, not definitive attributions.\n\n"
        "Local visual matches:\n"
        f"{chr(10).join(lines)}\n\n"
        "When you refer to them, explain why the uploaded image may align with or differ from these references."
    )
    return {"role": "system", "content": content}
