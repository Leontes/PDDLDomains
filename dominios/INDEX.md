# Catalog index

<!-- Generated with `pddldomains index`: do not edit by hand. -->

[Versión en español](INDICE.md)

41 collections, 737 problems and 100 reference plans.
The types are deduced from what each domain uses with its problems (not from what they declare); see `pddldomains types` and `docs/en/catalog.md`. The corrected errata are in the card (`info.toml`) of each collection.

## By type

| Type | Collections | Problems | What it is |
|------|------------:|----------:|--------|
| `classical` | 23 | 460 | classical: no numbers (except costs), time, PDDL 3 or PDDL+ |
| `strips` | 15 | 300 | classical, STRIPS only (and types) |
| `adl` | 8 | 160 | classical with negation, disjunction, equality, quantifiers or conditional effects |
| `costs` | 16 | 320 | action costs (:action-costs) and no other numbers |
| `numeric` | 16 | 237 | numeric fluents (PDDL 2.1) |
| `temporal` | 14 | 207 | durative actions (PDDL 2.1) |
| `continuous` | 5 | 35 | continuous effects in durative actions |
| `derived` | 1 | 20 | derived predicates (PDDL 2.2) |
| `til` | 1 | 20 | timed initial literals (PDDL 2.2) |
| `preferences` | 6 | 118 | preferences (PDDL 3) |
| `constraints` | 7 | 137 | trajectory constraints (PDDL 3) |
| `pddlplus` | 2 | 18 | processes and events (PDDL+) |

## By PDDL version

Each collection is at the highest level of what it uses (see `pddldomains levels`). A planner supporting up to level N must handle levels 1 to N: `pddldomains dataset --max-level N`.

| Level | Version | Adds | Collections | Problems | Cumulative |
|------:|---------|-------|------------:|----------:|-----------:|
| 1 | STRIPS | STRIPS without types | 2 | 40 | 40 |
| 2 | PDDL 1.2 | ADL: types, negation, disjunction, equality, quantifiers and conditional effects | 4 | 80 | 120 |
| 3 | PDDL 2.1 | numeric fluents (and action costs) and durative actions | 24 | 421 | 541 |
| 4 | PDDL 2.2 | derived predicates and timed initial literals | 2 | 40 | 581 |
| 5 | PDDL 3 | preferences, trajectory constraints and object fluents | 7 | 138 | 719 |
| 6 | PDDL+ | processes and events | 2 | 18 | 737 |

**1 · STRIPS**: [ipc-1998/gripper-round-1-strips](ipc-1998/gripper-round-1-strips/info.toml), [ipc-2000/blocks-strips-untyped](ipc-2000/blocks-strips-untyped/info.toml)

**2 · PDDL 1.2**: [ipc-2011/tidybot-sequential-satisficing](ipc-2011/tidybot-sequential-satisficing/info.toml), [ipc-2011/visit-all-sequential-satisficing](ipc-2011/visit-all-sequential-satisficing/info.toml), [ipc-2023-classical/rubiks-cube](ipc-2023-classical/rubiks-cube/info.toml), [ipc-2023-classical/slitherlink](ipc-2023-classical/slitherlink/info.toml)

**3 · PDDL 2.1**: [ipc-2002/driverlog-time-simple-automatic](ipc-2002/driverlog-time-simple-automatic/info.toml), [ipc-2002/zenotravel-time-simple-automatic](ipc-2002/zenotravel-time-simple-automatic/info.toml), [ipc-2011/barman-sequential-satisficing](ipc-2011/barman-sequential-satisficing/info.toml), [ipc-2011/elevator-sequential-satisficing](ipc-2011/elevator-sequential-satisficing/info.toml), [ipc-2011/floor-tile-sequential-satisficing](ipc-2011/floor-tile-sequential-satisficing/info.toml), [ipc-2011/no-mystery-sequential-satisficing](ipc-2011/no-mystery-sequential-satisficing/info.toml), [ipc-2011/openstacks-sequential-satisficing](ipc-2011/openstacks-sequential-satisficing/info.toml), [ipc-2011/parc-printer-sequential-satisficing](ipc-2011/parc-printer-sequential-satisficing/info.toml), [ipc-2011/parking-sequential-satisficing](ipc-2011/parking-sequential-satisficing/info.toml), [ipc-2011/peg-solitaire-sequential-satisficing](ipc-2011/peg-solitaire-sequential-satisficing/info.toml), [ipc-2011/scanalyzer-3d-sequential-satisficing](ipc-2011/scanalyzer-3d-sequential-satisficing/info.toml), [ipc-2011/sokoban-sequential-satisficing](ipc-2011/sokoban-sequential-satisficing/info.toml), [ipc-2011/transport-sequential-satisficing](ipc-2011/transport-sequential-satisficing/info.toml), [ipc-2011/woodworking-sequential-satisficing](ipc-2011/woodworking-sequential-satisficing/info.toml), [ipc-2023-classical/folding](ipc-2023-classical/folding/info.toml), [ipc-2023-classical/labyrinth](ipc-2023-classical/labyrinth/info.toml), [ipc-2023-classical/recharging-robots](ipc-2023-classical/recharging-robots/info.toml), [ipc-2023-classical/ricochet-robots](ipc-2023-classical/ricochet-robots/info.toml), [ipc-2023-numeric/counters](ipc-2023-numeric/counters/info.toml), [ipc-2023-numeric/zenotravel](ipc-2023-numeric/zenotravel/info.toml), [propios/greenhouse](propios/greenhouse/info.toml), [smtplan/generator-linear](smtplan/generator-linear/info.toml), [smtplan/generator-nonlinear](smtplan/generator-nonlinear/info.toml), [smtplan/generator-toricelli](smtplan/generator-toricelli/info.toml)

**4 · PDDL 2.2**: [ipc-2004/psr-middle-derived-predicates-adl](ipc-2004/psr-middle-derived-predicates-adl/info.toml), [ipc-2004/satellite-time-time-windows-strips](ipc-2004/satellite-time-time-windows-strips/info.toml)

**5 · PDDL 3**: [ipc-2006/pathways-preferences-complex](ipc-2006/pathways-preferences-complex/info.toml), [ipc-2006/pipesworld-preferences-complex](ipc-2006/pipesworld-preferences-complex/info.toml), [ipc-2006/storage-preferences-complex](ipc-2006/storage-preferences-complex/info.toml), [ipc-2006/storage-preferences-qualitative](ipc-2006/storage-preferences-qualitative/info.toml), [ipc-2006/tpp-preferences-complex](ipc-2006/tpp-preferences-complex/info.toml), [ipc-2006/trucks-preferences-complex](ipc-2006/trucks-preferences-complex/info.toml), [ipc-2006/trucks-time-constraints](ipc-2006/trucks-time-constraints/info.toml)

**6 · PDDL+**: [smtplan/car-nodrag](smtplan/car-nodrag/info.toml), [smtplan/generator-events](smtplan/generator-events/info.toml)

## ipc-1998

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [gripper-round-1-strips](ipc-1998/gripper-round-1-strips/info.toml) | `classical` `strips` | 1 (STRIPS) | 20 |  | A robot with two grippers carries balls from one room to another. |

## ipc-2000

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [blocks-strips-untyped](ipc-2000/blocks-strips-untyped/info.toml) | `classical` `strips` | 1 (STRIPS) | 20 |  | The blocks world: stacking blocks with one hand. Untyped STRIPS version. |

## ipc-2002

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [driverlog-time-simple-automatic](ipc-2002/driverlog-time-simple-automatic/info.toml) | `numeric` `temporal` | 3 (PDDL 2.1) | 17 | 1 | Logistics in which trucks need a driver to move; durative actions with fixed durations. |
| [zenotravel-time-simple-automatic](ipc-2002/zenotravel-time-simple-automatic/info.toml) | `numeric` `temporal` | 3 (PDDL 2.1) | 17 | 1 | Transporting people by plane between cities; durative actions with fixed durations. |

## ipc-2004

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [psr-middle-derived-predicates-adl](ipc-2004/psr-middle-derived-predicates-adl/info.toml) | `classical` `adl` `derived` | 4 (PDDL 2.2) | 20 |  | Power Supply Restoration after a fault: the state of the network is deduced with derived predicates. |
| [satellite-time-time-windows-strips](ipc-2004/satellite-time-time-windows-strips/info.toml) | `numeric` `temporal` `til` | 4 (PDDL 2.2) | 20 | 1 | Satellites that point their instruments to take images and send them to the ground, only possible within time windows (timed initial literals). |

## ipc-2006

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [pathways-preferences-complex](ipc-2006/pathways-preferences-complex/info.toml) | `numeric` `temporal` `preferences` `constraints` | 5 (PDDL 3) | 20 | 2 | Biochemical pathways: reactions to synthesize substances; durative actions, numeric quantities and preferences. |
| [pipesworld-preferences-complex](ipc-2006/pipesworld-preferences-complex/info.toml) | `numeric` `temporal` `preferences` `constraints` | 5 (PDDL 3) | 18 |  | Transporting oil derivatives through a pipeline network; durative actions and preferences. |
| [storage-preferences-complex](ipc-2006/storage-preferences-complex/info.toml) | `temporal` `preferences` `constraints` | 5 (PDDL 3) | 20 | 1 | Storage with durative actions, preferences (in the goal, in action conditions and in trajectory constraints) and hard constraints. |
| [storage-preferences-qualitative](ipc-2006/storage-preferences-qualitative/info.toml) | `preferences` `constraints` | 5 (PDDL 3) | 20 | 1 | Hoists moving crates between depots and containers, with goal preferences and trajectory constraints (`sometime`, `at-most-once`), without time. |
| [tpp-preferences-complex](ipc-2006/tpp-preferences-complex/info.toml) | `numeric` `temporal` `preferences` `constraints` | 5 (PDDL 3) | 20 | 1 | Traveling Purchaser Problem: trucks buying goods at markets and taking them to depots; durative actions, numeric quantities and preferences. |
| [trucks-preferences-complex](ipc-2006/trucks-preferences-complex/info.toml) | `numeric` `temporal` `preferences` `constraints` | 5 (PDDL 3) | 20 |  | Trucks with durative actions, preferences and trajectory constraints. |
| [trucks-time-constraints](ipc-2006/trucks-time-constraints/info.toml) | `numeric` `temporal` `constraints` | 5 (PDDL 3) | 20 |  | Logistics with trucks whose loading space is organized in areas; some packages have a delivery deadline (`within` constraints over durative actions). |

## ipc-2011

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [barman-sequential-satisficing](ipc-2011/barman-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | A bartender robot prepares cocktails with shot glasses, a shaker and dispensers. |
| [elevator-sequential-satisficing](ipc-2011/elevator-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Fast and slow elevators carrying passengers between floors. |
| [floor-tile-sequential-satisficing](ipc-2011/floor-tile-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 | 2 | Robots painting the tiles of a floor without stepping on the painted ones. |
| [no-mystery-sequential-satisficing](ipc-2011/no-mystery-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Logistics with limited fuel. |
| [openstacks-sequential-satisficing](ipc-2011/openstacks-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Producing orders while minimizing the number of stacks open at the same time. One domain per problem. |
| [parc-printer-sequential-satisficing](ipc-2011/parc-printer-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Scheduling the jobs of a PARC modular printer. One domain per problem. |
| [parking-sequential-satisficing](ipc-2011/parking-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 | 1 | Parking cars in a row by rearranging them in the curb locations of a street. |
| [peg-solitaire-sequential-satisficing](ipc-2011/peg-solitaire-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | The peg solitaire game. |
| [scanalyzer-3d-sequential-satisficing](ipc-2011/scanalyzer-3d-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Conveyor belts taking plants through a scanner to analyze them. |
| [sokoban-sequential-satisficing](ipc-2011/sokoban-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | The Sokoban game: pushing boxes to their goal positions. |
| [tidybot-sequential-satisficing](ipc-2011/tidybot-sequential-satisficing/info.toml) | `classical` `adl` | 2 (PDDL 1.2) | 20 | 2 | Household robots picking up objects and putting them in their place, with a cart. |
| [transport-sequential-satisficing](ipc-2011/transport-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 |  | Logistics with limited-capacity trucks on a road network. |
| [visit-all-sequential-satisficing](ipc-2011/visit-all-sequential-satisficing/info.toml) | `classical` `strips` | 2 (PDDL 1.2) | 20 |  | Visiting every cell of a grid. |
| [woodworking-sequential-satisficing](ipc-2011/woodworking-sequential-satisficing/info.toml) | `classical` `strips` `costs` | 3 (PDDL 2.1) | 20 | 1 | A woodworking shop: cutting, planing, sanding and varnishing parts with several machines. |

## ipc-2023-classical

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [folding](ipc-2023-classical/folding/info.toml) | `classical` `adl` `costs` | 3 (PDDL 2.1) | 20 (20 with a plan) |  | Folding a string on a grid, rotating it at its nodes, until it takes a given shape. |
| [labyrinth](ipc-2023-classical/labyrinth/info.toml) | `classical` `adl` `costs` | 3 (PDDL 2.1) | 20 (20 with a plan) |  | A robot moving through a labyrinth of cards that shift along rows and columns, as in the board game. |
| [recharging-robots](ipc-2023-classical/recharging-robots/info.toml) | `classical` `adl` `costs` | 3 (PDDL 2.1) | 20 (20 with a plan) |  | Robots with limited battery that must guard areas of a graph and can pass charge to each other. |
| [ricochet-robots](ipc-2023-classical/ricochet-robots/info.toml) | `classical` `adl` `costs` | 3 (PDDL 2.1) | 20 (20 with a plan) |  | The Ricochet Robots game: robots sliding in one direction until they hit a barrier or another robot. |
| [rubiks-cube](ipc-2023-classical/rubiks-cube/info.toml) | `classical` `adl` | 2 (PDDL 1.2) | 20 (20 with a plan) |  | The Rubik's cube, with conditional effects. |
| [slitherlink](ipc-2023-classical/slitherlink/info.toml) | `classical` `adl` | 2 (PDDL 1.2) | 20 |  | The Slitherlink puzzle: drawing a single closed loop along the edges of a numbered grid. |

## ipc-2023-numeric

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [counters](ipc-2023-numeric/counters/info.toml) | `numeric` | 3 (PDDL 2.1) | 20 | 1 | Counters that are incremented and decremented until some inequalities between them hold. |
| [zenotravel](ipc-2023-numeric/zenotravel/info.toml) | `numeric` | 3 (PDDL 2.1) | 20 | 1 | Planes carrying people between cities and burning fuel according to their speed. |

## propios

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [greenhouse](propios/greenhouse/info.toml) | `numeric` `temporal` `continuous` | 3 (PDDL 2.1) | 2 |  | A greenhouse made by hand to gather edge cases of temporal PDDL 2.1 that do not appear in any public benchmark found (neither in the IPC ones nor in those of COLIN/OPTIC or VAL): continuous effects inside `forall` and `when`, conditional effects with `over all` conditions, a non-fixed `?duration` in `at start` effects, a duration whose maximum depends on a continuously changing variable, and a conditional effect on a continuous variable. |

## smtplan

| Collection | Types | Level | Problems | Errata | Description |
|-----------|-------|-------|----------:|--------:|-------------|
| [car-nodrag](smtplan/car-nodrag/info.toml) | `numeric` `pddlplus` | 6 (PDDL+) | 10 | 1 | A car that accelerates and brakes to cover a distance and stop in time: speed and position change through a process, and an event blows the engine if it is pushed too hard. |
| [generator-events](smtplan/generator-events/info.toml) | `numeric` `temporal` `continuous` `pddlplus` | 6 (PDDL+) | 8 | 3 | A generator that must run for a period of time while being refuelled from tanks: one durative action, one non-linear process and two events. |
| [generator-linear](smtplan/generator-linear/info.toml) | `numeric` `temporal` `continuous` | 3 (PDDL 2.1) | 8 | 1 | The generator with linear refuelling: PDDL 2.1 with linear continuous effects, without processes or events. |
| [generator-nonlinear](smtplan/generator-nonlinear/info.toml) | `numeric` `temporal` `continuous` | 3 (PDDL 2.1) | 8 | 2 | The generator with non-linear refuelling: PDDL 2.1 with non-linear continuous effects. |
| [generator-toricelli](smtplan/generator-toricelli/info.toml) | `numeric` `temporal` `continuous` | 3 (PDDL 2.1) | 9 | 3 | The generator with refuelling following Torricelli's law: non-linear continuous effects and state-dependent durations. |
