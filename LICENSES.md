# Licenses

**English** · [Español](LICENCIAS.md)

The code of this repository (the `pddldomains` package, the tests and the scripts), the
documentation, the collection cards (`info.toml`), the index, the dataset definitions and
the own domains (`dominios/propios/`) are distributed under the [MIT license](LICENSE).

## Third-party domains and problems

The PDDL files in `dominios/` (except those in `dominios/propios/`) belong to their authors,
and the MIT license does **not** apply to them. They are redistributed for research, as is
usual in the automated planning community, citing their origin: the card (`info.toml`) of
each collection states the repository and commit it comes from, its authors when they are
known and which errata have been fixed.

| Collections | Source | License |
|-------------|--------|---------|
| `ipc-1998` … `ipc-2011` | IPC archive in [potassco/pddl-instances](https://github.com/potassco/pddl-instances) | not declared |
| `ipc-2023-classical/folding`, `labyrinth`, `recharging-robots`, `rubiks-cube` | [ipc2023-classical](https://github.com/ipc2023-classical) | public domain, as declared by their authors |
| `ipc-2023-classical/ricochet-robots`, `slitherlink` | [ipc2023-classical](https://github.com/ipc2023-classical) | not declared |
| `ipc-2023-numeric` | [ipc2023-numeric/ipc2023-dataset](https://github.com/ipc2023-numeric/ipc2023-dataset) | not declared |
| `smtplan` | [KCL-Planning/SMTPlan](https://github.com/KCL-Planning/SMTPlan) | not declared |

The errata fixes in those files follow the terms of the original. If you are the author of
any of them and would rather it were not redistributed here, open an issue and it will be
removed.

## Parking generator

`src/pddldomains/generators/parking.py` is a Python translation of
`parking/parking-generator.pl` from [AI-Planning/pddl-generators](https://github.com/AI-Planning/pddl-generators)
(commit `e6277fb`), the collection of generators gathered by Jendrik Seipp, Álvaro Torralba
and Jörg Hoffmann from Jörg Hoffmann's FF domain collection. That repository does not declare
a license; the translation is included with this attribution and would be removed if its
authors asked for it. The files in `tests/datos/parking/` are outputs of the original, which
the tests use to check that the translation produces the same problems.

If you use the generators in a publication, cite the original collection:

```bibtex
@Misc{seipp-et-al-zenodo2022,
  author =       "Jendrik Seipp and {\'A}lvaro Torralba and J{\"o}rg Hoffmann",
  title =        "{PDDL} Generators",
  publisher =    "Zenodo",
  year =         "2022",
  howpublished = "\url{https://doi.org/10.5281/zenodo.6382173}"
}
```

## Tools downloaded separately

`scripts/build_val.sh` and `scripts/build_generators.sh` download and build in `tools/`,
which is not part of the repository, [VAL](https://github.com/KCL-Planning/VAL)
(BSD-3-Clause), pddl-generators and the generators of the IPC 2023 domains, each under its
own terms.
