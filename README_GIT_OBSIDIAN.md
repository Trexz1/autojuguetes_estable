# JugueteríaBot - versión limpia para Git/Obsidian

Esta carpeta está preparada para subirse a GitHub como repositorio privado o guardarse en Obsidian.

## Importante

No incluye archivos sensibles ni pesados:

- `.env` real
- logs
- entorno virtual `.venv`
- `dist/` y `build/`
- `__pycache__`
- ejecutables como `ngrok.exe`

Usa `.env.example` como plantilla y crea tu `.env` localmente.

## Estado

Versión estable del flujo de WhatsApp con confirmación final antes de crear pedido.

Flujo principal:

producto → confirmar producto → cantidad → carrito → agregar más → entrega → dirección → referencia → pago → resumen → confirmar/cancelar → crear pedido
