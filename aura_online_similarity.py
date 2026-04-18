"""Búsqueda y ranking de obras similares en colecciones online."""

from __future__ import annotations

import json
import re

import requests
import streamlit as st


MET_PUBLIC_API_BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
AIC_API_BASE_URL = "https://api.artic.edu/api/v1"
CMA_API_BASE_URL = "https://openaccess-api.clevelandart.org/api"
SIMILAR_WEB_MATCH_LIMIT = 4
SIMILAR_WEB_SEARCH_TIMEOUT = 12
AIC_USER_AGENT = "aura-art-scanner (local-app)"


def normalize_text_list(values, limit=6):
    """Normaliza listas cortas de texto eliminando duplicados."""
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


def extract_json_object(raw_text):
    """Recupera un objeto JSON aunque venga envuelto en fences o ruido."""
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

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def build_similar_art_search_queries(search_hints, fallback_text=""):
    """Construye varias consultas cortas para recuperar obras similares."""
    queries = []
    artists = normalize_text_list(search_hints.get("likely_artists", []), limit=3)
    terms = normalize_text_list(search_hints.get("search_terms", []), limit=6)
    style = str(search_hints.get("likely_style", "")).strip()
    period = str(search_hints.get("likely_period", "")).strip()
    object_type = str(search_hints.get("object_type", "")).strip()
    material_terms = normalize_text_list(search_hints.get("material_terms", []), limit=4)

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
    """Reduce tipos libres a familias comparables entre APIs."""
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


def build_match_haystack(match):
    """Reúne metadata textual de una coincidencia para scoring."""
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

    for artist in artist_candidates:
        if artist == creator or artist in creator or creator in artist:
            return True
    return False


def score_online_match(match, search_hints):
    """Asigna una puntuación simple a una coincidencia online."""
    artists = [artist.lower() for artist in search_hints.get("likely_artists", [])]
    style = str(search_hints.get("likely_style", "")).lower()
    period = str(search_hints.get("likely_period", "")).lower()
    terms = [term.lower() for term in search_hints.get("search_terms", [])]
    material_terms = [term.lower() for term in search_hints.get("material_terms", [])]
    expected_object_type = normalize_object_type(search_hints.get("object_type", ""))
    match_object_type = normalize_object_type(match.get("object_type", ""))

    haystack = build_match_haystack(match)
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
    """Busca object IDs en la API pública del MET."""
    if not query:
        return []

    try:
        response = requests.get(
            f"{MET_PUBLIC_API_BASE_URL}/search",
            params={"q": query, "hasImages": str(bool(has_images)).lower()},
            timeout=SIMILAR_WEB_SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    object_ids = payload.get("objectIDs") or []
    return [object_id for object_id in object_ids if isinstance(object_id, int)]


@st.cache_data(show_spinner=False, ttl=60 * 60 * 8)
def fetch_met_object_online(object_id):
    """Recupera metadata de un objeto del MET."""
    try:
        response = requests.get(
            f"{MET_PUBLIC_API_BASE_URL}/objects/{object_id}",
            timeout=SIMILAR_WEB_SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

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
            payload.get("classification") or payload.get("objectName") or payload.get("medium") or ""
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

    config = payload.get("config") or {}
    iiif_url = str(config.get("iiif_url", "")).strip()
    website_url = str(config.get("website_url", "https://www.artic.edu")).strip()
    results = []

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
                    item.get("artwork_type_title") or item.get("classification_title") or item.get("medium_display") or ""
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
            params={"q": query, "has_image": 1, "limit": limit},
            timeout=SIMILAR_WEB_SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    results = []
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
                "object_type": normalize_object_type(item.get("type") or item.get("technique") or ""),
            }
        )

    return results


def infer_similar_art_search_hints(latest_user_message, assistant_response, *, client_openai, model_openai, build_model_message):
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

    try:
        completion = client_openai.chat.completions.create(
            model=model_openai,
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


def find_online_similar_artworks(
    latest_user_message,
    assistant_response,
    *,
    client_openai,
    model_openai,
    build_model_message,
    fetch_remote_image_bytes,
    selected_artist_context_name=None,
    selected_met_object_context_id=None,
    limit=SIMILAR_WEB_MATCH_LIMIT,
):
    """Busca referencias visuales online sin interrumpir el flujo principal."""
    if not latest_user_message or not latest_user_message.get("images"):
        return []
    if selected_artist_context_name or selected_met_object_context_id:
        return []

    search_hints = infer_similar_art_search_hints(
        latest_user_message,
        assistant_response,
        client_openai=client_openai,
        model_openai=model_openai,
        build_model_message=build_model_message,
    )
    if not search_hints:
        return []

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
            -max(score_online_match(candidate, search_hints) for candidate in source_buckets.get(source_key, [])),
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

    for match in deduped:
        match["image_bytes"] = fetch_remote_image_bytes(
            match.get("image_url", ""),
            source_name=str(match.get("source_name", "")),
        )

    return deduped
