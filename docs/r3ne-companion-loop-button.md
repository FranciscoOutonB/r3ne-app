# Companion — botón LOOP CLIP (R3NeServer)

Repite el clip bajo el playhead. **Solo actúa cuando el reloj es nuestro**: free-run,
o chase con la señal perdida. Un timecode externo *enganchado* es el master y el loop
se hace a un lado — el botón lo indica en ámbar.

R3NeServer **sí tiene módulo propio de Companion** (`swift-app/companion-module-r3ne-server`,
v1.4.0): trae la acción *Loop clip*, los feedbacks *Loop armed* / *Loop held by external
timecode* y un preset **LOOP** ya armado con los dos colores — no hay que configurar nada
a mano. Lo de abajo es la receta equivalente con **Generic OSC**, por si prefieres no
instalar el módulo.

## Conexión

| | |
|---|---|
| Módulo | Generic OSC |
| Target IP | IP de la Mac que corre R3NeServer (`127.0.0.1` si es la misma) |
| Target Port | **9000** (entrada de comandos) |
| Listen Port | **9001** (feedback de estado) |

En R3NeServer: activa Companion y pon *feedback host/port* apuntando a la Mac de
Companion. Si Companion escucha en otro puerto, mándale una vez
`/r3ne/subscribe <puerto>` y el servidor reapunta el feedback solo.

## Comandos

| OSC | Efecto |
|---|---|
| `/r3ne/loop` | alterna |
| `/r3ne/loop` + int `1` / `0` | fuerza encendido / apagado |
| `/r3ne/loop/on`, `/r3ne/loop/off` | explícito, para una botonera de dos teclas |

## Feedback

| OSC | Valor |
|---|---|
| `/r3ne/state/loop` | `1` = loop armado |
| `/r3ne/state/loopheld` | `1` = armado pero un timecode enganchado manda ahora mismo |

## El botón

**Un botón (toggle)**

- Text: `LOOP`
- Press → actions → *Generic OSC: Send message without arguments* → `/r3ne/loop`
- Feedback 1 → *Variable value* → `$(osc:/r3ne/state/loop)` = `1` → fondo **verde**
- Feedback 2 → *Variable value* → `$(osc:/r3ne/state/loopheld)` = `1` → fondo **ámbar**
  (ponlo DEBAJO del anterior para que gane cuando el timecode manda)

Ámbar = está armado pero no está ciclando: hay timecode enganchado. Si la señal se
cae, vuelve a verde solo y el clip sigue corriendo en vez de congelarse.

**Dos botones (on / off), si prefieres estado explícito**

- LOOP ON  → `/r3ne/loop/on`,  feedback `$(osc:/r3ne/state/loop)` = `1` → verde
- LOOP OFF → `/r3ne/loop/off`, feedback `$(osc:/r3ne/state/loop)` = `0` → gris

## Notas de operación

- Al armarlo, el loop **fija** el clip que está sonando. Si haces cue a otra canción
  (`/r3ne/cue/index`, `/r3ne/cue/next`) o un seek, se re-fija al clip nuevo: loopea
  lo que acabas de lanzar.
- Es un ajuste de sesión, no se guarda en el `.r3show`: abrir un show nunca arranca
  ciclando por su cuenta.
- En la app está en la barra de transporte y en **⇧⌘L**.

## Con el módulo de R3NeServer

Categoría **Transport**: arrastra el preset `Loop clip` (un botón, verde/ámbar), o
`Loop on` / `Loop off` si quieres estado explícito. La acción es *Loop clip under the
playhead* con opción on / off / toggle.
