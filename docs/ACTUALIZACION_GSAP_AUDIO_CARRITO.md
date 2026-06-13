# Actualización: entrada GSAP, confirmación de producto y notas de voz

## 1. Entrada animada al dashboard

Se añadió una pantalla inicial solo para `/panel` con logo y nombre de Robles Outlet. La animación usa GSAP Timeline y después muestra el dashboard.

Archivos modificados:

- `templates/base.html`
- `static/panel.css`
- `static/panel-gsap.js`

Reglas aplicadas:

- Animar `opacity`, `scale` y `transform`, no `width`, `height`, `top` ni `left`.
- Respetar `prefers-reduced-motion`.
- Mantener la animación como mejora visual, sin bloquear rutas ni lógica del panel.

## 2. Corrección del carrito conversacional

Antes, en el estado de agregar otro producto, frases como `muéstrame productos` podían entrar al fuzzy matching y terminar como producto incorrecto. También una categoría como `Peluches` podía tomarse como producto.

Ahora el flujo es:

1. El cliente pide ver productos o escribe una categoría.
2. El bot muestra productos o categorías sin agregar nada al carrito.
3. El cliente escribe el nombre exacto del producto.
4. El bot muestra precio, stock y categoría.
5. El cliente confirma con `sí`.
6. Solo entonces el bot pide cantidad.
7. El producto entra al carrito hasta que se captura la cantidad válida.

Nuevo estado conversacional:

```text
EsperandoConfirmacionProducto
```

## 3. Soporte para notas de voz

Se añadió procesamiento de mensajes `audio` del webhook de WhatsApp.

Flujo:

1. Meta envía `media_id` de audio.
2. El sistema descarga el audio con el token de Meta.
3. OpenAI transcribe el audio en español.
4. El texto transcrito se pasa al mismo motor conversacional del bot.
5. La consulta se guarda como `[AUDIO] transcripcion=...`.

Variable nueva en `.env`:

```env
AUDIO_TRANSCRIPTION_MODEL=whisper-1
```

No se usa la transcripción para decidir precios ni stock. La transcripción solo reemplaza el texto que el cliente habría escrito; inventario, stock y precios siguen saliendo de SQL Server.
