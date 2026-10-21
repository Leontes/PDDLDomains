# PDDLDomains

**English** · [Español](README.es.md)

A collection of PDDL domains and problems with tools to classify them, build test datasets,
check them for errors, validate plans with VAL and generate new random problems.

- **Catalog** (`dominios/`): 41 collections and 737 problems, from STRIPS to PDDL+, each
  stored once in the folder of its origin (`ipc-2011/barman-sequential-satisficing`,
  `smtplan/car-nodrag`…), with a card that documents where it comes from and which errata
  have been fixed. The [index](dominios/INDEX.md) lists them by origin, by type and by PDDL
  version.
- **Classification**: by type (`classical`, `temporal`, `preferences`, `pddlplus`…) and by
  PDDL version, on a cumulative scale of six levels (from STRIPS to PDDL+). Both are deduced
  from what each domain **uses** with its problems, not from what it declares.
- **Datasets**: lists of problems chosen with filters (type, requirement, level, size,
  number per collection…) or by hand, as a list of paths, CSV, JSON or exported to a
  directory.
- **Checking**: finds the typical errata of PDDL files (undeclared requirements, repeated
  or undeclared names, dashes glued to types…) and warns about what VAL does not handle.
- **VAL**: validates plans by reading VAL's verdict from its output, because VAL's exit
  code is not reliable.
- **Generators**: 25 random problem generators (written for this repository, from
  pddl-generators and from IPC 2023), including a generic one based on random walks that
  works for any classical domain and also produces a plan for each problem.

## Installation

Requires Python 3.12. The package has no dependencies: the catalog, the datasets, the
checker, the own generators and the random walk work with Python alone. VAL and the
external C/C++ generators also need git, make, gcc, g++ and cmake.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'        # with pytest, ruff and mypy
scripts/build_val.sh                     # VAL in tools/bin (git, cmake, g++)
scripts/build_generators.sh              # external generators in tools/ (optional)
.venv/bin/pip install -e '.[generators]' # modules for the labyrinth generator (optional)
```

`tools/` (VAL, generators and clones of the source repositories), `salidas/` and `.cache/`
are not under version control.

## Language

The tool speaks English or Spanish: help, checker messages, outputs and collection
descriptions. It uses Spanish with `--lang es`, with `PDDLDOMAINS_LANG=es` or with a Spanish
locale (`LANG=es_ES.UTF-8`); otherwise, English. Identifiers (subcommands, options, types,
checker codes, dataset names) are the same in both languages. Some folder names of the
repository (`dominios/`, `salidas/`) are Spanish.

## Usage

```bash
pddldomains list --type temporal                 # collections with durative actions
pddldomains info trucks-time-constraints         # card, analysis and problems
pddldomains types                                # the types and how many of each
pddldomains levels                               # the PDDL version scale
pddldomains list --max-level 3                   # what a planner up to PDDL 2.1 handles

pddldomains dataset smoke-test                   # '<domain> <problem>' per line
pddldomains dataset --type preferences --per-collection 3 --order smallest --format csv
pddldomains dataset temporal --export salidas/temporal   # copy to a directory
pddldomains dataset --list-definitions           # the definitions in datasets/

pddldomains lint                                 # check the whole catalog
pddldomains lint path/to/my/problems --val       # any directory, also with VAL
pddldomains validate domain.pddl p01.pddl p01.plan
pddldomains validate --reference with-plans      # the catalog's reference plans

pddldomains generate --list
pddldomains generate counters -n 10 -p counters=4..12          # random range
pddldomains generate barman -p cocktails=3,5,7 -n 2            # series: 2 per value
pddldomains generate random-walk -p collection=sokoban-sequential-satisficing -n 5

pddldomains sources check                        # compare with the original files
pddldomains index                                # regenerate dominios/INDEX.md and INDICE.md
```

From Python (for example, to parametrize the tests of a planner):

```python
import pytest
from pddldomains import load_dataset, select

@pytest.mark.parametrize("task", list(load_dataset("smoke-test")), ids=lambda t: t.id)
def test_solve(task):
    plan = solve(task.domain, task.problem)
    ...

temporal = select(types=["temporal"], exclude_types=["pddlplus"], per_collection=2)
```

To use it from another project, `pip install -e ../PDDLDomains` in its environment is
enough: the paths point to this repository's catalog (or to `$PDDL_DOMINIOS`).

## Layout

| Path | Contents |
|------|----------|
| `dominios/<origin>/<collection>/` | `domain.pddl` (or `domain-pNN.pddl`), `pNN.pddl`, `pNN.plan` when there is a reference plan, and `info.toml` |
| `dominios/INDEX.md`, `dominios/INDICE.md` | generated index, in English and Spanish |
| `datasets/*.toml` | dataset definitions |
| `src/pddldomains/` | the package and the CLI |
| `scripts/` | builds of VAL and the external generators |
| `docs/en/`, `docs/es/` | documentation, in English and Spanish |
| `tests/` | tests (`pytest`) |

## Documentation

- [Catalog](docs/en/catalog.md): format of the collections and their cards, errata,
  classification by type and by PDDL version, and how to add a collection.
- [Datasets](docs/en/datasets.md): definitions, filters and export.
- [Checking](docs/en/lint.md): the `lint` checks and the errata they came from.
- [VAL](docs/en/val.md): building, validation and known quirks.
- [Generators](docs/en/generators.md): the generators, their parameters and why their
  problems are solvable.

## Development

```bash
.venv/bin/pytest            # VAL, external generator and source tests are skipped if missing
.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
.venv/bin/mypy              # strict mode
```

The tool's texts are written in Spanish in the code and translated with the table in
`src/pddldomains/translations.py`; `tests/test_i18n.py` checks that none is left
untranslated.

## License

The code, the documentation and the own domains are distributed under the
[MIT license](LICENSE) (© 2026 José Segura). Third-party domains and problems in
`dominios/` keep their authors' terms, and the parking generator is a translation from
pddl-generators: see [LICENSES.md](LICENSES.md).
