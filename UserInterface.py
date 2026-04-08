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
import inspect
import os

from dotenv import load_dotenv
from openai import OpenAI
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
BACKGROUND_IMAGE_PATH = "/Users/andreavrob/Downloads/_ (1).jpeg"

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


# --------------------------------------------
# Configuración de página y tema visual
# --------------------------------------------
st.set_page_config(page_title="Aura Art Scanner", page_icon="🎨")

background_image_url = get_background_image_data_url(BACKGROUND_IMAGE_PATH)

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
@import url('https://fonts.googleapis.com/css2?family=Satisfy&display=swap');

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
    margin: 0 auto 1.15rem auto;
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

# Inyecta CSS directamente en la página para personalizar la interfaz.
st.markdown(css_background, unsafe_allow_html=True)

st.markdown(
    """<div class="page-top-spacer"></div>
    <div class="hero-shell">
        <div class="app-title-row">
            <div class="app-title-icon">🎨</div>
            <h1
                class="app-title"
                style="
                    font-family: 'Satisfy', 'Brush Script MT', 'Segoe Script',
                        'Apple Chancery', cursive;
                    font-size: clamp(3.45rem, 6vw, 5.2rem);
                    font-weight: 400;
                    line-height: 1.12;
                    letter-spacing: 0.01em;
                    color: #5b3a1f;
                    margin: 0;
                    padding: 0.14em 0 0.08em;
                    text-shadow: 0 7px 18px rgba(104, 72, 28, 0.14);
                    text-align: center;
                "
            >
                Aura Art Scanner
            </h1>
        </div>
        <div class="app-subtitle">
            This is a tool that helps you scan art and get information about it 🖌
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Formatos de imagen aceptados en el compositor del chat.
SUPPORTED_IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"]


# --------------------------------------------
# Estado de sesión
# --------------------------------------------
if "messages" not in st.session_state:
    # Los mensajes se guardan como diccionarios con "role", "content" y "images" opcional.
    st.session_state.messages = [{"role": "assistant", "content": "Ask about art..."}]

if "editing_message_index" not in st.session_state:
    # Guarda el índice del mensaje del usuario que se está editando.
    st.session_state.editing_message_index = None

if "pending_regeneration" not in st.session_state:
    # Indica que debe regenerarse una respuesta después de guardar una edición.
    st.session_state.pending_regeneration = None

def serialize_uploaded_images(uploaded_files):
    """Convierte archivos subidos en Streamlit a una estructura serializable en memoria.

    Cada imagen conserva:
    - el nombre original del archivo,
    - el tipo MIME,
    - los bytes crudos para renderizarla en Streamlit,
    - y una data URL en base64 para enviarla al modelo multimodal.
    """
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
    antiguas todavía usan ``use_container_width=True``.
    """
    width_parameter = inspect.signature(st.image).parameters.get("width")

    if width_parameter and width_parameter.default == "content":
        return {"width": "stretch"}

    return {"use_container_width": True}


def render_images(message):
    """Renderiza todas las imágenes adjuntas a un mismo mensaje de chat."""
    for image in message.get("images", []):
        st.image(
            image["bytes"],
            caption=image["name"],
            **get_image_display_kwargs(),
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

        st.image(profile["image_url"], use_container_width=True)
        st.caption(profile["image_credit"])

        with st.expander("See all profiles"):
            for item in AUDIENCE_PROFILES:
                st.markdown(f"**{item['icon']} {item['label']}**")
                st.write(item["description"])



def save_edited_message(index, edited_text):
    """Guarda un mensaje editado por la persona usuaria y activa la regeneración.

    Cuando se edita un prompt anterior, la conversación posterior deja de ser
    totalmente coherente. Por eso, el historial se recorta hasta el mensaje
    editado y la respuesta del asistente se genera de nuevo desde ese punto.
    """
    current_message = st.session_state.messages[index]
    normalized_text = edited_text.strip()

    if not normalized_text and not current_message.get("images"):
        st.warning("Write a message or keep at least one attached image.")
        return

    current_message["content"] = normalized_text
    # Elimina los mensajes posteriores para que la nueva respuesta sea coherente.
    st.session_state.messages = st.session_state.messages[: index + 1]
    st.session_state.editing_message_index = None
    st.session_state.pending_regeneration = index
    st.rerun()


def render_message(message, index, container=None):
    """Renderiza un mensaje de chat, incluyendo imágenes y controles de edición."""
    target = container if container is not None else st
    is_editing = (
        message["role"] == "user"
        and st.session_state.editing_message_index == index
    )
    avatar = "🖌️" if message["role"] == "assistant" else "🎨"

    with target.chat_message(message["role"], avatar=avatar):
        render_role_marker(message["role"])

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

        if message.get("content"):
            st.write(message["content"])

        render_images(message)

        if message["role"] == "user":
            # Solo los mensajes del usuario pueden editarse.
            if st.button("Edit message", key=f"edit_message_{index}"):
                st.session_state.editing_message_index = index
                st.rerun()


def build_model_message(message):
    """Convierte un mensaje interno al formato esperado por la API del modelo.

    Los mensajes de solo texto se envían tal cual.
    Los mensajes del usuario con imágenes adjuntas se transforman en contenido
    multimodal: un bloque de texto y un bloque ``image_url`` por cada imagen.
    """
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
    if disabled:
        st.info("Finish editing the selected message to continue chatting.")
        return None

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

        with st.expander("Attach artwork images"):
            uploaded_files = st.file_uploader(
                "Attach artwork images",
                type=SUPPORTED_IMAGE_TYPES,
                accept_multiple_files=True,
                label_visibility="collapsed",
            )

        if uploaded_files:
            st.caption(f"{len(uploaded_files)} image(s) ready to send.")

    if submitted and (prompt_text.strip() or uploaded_files):
        return {"text": prompt_text.strip(), "files": uploaded_files}

    return None


render_sidebar_audience_menu()

# Contenedor principal del historial de chat con scroll.
messages_container = st.container(
    height=get_messages_container_height(len(st.session_state.messages)),
    border=True,
)

for index, msg in enumerate(st.session_state.messages):
    render_message(msg, index, container=messages_container)


def generate_assistant_reply(container):
    """Envía la conversación actual a Gemini o OpenAI y muestra la respuesta en streaming."""
    conversation = [{"role": "system", "content": stronger_prompt}]
    conversation.extend(build_model_message(message) for message in st.session_state.messages)

    with container.chat_message("assistant", avatar="🖌️"):
        render_role_marker("assistant")
        stream = client_google.chat.completions.create(
            model=model_google,
            messages=conversation,
            stream=True,
        )
        response = st.write_stream(stream)

    st.session_state.messages.append({"role": "assistant", "content": response})


# Si un mensaje anterior fue editado, regenera la respuesta una sola vez en el rerun.
if st.session_state.pending_regeneration is not None:
    st.session_state.pending_regeneration = None
    generate_assistant_reply(messages_container)

# Desactiva nuevos envíos mientras la persona usuaria edita un mensaje anterior.
submission = get_user_submission(
    disabled=st.session_state.editing_message_index is not None
)

if submission:
    # Guarda el nuevo turno del usuario en la misma estructura del historial.
    user_message = {
        "role": "user",
        "content": submission["text"],
        "images": serialize_uploaded_images(submission["files"]),
    }

    st.session_state.messages.append(user_message)
    # Renderiza el mensaje recién enviado antes de iniciar el streaming de la respuesta.
    render_message(
        user_message,
        len(st.session_state.messages) - 1,
        container=messages_container,
    )
    # Genera la respuesta del asistente usando el historial actualizado.
    generate_assistant_reply(messages_container)

st.markdown(
    """
    <div class="app-signature">
        <span>Author: @andreavrob</span>
    </div>
    """,
    unsafe_allow_html=True,
)
