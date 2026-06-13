# Actualización: Agente principal OpenAI para WhatsApp

Esta versión añade una capa inteligente al flujo conversacional de JugueteríaBot sin reemplazar el motor actual de pedidos.

## Arquitectura implementada

```text
Cliente WhatsApp
   ↓
Webhook FastAPI
   ↓
Agente principal de conversación OpenAI
   ↓
JSON estructurado para interpretar mensajes
   ↓
Motor de flujo actual del bot
   ↓
Tools internas controladas por FastAPI/SQL Server
   - buscar productos
   - consultar stock
   - crear pedido
   - calcular total
   - generar link de pago
   - consultar expos
   - avisar al administrador
   ↓
Respuesta por WhatsApp
```

## Archivos modificados

- `main.py`
  - Agrega `agente_principal_conversacion_openai()`.
  - Agrega esquema JSON estricto para clasificar intención, producto, cantidad, método de entrega, pago, dirección, cancelación y confirmaciones.
  - Agrega tools internas `tool_buscar_productos_sql()`, `tool_consultar_stock_sql()` y `tool_consultar_expos_sql()`.
  - Mantiene el bot actual como motor de flujo. El agente no confirma pagos, stock ni pedidos por sí solo.
  - Agrega soporte opcional para `WHATSAPP_PROVIDER=openwa`.
  - Guarda logs operativos de conversación.

- `.env.example`
  - Agrega configuración del agente principal.
  - Agrega configuración opcional de OpenWA.

- `MIGRACION_AGENTE_OPENAI.sql`
  - Crea tablas e índices para logs y contexto del agente.

- `MIGRACION_OPERATIVA_ACTUAL.sql`
  - Incluye también la actualización del agente para poder ejecutar una migración general.

## Variables nuevas

```env
CONVERSATION_AGENT_ENABLED=1
CONVERSATION_AGENT_MODEL=gpt-4.1-mini
CONVERSATION_AGENT_MIN_CONFIDENCE=0.45
```

## OpenWA opcional

El sistema sigue usando Meta WhatsApp Cloud API por defecto. OpenWA se dejó como proveedor opcional:

```env
WHATSAPP_PROVIDER=openwa
OPENWA_BASE_URL=http://localhost:2785
OPENWA_API_KEY=TU_API_KEY
OPENWA_SESSION_ID=my-bot
OPENWA_CHAT_SUFFIX=@c.us
```

OpenWA es un gateway self-hosted de WhatsApp con API HTTP y arquitectura pluggable. Para producción formal con una cuenta comercial, Meta Cloud API sigue siendo el canal más estable porque es el flujo oficial ya integrado en el proyecto.

## Seguridad del flujo

El agente solo interpreta mensajes. Las acciones sensibles quedan controladas por el backend:

- Stock: solo se confirma desde SQL Server.
- Precio: solo se muestra desde SQL Server.
- Pedido: solo se crea cuando el motor de flujo tiene datos completos.
- Pago: solo se confirma por Mercado Pago/webhook o por validación del panel.
- Envío: conserva costo local configurado en `ENVIO_DOMICILIO`.

## Script SQL requerido

Ejecuta una de estas dos opciones:

1. Solo la actualización del agente:

```sql
:r MIGRACION_AGENTE_OPENAI.sql
```

2. Migración operativa completa:

```sql
:r MIGRACION_OPERATIVA_ACTUAL.sql
```

En SQL Server Management Studio también puedes abrir el `.sql` y ejecutarlo directamente.
