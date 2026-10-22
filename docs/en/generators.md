# Problem generators

**English** · [Español](../es/generadores.md)

```bash
pddldomains generate --list                       # the generators and whether they are available
pddldomains generate barman --params              # its parameters and explanation
pddldomains generate barman -n 5 -s 7             # 5 problems, seeds 7…11
pddldomains generate barman -p cocktails=4..8     # range: drawn for each problem
pddldomains generate barman -p cocktails=3,5,7 -n 2   # series: 2 problems per value
pddldomains generate smtplan/car-nodrag           # also by collection
pddldomains generate random-walk -p collection=sokoban-sequential-satisficing -n 10
```

Each generator produces problems for the domain of a catalog collection. The output (by
default `salidas/generados/<generator>/`, or `-o DIR`; `--force` empties it) contains:

- `domain.pddl`: a copy of the catalog domain (`domain-pNN.pddl` in collections with one
  domain per problem);
- `pNN.pddl` and, when the generator knows one, `pNN.plan`, a valid plan;
- `generation.json`: the generator, its commit (for external ones), the seed and the
  resolved parameters of each problem, to repeat the generation.

Then `generate` checks each problem against its domain (`lint`) and validates any plans with
VAL; it exits with code 1 if something fails (`--no-check` skips this). Each problem uses its
own seed (the initial one plus its position), so the same command always generates the same
problems.

Parameters take a value (`-p tanks=4`), a range (`-p tanks=2..8`, integer or real depending
on the parameter) or a series (`-p tanks=2,4,6`; with several series, all combinations). A
few (`tank-fuel`) draw the range for each item (each tank) instead of once per problem.
Parameters that would make the problem unsolvable are rejected with a message.

## Generators

### Own (`generators/own.py`)

Written for the exact version of the collections without a public generator that fits. Each
one explains in its help (`--params`) why its problems are solvable.

| Generator | Collection | Parameters |
|-----------|------------|------------|
| `counters` | `ipc-2023-numeric/counters` | `counters`, `max-int` (default: twice the counters) |
| `zenotravel-numeric` | `ipc-2023-numeric/zenotravel` | `cities`, `planes`, `people`, `max-distance`, `plane-goals` |
| `car` | `smtplan/car-nodrag` | `limit`, `max-time` |
| `generator-linear`, `generator-nonlinear` | `smtplan/…` | `tanks`, `surplus` |
| `generator-events`, `generator-toricelli` | `smtplan/…` | `tanks`, `surplus`, `tank-fuel` (and `flow`) |
| `greenhouse` | `propios/greenhouse` | `tanks`, `rain` |

### External (`generators/external.py`)

`scripts/build_generators.sh` downloads and builds in `tools/` (with git, make, gcc, g++ and
cmake), at fixed commits,
[pddl-generators](https://github.com/AI-Planning/pddl-generators) (`e6277fb`) and the IPC 2023
generators. The wrappers adjust the output so that it fits the catalog's domain:

| Generator | Collection | Adjustments |
|-----------|------------|-------------|
| `barman`, `nomystery` | `ipc-2011/…` | add `(= (total-cost) 0)` and the metric, which they do not write |
| `blocksworld` | `ipc-2000/blocks-strips-untyped` | `arm-empty` → `handempty`, `on-table` → `ontable`, domain `blocks` |
| `elevators`, `floortile`, `scanalyzer`, `transport`, `visitall`, `woodworking` | `ipc-2011/…` | |
| `gripper` | `ipc-1998/gripper-round-1-strips` | (deterministic: depends only on `balls`) |
| `driverlog`, `zenotravel` | `ipc-2002/…-time-simple-automatic` | (option `-s`, *simple time*) |
| `rubiks-cube` | `ipc-2023-classical/rubiks-cube` | |
| `folding`, `labyrinth` | `ipc-2023-classical/…` | also produce a plan; labyrinth needs `pip install -e '.[generators]'` |

In all of them, the problem is renamed after the generation.

Not wrapped, because they generate another version of the domain or need tools that are not
available:

- sokoban (generates the typed sokoban of IPC 2008, not the 2011 one) and zenotravel `-n`
  (the numeric one of 2002, not the 2023 one, which has its own generator);
- tidybot (needs Clojure/Leiningen) and peg-solitaire (Ruby);
- recharging-robots (cairo, scipy and shapely), ricochet-robots (an ASP solver) and
  slitherlink (Haskell);
- openstacks and parc-printer (no generator in pddl-generators), and the PDDL 3 collections
  of IPC 2006 and satellite with time windows (their generators do not produce those
  variants).

For the classical ones in this list there is `random-walk`.

### Ported (`generators/parking.py`)

`parking` (`ipc-2011/parking-sequential-satisficing`) was the only Perl generator in
pddl-generators, and it has been translated to Python so as not to depend on Perl. It is a
literal translation: it reproduces Perl's random number generator (`drand48`) and the order
in which the original calls it, so with the same seed it gives **exactly** the same problem
(checked on 1716 combinations of curbs, cars and seeds; the tests compare it with outputs of
the original stored in `tests/datos/parking/`). Like the wrapper of the original, it adds
`(= (total-cost) 0)` and the metric, which the original does not write, and renames the
problem (the original named it like the domain, the catalog's (‡) erratum). It needs
nothing from `tools/`.

### Random walk (`generators/walk.py`)

`random-walk` works for any classical collection without derived predicates (STRIPS and
ADL: types, negation, disjunction, quantifiers, equality and conditional effects; costs do
not influence the walk):

1. it starts from a problem of the collection (`base`, by default the smallest): its
   objects and its initial state;
2. it applies `steps` random actions, preferring those that lead to new states;
3. it picks as goal `goals` facts that were not there at the start, first from the
   predicates of the base problem's goal (`on` in blocks, `at-goal` in sokoban…).

The walk is a valid plan (saved as `pNN.plan` and validated with VAL), so the problem is
solvable. The actions are applied with the same simulator as
[`trace`](traces.md#the-simulator). With `mode=both` the initial state changes too: a walk
twice as long is taken and the state halfway becomes the initial one.

Random-walk goals are usually easier than the IPC ones: they are meant to provide many
variants of a domain, not to benchmark.

## Adding a generator

- **Own** (or ported): a subclass of `Generator` in `generators/own.py` with `name`,
  `collection`, `description`, `params` and `generate()`, which returns a
  `GeneratedProblem` (the text, optionally a plan); `check()` rejects parameters without a
  solution, and the class docstring is the explanation shown by `--params`. It is added to
  `OWN_GENERATORS`.
- **External**: an `ExternalGenerator(...)` in `generators/external.py` with the command and
  the adjustments, and its build in `scripts/build_generators.sh`.

In both cases, `tests/test_generators.py` tests it automatically: it generates a few
problems and checks them against the catalog's domain. The description, the parameter help
and the explanation are written in Spanish and need their translation in
`src/pddldomains/translations.py` (`tests/test_i18n.py` reports any missing one).
