# Chatbot Integrado con Langchain y Google APIs

Este proyecto integra Langchain, Gmail y Google Drive para crear un asistente inteligente que:

- Recibe y responde Webhooks provenientes de cambios en archivos de Google Drive.
- Notifica por correo electrónico sobre modificaciones importantes.
- Usa Langchain para responder preguntas contextuales sobre documentos.

## 🧠 Características

- 🔁 Monitorización de archivos en tiempo real vía Webhook.
- 📬 Notificaciones automáticas por correo (usando Gmail API).
- 📄 Capacidad de análisis contextual de archivos (PDF, texto) usando Langchain.
- 🔗 Integración con agentes personalizados.
- 🔊 Preparado para integrarse a plataformas como n8n o Zapier.

## 🗂️ Estructura del Proyecto

- `ChatBot-Langchain.py`: Configura el agente de Langchain, herramientas personalizadas y procesamiento de preguntas.
- `ChatBot-GoogleDriveWebhook.py`: Endpoint para recibir cambios desde Google Drive vía Webhook.
- `Chatbot-NotificacionesyCambios.py`: Procesa cambios en archivos y envía notificaciones por correo electrónico.

## ⚙️ Requisitos

Antes de ejecutar, instala las dependencias:

```bash
pip install -r requirements.txt
```

Variables de entorno necesarias (.env o variables del sistema):
```bash
GOOGLE_DRIVE_CREDENTIALS_JSON
GMAIL_USER
LANGCHAIN_API_KEY
WEBHOOK_SECRET_TOKEN
```

## 🛡️ Recomendaciones
- Asegúrate de tener autenticación habilitada para las APIs de Google (OAuth2 o service account).
- Usa ngrok o despliegue en cloud para exponer el Webhook si estás en desarrollo local.
- El modelo LLM puede configurarse para usar OpenAI, Gemini, u otro proveedor compatible con Langchain.
