# Generadores de problemas

[English](../en/generators.md) · **Español**

```bash
pddldomains generate --list                       # los generadores y si están disponibles
pddldomains generate barman --params              # sus parámetros y explicación
pddldomains generate barman -n 5 -s 7             # 5 problemas, semillas 7…11
pddldomains generate barman -p cocktails=4..8     # rango: se sortea en cada problema
pddldomains generate barman -p cocktails=3,5,7 -n 2   # serie: 2 problemas por valor
pddldomains generate smtplan/car-nodrag           # también por la colección
pddldomains generate random-walk -p collection=sokoban-sequential-satisficing -n 10
```

Cada generador produce problemas para el dominio de una colección del catálogo. La salida
(por defecto `salidas/generados/<generador>/`, o `-o DIR`; `--force` la vacía) tiene:

- `domain.pddl`: copia del dominio del catálogo (`domain-pNN.pddl` en las colecciones con un
  dominio por problema);
- `pNN.pddl` y, si el generador lo conoce, `pNN.plan`, un plan válido;
- `generation.json`: el generador, su commit (en los externos), la semilla y los parámetros
  resueltos de cada problema, para repetir la generación.

Después, `generate` revisa cada problema contra su dominio (`lint`) y valida con VAL los
planes que haya; sale con código 1 si algo falla (`--no-check` lo evita). Cada problema usa
su propia semilla (la inicial más su posición), así que la misma orden genera siempre los
mismos problemas.

Los parámetros admiten un valor (`-p tanks=4`), un rango (`-p tanks=2..8`, entero o real
según el parámetro) o una serie (`-p tanks=2,4,6`; con varias series, todas las
combinaciones). Unos pocos (`tank-fuel`) sortean el rango para cada elemento (cada
depósito) en lugar de una vez por problema. Los parámetros que harían el problema
imposible se rechazan con un mensaje.

## Generadores

### Propios (`generators/own.py`)

Escritos para la versión exacta de las colecciones sin generador público que encaje. Cada
uno explica en su ayuda (`--params`) por qué sus problemas tienen solución.

| Generador | Colección | Parámetros |
|-----------|-----------|------------|
| `counters` | `ipc-2023-numeric/counters` | `counters`, `max-int` (por defecto, el doble) |
| `zenotravel-numeric` | `ipc-2023-numeric/zenotravel` | `cities`, `planes`, `people`, `max-distance`, `plane-goals` |
| `car` | `smtplan/car-nodrag` | `limit`, `max-time` |
| `generator-linear`, `generator-nonlinear` | `smtplan/…` | `tanks`, `surplus` |
| `generator-events`, `generator-toricelli` | `smtplan/…` | `tanks`, `surplus`, `tank-fuel` (y `flow`) |
| `greenhouse` | `propios/greenhouse` | `tanks`, `rain` |

### Externos (`generators/external.py`)

`scripts/build_generators.sh` descarga y compila en `tools/` (con git, make, gcc, g++ y
cmake), con commit fijo,
[pddl-generators](https://github.com/AI-Planning/pddl-generators) (`e6277fb`) y los
generadores de la IPC 2023. Las envolturas retocan la salida para que encaje con el dominio
del catálogo:

| Generador | Colección | Retoques |
|-----------|-----------|----------|
| `barman`, `nomystery` | `ipc-2011/…` | añaden `(= (total-cost) 0)` y la métrica, que no escriben |
| `blocksworld` | `ipc-2000/blocks-strips-untyped` | `arm-empty` → `handempty`, `on-table` → `ontable`, dominio `blocks` |
| `elevators`, `floortile`, `scanalyzer`, `transport`, `visitall`, `woodworking` | `ipc-2011/…` | |
| `gripper` | `ipc-1998/gripper-round-1-strips` | (determinista: solo depende de `balls`) |
| `driverlog`, `zenotravel` | `ipc-2002/…-time-simple-automatic` | (opción `-s`, *simple time*) |
| `rubiks-cube` | `ipc-2023-classical/rubiks-cube` | |
| `folding`, `labyrinth` | `ipc-2023-classical/…` | dan además un plan; labyrinth necesita `pip install -e '.[generators]'` |

En todos, el nombre del problema pasa a ser el de la generación.

Sin envoltura, porque generan otra versión del dominio o necesitan herramientas que no hay:

- sokoban (genera el sokoban con tipos de la IPC 2008, no el de 2011) y zenotravel `-n`
  (la numérica de 2002, no la de 2023, que tiene generador propio);
- tidybot (necesita Clojure/Leiningen) y peg-solitaire (Ruby);
- recharging-robots (cairo, scipy y shapely), ricochet-robots (un resolvedor ASP) y
  slitherlink (Haskell);
- openstacks y parc-printer (sin generador en pddl-generators), y las colecciones PDDL 3
  de la IPC 2006 y satellite con ventanas de tiempo (sus generadores no producen esas
  variantes).

Para las clásicas de esta lista está `random-walk`.

### Portado (`generators/parking.py`)

`parking` (`ipc-2011/parking-sequential-satisficing`) era el único generador de Perl de
pddl-generators y se ha traducido a Python para no depender de Perl. Es una traducción
literal: reproduce el generador de números aleatorios de Perl (`drand48`) y el orden en que
el original lo llama, así que con la misma semilla da **exactamente** el mismo problema (se
comprobó en 1716 combinaciones de plazas, coches y semillas; los tests lo comparan con
salidas del original guardadas en `tests/datos/parking/`). Como la envoltura del original,
añade `(= (total-cost) 0)` y la métrica, que el original no escribe, y cambia el nombre del
problema (el original lo llamaba como el dominio, la errata (‡) del catálogo). No necesita
nada de `tools/`.

### Paseo aleatorio (`generators/walk.py`)

`random-walk` sirve para cualquier colección clásica sin predicados derivados (STRIPS y
ADL: tipos, negación, disyunción, cuantificadores, igualdad y efectos condicionales; los
costes se ignoran al simular):

1. parte de un problema de la colección (`base`, por defecto el más pequeño): sus objetos y
   su estado inicial;
2. aplica `steps` acciones al azar, prefiriendo las que llevan a estados nuevos;
3. elige como objetivo `goals` hechos que no estaban al principio, primero de los predicados
   del objetivo del problema base (`on` en blocks, `at-goal` en sokoban…).

El paseo es un plan válido (se guarda como `pNN.plan` y se valida con VAL), así que el
problema tiene solución. Con `mode=both` cambia también el estado inicial: se da un paseo
del doble de largo y el estado de la mitad pasa a ser el inicial.

Los objetivos de un paseo suelen ser más fáciles que los de la IPC: sirven para tener muchas
variantes de un dominio, no para medir.

## Añadir un generador

- **Propio** (o portado): una subclase de `Generator` en `generators/own.py` con `name`,
  `collection`, `description`, `params` y `generate()`, que devuelve un `GeneratedProblem`
  (el texto, opcionalmente un plan); `check()` rechaza los parámetros sin solución, y el
  docstring de la clase es la explicación que muestra `--params`. Se añade a
  `OWN_GENERATORS`.
- **Externo**: un `ExternalGenerator(...)` en `generators/external.py` con la orden y los
  retoques, y su compilación en `scripts/build_generators.sh`.

En los dos casos, `tests/test_generators.py` lo prueba solo: genera unos problemas y los
revisa contra el dominio del catálogo. La descripción, la ayuda de los parámetros y la
explicación se escriben en español y necesitan su traducción en
`src/pddldomains/translations.py` (`tests/test_i18n.py` avisa si falta).
