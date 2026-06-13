# Seguridad y estabilidad añadida

- Logs separados en `logs/app.log`, `logs/whatsapp.log` y `logs/errores.log`.
- Rate limit básico para `/chat` y webhook de WhatsApp.
- Ruta `/diagnostico` para validar entorno, SQL y OpenAI.
- Ruta `/panel/diagnostico` para validar SQL Server, Meta WhatsApp, OpenAI y variables de entorno.
- Rol `lectura` para revisión sin permisos de escritura.
- Validación de stock antes de confirmar pedido y antes de marcar entregado.
- Descuento de stock solo al marcar como entregado.

Antes de vender el sistema, cambiar contraseñas y `PANEL_SECRET_KEY` en `.env`.
