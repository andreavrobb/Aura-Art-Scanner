"""Prototipo mínimo de Aura Art Scanner.

Este archivo funciona como una versión muy simple de la interfaz:
- muestra el título de la app,
- permite escribir un mensaje,
- acepta una imagen adjunta,
- y enseña de inmediato el texto o la imagen subida.

Se conserva como referencia de una interfaz básica y ligera.
"""

import streamlit as st


# Encabezado principal del prototipo.
st.title("🎨 Aura Art Scanner")
st.caption("This is a tool that helps you scan art and get information about it  🖌")


# Entrada de chat que acepta texto e imágenes para pruebas rápidas.
prompt = st.chat_input(
    "Say something and/or attach an image",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
)

# `prompt` será `None` hasta que el usuario envíe algo desde el chat.
# Si el usuario escribió texto, se muestra tal cual en pantalla.
if prompt and prompt.text:
    st.markdown(prompt.text)

# `st.chat_input` devuelve una lista de archivos en la clave `files`.
# Como este prototipo es mínimo, solo mostramos la primera imagen recibida.
if prompt and prompt["files"]:
    st.image(prompt["files"][0])
