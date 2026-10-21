# Datasets

[English](../en/datasets.md) · **Español**

Un dataset es una lista de problemas del catálogo agrupados, para hacer pruebas. Se define
en un fichero TOML (los del repositorio están en `datasets/`) o con los filtros de la línea
de comandos.

## Definiciones

```toml
description = "Lo que es y para qué sirve"
description-en = "What it is and what it is for"   # la descripción en inglés

[[group]]                       # un grupo explícito
name = "strips/blocksworld"
collection = "ipc-2000/blocks-strips-untyped"
problems = ["p01", "p02"]       # opcional: todos si no se dice

[[select]]                      # una selección: cada colección elegida es un grupo
types = ["temporal"]
exclude-types = ["pddlplus"]
max-kb = 50
per-collection = 3
order = "random"
seed = 1
```

Se pueden mezclar varios `[[group]]` y varios `[[select]]`; el dataset es la unión, en
orden. Una selección admite:

| Clave | Qué hace |
|-------|----------|
| `collections`, `exclude-collections` | identificadores, con comodines (`"ipc-2011/*"`) |
| `types`, `exclude-types` | tipos (`pddldomains types`); con `types` se exigen todos |
| `requirements`, `exclude-requirements` | requisitos usados (`":durative-actions"`) |
| `levels` | niveles de versión de PDDL admitidos, por número o nombre (`3`, `"PDDL 2.1"`, `"pddl+"`…; ver [catalogo.md](catalogo.md#versión-de-pddl-niveles)) |
| `min-level`, `max-level` | un rango de niveles; `max-level = 3` es lo que tiene que resolver un planificador que llega a PDDL 2.1 |
| `problems` | nombres de problema, con comodines (`"p0*"`) |
| `min-objects`, `max-objects`, `max-kb` | tamaño de cada problema |
| `with-plan` | solo problemas con plan de referencia |
| `per-collection` | como mucho tantos problemas por colección… |
| `order` | …en este orden: `first` (natural, por defecto), `smallest` o `random` |
| `seed` | semilla del orden aleatorio (el mismo dataset cada vez) |
| `group` | plantilla del nombre del grupo: `{id}` (por defecto), `{origin}`, `{name}`, `{level}` (el nivel de la colección) |

Los tipos, requisitos y niveles se miran en cada problema con su dominio: una selección de
`preferences` se queda solo con los problemas que tienen preferencias.

Para "esto **o** aquello" se usan dos `[[select]]` (ver `datasets/pddl3.toml`).

## Las del repositorio

`pddldomains dataset --list-definitions` las enumera:

| Dataset | Qué es |
|---------|--------|
| `by-level` | los dos problemas más pequeños de cada colección, agrupados por nivel de versión de PDDL (`levelN/<colección>`) |
| `smoke-test` | el problema más pequeño de cada colección (prueba de humo) |
| `small-classical` | los tres problemas clásicos más pequeños de cada colección |
| `temporal` | cinco temporales al azar (semilla fija) por colección, sin PDDL 3 ni PDDL+ |
| `pddl3` | cinco problemas con preferencias o restricciones por colección |
| `with-plans` | los problemas con plan de referencia |

## Línea de comandos

```bash
pddldomains dataset temporal                         # '<dominio> <problema>' por línea
pddldomains dataset temporal --relative              # rutas relativas al catálogo
pddldomains dataset temporal --format csv            # o json, con tipos y tamaños
pddldomains dataset temporal -o lista.txt            # a un fichero
pddldomains dataset --type numeric --max-kb 10       # sin definición: con filtros
pddldomains dataset by-level --max-level 3           # hasta PDDL 2.1, agrupado por nivel
pddldomains dataset by-level --type temporal         # los filtros restringen la definición
pddldomains dataset by-level --export salidas/by-level            # copia
pddldomains dataset by-level --export salidas/by-level --link     # enlaces simbólicos
pddldomains list --type preferences                  # las colecciones que cumplen el filtro
```

Al exportar, cada grupo queda en `<destino>/<grupo>/` con el formato del catálogo (dominio,
problemas y planes) y se escribe `<destino>/dataset.json` con la lista de problemas
(rutas relativas al destino, tipos y tamaños).

## Desde Python

```python
from pddldomains import load_dataset, select

for task in load_dataset("smoke-test"):             # Task: domain, problem, plan, id
    ...

dataset = select(types=["temporal"], per_collection=2, order="smallest")  # guiones bajos
hasta_21 = select(max_level="PDDL 2.1")
for entry in dataset.entries:                       # con el grupo y el análisis
    print(entry.group, entry.task.problem, entry.analysis.tags, entry.analysis.size)
```

Desde otro proyecto, con `pip install -e ../PDDLDomains`; `$PDDL_DOMINIOS` apunta a otro
directorio de catálogo si hace falta.
