# PDDLDomains

[English](README.md) · **Español**

Colección de dominios y problemas PDDL con herramientas para clasificarlos, crear datasets
de prueba, revisarlos, validar planes con VAL, generar problemas nuevos al azar y obtener las
trazas de los planes.

- **Catálogo** (`dominios/`): 41 colecciones y 737 problemas, de STRIPS a PDDL+, cada uno
  una sola vez y en la carpeta de su origen (`ipc-2011/barman-sequential-satisficing`,
  `smtplan/car-nodrag`…), con una ficha que documenta de dónde sale y qué erratas se le
  han corregido. El [índice](dominios/INDICE.md) los lista por origen, por tipo y por
  versión de PDDL.
- **Clasificación**: por tipos (`classical`, `temporal`, `preferences`, `pddlplus`…) y por
  versión de PDDL, en una escala acumulativa de seis niveles (de STRIPS a PDDL+). Las dos
  se deducen de lo que **usa** cada dominio con sus problemas, no de lo que declara.
- **Datasets**: listas de problemas elegidas por filtros (tipo, requisito, nivel, tamaño,
  número por colección…) o a mano, como lista de rutas, CSV, JSON o exportadas a un
  directorio.
- **Revisión**: encuentra las erratas típicas de los ficheros PDDL (requisitos sin
  declarar, nombres repetidos o sin declarar, guiones pegados…) y avisa de lo que VAL no
  lleva bien.
- **VAL**: valida planes leyendo su veredicto del texto, porque el código de salida de VAL
  no es fiable.
- **Generadores**: 25 generadores de problemas aleatorios (propios, de pddl-generators y de
  la IPC 2023), entre ellos uno genérico por paseo aleatorio que sirve para cualquier
  dominio clásico y da un plan de cada problema.
- **Trazas**: los estados por los que pasa un plan, en JSON, con valores cierto, falso o
  desconocido y fluentes numéricos, degradables de forma reproducible (huecos, estados que
  faltan y ruido) y con su procedencia.

## Instalación

Requiere Python 3.12. El paquete no tiene dependencias: el catálogo, los datasets, la
revisión, los generadores propios y el paseo aleatorio funcionan solo con Python. VAL y los
generadores externos de C/C++ necesitan además git, make, gcc, g++ y cmake.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'        # con pytest, ruff y mypy
scripts/build_val.sh                     # VAL en tools/bin (git, cmake, g++)
scripts/build_generators.sh              # generadores externos en tools/ (opcional)
.venv/bin/pip install -e '.[generators]' # módulos del generador de labyrinth (opcional)
```

`tools/` (VAL, generadores y clones de los repositorios de origen), `salidas/` y `.cache/`
no están en git.

## Idioma

La herramienta escribe en inglés o en español: la ayuda, los mensajes de la revisión, las
salidas y las descripciones de las fichas. Sale en español con `--lang es`, con
`PDDLDOMAINS_LANG=es` o con una configuración regional en español (`LANG=es_ES.UTF-8`); si
no, en inglés. Los identificadores (subcomandos, opciones, tipos, códigos de la revisión,
nombres de datasets) son los mismos en los dos idiomas.

```bash
export PDDLDOMAINS_LANG=es       # por ejemplo, en ~/.bashrc
pddldomains --lang es lint       # o solo para una orden
```

## Uso

```bash
pddldomains list --type temporal                 # colecciones con acciones durativas
pddldomains info trucks-time-constraints         # ficha, análisis y problemas
pddldomains types                                # los tipos y cuántos hay de cada uno
pddldomains levels                               # la escala de versiones de PDDL
pddldomains list --max-level 3                   # lo que soporta quien llega a PDDL 2.1

pddldomains dataset smoke-test                   # '<dominio> <problema>' por línea
pddldomains dataset --type preferences --per-collection 3 --order smallest --format csv
pddldomains dataset temporal --export salidas/temporal   # copia a un directorio
pddldomains dataset --list-definitions           # las definiciones de datasets/

pddldomains lint                                 # revisa todo el catálogo
pddldomains lint ruta/a/mis/problemas --val      # cualquier directorio, también con VAL
pddldomains validate dominio.pddl p01.pddl p01.plan
pddldomains validate --reference with-plans      # los planes de referencia del catálogo

pddldomains generate --list
pddldomains generate counters -n 10 -p counters=4..12          # rango aleatorio
pddldomains generate barman -p cocktails=3,5,7 -n 2            # serie: 2 por valor
pddldomains generate random-walk -p collection=sokoban-sequential-satisficing -n 5

pddldomains trace --task rubiks-cube/p05 -o traza.json      # estados del plan de referencia
pddldomains trace dominio.pddl p01.pddl p01.plan --missing 30 --noise 5 --seed 7

pddldomains sources check                        # compara con los ficheros originales
pddldomains index                                # regenera dominios/INDEX.md e INDICE.md
```

Desde Python (por ejemplo, para parametrizar los tests de un planificador):

```python
import pytest
from pddldomains import load_dataset, select

@pytest.mark.parametrize("task", list(load_dataset("smoke-test")), ids=lambda t: t.id)
def test_solve(task):
    plan = solve(task.domain, task.problem)
    ...

temporales = select(types=["temporal"], exclude_types=["pddlplus"], per_collection=2)
```

Para usarlo desde otro proyecto basta con `pip install -e ../PDDLDomains` en su entorno: las
rutas apuntan al catálogo de este repositorio (o al de `$PDDL_DOMINIOS`).

## Estructura

| Ruta | Qué hay |
|------|---------|
| `dominios/<origen>/<colección>/` | `domain.pddl` (o `domain-pNN.pddl`), `pNN.pddl`, `pNN.plan` si hay plan de referencia, e `info.toml` |
| `dominios/INDICE.md`, `dominios/INDEX.md` | índice generado, en español y en inglés |
| `datasets/*.toml` | definiciones de datasets |
| `src/pddldomains/` | el paquete y la CLI |
| `scripts/` | compilación de VAL y de los generadores externos |
| `docs/es/`, `docs/en/` | documentación, en español y en inglés |
| `tests/` | tests (`pytest`) |

## Documentación

- [Catálogo](docs/es/catalogo.md): formato de las colecciones y de las fichas, erratas,
  clasificación por tipos y por versión de PDDL, y cómo añadir una colección.
- [Datasets](docs/es/datasets.md): definiciones, filtros y exportación.
- [Revisión](docs/es/revision.md): las comprobaciones de `lint` y las erratas que las
  originaron.
- [VAL](docs/es/val.md): compilación, validación y rarezas conocidas.
- [Generadores](docs/es/generadores.md): los generadores, sus parámetros y por qué sus
  problemas tienen solución.
- [Trazas](docs/es/trazas.md): el formato de las trazas, la degradación y el simulador.

## Desarrollo

```bash
.venv/bin/pytest            # los tests de VAL, generadores externos y orígenes se saltan si faltan
.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
.venv/bin/mypy              # modo estricto
```

Los textos de la herramienta se escriben en español en el código y se traducen con la tabla
de `src/pddldomains/translations.py`; `tests/test_i18n.py` comprueba que ninguno se queda
sin traducir.

## Licencia

El código, la documentación y los dominios propios se distribuyen con la
[licencia MIT](LICENSE) (© 2026 José Segura). Los dominios y problemas de terceros de
`dominios/` conservan las condiciones de sus autores, y el generador de parking es una
traducción de pddl-generators: ver [LICENCIAS.md](LICENCIAS.md).
