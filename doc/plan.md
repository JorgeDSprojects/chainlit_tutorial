# Plan: Implementación Fases 5 + 6 + Carga de Archivos

> **Fecha**: 17 de diciembre de 2025  
> **Estado**: Aprobado  
> **Versión**: 2.0

Plan integral para memoria, historial persistente, modelos dinámicos y carga de archivos.

## Configuración Global

| Parámetro | Valor | Ubicación |
|-----------|-------|-----------|
| MAX_CONTEXT_MESSAGES | 15 | .env |
| VISION_MODEL | llama3.2-vision | .env |
| PDF_CHUNK_SIZE | 2000 | .env |
| PDF_CHUNK_OVERLAP | 200 | .env |
| MAX_PDF_SIZE_MB | 10 | .env |
| MAX_IMAGE_SIZE_MB | 5 | .env |

---

## Fase 5: Sistema de Memoria

### 5.1 Configuración de Límites
- **Archivo**: `src/config.py`
- **Cambios**: Añadir `MAX_CONTEXT_MESSAGES`, `VISION_MODEL`, `PDF_CHUNK_SIZE`, `PDF_CHUNK_OVERLAP`, `MAX_PDF_SIZE_MB`, `MAX_IMAGE_SIZE_MB`
- **Validación**: Cambiar valor en .env → Reiniciar → Verificar que se aplica el nuevo límite

### 5.2 Memoria a Corto Plazo
- **Archivos**: `src/services/llm_service.py`, `src/app.py`
- **Cambios**: 
  - Modificar `stream_response()` para recibir `history: list[dict]`
  - Mantener lista de mensajes en `cl.user_session`, truncar a `MAX_CONTEXT_MESSAGES`
- **Validación**: 
  1. Enviar "Mi color favorito es azul"
  2. Enviar "¿Cuál es mi color favorito?"
  3. ✅ Bot responde "azul"

### 5.3 Memoria a Largo Plazo
- **Archivo nuevo**: `src/services/conversation_service.py`
- **Funciones**: `create_conversation()`, `add_message()`, `get_conversation_history()`, `delete_conversation()`
- **Cambios en** `src/app.py`:
  - `@cl.on_chat_start`: crear nueva `Conversation` vinculada al usuario
  - `@cl.on_message`: guardar mensaje user y assistant en BD
- **Validación**: 
  1. Mantener una conversación
  2. Abrir chat.db con DB Browser
  3. ✅ Verificar registros en `conversations` y `messages` con `user_id` correcto

---

## Fase 6: Threads e Historial

### 6.1 Data Layer para Chainlit
- **Archivo nuevo**: `src/services/chainlit_data_layer.py`
- **Implementar**: `BaseDataLayer` de Chainlit
- **Métodos**: `get_user_threads()`, `get_thread()`, `delete_thread()`, `create_step()`, `update_thread()`
- **Validación**: 
  1. Iniciar sesión
  2. Ver barra lateral con historial
  3. ✅ Click en chat antiguo → Se carga la conversación

### 6.2 Reanudar Conversaciones
- **Archivo**: `src/app.py`
- **Implementar**: `@cl.on_chat_resume`
- **Lógica**: Cargar historial de BD → Popular `cl.user_session["history"]` → Mostrar mensajes previos
- **Validación**: 
  1. Tener conversación con 5 mensajes
  2. Cerrar chat
  3. Reabrir desde historial
  4. ✅ Ver los 5 mensajes y poder continuar

### 6.3 Modelos Dinámicos de Ollama
- **Archivo**: `src/services/llm_service.py`
- **Función nueva**: `get_ollama_models()` → `GET http://localhost:11434/api/tags`
- **Cambios en** `src/app.py`:
  - Modificar `@cl.on_chat_start` para construir `ChatSettings` dinámicamente
  - Añadir selector de temperatura (0.0 - 1.0)
- **Validación**: 
  1. Ejecutar `ollama pull phi`
  2. Refrescar chat
  3. ✅ "phi" aparece en lista de modelos

### 6.4 Configuración Persistente por Usuario
- **Archivo**: `src/db/models.py`
- **Modelo nuevo**: `UserSettings` con `user_id`, `default_model`, `temperature`, `favorite_models` (JSON)
- **Archivo nuevo**: `src/services/user_settings_service.py`
- **Funciones**: `get_settings()`, `save_settings()`
- **Cambios en** `src/app.py`:
  - `@cl.on_settings_update`: persistir cambios en BD
  - `@cl.on_chat_start`: cargar settings del usuario
- **Validación**: 
  1. Cambiar modelo a "qwen2.5" y temperatura a 0.7
  2. Cerrar sesión
  3. Iniciar sesión
  4. ✅ Settings deben estar en "qwen2.5" y 0.7

---

## Fase 7: Carga de Archivos

### 7.1 Procesador de Archivos
- **Dependencias nuevas** en `requirements.txt`: `pypdf2`, `Pillow`
- **Archivo nuevo**: `src/services/file_processor.py`
- **Funciones**:
  - `extract_pdf_text(file_bytes) -> str`
  - `chunk_text(text, chunk_size=2000, overlap=200) -> list[str]`
  - `summarize_chunks(chunks, llm_service) -> str`
  - `read_txt(file_bytes) -> str`
  - `validate_file_size(file_bytes, file_type) -> bool`
- **Validación**: 
  1. Subir PDF de 10 páginas
  2. ✅ Se divide en chunks y genera resumen concatenado

### 7.2 Selector Manual de Modelo Multimodal
- **Cambios en** `src/app.py`:
  - Añadir en ChatSettings: selector "Modelo para imágenes"
  - Cargar modelos con capacidad vision de Ollama
- **Lógica**: Si hay imagen adjunta → usar modelo vision seleccionado
- **Validación**: 
  1. Adjuntar imagen
  2. ✅ Bot describe el contenido usando modelo vision configurado

### 7.3 Integración en Chat
- **Archivo**: `src/app.py`
- **Modificar** `@cl.on_message` para detectar `msg.elements`
- **Tipos soportados**: `.pdf`, `.txt`, `.png`, `.jpg`, `.jpeg`
- **Lógica**:
  - Texto/PDF: extraer contenido → añadir como contexto
  - Imágenes: enviar a modelo vision → incluir descripción
- **Validación**: 
  1. Subir archivo.txt con "Hola mundo"
  2. Preguntar "¿Qué dice el archivo?"
  3. ✅ Bot responde "Hola mundo"

---

## Orden de Implementación

| Paso | Tarea | Dependencia | Estado |
|------|-------|-------------|--------|
| 1 | 5.1 Configuración de límites | - | ⬜ Pendiente |
| 2 | 5.2 Memoria corto plazo | 5.1 | ⬜ Pendiente |
| 3 | 5.3 Memoria largo plazo | 5.2 | ⬜ Pendiente |
| 4 | 6.3 Modelos dinámicos | - | ⬜ Pendiente |
| 5 | 6.4 Settings por usuario | 6.3 | ⬜ Pendiente |
| 6 | 6.1 Data Layer | 5.3 | ⬜ Pendiente |
| 7 | 6.2 Reanudar conversaciones | 6.1 | ⬜ Pendiente |
| 8 | 7.1 Procesador archivos | - | ⬜ Pendiente |
| 9 | 7.2 Modelo multimodal | 6.3, 7.1 | ⬜ Pendiente |
| 10 | 7.3 Integración chat | 7.1, 7.2 | ⬜ Pendiente |

---

## Archivos a Crear

- `src/services/conversation_service.py`
- `src/services/chainlit_data_layer.py`
- `src/services/user_settings_service.py`
- `src/services/file_processor.py`

## Archivos a Modificar

- `src/config.py`
- `src/app.py`
- `src/services/llm_service.py`
- `src/db/models.py`
- `requirements.txt`
- `.env`