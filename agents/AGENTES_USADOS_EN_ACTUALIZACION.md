# Agentes usados como referencia técnica

La actualización se diseñó con roles equivalentes a los agentes que se habían propuesto para JugueteríaBot:

## Backend Architect
- Mantiene FastAPI como núcleo.
- Integra OpenAI sin romper el webhook actual.
- Conserva SQL Server como fuente de verdad para productos, stock, pedidos y pagos.

## Workflow Architect
- El agente interpreta intención y entidades.
- El bot actual conserva estados como `CompraPendiente`, `EsperandoCantidad`, `EsperandoDireccion`, `EsperandoMetodoPago` y `CompraListaParaConfirmacion`.
- Se evita que un mensaje confuso salte pasos obligatorios.

## Security Engineer
- El agente no confirma pagos.
- El agente no inventa stock.
- El agente no crea pedidos directamente.
- Las tools internas consultan SQL Server mediante funciones controladas.

## API Tester
- Se agregó validación por compilación de Python.
- Se conservan endpoints existentes.
- Se agregó proveedor opcional `openwa` sin eliminar Meta Cloud API.

## Reality Checker
- OpenWA se dejó como opción, no como reemplazo obligatorio.
- Meta WhatsApp Cloud API sigue siendo el proveedor predeterminado por ser el canal oficial ya operativo del sistema.

## Support Responder
- El agente interpreta modismos, errores de escritura y mensajes incompletos.
- El generador de respuesta sigue usando los mensajes existentes del bot para evitar respuestas fuera del flujo.
