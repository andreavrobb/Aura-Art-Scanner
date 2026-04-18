"""Versión experimental de Aura Art Scanner con selección manual de proveedor LLM.

Este archivo documenta un flujo más técnico que el de `main_01.py`:
- carga claves desde variables de entorno,
- crea clientes compatibles con OpenAI,
- ofrece varios proveedores de modelo,
- y enruta la conversación al backend elegido.

Se usa como laboratorio para comparar modelos y comportamientos.
"""

import os
import streamlit as st

from dotenv import load_dotenv
from openai import OpenAI

# Cliente nativo de Gemini.
import google.generativeai as genai

# ============================================
# Carga de configuración
# ============================================
load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Selector manual del proveedor de modelo.
MODEL_PROVIDER = "openai"
# Opciones: `openai`, `gemini`, `groq`, `deepseek`.

# Cliente estándar de OpenAI.
client_openai = OpenAI(api_key=OPENAI_API_KEY)
# Cliente compatible con la API de Groq.
client_groq = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)
# Cliente compatible con la API de DeepSeek.
client_deepseek = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

# Cliente nativo de Gemini.
genai.configure(api_key=GOOGLE_API_KEY)
model_gemini = genai.GenerativeModel("gemini-2.5-flash")

# ============================================
# Interfaz
# ============================================
st.set_page_config(page_title="Aura Art Scanner", page_icon="🎨")

# Título y estado del proveedor activo.
st.title("🎨 Aura Art Scanner")
st.caption("This is a tool that helps you scan art and get information about it 🖌")
st.caption(f"🧠 Model active: {MODEL_PROVIDER}")

# ============================================
# Prompt base
# ============================================
# Cada bloque separa una parte del comportamiento deseado del asistente.
role_section = r"""🎨🤖 **Rol principal**
Eres un asistente experto en ciencia de datos aplicada al arte, computer vision, historia del arte e ingeniería de software.
Tu enfoque es educativo, técnico y práctico.
"""

security_section = r"""🛡️ Seguridad:
Solo arte, IA, datasets, software.
"""

goal_section = r"""🎯 Objetivo:
Formar en IA para arte end-to-end.
"""

style_section = r"""🧭 Estilo:
Mentor técnico con código.
"""

response_template = r"""🧱 Estructura:
1) Contexto
2) Análisis
3) IA
4) Pipeline
5) Checklist
6) Siguiente paso
"""

data_mastery_section = r"""🗂️ Datos:
APIs, scraping, pipelines, datasets.
"""

engineering_section = r"""🛠️ Ingeniería:
Streamlit + FastAPI + APIs
"""

closing_cta = r"""🏁 Cierre:
Siguientes pasos + pregunta
"""

end_state = r"""🎯 Meta:
App IA arte completa
"""

# Ensamblamos el prompt final uniendo todas las secciones.
stronger_prompt = "\n".join([
    role_section,
    security_section,
    goal_section,
    style_section,
    response_template,
    data_mastery_section,
    engineering_section,
    closing_cta,
    end_state
])

# ============================================
# Estado de sesión
# ============================================
# Historial persistente de la conversación dentro de Streamlit.
if "messages" not in st.session_state:
    st.session_state.messages = []

# Re-render del historial existente para que la conversación siga visible.
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# ============================================
# Adaptadores
# ============================================

def call_openai_like(client, model, messages):
    """Ejecuta streaming contra un cliente compatible con OpenAI."""
    placeholder = st.empty()
    full = ""

    # Pedimos streaming para ir pintando la respuesta token a token.
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True
    )

    for chunk in stream:
        # Cada chunk puede traer una pequeña porción de texto o venir vacío.
        if chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            full += text

            # Renderizamos el acumulado completo para que el markdown no parpadee.
            placeholder.markdown(full)

    return full


def build_gemini_prompt(system_prompt, messages):
    """Convierte el historial de chat al formato de prompt plano que usa Gemini."""
    prompt = system_prompt + "\n\n"
    for m in messages:
        # Convertimos el historial estructurado a un transcript simple.
        if m["role"] == "user":
            prompt += f"User: {m['content']}\n"
        elif m["role"] == "assistant":
            prompt += f"Assistant: {m['content']}\n"
    prompt += "Assistant:"
    return prompt


def call_gemini(prompt):
    """Ejecuta Gemini con streaming y va pintando la respuesta progresivamente."""
    placeholder = st.empty()
    full = ""

    # Gemini nativo usa otra API, pero mantenemos una experiencia visual similar.
    response = model_gemini.generate_content(prompt, stream=True)

    for chunk in response:
        if hasattr(chunk, "text"):
            full += chunk.text
            placeholder.markdown(full)

    return full


# ============================================
# Enrutador
# ============================================
def run_llm(provider, conversation, stronger_prompt, messages):
    """Selecciona el backend LLM según el proveedor configurado."""
    # Cada rama traduce la misma conversación al backend elegido.
    if provider == "openai":
        return call_openai_like(client_openai, "gpt-5.4-mini", conversation)

    elif provider == "groq":
        return call_openai_like(client_groq, "llama-3.1-70b-versatile", conversation)

    elif provider == "deepseek":
        return call_openai_like(client_deepseek, "deepseek-chat", conversation)

    elif provider == "gemini":
        gemini_prompt = build_gemini_prompt(stronger_prompt, messages)
        return call_gemini(gemini_prompt)

    else:
        raise ValueError(f"Provider no soportado: {provider}")


# ============================================
# Entrada del usuario
# ============================================
user_input = st.chat_input("Ask about art...")

if user_input:
    # Guardamos el mensaje del usuario para conservar el historial.
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    st.chat_message("user").write(user_input)

    # Construimos la conversación completa con el prompt del sistema al inicio.
    conversation = [{
        "role": "system",
        "content": stronger_prompt
    }]
    # Añadimos el historial para que el modelo vea toda la conversación previa.
    conversation.extend(st.session_state.messages)

    with st.chat_message("assistant"):
        response = run_llm(
            MODEL_PROVIDER,
            conversation,
            stronger_prompt,
            st.session_state.messages
        )

    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })
