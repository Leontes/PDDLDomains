# The catalog

**English** · [Español](../es/catalogo.md)

`dominios/<origin>/<collection>/`: each collection is a domain with its problems, stored
once, in the folder of its origin. A collection's identifier is `<origin>/<collection>`, for
example `ipc-2006/trucks-time-constraints`; on the command line its last part is enough if
it is unambiguous (`trucks-time-constraints`).

Collection names are those of their origin: the ones of
[potassco/pddl-instances](https://github.com/potassco/pddl-instances) for the IPC from 1998
to 2011 (which state the track and the variant: `driverlog-time-simple-automatic`), those of
the IPC 2023 repositories and those of SMTPlan. The type does **not** decide the folder: a
domain may be temporal and PDDL 3 at the same time, and that is queried with
`pddldomains list --type …`.

## Contents of a collection

| File | What it is |
|------|------------|
| `domain.pddl` | the domain |
| `domain-pNN.pddl` | one domain per problem, instead of `domain.pddl` (openstacks and parc-printer from IPC 2011) |
| `pNN.pddl` | the problems; `pNN` is instance `NN` of the origin |
| `pNN.plan` | reference plan, when the origin provides one (IPC 2023) |
| `info.toml` | the card |

## The card (`info.toml`)

```toml
title = "Trucks (Time, Constraints)"
description = "Logística con camiones cuyo espacio de carga se organiza por zonas…"
description-en = "Logistics with trucks whose loading space is organized in areas…"
authors = "Yannis Dimopoulos, Alfonso Gerevini, and Alessandro Saetti"   # optional
notes = "…"                                                               # optional
notes-en = "…"                                                            # if there are notes

[origin]
source = "IPC 2006"                       # competition or provenance (required)
repository = "https://github.com/potassco/pddl-instances"   # except for own collections
commit = "cf19edf"
path = "ipc-2006/domains/trucks-time-constraints"
# Source files: {n} is the problem number and {nn} the same with two digits.
domain = "domain.pddl"                    # "domains/domain-{n}.pddl" if one per problem
problems = "instances/instance-{n}.pddl"
plans = "p{nn}.plan"                      # optional
instances = 20                            # how many instances the origin has
homepage = "https://…"                    # optional

[[errata]]
kind = "requirements"   # (*) an undeclared requirement; "other" (‡) anything else
files = ["domain.pddl"] # wildcards allowed: "p*.pddl"
description = "Usa `total-cost` sin declarar `:action-costs`. Se ha añadido."
description-en = "It uses `total-cost` without declaring `:action-costs`. It has been added."
```

Texts are written in Spanish and English: every text field (`description`, `notes`,
`authors`, `source` and the errata `description`) may have an `-en` version, which is the
one shown in English (`tests/test_i18n.py` requires `description-en`, `notes-en` when there
are notes and the one of every erratum). `pddldomains info <collection>` shows the card
together with the analysis, in the tool's language.

## Errata

Files are copied **unmodified**, with two exceptions that are fixed in the file itself and
documented in the card:

- **(\*) requirements**: every construct used must have its requirement declared (strict
  mode; when `:requirements` is not declared, `:strips` is assumed). A mismatch is treated
  as an erratum of the file and the missing requirement is added.
- **(‡) other**: mismatches of another kind, when it is decided to fix them. Mostly
  repeated names: every name (domain, problem, types, constants, objects, predicates,
  functions and actions) is declared only once, even though PDDL allows otherwise, because a
  repeated name is hard to read and has caused problems (VAL crashes if a function is named
  like the domain). Preferences may repeat names.

If a domain needs changes of another kind, it is added as a new collection.

`pddldomains sources check` compares every file with its original (cloning the source
repository into `tools/fuentes/`) and fails if any difference is missing from the card's
errata; `pddldomains sources diff <collection>` shows them. `pddldomains lint` finds in the
originals every erratum fixed so far (checked by `tests/test_sources.py`).

## Classification

`pddldomains/features.py` walks each domain with its problems and records which
requirements it **uses**, in strict mode and following the rules of the PDDL 2.1 grammar.
The types come from that:

| Type | When |
|------|------|
| `classical` | no numeric fluents (except costs), durative actions, TILs, PDDL 3 or PDDL+ |
| `strips` / `adl` | classical without / with negation, disjunction, equality, quantifiers or conditional effects |
| `costs` | `:action-costs` (only `total-cost`), with no other numbers |
| `numeric` | `:numeric-fluents` (comparisons, numeric effects, a metric with `total-time`…) |
| `temporal` | `:durative-actions` |
| `continuous` | effects with `#t` in durative actions |
| `derived` | `:derived-predicates` |
| `til` | `(at <t> <literal>)` in `:init` |
| `preferences`, `constraints` | PDDL 3 |
| `object-fluents` | functions with an object type (PDDL 3.1) |
| `pddlplus` | processes and events |

A collection's types are those of the union of its problems; datasets filter by those of
each problem. The analysis is cached in `.cache/analisis.json` and redone when a file
changes.

## PDDL version (levels)

Besides the types, each domain has a **level**: the PDDL version needed for what it uses, on
an ordered scale of six levels, from STRIPS to PDDL+. A domain is at the highest level of the
requirements it uses, so the scale is cumulative: a planner supporting up to level N must
handle every domain of levels 1 to N. It is useful, for example, to test a planner as it
supports more of PDDL.

| Level | Version | Requirements that lead to it |
|------:|---------|------------------------------|
| 1 | STRIPS | none (`:strips`) |
| 2 | PDDL 1.2 | `:typing`, `:negative-preconditions`, `:disjunctive-preconditions`, `:equality`, `:existential-preconditions`, `:universal-preconditions`, `:conditional-effects` |
| 3 | PDDL 2.1 | `:numeric-fluents`, `:action-costs`, `:durative-actions`, `:duration-inequalities`, `:continuous-effects` |
| 4 | PDDL 2.2 | `:derived-predicates`, `:timed-initial-literals` |
| 5 | PDDL 3 | `:preferences`, `:constraints`, `:object-fluents` |
| 6 | PDDL+ | `:time` (processes and events) |

Three requirements are not at the level of the PDDL version that introduced them:

- `:typing` (PDDL 1.2, like STRIPS) is at level 2, with the rest of ADL, which includes it:
  level 1 is pure STRIPS, without types (blocksworld and gripper);
- `:action-costs` (PDDL 3.1) is at level 3, because action costs are a special case of the
  numeric fluents of PDDL 2.1. That is why the IPC 2011 classical domains with costs are at
  level 3;
- `:object-fluents` (PDDL 3.1) is at level 5, with the rest of PDDL 3.

The scale is `LEVELS` (`src/pddldomains/features.py`).

```bash
pddldomains levels                        # the scale and how many domains each level has
pddldomains list --max-level 3            # what a planner up to PDDL 2.1 must solve
pddldomains list --level "PDDL 2.2"       # that level only (also --min-level)
pddldomains info satellite-time-time-windows-strips   # "Level: 4 (PDDL 2.2) because of :timed-initial-literals"
pddldomains dataset by-level --export salidas/by-level    # levelN/<origin>/<collection>/
```

`tests/test_catalog.py` checks the level of fifteen reference domains, two or three per
level.

## Provenance

| Origin | Repository | Commit |
|--------|------------|--------|
| `ipc-1998` … `ipc-2011` | [potassco/pddl-instances](https://github.com/potassco/pddl-instances) | `cf19edf` |
| `ipc-2023-classical` | [ipc2023-classical/ipc2023-dataset](https://github.com/ipc2023-classical/ipc2023-dataset) | `1e29a0e` |
| `ipc-2023-numeric` | [ipc2023-numeric/ipc2023-dataset](https://github.com/ipc2023-numeric/ipc2023-dataset) | `0799944` |
| `smtplan` | [KCL-Planning/SMTPlan](https://github.com/KCL-Planning/SMTPlan) (`benchmarks/`) | `b085bd7` |
| `propios` | made by hand for the catalog (greenhouse) | |

Notes:

- IPC 2023 had no temporal, PDDL 3 or PDDL+ tracks; those collections come from the
  historical IPC archive (2002 to 2006) and from the SMTPlan benchmarks.
- The ENHSP PDDL+ benchmarks were left out because they use `:constraint`, an extension of
  that planner that is not standard.
- From satellite (IPC 2004) instances 1 to 20 of 36 have been copied (the others weigh from
  90 KB to 3 MB), and from pathways (IPC 2006), 1 to 20 of 30. From the other collections,
  all of them or the first 20.
- In the IPC 2023 repository, `sat/rubiks-cube` is a link to `opt/rubiks-cube`.

## Adding a collection

1. Create `dominios/<origin>/<collection>/` with its `info.toml`, with a complete
   `[origin]`.
2. `pddldomains sources fetch <collection> --problems 1-20`: copies the domain, the problems
   (as `pNN.pddl`) and the plans from the origin, and checks them.
3. Fix whatever the checker reports (`pddldomains lint <collection>`) and document each fix
   in `[[errata]]`, in Spanish and English.
4. `pddldomains sources check <collection>`: every difference with the original documented.
5. `pddldomains index` and `pytest`.

An own collection (without a repository) only needs the files and a card with
`[origin] source = "…"`, and goes in `dominios/propios/`.
