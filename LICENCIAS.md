# Licencias

[English](LICENSES.md) · **Español**

El código de este repositorio (el paquete `pddldomains`, los tests y los scripts), la
documentación, las fichas de las colecciones (`info.toml`), el índice, las definiciones de
datasets y los dominios propios (`dominios/propios/`) se distribuyen con la
[licencia MIT](LICENSE).

## Dominios y problemas de terceros

Los ficheros PDDL de `dominios/` (salvo los de `dominios/propios/`) son de sus autores, y la
licencia MIT **no** se aplica a ellos. Se redistribuyen para investigación, como es habitual
en la comunidad de planificación automática, citando su origen: la ficha (`info.toml`) de
cada colección dice de qué repositorio y commit sale, quiénes son sus autores cuando se
conocen y qué erratas se le han corregido.

| Colecciones | Fuente | Licencia |
|-------------|--------|----------|
| `ipc-1998` … `ipc-2011` | archivo de la IPC en [potassco/pddl-instances](https://github.com/potassco/pddl-instances) | no declarada |
| `ipc-2023-classical/folding`, `labyrinth`, `recharging-robots`, `rubiks-cube` | [ipc2023-classical](https://github.com/ipc2023-classical) | dominio público, por declaración de sus autores |
| `ipc-2023-classical/ricochet-robots`, `slitherlink` | [ipc2023-classical](https://github.com/ipc2023-classical) | no declarada |
| `ipc-2023-numeric` | [ipc2023-numeric/ipc2023-dataset](https://github.com/ipc2023-numeric/ipc2023-dataset) | no declarada |
| `smtplan` | [KCL-Planning/SMTPlan](https://github.com/KCL-Planning/SMTPlan) | no declarada |

Las correcciones de erratas de esos ficheros siguen las condiciones del original. Si eres
autor de alguno de ellos y prefieres que no se redistribuya aquí, abre una incidencia y se
retirará.

## Generador de parking

`src/pddldomains/generators/parking.py` es una traducción a Python de
`parking/parking-generator.pl`, de [AI-Planning/pddl-generators](https://github.com/AI-Planning/pddl-generators)
(commit `e6277fb`), la colección de generadores reunida por Jendrik Seipp, Álvaro Torralba y
Jörg Hoffmann a partir de la colección de dominios de FF de Jörg Hoffmann. Ese repositorio no
declara licencia; la traducción se incluye con esta atribución y se retiraría si sus autores lo
pidieran. Los ficheros de `tests/datos/parking/` son salidas del original, que los tests usan
para comprobar que la traducción da los mismos problemas.

Si usas los generadores en una publicación, cita la colección original:

```bibtex
@Misc{seipp-et-al-zenodo2022,
  author =       "Jendrik Seipp and {\'A}lvaro Torralba and J{\"o}rg Hoffmann",
  title =        "{PDDL} Generators",
  publisher =    "Zenodo",
  year =         "2022",
  howpublished = "\url{https://doi.org/10.5281/zenodo.6382173}"
}
```

## Herramientas que se descargan aparte

`scripts/build_val.sh` y `scripts/build_generators.sh` descargan y compilan en `tools/`,
que no forma parte del repositorio, [VAL](https://github.com/KCL-Planning/VAL)
(BSD-3-Clause), pddl-generators y los generadores de los dominios de la IPC 2023, cada uno con
sus propias condiciones.
