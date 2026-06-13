# Uso de GSAP en JugueteríaBot

GSAP se integra como mejora progresiva del panel. Si el CDN no carga, el panel sigue funcionando con CSS y React básico.

## Skills aplicadas

| Skill | Uso en este proyecto |
|---|---|
| gsap-core | Animaciones limpias de entrada, botones, cards, navbar y formularios. |
| gsap-timeline | Secuencias ordenadas para hero, cards y tablas sin saturar el navegador. |
| gsap-performance | Solo se animan `transform` y `opacity`; se evita animar `width`, `height`, `top`, `left`, `margin` o `padding`. |
| gsap-scrolltrigger | Reservado para páginas visuales/públicas. En el panel administrativo se evita saturar tablas largas. |
| gsap-react | Para una futura migración a React con bundler/Vite. El panel actual usa React UMD progresivo, por eso aquí se usa GSAP por CDN. |

## Reglas de rendimiento

1. Animar principalmente `x`, `y`, `scale`, `rotation`, `opacity` y `autoAlpha`.
2. No animar propiedades que recalculan layout en listas o tablas grandes.
3. Respetar `prefers-reduced-motion`.
4. Usar animaciones cortas: 0.2 a 0.7 segundos.
5. No bloquear formularios ni flujos críticos por una animación.
6. En páginas públicas, usar ScrollTrigger solo por secciones, no por cada elemento individual.

## React futuro con gsap-react

Cuando el frontend se migre a React/Vite, instalar:

```bash
npm install gsap @gsap/react
```

Patrón recomendado:

```jsx
import { useRef } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(useGSAP);

export function PanelCards() {
  const scope = useRef(null);

  useGSAP(() => {
    gsap.from(".card", {
      opacity: 0,
      y: 24,
      duration: 0.5,
      stagger: 0.06,
      ease: "power2.out"
    });
  }, { scope });

  return <section ref={scope}>...</section>;
}
```

El uso de `scope` evita animar elementos fuera del componente.
