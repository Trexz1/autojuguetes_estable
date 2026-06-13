# Agentes de trabajo para JugueteríaBot

Este proyecto no instala agentes como dependencias de ejecución. Los integra como **roles operativos** para guiar análisis, implementación, pruebas, empaquetado y venta del sistema.

## Equipo técnico principal

| Agente | Cuándo se usa | Resultado esperado |
|---|---|---|
| Workflow Architect | Antes de cambiar el flujo del bot, pedidos, expos o atención por WhatsApp. | Mapa de estados, entradas válidas, salidas, errores y recuperación. |
| Backend Architect | Al modificar FastAPI, endpoints, servicios, webhooks o estructura general. | Código organizado, rutas coherentes, separación de responsabilidades y compatibilidad con el sistema estable. |
| Database Optimizer | Al cambiar consultas SQL Server, stock, pedidos, clientes o reportes. | Consultas seguras, índices sugeridos, menos lecturas innecesarias y migraciones claras. |
| Security Engineer | Al tocar login, roles, tokens, sesiones, validaciones, CORS o endpoints públicos. | Menor superficie de ataque, secretos fuera del ZIP público, validación de entradas y errores controlados. |
| Frontend Developer | Al mejorar panel React/Jinja, tablas, formularios, dashboard o responsividad. | Interfaz más fluida, accesible, consistente y sin romper formularios existentes. |
| API Tester | Antes de entregar o comprimir. | Pruebas de endpoints críticos, login, CRUD, pedidos, webhook y errores esperados. |
| Reality Checker | Antes de cerrar una tarea. | Verificación de que lo pedido sí quedó implementado y no solo documentado. |
| Technical Writer | Al entregar a cliente, escuela o equipo. | Manuales, bitácoras, instrucciones de instalación y documentación de cambios. |

## Equipo para empaquetar en Windows

| Agente | Uso |
|---|---|
| DevOps Automator | Automatiza instalación, entorno virtual, requirements, PyInstaller, ngrok y scripts BAT. |
| Infrastructure Maintainer | Revisa arranque, rutas, logs, puertos, dependencias del sistema y recuperación ante fallos. |
| Backend Architect | Valida que el ejecutable cargue FastAPI y recursos internos. |
| Security Engineer | Evita incluir secretos reales en entregables y revisa permisos/roles. |
| Technical Writer | Mantiene instrucciones de instalación y operación. |
| Reality Checker | Confirma que el ZIP limpio contiene lo necesario para correr y mantener el sistema. |

## Revisión previa al ZIP

| Agente | Verificación |
|---|---|
| Code Reviewer | Sintaxis, imports, cambios peligrosos, duplicados y deuda técnica visible. |
| API Tester | Rutas, errores esperados, formularios y endpoints principales. |
| Evidence Collector | Evidencia de pruebas: comandos, resultados y archivos modificados. |
| Reality Checker | Cumplimiento contra la solicitud original. |
| Security Engineer | Secretos, .env, tokens, permisos, inyección SQL y exposición de endpoints. |

## Cómo pedirlos en futuras actualizaciones

Ejemplos:

```text
Usa Workflow Architect + Backend Architect + API Tester para cambiar el flujo de pedidos sin romper el bot.
```

```text
Usa Frontend Developer + GSAP Performance + Reality Checker para mejorar la interfaz y entregar ZIP limpio.
```

```text
Usa DevOps Automator + Infrastructure Maintainer + Security Engineer para crear instalador Windows.
```
