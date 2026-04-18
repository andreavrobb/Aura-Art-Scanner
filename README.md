# Aura Art Scanner

Aura Art Scanner es una aplicación en `Streamlit` para analizar obras de arte a partir de texto e imágenes. Combina un asistente multimodal, datasets locales curados, referencias activables desde la interfaz, búsqueda de obras similares en APIs públicas y un índice local de similitud visual por embeddings.

## Qué hace Aura

- Analiza imágenes subidas por el usuario con un modelo multimodal.
- Explica estilo, técnica, composición, simbolismo y posibles influencias.
- Mantiene el foco solo en arte, historia del arte e interpretación visual.
- Permite activar contexto local desde:
  - `Artist Explorer`
  - `MET Object Explorer`
- Busca coincidencias visuales en un índice local construido sobre imágenes precargadas del proyecto.
- Si no encuentra buenos vecinos locales, puede buscar referencias online en colecciones abiertas.
- Permite editar mensajes anteriores y regenerar la respuesta desde ese punto.

## Arquitectura General

Aura funciona en varias capas:

1. La interfaz principal recibe texto e imágenes desde `Streamlit`.
2. Las imágenes se serializan en memoria y se envían al modelo como contenido multimodal.
3. Aura puede enriquecer la respuesta con contexto local de artistas u objetos del MET.
4. Si existe un índice local de embeddings, busca primero vecinos visuales dentro del proyecto.
5. Si no hay coincidencias locales útiles, busca obras similares en museos online.
6. El LLM redacta la respuesta final usando la imagen, el prompt base y el contexto recuperado.

## Módulos Python

- [UserInterface.py](/Users/andreavrob/Desktop/Aura-Art-Scanner/UserInterface.py): interfaz principal, flujo de chat, exploradores, renderizado, búsqueda online y conexión con OpenAI.
- [prompts.py](/Users/andreavrob/Desktop/Aura-Art-Scanner/prompts.py): prompt base que define el rol, límites, tono y estructura de respuesta de Aura.
- [aura_data.py](/Users/andreavrob/Desktop/Aura-Art-Scanner/aura_data.py): carga de datasets locales, resolución de imágenes, relaciones entre artistas/objetos y mensajes de referencia.
- [aura_online_similarity.py](/Users/andreavrob/Desktop/Aura-Art-Scanner/aura_online_similarity.py): búsqueda online de obras similares, normalización de resultados y ranking entre APIs de museos.
- [local_similarity.py](/Users/andreavrob/Desktop/Aura-Art-Scanner/local_similarity.py): generación y consulta de embeddings visuales locales usando OpenCLIP.
- [build_local_index.py](/Users/andreavrob/Desktop/Aura-Art-Scanner/build_local_index.py): script que recorre las imágenes locales del proyecto y construye el índice visual.
- [data_extraction.py](/Users/andreavrob/Desktop/Aura-Art-Scanner/data_extraction.py): script auxiliar para descargar metadata e imágenes desde la API pública del MET.
- [main_01.py](/Users/andreavrob/Desktop/Aura-Art-Scanner/main_01.py): prototipo mínimo de Streamlit.
- [main_02.py](/Users/andreavrob/Desktop/Aura-Art-Scanner/main_02.py): versión experimental con selección manual de proveedor LLM.

## Datasets Locales

Aura trabaja con dos orígenes locales principales:

- `met_art_data/`
  - `Artists2.csv`: perfiles de artistas.
  - `resized 3/`: previews locales ya precargadas.

- `met_art_data2/`
  - `metadata_cleaned_updated.csv`: metadata curada de objetos del MET.
  - `images_extracted/`: imágenes locales asociadas a esos objetos.

## Similitud Visual Local

Aura ya puede usar embeddings visuales reales sobre tu dataset local.

### Cómo funciona

1. `build_local_index.py` recorre:
   - `met_art_data/resized 3`
   - `met_art_data2/images_extracted`
2. `local_similarity.py` usa OpenCLIP para generar un embedding por imagen.
3. Los embeddings se guardan en:
   - `local_similarity_index/embeddings.npy`
   - `local_similarity_index/metadata.json`
4. Cuando el usuario sube una imagen, Aura genera su embedding.
5. Luego calcula similitud coseno contra el índice local y devuelve los vecinos más cercanos.

### Qué gana Aura con esto

- La semejanza ya no depende solo del razonamiento semántico del LLM.
- Aura puede recuperar referencias visuales locales antes de buscar en internet.
- Las coincidencias locales también se pasan al modelo como evidencia contextual.

## Similitudes Online

Si no hay contexto local activo y no aparecen vecinos locales útiles, Aura puede consultar:

- The Metropolitan Museum of Art Collection API
- Art Institute of Chicago API
- Cleveland Museum of Art Open Access API

La lógica online intenta priorizar:

- mismo artista
- mismo tipo de objeto
- periodo parecido
- materiales o técnicas afines
- términos visuales inferidos por el modelo

Las coincidencias online son referencias probables, no atribuciones definitivas.

## Exploradores Integrados

### Artist Explorer

Permite:

- buscar por nombre, biografía, género o nacionalidad
- ver previews locales del artista
- activar un artista como referencia opcional para el chat
- sugerir artistas cercanos del mismo dataset

### MET Object Explorer

Permite:

- filtrar por título, artista, departamento, periodo, rol o año
- ver una imagen local de la obra si existe
- activar un objeto del MET como referencia opcional
- consultar objetos relacionados dentro del dataset local

## Flujo del Chat

Cuando el usuario envía un mensaje con imagen, Aura hace esto:

1. Guarda el mensaje y serializa las imágenes.
2. Construye la conversación para el modelo.
3. Añade el prompt base de `prompts.py`.
4. Añade contexto local activo si el usuario seleccionó artista u objeto.
5. Añade vecinos visuales locales si existe el índice de embeddings.
6. Genera la respuesta en streaming.
7. Si hace falta, completa con coincidencias online.
8. Guarda la respuesta en el historial para futuros reruns.

## Requisitos

- Python `>=3.13`
- Dependencias del proyecto instaladas con `uv` o `pip`
- Clave para OpenAI en `.env`
- Internet para:
  - generar respuestas con el modelo
  - descargar pesos del modelo de embeddings si aún no están cacheados
  - consultar APIs de museos online

## Variables de Entorno

En `.env` puedes usar, según tu configuración:

```env
AURA_API_KEY=tu_api_key_de_openai
AURA=tu_token_de_huggingface
HF_TOKEN=opcional_si_prefieres_usar_el_nombre_estandar
OPENAI_API_KEY=opcional_en_los_prototipos
GOOGLE_API_KEY=opcional_en_los_prototipos
GROQ_API_KEY=opcional_en_main_02.py
DEEPSEEK_API_KEY=opcional_en_main_02.py
```

Notas:

- La interfaz principal usa `AURA_API_KEY`.
- El módulo de embeddings puede reutilizar `AURA` como `HF_TOKEN`.
- `HF_TOKEN` solo mejora autenticación y velocidad de descarga en Hugging Face.

## Instalación

Con `uv`:

```bash
uv sync
```

Si quieres activar el entorno creado por `uv`:

```bash
source .venv/bin/activate
```

Con `pip`:

```bash
pip install -e .
```

## Construcción del Índice Local

Antes de usar la similitud visual local, construye el índice:

```bash
./.venv/bin/python build_local_index.py
```

O, si activaste el entorno:

```bash
python build_local_index.py
```

Esto generará:

- `local_similarity_index/embeddings.npy`
- `local_similarity_index/metadata.json`

## Ejecución

Para arrancar la app principal:

```bash
streamlit run UserInterface.py
```

Si prefieres usar el entorno de `uv` sin activarlo antes:

```bash
./.venv/bin/streamlit run UserInterface.py
```

## Cómo Usar Aura

1. Abre `Chat Studio`.
2. Sube una imagen de una obra o escribe una pregunta.
3. Deja que Aura analice la imagen o pide algo concreto.
4. Si quieres más precisión, activa un artista o un objeto desde los exploradores.
5. Revisa las coincidencias locales del índice visual si están disponibles.
6. Si no hay matches locales útiles, Aura puede mostrar referencias online.
7. Si quieres refinar una conversación, edita un mensaje previo y regenera.

## Estado de la Similitud Local en la UI

La interfaz muestra uno de estos estados:

- índice local listo
- dependencias listas pero índice aún no construido
- dependencias faltantes para embeddings

Esto facilita saber si Aura está usando recuperación visual local real o solo el flujo semántico/online.

## Desarrollo

Si vas a extender Aura, estos son los puntos más relevantes:

- `UserInterface.py`
  - chat multimodal
  - render de coincidencias
  - exploradores
  - flujo de respuesta

- `aura_data.py`
  - carga y limpieza de datasets locales
  - enlaces entre metadata y previews
  - referencias activables para el chat

- `aura_online_similarity.py`
  - construcción de queries
  - recuperación en APIs de museos
  - ranking de coincidencias online

- `local_similarity.py`
  - embeddings
  - carga del índice
  - búsqueda visual local

- `build_local_index.py`
  - definición de qué imágenes entran al índice
  - metadata que luego se mostrará en resultados

- `prompts.py`
  - rol, tono, límites y estructura del asistente

## Notas Técnicas

- El índice local actual usa OpenCLIP con `ViT-B-32`.
- La similitud se calcula con producto punto sobre embeddings normalizados, equivalente a coseno.
- Si el índice local no existe, Aura sigue funcionando con su pipeline actual.
- `UserInterface.py` ya incluye comentarios en español en la mayor parte del flujo principal.

## Licencia

Consulta [LICENSE](/Users/andreavrob/Desktop/Aura-Art-Scanner/LICENSE) para los términos del proyecto.
