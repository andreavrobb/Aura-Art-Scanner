import os
from dotenv import load_dotenv
import streamlit as st

# OpenAI-compatible clients
from openai import OpenAI

# Gemini
import google.generativeai as genai

# ============================================
# CONFIG
# ============================================
load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 🔥 CONTROL MANUAL DEL MODELO (EDITA AQUÍ)
MODEL_PROVIDER = "openai"
# opciones: "openai", "gemini", "groq", "deepseek"

# OpenAI-compatible clients
client_openai = OpenAI(api_key=OPENAI_API_KEY)


client_groq = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

client_deepseek = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

# Gemini
genai.configure(api_key=GOOGLE_API_KEY)
model_gemini = genai.GenerativeModel("gemini-2.5-flash")

# ============================================
# UI
# ============================================
st.set_page_config(page_title="Aura Art Scanner", page_icon="🎨")

st.title("🎨 Aura Art Scanner")
st.caption("This is a tool that helps you scan art and get information about it 🖌")

# Debug opcional
st.caption(f"🧠 Model active: {MODEL_PROVIDER}")

# ============================================
# STRONGER PROMPT (TUYO)
# ============================================
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
# SESSION
# ============================================
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# ============================================
# ADAPTERS
# ============================================

def call_openai_like(client, model, messages):
    placeholder = st.empty()
    full = ""

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            full += text

            # 👇 clave: render completo acumulado
            placeholder.markdown(full)

    return full


def build_gemini_prompt(system_prompt, messages):
    prompt = system_prompt + "\n\n"
    for m in messages:
        if m["role"] == "user":
            prompt += f"User: {m['content']}\n"
        elif m["role"] == "assistant":
            prompt += f"Assistant: {m['content']}\n"
    prompt += "Assistant:"
    return prompt


def call_gemini(prompt):
    placeholder = st.empty()
    full = ""

    response = model_gemini.generate_content(prompt, stream=True)

    for chunk in response:
        if hasattr(chunk, "text"):
            full += chunk.text
            placeholder.markdown(full)

    return full


# ============================================
# ROUTER
# ============================================
def run_llm(provider, conversation, stronger_prompt, messages):

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
# USER INPUT
# ============================================
user_input = st.chat_input("Ask about art...")

if user_input:
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    st.chat_message("user").write(user_input)

    conversation = [{
        "role": "system",
        "content": stronger_prompt
    }]
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