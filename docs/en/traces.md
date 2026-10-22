# Plan traces

**English** · [Español](../es/trazas.md)

```bash
pddldomains trace domain.pddl p01.pddl p01.plan -o trace.json
pddldomains trace --task rubiks-cube/p05                 # with the reference plan
pddldomains trace --task blocks-strips-untyped/p01 my.plan --missing 30 --noise 5 --seed 7
pddldomains trace --task counters/p01 plan.txt --missing-states 20 --world open --val
pddldomains trace --task folding/p03 --planner lama --planner-config lama-first --planner-seed 1
```

`trace` runs a plan on its problem, checking the precondition of each action, and writes in
JSON the states it goes through: the initial state and the state each action leaves, with
the action and its arguments. It can degrade the observations (gaps, missing states and
noise) reproducibly, and it records in the trace how it did so and where the domain, the
problem and the plan come from.

It exits with code 0 if the plan reaches the goal (and VAL considers it valid, with
`--val`); 1 if it does not reach it, although the trace is written anyway; and 2 if the plan
cannot be run (an unknown or inapplicable action) or the input is not valid.

## A trace

The first two steps of a blocks plan, with 20 % gaps (abridged):

```json
{
  "format": "pddldomains-trace",
  "version": 1,
  "generator": "pddldomains 0.1.0",
  "collection": "ipc-2000/blocks-strips-untyped",
  "domain": {"name": "blocks", "file": "ipc-2000/blocks-strips-untyped/domain.pddl", "sha256": "7c9c…"},
  "problem": {"name": "blocks-4-0", "file": "ipc-2000/blocks-strips-untyped/p01.pddl", "id": "p01", "sha256": "9d48…"},
  "plan": {"file": "p01.plan", "sha256": "f215…", "length": 2, "planner": "my-planner", "config": null, "seed": null},
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

`states[i]` is state `i` and `actions[i-1]` is the action that leads from state `i-1` to
state `i`. The file has one state or action per line; with `--compact`, everything on a
single line.

### States

Each state gives the value of the atoms of the universe:

- `true`: the true ones, including those of derived predicates;
- `unknown`: the unknown ones (gaps);
- `false`: the false ones, only with `--world open`. By default the trace is closed-world
  (`"world": "closed"`): an atom of the universe that is neither among the true ones nor
  among the unknown ones is false.

And the value of the numeric fluents that have one, constant ones included (`capacity`,
`distance`…): `values` the observed ones and `unknown_values` the unknown ones.

A state that is missing entirely only has `step`, `time` and `"missing": true`.

### Atom universe

The universe is the set of atoms whose value the trace gives (`--universe`):

- `dynamic` (default): every grounding, according to the types, of the predicates that the
  actions change and of the derived ones, plus the static atoms true in the initial state.
  The other static atoms are false in every state: they are neither listed nor degraded.
- `typed`: every grounding of every predicate according to the types.

Both also include any atom true in some state, even if it does not respect the types. In
domains with many static predicates the difference is huge: in slitherlink the `typed`
universe reaches 400 million atoms and the `dynamic` one fewer than 20,000. A trace is not
generated if the universe exceeds `--max-atoms` (default: 250,000).

### Objects

`objects` gives the declared type of each object and constant (`["either", "t1", "t2"]`
with `either`; `object` if the domain has no types), but not the type hierarchy: it is in
the domain.

### Steps and times

`step` is the number of the state (0 the initial one) or of the action (from 1). `time` is
the instant: in a plan without times, as in VAL, action `i` and the state it leaves are at
instant `i`. If the plan gives times (`0.000: (action ...) [1.000]`), the actions are
sorted by time, each one is at its own time and the state it leaves is at that time plus
the duration. Temporal plans cannot be run: the simulator only supports instantaneous
actions.

## Degradation

| Option | What it does |
|--------|--------------|
| `--missing P` | P % of the atoms and numeric values of each state become unknown |
| `--missing-states P` | P % of the states are missing entirely |
| `--noise P` | P % of the observed (not unknown) atoms of each state are flipped and P % of its observed numeric values are altered |
| `--numeric-noise Q` | an altered value changes by at most Q % of its value (of 1 if it is 0), up or down (default: 10) |
| `--seed N` | the seed (default: 0) |

- **Exact**: the percentages are applied in each state, rounding: with 29 atoms and
  `--missing 20`, every state has exactly 6 unknown atoms. `degradation` records how many
  atoms and values were hidden, flipped or altered in total, and which states are missing.
- **Reproducible**: with the same files and the same seed, the trace is identical. Each
  choice (gaps, noise, states) uses its own random sequence, derived from the seed and the
  state, with `random()`, whose sequence Python guarantees across versions.
- **Nested**: with the same seed, the gaps of `--missing 30` include those of
  `--missing 20`, and the same holds for missing states and for noise (with the same gaps).
  This helps study how a method degrades as information is removed, without everything
  changing from one percentage to the next.
- Only the states are degraded. The actions are always complete.

## Provenance

- `collection`: the catalog collection of the domain (`null` if it is not from the
  catalog).
- `domain`, `problem`: the name they declare, the file (relative to the catalog if it
  belongs to it) and its SHA-256. The problem of a collection also has its identifier
  (`id`, `p01`). The domain is the reference to validate against later: `pddldomains
  validate` or VAL.
- `plan`: the file, its SHA-256, its length and the planner that produced it, with its
  configuration and its seed (`--planner`, `--planner-config`, `--planner-seed`), if given.
- `execution`: whether the plan reaches the goal and, with `--val`, VAL's verdict (`valid`,
  `invalid` or `error`).
- `degradation`: the parameters, the seed and what was degraded.

## The simulator

The states are computed by `pddldomains.simulator`, the same one used by the random walk of
the generators. It supports STRIPS and ADL (types, negation, disjunction, quantifiers,
equality and conditional effects), derived predicates (stratified), numeric fluents
(comparisons, arithmetic and `increase`, `decrease`, `assign`, `scale-up` and `scale-down`)
and action costs. Preferences are taken as true and trajectory constraints are not checked.
It does not support durative actions, processes, events, timed initial literals or object
fluents.

The effects of an action are computed on the previous state (numeric ones too) and applied
at once: first the deletions and then the additions.

The tests compare its states, step by step, with those rebuilt from the output of
`Validate -v` (the `Adding`, `Deleting` and `Updating` lines): the IPC 2023 reference plans
and random plans of numeric domains and of domains with derived predicates. During
development, 139 plans from every catalog collection with instantaneous actions were checked
this way, with no differences.

## From Python

```python
from pathlib import Path
from pddldomains.traces import Degradation, Provenance, generate_trace, write_trace

trace = generate_trace(
    Path("domain.pddl"), Path("p01.pddl"), Path("p01.plan"),
    degradation=Degradation(missing=30, noise=5, seed=7),
    provenance=Provenance("lama", "lama-first", 1),
)
with open("trace.json", "w", encoding="utf-8") as stream:
    write_trace(trace, stream)
```

To generate many traces from the same plan with different degradations, `execute()` runs the
plan once and `build_trace()` builds each trace from that execution.

## Performance

The cost grows with the size of the universe times the number of states. With `--missing 30
--noise 5`, 84 of the 100 reference plans of the catalog take less than a second. The
slowest are those of folding, with universes of up to 110,000 atoms: p07 (753 states) takes
35 s, uses 340 MB of memory and produces 470 MB of JSON. Without degradation it is about
four times faster.
