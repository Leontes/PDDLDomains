# VAL

[English](../en/val.md) · **Español**

[VAL](https://github.com/KCL-Planning/VAL) es el validador de planes de referencia de la IPC.
`scripts/build_val.sh [ref]` lo descarga y compila (git, cmake y g++) y deja en `tools/bin/`
`Validate` (valida planes) y `Parser` (comprueba la sintaxis). Por defecto compila el commit
`3c7a1f3`, el último de la rama `master` (2021). También se buscan en `$VAL_BIN` y en el
`PATH`.

```bash
pddldomains validate dominio.pddl p01.pddl p01.plan [otro.plan…]
pddldomains validate --task ipc-2023-classical/folding/p01 mi-plan.plan
pddldomains validate --reference with-plans        # planes de referencia de un dataset…
pddldomains validate --reference folding           # …o de una colección
pddldomains validate ... -t 0.001 -m 4000 -v       # tolerancia, MB y salida de VAL
pddldomains lint --val <objetivo>                  # Parser de VAL además de la revisión
```

Desde Python, `pddldomains.val.validate(dominio, problema, plan)` devuelve un `ValResult`
con `verdict` (`valid`, `invalid` o `error`), `message`, `value` ("Final value") y
`violated` (las preferencias violadas).

## El veredicto se lee del texto

El código de salida de VAL **no es fiable**: sale con 1 si el plan no es válido, pero con 0
si no puede leer el plan ("Bad plan file!"), también cuando el fichero no existe. Así que:

| Veredicto | Cuándo |
|-----------|--------|
| `valid` | la salida dice "Plan valid" |
| `invalid` | el plan se ha leído y no es válido (código 1, "Goal not satisfied", "Plan failed"…) |
| `error` | VAL no ha dado veredicto: plan ilegible, fallo de segmentación, sin memoria o sin tiempo. No dice nada del plan |

VAL se ejecuta con un límite duro de memoria virtual (`RLIMIT_AS`, por defecto el 80 % de
la memoria disponible): con planes grandes de preferencias puede necesitar mucha (2,3 GB
con storage p20 de la IPC 2006) y, sin límite, agotar la de la máquina. Si se queda sin memoria
termina con `std::bad_alloc` y el resultado es `error`, no `invalid`.

## Rarezas conocidas

Encontradas validando planes con esa versión de VAL. La revisión avisa de las que se ven
en los ficheros (códigos `val-*`, ver [revision.md](revision.md)).

**Fallos de segmentación** (código 139, sin salida):

- un problema sin sección `:init`, aunque es opcional en PDDL;
- una función que se llama igual que el dominio (dominio `battery` con función `(battery)`);
- cualquier dominio con `:object-fluents`, incluso uno mínimo.

**Resultados equivocados:**

- `(:constraints (and))` vacío: cuenta como violadas todas las preferencias del objetivo y
  da mal "Final value". Sin la sección, bien.
- `hold-after` no funciona: dice "Failure to satisfy" incluso con planes trivialmente
  válidos, y a veces falla con un fallo de segmentación.
- En las restricciones de trayectoria evalúa `>` estricto como `>=`:
  `(sometime (> (ca) 0))` cuenta como cumplida con `ca = 0` todo el rato. Explica todos los
  valores de VAL distintos de los de PDDL 3 en tpp y pathways (IPC 2006).
- pathways (IPC 2006): VAL da por violada `p0A` pero no suma su peso a "Final value" (da 1
  en lugar de 9 con un plan de una acción). Causa desconocida.
- Redondeo en los límites exactos de una invariante: un plan en el que una variable
  continua acaba justo en la cota de un `over all` se rechaza; con 1e-6 más de margen es
  válido.

**Restricciones que impone:**

- La tolerancia por defecto (`-t`) es 0,01: dos sucesos más cercanos cuentan como
  simultáneos. Un planificador que use ε = 0,001 tiene que validar con `-t 0.001`.
- Exclusión mutua: rechaza ("Mutex violation") dos sucesos en el mismo instante si uno lee
  un hecho y el otro lo escribe, aunque la escritura no cambie su valor.
- "Bad plan description!" si una acción durativa usa `?duration` en una condición (la
  gramática de PDDL 2.1 tampoco lo permite).
- Rechaza `:condition ()`; hay que escribir `(and)`.
- Para planes secuenciales, la acción k ocurre en el instante k (importa en las
  restricciones con tiempo).

**Avisos falsos de `Parser`:**

- "Undeclared requirement :action-costs" cuando se usa `total-cost` en un dominio que
  declara `:fluents` o `:numeric-fluents`, que ya lo cubren (tpp de la IPC 2006).
