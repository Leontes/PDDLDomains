# Datasets

**English** · [Español](../es/datasets.md)

A dataset is a list of catalog problems, grouped, for testing. It is defined in a TOML file
(the repository's ones are in `datasets/`) or with the command-line filters.

## Definitions

```toml
description = "Lo que es y para qué sirve"
description-en = "What it is and what it is for"   # the English description

[[group]]                       # an explicit group
name = "strips/blocksworld"
collection = "ipc-2000/blocks-strips-untyped"
problems = ["p01", "p02"]       # optional: all of them if not given

[[select]]                      # a selection: each chosen collection is a group
types = ["temporal"]
exclude-types = ["pddlplus"]
max-kb = 50
per-collection = 3
order = "random"
seed = 1
```

Several `[[group]]` and `[[select]]` blocks can be mixed; the dataset is their union, in
order. A selection accepts:

| Key | What it does |
|-----|--------------|
| `collections`, `exclude-collections` | identifiers, with wildcards (`"ipc-2011/*"`) |
| `types`, `exclude-types` | types (`pddldomains types`); with `types` all of them are required |
| `requirements`, `exclude-requirements` | used requirements (`":durative-actions"`) |
| `levels` | accepted PDDL version levels, by number or name (`3`, `"PDDL 2.1"`, `"pddl+"`…; see [catalog.md](catalog.md#pddl-version-levels)) |
| `min-level`, `max-level` | a range of levels; `max-level = 3` is what a planner supporting up to PDDL 2.1 must solve |
| `problems` | problem names, with wildcards (`"p0*"`) |
| `min-objects`, `max-objects`, `max-kb` | size of each problem |
| `with-plan` | only problems with a reference plan |
| `per-collection` | at most this many problems per collection… |
| `order` | …in this order: `first` (natural, default), `smallest` or `random` |
| `seed` | seed of the random order (the same dataset every time) |
| `group` | template of the group name: `{id}` (default), `{origin}`, `{name}`, `{level}` (the collection's level) |

Types, requirements and levels are checked on each problem with its domain: a
`preferences` selection keeps only the problems that have preferences.

For "this **or** that", use two `[[select]]` blocks (see `datasets/pddl3.toml`).

## The repository's datasets

`pddldomains dataset --list-definitions` lists them:

| Dataset | What it is |
|---------|------------|
| `by-level` | the two smallest problems of each collection, grouped by PDDL version level (`levelN/<collection>`) |
| `smoke-test` | the smallest problem of each collection |
| `small-classical` | the three smallest classical problems of each collection |
| `temporal` | five random temporal problems (fixed seed) per collection, without PDDL 3 or PDDL+ |
| `pddl3` | five problems with preferences or constraints per collection |
| `with-plans` | the problems with a reference plan |

## Command line

```bash
pddldomains dataset temporal                         # '<domain> <problem>' per line
pddldomains dataset temporal --relative              # paths relative to the catalog
pddldomains dataset temporal --format csv            # or json, with types and sizes
pddldomains dataset temporal -o list.txt             # to a file
pddldomains dataset --type numeric --max-kb 10       # without a definition: with filters
pddldomains dataset by-level --max-level 3           # up to PDDL 2.1, grouped by level
pddldomains dataset by-level --type temporal         # filters narrow the definition
pddldomains dataset by-level --export salidas/by-level            # copy
pddldomains dataset by-level --export salidas/by-level --link     # symbolic links
pddldomains list --type preferences                  # the collections that match the filter
```

When exporting, each group goes to `<destination>/<group>/` in the catalog format (domain,
problems and plans), and `<destination>/dataset.json` is written with the list of problems
(paths relative to the destination, types and sizes).

## From Python

```python
from pddldomains import load_dataset, select

for task in load_dataset("smoke-test"):             # Task: domain, problem, plan, id
    ...

dataset = select(types=["temporal"], per_collection=2, order="smallest")  # underscores
up_to_21 = select(max_level="PDDL 2.1")
for entry in dataset.entries:                       # with the group and the analysis
    print(entry.group, entry.task.problem, entry.analysis.tags, entry.analysis.size)
```

From another project, with `pip install -e ../PDDLDomains`; `$PDDL_DOMINIOS` points to
another catalog directory if needed.
