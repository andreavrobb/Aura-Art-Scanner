# Aura Art Scanner
Aura Art Scanner es una aplicación conversacional en `Streamlit` para explorar, analizar y comparar obras de arte a partir de texto o imágenes. La interfaz combina chat multimodal, exploradores curados de artistas y objetos del MET, y una capa de referencias online para encontrar obras similares cuando el usuario sube una imagen.

## Qué hace Aura
- Analiza imágenes de arte subidas por el usuario.
- Detecta posibles artistas, estilos, períodos, materiales y tipos de obra.
- Responde con contexto visual e histórico usando Gemini o OpenAI.
- Permite activar referencias locales desde:
  - `Artist Explorer`
  - `MET Object Explorer`
- Busca imágenes similares en varias fuentes online cuando la obra es desconocida.
- Prioriza coincidencias del mismo artista y del mismo tipo de obra cuando hay suficientes pistas.
- Permite editar mensajes previos y regenerar la conversación desde ese punto.

## Funcionalidades principales
### Chat multimodal
- Sube una o varias imágenes.
- Escribe una pregunta o comentario.
- Aura analiza el contenido visual y responde con contexto artístico.

### Referencias locales
- `Artist Explorer`: navega artistas locales con biografía, nacionalidad, género y previews guardadas en disco.
- `MET Object Explorer`: explora objetos del MET desde un CSV local con filtros por título, departamento, período, rol y año.
- Puedes activar un artista o un objeto como contexto de referencia para el chat.

### Similitudes online
Cuando la imagen subida no tiene una referencia local clara, Aura intenta buscar obras similares en varias fuentes públicas:
- The Metropolitan Museum of Art Collection API
- Art Institute of Chicago API
- Cleveland Museum of Art Open Access API

La búsqueda prioriza:
- mismo artista
- mismo tipo de obra
- mismo período o materiales afines

Si una fuente falla, las demás siguen funcionando y la app no se rompe.

## Estructura del proyecto
- `UserInterface.py`: interfaz principal de Aura y lógica de análisis, búsqueda y renderizado.
- `prompts.py`: prompt base que guía el comportamiento del modelo.
- `met_art_data/`: dataset local de artistas y previews.
- `met_art_data2/`: dataset local del MET y sus imágenes extraídas.
- `assets/`: recursos visuales de la interfaz, incluyendo la imagen de fondo.

## Requisitos
- Python 3.13 o superior
- Acceso a internet para:
  - Gemini/OpenAI
  - búsquedas online de obras similares
  - cargar algunas imágenes remotas
- Variables de entorno para los modelos que quieras usar:
  - `OPENAI_API_KEY`
  - `GOOGLE_API_KEY`

## Instalación
1. Crea y activa tu entorno virtual.
2. Instala dependencias con `uv` o `pip`:

```bash
uv sync
```

Si prefieres `pip`, usa:

```bash
pip install -e .
```

## Ejecución
Arranca la app con:

```bash
streamlit run UserInterface.py
```

Con `uv` también puedes usar:

```bash
uv run streamlit run UserInterface.py
```

## Cómo usar Aura
1. Abre `Chat Studio`.
2. Sube una imagen de una obra.
3. Escribe tu pregunta o deja que Aura analice la pieza.
4. Si quieres más contexto, abre `Artist Explorer` o `MET Object Explorer` y activa una referencia.
5. Si la obra no es reconocida localmente, Aura intentará mostrar referencias similares de internet.

## Fuentes de datos online
Aura usa APIs públicas sin `API key` para enriquecer la experiencia:
- The Met Collection API
- Art Institute of Chicago API
- Cleveland Museum of Art Open Access API

## Notas de comportamiento
- Las coincidencias online son referencias probables, no atribuciones definitivas.
- Cuando el modelo detecta que una imagen parece escultura, cerámica, utensilio u otro objeto, intenta buscar ese mismo tipo antes de abrir la búsqueda a resultados más generales.
- Si una API externa no responde, Aura muestra solo los resultados disponibles sin interrumpir la conversación.

## Personalización visual
La interfaz usa:
- una imagen de fondo local en `assets/reflets_du_soir_echappee_belle.jpeg`
- paneles translúcidos
- tipografía y colores ajustados para una lectura más suave

## Desarrollo
Los cambios más importantes viven en `UserInterface.py`, así que si vas a extender Aura normalmente empezarás ahí:
- lógica de chat
- análisis de imágenes
- búsqueda de referencias online
- exploradores locales
- estilo visual de la interfaz

## Licencia
Revisa `LICENSE` para los términos del proyecto.
