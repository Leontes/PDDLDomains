"""Generadores externos: los de pddl-generators y los de la IPC 2023.

``scripts/build_generators.sh`` los descarga (con commit fijo) y compila en ``tools/``.
Cada envoltura traduce los parámetros a la línea de órdenes del generador y retoca la
salida para que encaje con la versión del dominio que hay en el catálogo:

* blocksworld: el dominio de 4 operadores de pddl-generators llama ``arm-empty`` y
  ``on-table`` a lo que el de la IPC 2000 llama ``handempty`` y ``ontable``;
* barman y nomystery no dan valor inicial a ``total-cost`` (ni métrica, alguno): se
  añaden, como en los problemas de la IPC;
* el nombre del problema se cambia siempre por el de la generación.

El de parking, el único de Perl, está portado a Python (:mod:`pddldomains.generators.parking`).

Las envolturas solo se han escrito para los generadores cuyos problemas pasan la revisión
contra el dominio del catálogo. Los que generan otra versión del dominio (sokoban, la
zenotravel numérica de 2002) o necesitan herramientas que no hay (tidybot: Clojure; pegsol:
Ruby; recharging-robots, ricochet-robots y slitherlink: cairo, un resolvedor ASP o Haskell)
no tienen envoltura; ver ``docs/es/generadores.md``.
"""

import importlib.util
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pddldomains.catalog import ROOT, Collection
from pddldomains.generators.base import (
    GeneratedProblem,
    Generator,
    GeneratorError,
    Param,
    ensure_total_cost,
    rename_tokens,
    set_domain_name,
    set_problem_name,
)
from pddldomains.i18n import _

#: Directorio de las herramientas externas.
TOOLS = ROOT / "tools"
#: Tiempo máximo de un generador externo, en segundos.
TIMEOUT = 600

type Command = Callable[[dict[str, Any], int, Path, Path], list[str]]
type Postprocess = Callable[[str], str]


class ExternalGenerator(Generator):
    """Un generador externo configurado con datos.

    Attributes:
        tool: directorio del generador.
        executable: fichero (relativo a ``tool``) que tiene que existir.
        command: construye la orden a partir de (parámetros, semilla, fichero del problema,
            fichero del plan).
        writes_file: si escribe el problema en el fichero (si no, por la salida estándar).
        writes_plan: si escribe además un plan.
        modules: módulos de Python que necesita.
        postprocess: retoques del texto, en orden.
    """

    def __init__(
        self,
        name: str,
        collection: str,
        description: str,
        origin: str,
        tool: Path,
        executable: str,
        params: tuple[Param, ...],
        command: Command,
        *,
        writes_file: bool = False,
        writes_plan: bool = False,
        modules: tuple[str, ...] = (),
        postprocess: tuple[Postprocess, ...] = (),
        check: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.name = name
        self.collection = collection
        self.description = description
        self.origin = origin
        self.tool = tool
        self.executable = executable
        self.params = params
        self.command = command
        self.writes_file = writes_file
        self.writes_plan = writes_plan
        self.modules = modules
        self.postprocess = postprocess
        self._check = check

    def explanation(self) -> str:
        return ""  # el docstring de la clase es el de la envoltura, no el del generador

    def unavailable(self) -> str | None:
        if not (self.tool / self.executable).exists():
            return _("no está descargado o compilado (scripts/build_generators.sh)")
        missing = [m for m in self.modules if importlib.util.find_spec(m) is None]
        if missing:
            modules = " ".join(missing)
            return _("faltan módulos de Python: {modules} (pip install {modules})", modules=modules)
        return None

    def check(self, params: dict[str, Any]) -> None:
        if self._check is not None:
            self._check(params)

    def generate(
        self, params: dict[str, Any], seed: int, name: str, collection: Collection
    ) -> GeneratedProblem:
        reason = self.unavailable()
        if reason:
            raise GeneratorError(f"{self.name}: {reason}")  # reason ya está traducido
        with tempfile.TemporaryDirectory(prefix="pddldomains-") as directory:
            problem_file = Path(directory) / "problem.pddl"
            plan_file = Path(directory) / "problem.plan"
            command = self.command(params, seed, problem_file, plan_file)
            try:
                result = subprocess.run(
                    command,
                    cwd=self.tool,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise GeneratorError(
                    _("{name}: no ha terminado en {seconds} s", name=self.name, seconds=TIMEOUT)
                ) from error
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip().splitlines()[-3:]
                raise GeneratorError(
                    _(
                        "{name} terminó con código {code}: {detail}",
                        name=self.name,
                        code=result.returncode,
                        detail=" / ".join(detail),
                    )
                )
            text = (
                problem_file.read_text()
                if self.writes_file and problem_file.exists()
                else result.stdout
            )
            plan = None
            if self.writes_plan and plan_file.exists() and plan_file.stat().st_size:
                plan = plan_file.read_text()
        if "(define" not in text:
            raise GeneratorError(_("{name} no ha generado ningún problema", name=self.name))
        for step in self.postprocess:
            text = step(text)
        text = set_problem_name(text, name)
        return GeneratedProblem(text, plan)


def _python(script: str) -> list[str]:
    """Una orden para un script de Python con el intérprete actual (no ``python``, que puede
    no existir; el actual tiene además los módulos opcionales del entorno)."""
    return [sys.executable, script]


def _shots_check(params: dict[str, Any]) -> None:
    if params["shots"] and params["shots"] < params["cocktails"] + 1:
        raise GeneratorError(_("shots tiene que ser al menos cocktails + 1"))


def _folds_check(params: dict[str, Any]) -> None:
    if params["folds"] >= params["length"]:
        raise GeneratorError(_("folds tiene que ser menor que length"))


_PG = TOOLS / "pddl-generators"
_IPC2023 = TOOLS / "ipc2023"

EXTERNAL_GENERATORS: tuple[Generator, ...] = (
    ExternalGenerator(
        "barman",
        "ipc-2011/barman-sequential-satisficing",
        "barman que prepara cócteles",
        "pddl-generators",
        _PG / "barman",
        "barman-generator.py",
        (
            Param("cocktails", int, "3..7", "número de cócteles", minimum=1),
            Param("ingredients", int, 3, "número de ingredientes", minimum=2),
            Param("shots", int, 0, "número de vasos (0: cocktails + 1)", minimum=0),
        ),
        lambda p, s, out, plan: [
            *_python("barman-generator.py"),
            str(p["cocktails"]),
            str(p["ingredients"]),
            str(p["shots"] or p["cocktails"] + 1),
            str(s),
        ],
        postprocess=(ensure_total_cost,),
        check=_shots_check,
    ),
    ExternalGenerator(
        "blocksworld",
        "ipc-2000/blocks-strips-untyped",
        "mundo de bloques (estados al azar con bwstates)",
        "pddl-generators",
        _PG / "blocksworld",
        "blocksworld",
        (Param("blocks", int, "4..12", "número de bloques", minimum=1),),
        lambda p, s, out, plan: ["./blocksworld", "4", str(p["blocks"]), str(s)],
        postprocess=(
            lambda text: rename_tokens(text, {"arm-empty": "handempty", "on-table": "ontable"}),
            lambda text: set_domain_name(text, "blocks"),
        ),
    ),
    ExternalGenerator(
        "driverlog",
        "ipc-2002/driverlog-time-simple-automatic",
        "driverlog temporal (variante simple time de la IPC 2002)",
        "pddl-generators",
        _PG / "driverlog",
        "dlgen",
        (
            Param("junctions", int, "3..8", "número de cruces", minimum=2),
            Param("drivers", int, "2..4", "número de conductores", minimum=1),
            Param("packages", int, "2..8", "número de paquetes", minimum=1),
            Param("trucks", int, "2..4", "número de camiones", minimum=1),
        ),
        lambda p, s, out, plan: [
            "./dlgen",
            "-s",
            str(s),
            str(p["junctions"]),
            str(p["drivers"]),
            str(p["packages"]),
            str(p["trucks"]),
        ],
    ),
    ExternalGenerator(
        "elevators",
        "ipc-2011/elevator-sequential-satisficing",
        "ascensores rápidos y lentos",
        "pddl-generators",
        _PG / "elevators",
        "generate.py",
        (
            Param("areas", int, "2..3", "número de zonas del edificio", minimum=1),
            Param("area-size", int, "2..4", "plantas por zona", minimum=2),
            Param("passengers", int, "3..8", "número de pasajeros", minimum=1),
            Param("fast", int, 1, "ascensores rápidos", minimum=0),
            Param("slow", int, 1, "ascensores lentos por zona", minimum=1),
        ),
        lambda p, s, out, plan: [
            *_python("generate.py"),
            str(p["areas"]),
            str(p["area-size"]),
            str(p["passengers"]),
            str(p["fast"]),
            str(p["slow"]),
            "--seed",
            str(s),
        ],
    ),
    ExternalGenerator(
        "floortile",
        "ipc-2011/floor-tile-sequential-satisficing",
        "robots que pintan baldosas",
        "pddl-generators",
        _PG / "floortile",
        "floortile-generator.py",
        (
            Param("rows", int, "3..5", "filas", minimum=2),
            Param("columns", int, "3..5", "columnas", minimum=2),
            Param("robots", int, "2..3", "robots (2 a 4)", minimum=1),
        ),
        lambda p, s, out, plan: [
            *_python("floortile-generator.py"),
            "problem",
            str(p["rows"]),
            str(p["columns"]),
            str(p["robots"]),
            "seq",
            str(s),
        ],
    ),
    ExternalGenerator(
        "gripper",
        "ipc-1998/gripper-round-1-strips",
        "robot con dos pinzas que lleva bolas (determinista: solo depende de balls)",
        "pddl-generators",
        _PG / "gripper",
        "gripper",
        (Param("balls", int, "4..20", "número de bolas", minimum=1),),
        lambda p, s, out, plan: ["./gripper", "-n", str(p["balls"])],
    ),
    ExternalGenerator(
        "nomystery",
        "ipc-2011/no-mystery-sequential-satisficing",
        "logística con combustible limitado",
        "pddl-generators",
        _PG / "nomystery",
        "nomystery",
        (
            Param("locations", int, "3..8", "número de lugares", minimum=2),
            Param("packages", int, "3..8", "número de paquetes", minimum=1),
            Param(
                "constrainedness",
                float,
                1.5,
                "combustible inicial / coste óptimo (>= 1)",
                minimum=1,
            ),
        ),
        lambda p, s, out, plan: [
            "./nomystery",
            "-l",
            str(p["locations"]),
            "-p",
            str(p["packages"]),
            "-c",
            str(p["constrainedness"]),
            "-s",
            str(s),
        ],
        postprocess=(ensure_total_cost,),
    ),
    ExternalGenerator(
        "scanalyzer",
        "ipc-2011/scanalyzer-3d-sequential-satisficing",
        "cintas que llevan plantas al escáner",
        "pddl-generators",
        _PG / "scanalyzer",
        "generator.py",
        (
            Param("size", int, "2..5", "número de segmentos", minimum=1),
            Param(
                "segments",
                str,
                "single",
                "segmentos enteros (single) o partidos (ab)",
                choices=("single", "ab"),
            ),
            Param(
                "inout",
                str,
                "in",
                "tipo de problema: in, both o none",
                choices=("in", "both", "none"),
            ),
        ),
        lambda p, s, out, plan: [
            *_python("generator.py"),
            str(p["size"]),
            p["segments"],
            p["inout"],
            "--seed",
            str(s),
        ],
    ),
    ExternalGenerator(
        "transport",
        "ipc-2011/transport-sequential-satisficing",
        "camiones con capacidad en una red de carreteras",
        "pddl-generators",
        _PG / "transport",
        "city-generator.py",
        (
            Param("nodes", int, "6..12", "número de lugares", minimum=2),
            Param("size", int, 1000, "lado del mapa", minimum=10),
            Param("degree", int, 3, "grado de la red", minimum=1),
            Param("min-distance", int, 100, "distancia mínima entre lugares", minimum=1),
            Param("trucks", int, "2..4", "número de camiones", minimum=1),
            Param("packages", int, "2..8", "número de paquetes", minimum=1),
        ),
        lambda p, s, out, plan: [
            *_python("city-generator.py"),
            str(p["nodes"]),
            str(p["size"]),
            str(p["degree"]),
            str(p["min-distance"]),
            str(p["trucks"]),
            str(p["packages"]),
            str(s),
        ],
    ),
    ExternalGenerator(
        "visitall",
        "ipc-2011/visit-all-sequential-satisficing",
        "visitar las casillas de una cuadrícula",
        "pddl-generators",
        _PG / "visitall",
        "grid",
        (
            Param("size", int, "3..8", "lado de la cuadrícula", minimum=2),
            Param("ratio", float, 1.0, "proporción de casillas que hay que visitar", minimum=0.01),
        ),
        lambda p, s, out, plan: [
            "./grid",
            "-n",
            str(p["size"]),
            "-r",
            str(p["ratio"]),
            "-s",
            str(s),
        ],
    ),
    ExternalGenerator(
        "woodworking",
        "ipc-2011/woodworking-sequential-satisficing",
        "carpintería con varias máquinas",
        "pddl-generators",
        _PG / "woodworking",
        "create_woodworking_instance.py",
        (
            Param("parts", int, "3..9", "número de piezas", minimum=1),
            Param("wood-factor", float, 1.2, "madera disponible / necesaria", minimum=1),
            Param("machines", int, 1, "máquinas de cada tipo", minimum=1),
        ),
        lambda p, s, out, plan: [
            *_python("create_woodworking_instance.py"),
            str(p["wood-factor"]),
            str(p["parts"]),
            str(p["machines"]),
            str(s),
        ],
    ),
    ExternalGenerator(
        "zenotravel",
        "ipc-2002/zenotravel-time-simple-automatic",
        "zenotravel temporal (variante simple time de la IPC 2002)",
        "pddl-generators",
        _PG / "zenotravel",
        "ztravel",
        (
            Param("cities", int, "3..6", "número de ciudades", minimum=2),
            Param("planes", int, "1..3", "número de aviones", minimum=1),
            Param("people", int, "2..8", "número de personas", minimum=1),
        ),
        lambda p, s, out, plan: [
            "./ztravel",
            "-s",
            str(s),
            str(p["cities"]),
            str(p["planes"]),
            str(p["people"]),
        ],
    ),
    ExternalGenerator(
        "rubiks-cube",
        "ipc-2023-classical/rubiks-cube",
        "cubo de Rubik desordenado con movimientos al azar",
        "IPC 2023",
        _IPC2023 / "rubiks-cube",
        "generator.py",
        (Param("moves", int, "3..12", "movimientos al azar desde el cubo resuelto", minimum=1),),
        lambda p, s, out, plan: [
            *_python("generator.py"),
            "-s",
            str(s),
            "-o",
            str(out),
            str(p["moves"]),
        ],
        writes_file=True,
    ),
    ExternalGenerator(
        "folding",
        "ipc-2023-classical/folding",
        "plegar una cadena (con plan de referencia)",
        "IPC 2023",
        _IPC2023 / "folding",
        "generate.py",
        (
            Param("length", int, "8..32", "elementos de la cadena", minimum=3),
            Param("folds", int, "1..6", "pliegues (menos que length)", minimum=1),
            Param(
                "scenario",
                str,
                "zigzag",
                "zigzag, spiral o bias-spiral",
                choices=("zigzag", "spiral", "bias-spiral"),
            ),
        ),
        lambda p, s, out, plan: [
            *_python("generate.py"),
            str(s),
            p["scenario"],
            str(p["length"]),
            str(p["folds"]),
            str(out),
            str(plan),
        ],
        writes_file=True,
        writes_plan=True,
        check=_folds_check,
    ),
    ExternalGenerator(
        "labyrinth",
        "ipc-2023-classical/labyrinth",
        "laberinto de cartas desplazables (con plan de referencia)",
        "IPC 2023",
        _IPC2023 / "labyrinth",
        "generator.py",
        (
            Param("size", int, "4..6", "lado del tablero", minimum=3),
            Param("rotations", int, "2..6", "desplazamientos para desordenarlo", minimum=1),
        ),
        lambda p, s, out, plan: [
            *_python("generator.py"),
            "--size",
            str(p["size"]),
            "--num-rotations",
            str(p["rotations"]),
            "--seed",
            str(s),
            "--pddl",
            str(out),
            "--plan",
            str(plan),
        ],
        writes_file=True,
        writes_plan=True,
        modules=("drawsvg", "networkx"),
    ),
)
