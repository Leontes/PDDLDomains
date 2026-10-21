# Checking (`pddldomains lint`)

**English** · [Español](../es/revision.md)

It checks domains and problems and reports its findings like a compiler:

```
dominios/ipc-2006/tpp-preferences-complex/p01.pddl:60: warning [val-strict-comparison] 5 strict comparisons…
```

```bash
pddldomains lint                              # the whole catalog
pddldomains lint ipc-2011/tidybot-sequential-satisficing ipc-2006/tpp-preferences-complex/p03
pddldomains lint path/to/a/directory          # domain.pddl (or domain-pNN.pddl) and its problems
pddldomains lint problem.pddl --domain d.pddl
pddldomains lint --val ...                    # also VAL's syntax check
pddldomains lint -v ...                       # include 'info' findings
pddldomains lint --errors-only --format json ...
```

The codes (`[undeclared-requirement]`…) are fixed identifiers; the messages are in the
tool's language (see the [README](../../README.md#language)). It exits with code 1 if there
is any error. There are three levels:

- **error**: what a strict planner would reject;
- **warning**: valid PDDL that is usually an erratum or that some tool does not handle;
- **info** (only with `-v`): declared requirements that are not used.

`pddldomains generate` and `pddldomains sources fetch` automatically check what they
generate or fetch. The catalog has no errors at all (checked by `tests/test_lint.py`).

## The catalog's errata

Every check in this table comes from a real erratum, and the checker finds all of them in
the original files (`tests/test_sources.py`):

| Code | Level | Original erratum |
|------|-------|------------------|
| `undeclared-requirement` | error | (\*) `total-cost` without `:action-costs` (floor-tile), `not` without `:negative-preconditions` (tidybot, pathways), `#t` without `:continuous-effects` (generator), a `total-time` metric without `:numeric-fluents` (temporal driverlog and zenotravel), a commented-out `:requirements` line (counters, numeric zenotravel) |
| `glued-dash` | error | (‡) `?g -goods` (tpp), `?t -tank` (generator-events) |
| `malformed-variable` | error | (‡) `? g`, `? duration` (generator-toricelli); also parameters without `?` |
| `type-without-names` | error | (‡) a `- board` line with no objects (woodworking p10) |
| `function-without-parentheses` | error | (‡) `(= d 0)` instead of `(= (d) 0)` (car) |
| `repeated-value` | error | (‡) two initial values for the same function (pathways) |
| `domain-mismatch` | error | (‡) problems for `generator` with a domain named `generator2` |
| `repeated-declaration` | error | (‡) the type `area` declared twice (storage) |
| `shared-name` | warning | (‡) the domain named like a type (satellite), actions named like predicates (floor-tile), problems named like the domain (parking), an object named like its type (tidybot) |
| `uninitialized-function` | warning | (‡) `ptime` without an initial value (generator-events): VAL rejects every plan. It only counts functions the domain reads, from actions that can apply in that problem, and that do not get a value with `assign` |

## Names, types and structure

| Code | Level | What |
|------|-------|------|
| `syntax` | error | unbalanced parentheses or a file that is not a `(define ...)` |
| `invalid-section`, `repeated-section` | error | malformed or repeated sections |
| `unknown-section` | warning | a section that is not PDDL |
| `unknown-requirement` | error | a requirement that does not exist (with a suggestion) |
| `undeclared-predicate`, `undeclared-function`, `undeclared-object`, `undeclared-type` | error | undeclared names (with the closest one as a suggestion) |
| `unbound-variable` | error | a variable that is neither a parameter nor quantified |
| `arity` | error | a predicate or function with a number of arguments other than declared |
| `function-as-predicate`, `predicate-as-function` | error | one used where the other belongs |
| `undeclared-preference` | error | `is-violated` of a preference that does not exist |
| `incompatible-type` | warning | an object in `:init` whose type does not fit the predicate's |
| `repeated-fact` | warning | the same fact twice in `:init` |
| `missing-goal` | error | a problem without `:goal` |
| `missing-effect` | warning | an action without `:effect` |
| `invalid-formula`, `invalid-effect`, `invalid-expression`, `invalid-term`, `invalid-fact`, `invalid-value`, `invalid-declaration`, `invalid-field`, `missing-field-value`, `invalid-parameters`, `unnamed-operator`, `invalid-derived`, `invalid-metric`, `invalid-domain`, `invalid-type`, `dash-without-type` | error | malformed constructs |
| `unused-requirement` | info | a declared requirement that is not used |

## What VAL does not handle

See [val.md](val.md). These are warnings: the file is correct, but VAL crashes or gives a
wrong result with it.

| Code | What happens with VAL |
|------|-----------------------|
| `val-missing-init` | without an `:init` section (optional in PDDL) it crashes with a segmentation fault |
| `val-function-named-like-domain` | a function named like the domain: segmentation fault |
| `val-object-fluents` | any domain with `:object-fluents`: segmentation fault |
| `val-empty-constraints` | with `(:constraints (and))` it counts every goal preference as violated |
| `val-hold-after` | it evaluates `hold-after` wrongly |
| `val-strict-comparison` | in constraints it evaluates `>` as `>=` (and `<` as `<=`): this explains VAL's different values in tpp and pathways |
| `val-parser` | the messages of VAL's `Parser`, with `--val` |

## What it does not check

The checker is static: it does not ground the problem, so it does not know whether the
problem is solvable, or whether a function initialized only for some objects is ever read
without a value. That is what the reference plans and `pddldomains validate` are for.
