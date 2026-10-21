# VAL

**English** · [Español](../es/val.md)

[VAL](https://github.com/KCL-Planning/VAL) is the reference plan validator of the IPC.
`scripts/build_val.sh [ref]` downloads and builds it (git, cmake and g++) and leaves in
`tools/bin/` `Validate` (validates plans) and `Parser` (checks the syntax). By default it
builds commit `3c7a1f3`, the latest of the `master` branch (2021). They are also looked for
in `$VAL_BIN` and in the `PATH`.

```bash
pddldomains validate domain.pddl p01.pddl p01.plan [other.plan…]
pddldomains validate --task ipc-2023-classical/folding/p01 my-plan.plan
pddldomains validate --reference with-plans        # reference plans of a dataset…
pddldomains validate --reference folding           # …or of a collection
pddldomains validate ... -t 0.001 -m 4000 -v       # tolerance, MB and VAL's output
pddldomains lint --val <target>                    # VAL's Parser on top of the checker
```

From Python, `pddldomains.val.validate(domain, problem, plan)` returns a `ValResult` with
`verdict` (`valid`, `invalid` or `error`), `message`, `value` ("Final value") and `violated`
(the violated preferences).

## The verdict is read from the output

VAL's exit code is **not reliable**: it exits with 1 if the plan is invalid, but with 0 if it
cannot read the plan ("Bad plan file!"), also when the file does not exist. Therefore:

| Verdict | When |
|---------|------|
| `valid` | the output says "Plan valid" |
| `invalid` | the plan was read and is not valid (code 1, "Goal not satisfied", "Plan failed"…) |
| `error` | VAL gave no verdict: unreadable plan, segmentation fault, out of memory or out of time. It says nothing about the plan |

VAL runs with a hard virtual memory limit (`RLIMIT_AS`, by default 80% of the available
memory): with large preference plans it may need a lot (2.3 GB with storage p20 from IPC
2006) and, without a limit, exhaust the machine's memory. If it runs out of memory it ends
with `std::bad_alloc` and the result is `error`, not `invalid`.

## Known quirks

Found while validating plans with that version of VAL. The checker warns about those that
can be seen in the files (`val-*` codes, see [lint.md](lint.md)).

**Segmentation faults** (code 139, no output):

- a problem without an `:init` section, although it is optional in PDDL;
- a function named like the domain (domain `battery` with function `(battery)`);
- any domain with `:object-fluents`, even a minimal one.

**Wrong results:**

- An empty `(:constraints (and))`: it counts every goal preference as violated and gets
  "Final value" wrong. Without the section, it is right.
- `hold-after` does not work: it says "Failure to satisfy" even for trivially valid plans,
  and sometimes crashes with a segmentation fault.
- In trajectory constraints it evaluates a strict `>` as `>=`: `(sometime (> (ca) 0))`
  counts as satisfied with `ca = 0` all the time. This explains all of VAL's values that
  differ from the PDDL 3 ones in tpp and pathways (IPC 2006).
- pathways (IPC 2006): VAL reports `p0A` as violated but does not add its weight to "Final
  value" (it gives 1 instead of 9 for a one-action plan). Unknown cause.
- Rounding at the exact bounds of an invariant: a plan in which a continuous variable ends
  exactly at the bound of an `over all` is rejected; with a margin of 1e-6 it is valid.

**Constraints it imposes:**

- The default tolerance (`-t`) is 0.01: two happenings closer than that count as
  simultaneous. A planner using ε = 0.001 has to validate with `-t 0.001`.
- Mutual exclusion: it rejects ("Mutex violation") two happenings at the same time if one
  reads a fact and the other writes it, even if the write does not change its value.
- "Bad plan description!" if a durative action uses `?duration` in a condition (the PDDL 2.1
  grammar does not allow it either).
- It rejects `:condition ()`; `(and)` must be written instead.
- For sequential plans, action k happens at time k (this matters for constraints with
  time).

**False warnings from `Parser`:**

- "Undeclared requirement :action-costs" when `total-cost` is used in a domain that
  declares `:fluents` or `:numeric-fluents`, which already cover it (tpp from IPC 2006).
