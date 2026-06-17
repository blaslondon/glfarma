# glfarma-bot 🤖

Bot de Telegram para consultas internas de GL Farma — normas de obras sociales y procedimientos.

## Arquitectura

```
Google Drive (carpeta "normas para bot")
        ↓ (drive_watcher, cada 5 min)
  Extracción de texto (pdfplumber)
        ↓
  ChromaDB (embeddings vectoriales)
        ↓
  Telegram Bot (python-telegram-bot)
        ↓
  Claude API (genera la respuesta)
```

## Setup local

### 1. Clonar e instalar dependencias
```bash
git clone https://github.com/tu-usuario/glfarma-bot
cd glfarma-bot
pip install -r requirements.txt
```

### 2. Google Service Account
1. Ir a [Google Cloud Console](https://console.cloud.google.com)
2. Crear proyecto nuevo → Habilitar Google Drive API
3. Crear Service Account → Descargar JSON
4. Guardar en `credentials/service_account.json`
5. Compartir la carpeta "normas para bot" con el email del service account

### 3. Variables de entorno
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 4. Correr localmente
```bash
python main.py
```

## Deploy en Railway

### Variables de entorno a configurar en Railway:
| Variable | Descripción |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token del bot de BotFather |
| `ANTHROPIC_API_KEY` | API key de Anthropic |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path al JSON (o contenido como string) |
| `CHROMA_PATH` | `/data/chroma` (usar volumen persistente) |

### Volumen persistente
En Railway, crear un volumen en `/data` para que ChromaDB persista entre deployments.

## Uso

El bot responde consultas en lenguaje natural:
- "¿Cuál es el procedimiento para OSDE?"
- "¿Qué documentación pide PAMI para recetas?"
- "¿Cómo proceso una receta de Swiss Medical?"

## Actualizar normas

Simplemente subir un PDF a la carpeta "normas para bot" en Google Drive.
El bot lo detecta automáticamente en el próximo ciclo (máximo 5 minutos) y lo incorpora.
