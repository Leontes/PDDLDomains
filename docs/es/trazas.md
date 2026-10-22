# Trazas de plan

[English](../en/traces.md) · **Español**

```bash
pddldomains trace dominio.pddl p01.pddl p01.plan -o traza.json
pddldomains trace --task rubiks-cube/p05                 # con el plan de referencia
pddldomains trace --task blocks-strips-untyped/p01 mi.plan --missing 30 --noise 5 --seed 7
pddldomains trace --task counters/p01 plan.txt --missing-states 20 --world open --val
pddldomains trace --task folding/p03 --planner lama --planner-config lama-first --planner-seed 1
```

`trace` ejecuta un plan sobre su problema, comprobando la precondición de cada acción, y
escribe en JSON los estados por los que pasa: el inicial y el que deja cada acción, con la
acción y sus argumentos. Puede degradar las observaciones (huecos, estados que faltan y
ruido) de forma reproducible, y anota en la traza cómo lo ha hecho y de dónde salen el
dominio, el problema y el plan.

Sale con código 0 si el plan alcanza el objetivo (y VAL lo da por válido, con `--val`); 1 si
no lo alcanza, aunque escribe la traza igualmente; y 2 si el plan no se puede ejecutar (una
acción desconocida o no aplicable) o la entrada no es válida.

## Una traza

Los dos primeros pasos de un plan de blocks, con un 20 % de huecos (resumida):

```json
{
  "format": "pddldomains-trace",
  "version": 1,
  "generator": "pddldomains 0.1.0",
  "collection": "ipc-2000/blocks-strips-untyped",
  "domain": {"name": "blocks", "file": "ipc-2000/blocks-strips-untyped/domain.pddl", "sha256": "7c9c…"},
  "problem": {"name": "blocks-4-0", "file": "ipc-2000/blocks-strips-untyped/p01.pddl", "id": "p01", "sha256": "9d48…"},
  "plan": {"file": "p01.plan", "sha256": "f215…", "length": 2, "planner": "mi-planificador", "config": null, "seed": null},
  "execution": {"goal_reached": false, "val": null},
  "degradation": {
    "seed": 1, "missing_percent": 20.0, "missing_states_percent": 0.0, "noise_percent": 0.0,
    "numeric_noise_percent": 10.0, "hidden_atoms": 18, "hidden_values": 0, "flipped_atoms": 0,
    "perturbed_values": 0, "missing_states": []
  },
  "world": "closed",
  "universe": {"kind": "dynamic", "size": 29},
  "objects": {"a": "object", "b": "object", "c": "object", "d": "object"},
  "states": [
    {"step": 0, "time": 0, "true": ["(clear a)", "(clear b)", "(clear c)", "(handempty)", "(ontable a)", "(ontable c)", "(ontable d)"],
     "unknown": ["(clear d)", "(on a b)", "(on a d)", "(on c c)", "(on d d)", "(ontable b)"], "values": {}, "unknown_values": []},
    {"step": 1, "time": 1, "true": ["(clear a)", "(clear c)", "(clear d)", "(ontable a)", "(ontable c)"],
     "unknown": ["(holding a)", "(holding b)", "(on a c)", "(on a d)", "(on d b)", "(ontable d)"], "values": {}, "unknown_values": []},
    {"step": 2, "time": 2, "true": ["(clear b)", "(clear c)", "(clear d)", "(handempty)", "(ontable a)", "(ontable d)"],
     "unknown": ["(on a b)", "(on b a)", "(on b c)", "(on c c)", "(on c d)", "(ontable c)"], "values": {}, "unknown_values": []}
  ],
  "actions": [
    {"step": 1, "time": 1, "name": "pick-up", "arguments": ["b"]},
    {"step": 2, "time": 2, "name": "stack", "arguments": ["b", "a"]}
  ]
}
```

`states[i]` es el estado `i` y `actions[i-1]` la acción que lleva del estado `i-1` al `i`.
El fichero tiene un estado o una acción por línea; con `--compact`, todo en una sola.

### Estados

Cada estado da el valor de los átomos del universo:

- `true`: los ciertos, incluidos los de predicados derivados;
- `unknown`: los desconocidos (huecos);
- `false`: los falsos, solo con `--world open`. Por defecto la traza es de mundo cerrado
  (`"world": "closed"`): un átomo del universo que no está entre los ciertos ni entre los
  desconocidos es falso.

Y el de los fluentes numéricos que tienen valor, incluidos los constantes (`capacity`,
`distance`…): `values` los observados y `unknown_values` los desconocidos.

Un estado que falta entero solo tiene `step`, `time` y `"missing": true`.

### Universo de átomos

El universo son los átomos de los que la traza da el valor (`--universe`):

- `dynamic` (por defecto): todas las instancias, según los tipos, de los predicados que
  cambian las acciones y de los derivados, más los átomos estáticos ciertos en el estado
  inicial. El resto de átomos estáticos son falsos en todos los estados: no se listan ni se
  degradan.
- `typed`: todas las instancias de todos los predicados según los tipos.

Los dos incluyen además cualquier átomo cierto en algún estado, aunque no respete los tipos.
En los dominios con muchos predicados estáticos la diferencia es enorme: en slitherlink el
universo `typed` llega a 400 millones de átomos y el `dynamic` a menos de 20 000. Una
traza no se genera si el universo pasa de `--max-atoms` (por defecto, 250 000).

### Objetos

`objects` da el tipo declarado de cada objeto y constante (`["either", "t1", "t2"]` con
`either`; `object` si el dominio no tiene tipos), pero no la jerarquía de tipos: está en el
dominio.

### Pasos e instantes

`step` es el número del estado (0 el inicial) o de la acción (desde 1). `time` es el
instante: en un plan sin instantes, como en VAL, la acción `i` y el estado que deja están en
el instante `i`. Si el plan da instantes (`0.000: (acción ...) [1.000]`), las acciones se
ordenan por instante, cada una está en el suyo y el estado que deja, en el instante más la
duración. Los planes temporales no se pueden ejecutar: el simulador solo admite acciones
instantáneas.

## Degradación

| Opción | Qué hace |
|--------|----------|
| `--missing P` | el P % de los átomos y de los valores numéricos de cada estado pasan a ser desconocidos |
| `--missing-states P` | falta el P % de los estados enteros |
| `--noise P` | se invierte el P % de los átomos observados (no desconocidos) de cada estado y se altera el P % de sus valores numéricos observados |
| `--numeric-noise Q` | un valor alterado cambia como mucho un Q % de su valor (de 1 si es 0), al alza o a la baja (por defecto, 10) |
| `--seed N` | la semilla (por defecto, 0) |

- **Exacta**: los porcentajes se aplican en cada estado, redondeando: con 29 átomos y
  `--missing 20`, cada estado tiene exactamente 6 desconocidos. `degradation` anota cuántos
  átomos y valores se han ocultado, invertido o alterado en total, y qué estados faltan.
- **Reproducible**: con los mismos ficheros y la misma semilla, la traza es idéntica. Cada
  elección (huecos, ruido, estados) usa su propia secuencia aleatoria, derivada de la
  semilla y del estado, con `random()`, cuya secuencia Python garantiza entre versiones.
- **Anidada**: con la misma semilla, los huecos de `--missing 30` incluyen los de
  `--missing 20`, y lo mismo con los estados que faltan y con el ruido (con los mismos
  huecos). Sirve para estudiar cómo empeora un método al quitarle información, sin que
  cambie todo de un porcentaje al siguiente.
- Solo se degradan los estados. Las acciones se dan siempre completas.

## Procedencia

- `collection`: la colección del catálogo del dominio (`null` si no es del catálogo).
- `domain`, `problem`: el nombre que declaran, el fichero (relativo al catálogo si es suyo)
  y su SHA-256. El problema de una colección lleva además su identificador (`id`, `p01`).
  El dominio es la referencia con la que validar después: `pddldomains validate` o VAL.
- `plan`: el fichero, su SHA-256, su longitud y el planificador que lo dio, con su
  configuración y su semilla (`--planner`, `--planner-config`, `--planner-seed`), si se dan.
- `execution`: si el plan alcanza el objetivo y, con `--val`, el veredicto de VAL (`valid`,
  `invalid` o `error`).
- `degradation`: los parámetros, la semilla y lo que se ha degradado.

## El simulador

Los estados los calcula `pddldomains.simulator`, el mismo que usa el paseo aleatorio de los
generadores. Admite STRIPS y ADL (tipos, negación, disyunción, cuantificadores, igualdad y
efectos condicionales), predicados derivados (estratificados), fluentes numéricos
(comparaciones, aritmética e `increase`, `decrease`, `assign`, `scale-up` y `scale-down`) y
costes de acción. Las preferencias se toman como ciertas y las restricciones de trayectoria
no se comprueban. No admite acciones durativas, procesos, eventos, literales iniciales
temporizados ni fluentes de objetos.

Los efectos de una acción se calculan sobre el estado de antes (también los numéricos) y se
aplican a la vez: primero los borrados y después las adiciones.

Los tests comparan sus estados, paso a paso, con los que se reconstruyen de la salida de
`Validate -v` (las líneas `Adding`, `Deleting` y `Updating`): los planes de referencia de la
IPC 2023 y planes aleatorios de dominios numéricos y con predicados derivados. Durante el
desarrollo se comprobaron así 139 planes de todas las colecciones del catálogo con acciones
instantáneas, sin ninguna diferencia.

## Desde Python

```python
from pathlib import Path
from pddldomains.traces import Degradation, Provenance, generate_trace, write_trace

trace = generate_trace(
    Path("domain.pddl"), Path("p01.pddl"), Path("p01.plan"),
    degradation=Degradation(missing=30, noise=5, seed=7),
    provenance=Provenance("lama", "lama-first", 1),
)
with open("traza.json", "w", encoding="utf-8") as stream:
    write_trace(trace, stream)
```

Para generar muchas trazas desde el mismo plan con distintas degradaciones, `execute()`
ejecuta el plan una vez y `build_trace()` construye cada traza a partir de esa ejecución.

## Rendimiento

El coste crece con el tamaño del universo por el número de estados. Con `--missing 30
--noise 5`, 84 de los 100 planes de referencia del catálogo tardan menos de un segundo. Los
más lentos son los de folding, con universos de hasta 110 000 átomos: p07 (753 estados)
tarda 35 s, usa 340 MB de memoria y da 470 MB de JSON. Sin degradación es unas cuatro veces
más rápido.
