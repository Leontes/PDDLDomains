"""Generador de parking, portado a Python desde pddl-generators (``parking-generator.pl``).

El original es ``parking/parking-generator.pl`` de AI-Planning/pddl-generators
(https://github.com/AI-Planning/pddl-generators, commit ``e6277fb``), la colección reunida por
Jendrik Seipp, Álvaro Torralba y Jörg Hoffmann (https://doi.org/10.5281/zenodo.6382173). Ese
repositorio no declara licencia: la traducción se incluye con esta atribución (ver
``LICENCIAS.md``).

El dominio de parking (IPC 2008 y 2011) consiste en aparcar coches en una calle con N plazas
junto al bordillo, en las que se puede aparcar en doble fila pero no en triple. Se pasa de
una configuración de coches aparcados a otra moviendo coches de un sitio a otro. Con
``2·(N-1)`` coches, como en la IPC, queda siempre una plaza libre y hay solución; con menos,
también.

Es una traducción literal del original de Perl, para no depender de Perl: con la misma
semilla da exactamente el mismo problema, porque reproduce el generador de números
aleatorios de Perl (``drand48``, el que usa Perl desde la versión 5.20 en todas las
plataformas) y el orden en que el script lo llama. Lo comprueban los tests con salidas del
original guardadas en ``tests/datos/parking/``. Solo se ha portado el modo ``seq``, el del
catálogo (el original escribe además la métrica ``total-time`` en modo ``time``).

Como hacía la envoltura del original, al texto se le añaden después el valor inicial de
``total-cost`` y la métrica de coste, que el original no escribe, y se cambia el nombre del
problema (el original lo llama ``parking``, como el dominio: la errata (‡) del catálogo).
"""

import math
from typing import Any

from pddldomains.catalog import Collection
from pddldomains.generators.base import (
    GeneratedProblem,
    Generator,
    GeneratorError,
    Param,
    ensure_total_cost,
    set_problem_name,
)
from pddldomains.i18n import _


class PerlRandom:
    """El generador de números aleatorios de Perl 5.20 o posterior (``drand48``)."""

    def __init__(self, seed: int) -> None:
        # srand(semilla): la semilla se trunca a 32 bits y va en los bits altos del estado.
        self.state = 0x330E + ((seed & 0xFFFFFFFF) << 16)

    def rand(self, limit: float = 1.0) -> float:
        """``rand(limit)`` de Perl: un real en [0, limit)."""
        self.state = (self.state * 0x5DEECE66D + 0xB) & 0xFFFFFFFFFFFF
        return limit * (self.state / 2**48)


def _rand_between(low: int, high: int, rng: PerlRandom) -> int:
    """``rand_between`` del original: un entero en [low, high] (sin sortear si son iguales)."""
    if low == high:
        return low
    low, high = min(low, high), max(low, high)
    return low + int(rng.rand(1 + high - low))


def _shuffle(items: list[str], rng: PerlRandom) -> list[str]:
    """``shuffle`` del original: saca elementos al azar uno a uno."""
    remaining = list(items)
    result = []
    while remaining:
        result.append(remaining.pop(int(rng.rand(len(remaining)))))
    return result


def _place(curbs: list[str], cars: list[str], against_curb: int) -> dict[str, str]:
    """Los primeros ``against_curb`` coches junto al bordillo y el resto detrás de ellos.

    Las claves son plazas (el coche junto al bordillo) y coches (el coche aparcado detrás).
    """
    against = {curbs[i]: cars[i] for i in range(against_curb)}
    for i in range(against_curb, len(cars)):
        against[cars[i - against_curb]] = cars[i]
    return against


def _initial(curbs: list[str], cars: list[str], rng: PerlRandom) -> dict[str, str]:
    at_least = math.ceil(len(cars) / 2)
    at_most = min(len(curbs), len(cars))
    against_curb = _rand_between(at_least, at_most, rng)
    return _place(curbs, _shuffle(cars, rng), against_curb)


def _layout(curbs: list[str], against: dict[str, str]) -> str:
    text = ""
    for curb in curbs:
        text += f";  {curb}: "
        if curb in against:
            car = against[curb]
            text += f"{car} " + (f"{against[car]} " if car in against else "")
        text += "\n"
    return text


def perl_problem(curbs: int, cars: int, seed: int) -> str:
    """El texto exacto de ``parking-generator.pl problem <curbs> <cars> seq <seed>``.

    ``cars = 0`` es el máximo, ``2·(curbs - 1)``, como en el original.
    """
    most = 2 * curbs - 2
    cars = cars or most
    if cars > most:
        raise GeneratorError(
            _("con {curbs} plazas caben como mucho {most} coches", curbs=curbs, most=most)
        )
    rng = PerlRandom(seed)
    curb_names = [f"curb_{i:0{len(str(curbs - 1))}d}" for i in range(curbs)]
    car_names = [f"car_{i:0{len(str(cars - 1))}d}" for i in range(cars)]
    initial = _initial(curb_names, car_names, rng)
    goal = _place(curb_names, car_names, min(curbs, cars))

    text = "(define   (problem parking)\n  (:domain parking)\n"
    text += "  (:objects\n    " + "".join(f" {car} " for car in car_names) + "- car\n     "
    text += "".join(f"{curb} " for curb in curb_names) + "- curb\n  )\n"
    text += "  (:init\n"
    for curb in curb_names:
        if curb not in initial:
            text += f"    (curb-clear {curb})\n"
            continue
        car = initial[curb]
        text += f"    (at-curb {car})\n    (at-curb-num {car} {curb})\n"
        if car in initial:
            text += f"    (behind-car {initial[car]} {car})\n    (car-clear {initial[car]})\n"
        else:
            text += f"    (car-clear {car})\n"
    text += "  )\n  (:goal\n    (and\n"
    for curb in curb_names:
        if curb in goal:
            car = goal[curb]
            text += f"      (at-curb-num {car} {curb})\n"
            if car in goal:
                text += f"      (behind-car {goal[car]} {car})\n"
    text += "    )\n  )\n)\n"
    text += "; =========== INIT =========== \n" + _layout(curb_names, initial)
    text += "; ========== /INIT =========== \n\n"
    text += "; =========== GOAL =========== \n" + _layout(curb_names, goal)
    text += "; =========== /GOAL =========== \n"
    return text


class ParkingGenerator(Generator):
    """Aparcar coches en una calle con N plazas junto al bordillo (en doble fila, no en triple).

    Con ``2·(N-1)`` coches, como en la IPC, queda siempre una plaza libre y hay solución; con
    menos, también. Es una traducción a Python del generador de parking de pddl-generators que
    da, con la misma semilla, los mismos problemas que el original de Perl.
    """

    name = "parking"
    collection = "ipc-2011/parking-sequential-satisficing"
    description = "aparcar coches en fila (los mismos problemas que el original de Perl)"
    origin = "ported"
    params = (
        Param("curbs", int, "3..8", "plazas junto al bordillo", minimum=2),
        Param("cars", int, 0, "coches (0: 2·(curbs - 1), como en la IPC)", minimum=0),
    )

    def check(self, params: dict[str, Any]) -> None:
        most = 2 * (params["curbs"] - 1)
        if params["cars"] > most:
            raise GeneratorError(
                _(
                    "con {curbs} plazas caben como mucho {most} coches",
                    curbs=params["curbs"],
                    most=most,
                )
            )

    def generate(
        self, params: dict[str, Any], seed: int, name: str, collection: Collection
    ) -> GeneratedProblem:
        text = perl_problem(params["curbs"], params["cars"], seed)
        return GeneratedProblem(set_problem_name(ensure_total_cost(text), name))
