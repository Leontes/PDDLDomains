# El catálogo

[English](../en/catalog.md) · **Español**

`dominios/<origen>/<colección>/`: cada colección es un dominio con sus problemas, y está
una sola vez, en la carpeta de su origen. El identificador de una colección es
`<origen>/<colección>`, por ejemplo `ipc-2006/trucks-time-constraints`; en la línea de
comandos basta con la parte final si no es ambigua (`trucks-time-constraints`).

Los nombres de las colecciones son los de su origen: los de
[potassco/pddl-instances](https://github.com/potassco/pddl-instances) para la IPC de 1998 a
2011 (que dicen la pista y la variante: `driverlog-time-simple-automatic`), los de los
repositorios de la IPC 2023 y los de SMTPlan. El tipo **no** decide la carpeta: un dominio
puede ser temporal y PDDL 3 a la vez, y se consulta con `pddldomains list --type …`.

## Contenido de una colección

| Fichero | Qué es |
|---------|--------|
| `domain.pddl` | el dominio |
| `domain-pNN.pddl` | un dominio por problema, en lugar de `domain.pddl` (openstacks y parc-printer de la IPC 2011) |
| `pNN.pddl` | los problemas; `pNN` es la instancia `NN` del origen |
| `pNN.plan` | plan de referencia, si el origen lo trae (IPC 2023) |
| `info.toml` | la ficha |

## La ficha (`info.toml`)

```toml
title = "Trucks (Time, Constraints)"
description = "Logística con camiones cuyo espacio de carga se organiza por zonas…"
description-en = "Logistics with trucks whose loading space is organized in areas…"
authors = "Yannis Dimopoulos, Alfonso Gerevini, and Alessandro Saetti"   # opcional
notes = "…"                                                               # opcional
notes-en = "…"                                                            # si hay notes

[origin]
source = "IPC 2006"                       # competición o procedencia (obligatorio)
repository = "https://github.com/potassco/pddl-instances"   # salvo en las propias
commit = "cf19edf"
path = "ipc-2006/domains/trucks-time-constraints"
# Ficheros de origen: {n} es el número del problema y {nn}, el mismo con dos cifras.
domain = "domain.pddl"                    # "domains/domain-{n}.pddl" si hay uno por problema
problems = "instances/instance-{n}.pddl"
plans = "p{nn}.plan"                      # opcional
instances = 20                            # cuántas instancias tiene el origen
homepage = "https://…"                    # opcional

[[errata]]
kind = "requirements"   # (*) un requisito sin declarar; "other" (‡) cualquier otra
files = ["domain.pddl"] # admite comodines: "p*.pddl"
description = "Usa `total-cost` sin declarar `:action-costs`. Se ha añadido."
description-en = "It uses `total-cost` without declaring `:action-costs`. It has been added."
```

Los textos van en español y en inglés: cada campo de texto (`description`, `notes`,
`authors`, `source` y la `description` de las erratas) puede tener su versión `-en`, que es
la que se muestra en inglés (`tests/test_i18n.py` exige `description-en`, `notes-en` si hay
notas y la de cada errata). `pddldomains info <colección>` muestra la ficha junto con el
análisis, en el idioma de la herramienta.

## Erratas

Los ficheros se copian **sin modificar**, con dos excepciones que se corrigen en el propio
fichero y se documentan en la ficha:

- **(\*) requisitos**: toda construcción que se use tiene que tener su requisito declarado
  (modo estricto; si no se declara `:requirements`, se supone `:strips`). Una discordancia
  se trata como errata del fichero y se añade el requisito que falta.
- **(‡) otras**: las discordancias de otro tipo, cuando se decide corregirlas. Sobre todo
  nombres repetidos: cada nombre (dominio, problema, tipos, constantes, objetos,
  predicados, funciones y acciones) se declara una sola vez, aunque PDDL lo permita, porque
  un nombre repetido es difícil de leer y ha dado problemas (VAL falla si una función se
  llama como el dominio). Las preferencias sí pueden repetir nombre.

Si un dominio necesita retoques de otro tipo, se añade como colección nueva.

`pddldomains sources check` compara cada fichero con su original (clonando el repositorio
de origen en `tools/fuentes/`) y falla si alguna diferencia no está en las erratas de la
ficha; `pddldomains sources diff <colección>` las muestra. `pddldomains lint` encuentra en
los originales todas las erratas corregidas hasta ahora (lo comprueba
`tests/test_sources.py`).

## Clasificación

`pddldomains/features.py` recorre cada dominio con sus problemas y anota qué requisitos
**usa**, en modo estricto y con las reglas de la gramática de PDDL 2.1.
De ahí salen los tipos:

| Tipo | Cuándo |
|------|--------|
| `classical` | sin fluentes numéricos (salvo costes), acciones durativas, TIL, PDDL 3 ni PDDL+ |
| `strips` / `adl` | clásico sin / con negación, disyunción, igualdad, cuantificadores o efectos condicionales |
| `costs` | `:action-costs` (solo `total-cost`), sin más números |
| `numeric` | `:numeric-fluents` (comparaciones, efectos numéricos, métrica con `total-time`…) |
| `temporal` | `:durative-actions` |
| `continuous` | efectos con `#t` en acciones durativas |
| `derived` | `:derived-predicates` |
| `til` | `(at <t> <literal>)` en `:init` |
| `preferences`, `constraints` | PDDL 3 |
| `object-fluents` | funciones con tipo de objeto (PDDL 3.1) |
| `pddlplus` | procesos y eventos |

Los tipos de una colección son los de la unión de sus problemas; los datasets filtran por
los de cada problema. El análisis se guarda en `.cache/analisis.json` y se rehace al
cambiar un fichero.

## Versión de PDDL (niveles)

Además de los tipos, cada dominio tiene un **nivel**: la versión de PDDL que hace falta para
lo que usa, en una escala ordenada de seis niveles, de STRIPS a PDDL+. Un dominio está en el
nivel más alto de los requisitos que usa, así que la escala es acumulativa: un planificador
que soporta hasta el nivel N tiene que poder con todos los dominios de los niveles 1 a N.
Sirve, por ejemplo, para probar un planificador a medida que va soportando más PDDL.

| Nivel | Versión | Requisitos que llevan a él |
|------:|---------|----------------------------|
| 1 | STRIPS | ninguno (`:strips`) |
| 2 | PDDL 1.2 | `:typing`, `:negative-preconditions`, `:disjunctive-preconditions`, `:equality`, `:existential-preconditions`, `:universal-preconditions`, `:conditional-effects` |
| 3 | PDDL 2.1 | `:numeric-fluents`, `:action-costs`, `:durative-actions`, `:duration-inequalities`, `:continuous-effects` |
| 4 | PDDL 2.2 | `:derived-predicates`, `:timed-initial-literals` |
| 5 | PDDL 3 | `:preferences`, `:constraints`, `:object-fluents` |
| 6 | PDDL+ | `:time` (procesos y eventos) |

Tres requisitos no van en el nivel de la versión de PDDL que los introdujo:

- `:typing` (PDDL 1.2, como STRIPS) va en el nivel 2, con el resto de ADL, que lo incluye:
  el nivel 1 es STRIPS puro, sin tipos (blocksworld y gripper);
- `:action-costs` (PDDL 3.1) va en el nivel 3, porque los costes de acción son un caso
  particular de los fluentes numéricos de PDDL 2.1. Por eso los clásicos con costes de la
  IPC 2011 son de nivel 3;
- `:object-fluents` (PDDL 3.1) va en el nivel 5, con el resto de PDDL 3.

La escala está en `LEVELS` (`src/pddldomains/features.py`).

```bash
pddldomains levels                        # la escala y cuántos dominios hay en cada nivel
pddldomains list --max-level 3            # lo que tiene que resolver quien llega a PDDL 2.1
pddldomains list --level "PDDL 2.2"       # solo ese nivel (también --min-level)
pddldomains info satellite-time-time-windows-strips   # "Nivel: 4 (PDDL 2.2) por :timed-initial-literals"
pddldomains dataset by-level --export salidas/by-level    # levelN/<origen>/<colección>/
```

`tests/test_catalog.py` comprueba el nivel de quince dominios de referencia, dos o tres por
nivel.

## Procedencia

| Origen | Repositorio | Commit |
|--------|-------------|--------|
| `ipc-1998` … `ipc-2011` | [potassco/pddl-instances](https://github.com/potassco/pddl-instances) | `cf19edf` |
| `ipc-2023-classical` | [ipc2023-classical/ipc2023-dataset](https://github.com/ipc2023-classical/ipc2023-dataset) | `1e29a0e` |
| `ipc-2023-numeric` | [ipc2023-numeric/ipc2023-dataset](https://github.com/ipc2023-numeric/ipc2023-dataset) | `0799944` |
| `smtplan` | [KCL-Planning/SMTPlan](https://github.com/KCL-Planning/SMTPlan) (`benchmarks/`) | `b085bd7` |
| `propios` | creados a mano para el catálogo (greenhouse) | |

Notas:

- La IPC 2023 no tuvo pistas temporal, de PDDL 3 ni de PDDL+; esas colecciones salen del
  archivo histórico de la IPC (2002 a 2006) y de los benchmarks de SMTPlan.
- Los benchmarks PDDL+ de ENHSP se descartaron porque usan `:constraint`, una extensión de
  ese planificador que no es estándar.
- De satellite (IPC 2004) se han copiado las instancias 1 a 20 de 36 (las demás pesan de
  90 KB a 3 MB) y de pathways (IPC 2006), 1 a 20 de 30. De las demás colecciones, todas o
  las 20 primeras.
- En el repositorio de la IPC 2023, `sat/rubiks-cube` es un enlace a `opt/rubiks-cube`.

## Añadir una colección

1. Crear `dominios/<origen>/<colección>/` con su `info.toml`, con `[origin]` completo.
2. `pddldomains sources fetch <colección> --problems 1-20`: copia el dominio, los problemas
   (como `pNN.pddl`) y los planes del origen, y los revisa.
3. Corregir lo que diga la revisión (`pddldomains lint <colección>`) y documentar cada
   corrección en `[[errata]]`, en español y en inglés.
4. `pddldomains sources check <colección>`: toda diferencia con el original documentada.
5. `pddldomains index` y `pytest`.

Una colección propia (sin repositorio) solo necesita los ficheros y una ficha con
`[origin] source = "…"`, y va en `dominios/propios/`.
