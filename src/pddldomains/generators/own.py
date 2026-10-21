"""Generadores propios, escritos para la versión exacta de los dominios del catálogo.

Cubren las colecciones para las que no hay un generador público que encaje: las numéricas
de la IPC 2023, las de SMTPlan (PDDL+ y efectos continuos) y greenhouse. Cada uno explica
por qué sus problemas tienen solución.
"""

import math
import random
from typing import Any

from pddldomains.catalog import Collection
from pddldomains.generators.base import (
    GeneratedProblem,
    Generator,
    GeneratorError,
    Param,
    number,
    write_problem,
)
from pddldomains.i18n import _


class CountersGenerator(Generator):
    """Contadores con valores iniciales al azar y la cadena ``c0 < c1 < … < cN-1``.

    Como en la IPC 2023, ``max_int`` es el doble del número de contadores (salvo que se
    diga otro). Tiene solución si ``max_int >= n - 1``: basta con dejar ``ci = i``.
    """

    name = "counters"
    collection = "ipc-2023-numeric/counters"
    description = "contadores con valores al azar que hay que ordenar (cadena de desigualdades)"
    params = (
        Param("counters", int, "4..12", "número de contadores", minimum=2),
        Param(
            "max-int",
            int,
            0,
            "valor máximo de un contador (0: el doble de los contadores)",
            minimum=0,
        ),
    )

    def check(self, params: dict[str, Any]) -> None:
        if params["max-int"] and params["max-int"] < params["counters"] - 1:
            raise GeneratorError(
                _("max-int tiene que ser al menos counters - 1 (si no, no hay solución)")
            )

    def generate(
        self, params: dict[str, Any], seed: int, name: str, collection: Collection
    ) -> GeneratedProblem:
        rng = random.Random(seed)
        n = params["counters"]
        top = params["max-int"] or 2 * n
        counters = [f"c{i}" for i in range(n)]
        init = [f"(= (max_int) {top})"] + [
            f"(= (value {c}) {rng.randint(0, top)})" for c in counters
        ]
        goal = [
            f"(<= (+ (value {a}) 1) (value {b}))"
            for a, b in zip(counters, counters[1:], strict=False)
        ]
        return GeneratedProblem(
            write_problem(name, "fn-counters", {"counter": counters}, init, goal)
        )


class ZenotravelNumericGenerator(Generator):
    """ZenoTravel numérico (versión de la IPC 2023, con ``located``, ``onboard`` y ``zoom-limit``).

    Cada avión tiene capacidad para el vuelo rápido más largo, y repostar llena el depósito,
    así que todo vuelo es posible: siempre hay solución.
    """

    name = "zenotravel-numeric"
    collection = "ipc-2023-numeric/zenotravel"
    description = "aviones con combustible que llevan personas entre ciudades"
    params = (
        Param("cities", int, "3..6", "número de ciudades", minimum=2),
        Param("planes", int, "1..3", "número de aviones", minimum=1),
        Param("people", int, "2..8", "número de personas", minimum=1),
        Param("max-distance", int, 1000, "distancia máxima entre dos ciudades", minimum=1),
        Param("plane-goals", float, 0.5, "proporción de aviones con ciudad de destino", minimum=0),
    )

    def generate(
        self, params: dict[str, Any], seed: int, name: str, collection: Collection
    ) -> GeneratedProblem:
        rng = random.Random(seed)
        cities = [f"city{i}" for i in range(params["cities"])]
        planes = [f"plane{i + 1}" for i in range(params["planes"])]
        people = [f"person{i + 1}" for i in range(params["people"])]
        top = params["max-distance"]
        distance = {}
        for i, a in enumerate(cities):
            for b in cities[i:]:
                distance[a, b] = distance[b, a] = (
                    0 if a == b else rng.randint(max(1, top // 10), top)
                )
        longest = max(distance.values())
        init = []
        for plane in planes:
            slow = rng.randint(1, 5)
            fast = rng.randint(slow + 1, 3 * slow + 1)
            capacity = rng.randint(longest * fast, longest * fast * 2)
            init += [
                f"(located {plane} {rng.choice(cities)})",
                f"(= (capacity {plane}) {capacity})",
                f"(= (fuel {plane}) {rng.randint(0, capacity)})",
                f"(= (slow-burn {plane}) {slow})",
                f"(= (fast-burn {plane}) {fast})",
                f"(= (onboard {plane}) 0)",
                f"(= (zoom-limit {plane}) {rng.randint(1, 10)})",
            ]
        init += [f"(located {person} {rng.choice(cities)})" for person in people]
        init += [f"(= (distance {a} {b}) {d})" for (a, b), d in sorted(distance.items())]
        init.append("(= (total-fuel-used) 0)")
        goal = [f"(located {person} {rng.choice(cities)})" for person in people]
        goal += [
            f"(located {plane} {rng.choice(cities)})"
            for plane in planes
            if rng.random() < params["plane-goals"]
        ]
        objects = {"aircraft": planes, "person": people, "city": cities}
        metric = "minimize (+ (* 1 (total-time)) (* 1 (total-fuel-used)))"
        return GeneratedProblem(
            write_problem(name, "zenotravel", objects, init, goal, metric=metric)
        )


class CarGenerator(Generator):
    """El coche de SMTPlan sin rozamiento: límites de aceleración y tiempo máximo.

    Para parar hay que haber recorrido 30 unidades. Acelerando con ``a = L`` y frenando con
    ``-L`` se recorren en ``2·sqrt(30/L)`` (con velocidad máxima ``sqrt(30·L)``, por debajo de
    100, donde se rompe el motor, si ``L <= 333``). Así que hay solución si ``max-time`` llega
    a ese tiempo; con 50, el de SMTPlan, siempre llega.
    """

    name = "car"
    collection = "smtplan/car-nodrag"
    description = "coche que acelera y frena (PDDL+: un proceso y un evento)"
    params = (
        Param(
            "limit",
            int,
            "1..10",
            "límite de aceleración (up_limit = limit, down_limit = -limit)",
            minimum=1,
        ),
        Param(
            "max-time",
            float,
            50,
            "tiempo máximo de marcha (running_time en el objetivo)",
            minimum=1,
        ),
    )

    def check(self, params: dict[str, Any]) -> None:
        fastest = 2 * math.sqrt(30 / min(params["limit"], 333))
        if params["max-time"] < fastest:
            raise GeneratorError(
                _(
                    "con limit={limit} hacen falta al menos {fastest:.2f} unidades de tiempo "
                    "(max-time es {max_time:g}): no habría solución",
                    limit=params["limit"],
                    fastest=fastest,
                    max_time=params["max-time"],
                )
            )

    def generate(
        self, params: dict[str, Any], seed: int, name: str, collection: Collection
    ) -> GeneratedProblem:
        limit = params["limit"]
        init = [
            "(running)",
            "(transmission_fine)",
            "(= (running_time) 0)",
            f"(= (up_limit) {limit})",
            f"(= (down_limit) -{limit})",
            "(= (d) 0)",
            "(= (a) 0)",
            "(= (v) 0)",
        ]
        goal = [
            "(goal_reached)",
            "(not (engineBlown))",
            f"(<= (running_time) {number(params['max-time'])})",
            "(transmission_fine)",
        ]
        return GeneratedProblem(
            write_problem(name, "car", {}, init, goal, metric="minimize (total-time)")
        )


class _GeneratorFamily(Generator):
    """El generador de SMTPlan: funcionar 1000 unidades de tiempo reponiendo combustible.

    El generador gasta 1 por unidad de tiempo durante 1000 y cada depósito aporta
    ``contribution`` al repostar. El combustible inicial es ``1000 - aportes + surplus``, así
    que con ``surplus >= 0`` hay combustible de sobra: siempre hay solución.
    """

    runtime = 1000
    capacity = 1000
    origin = "own"

    def contributions(self, rng: random.Random, params: dict[str, Any]) -> list[float]:
        raise NotImplementedError

    def tank_facts(self, tank: str, contribution: float, params: dict[str, Any]) -> list[str]:
        return [f"(available {tank})"]

    def check(self, params: dict[str, Any]) -> None:
        if params["surplus"] < 0:
            raise GeneratorError(_("surplus tiene que ser >= 0 (si no, no hay solución)"))

    def generate(
        self, params: dict[str, Any], seed: int, name: str, collection: Collection
    ) -> GeneratedProblem:
        rng = random.Random(seed)
        tanks = [f"tank{i + 1}" for i in range(params["tanks"])]
        contributions = self.contributions(rng, params)
        fuel = self.runtime - sum(contributions) + params["surplus"]
        if fuel < 0:
            raise GeneratorError(
                _(
                    "con {tanks} depósitos el combustible inicial sería negativo; use menos "
                    "depósitos",
                    tanks=len(tanks),
                )
            )
        facts = []
        for tank, contribution in zip(tanks, contributions, strict=True):
            facts += self.tank_facts(tank, contribution, params)
        problem = self.write(name, tanks, number(round(fuel, 3)), facts)
        return GeneratedProblem(problem, notes={"initial-fuel": round(fuel, 3)})

    def write(self, name: str, tanks: list[str], fuel: str, tank_facts: list[str]) -> str:
        init = [f"(= (fuelLevel gen) {fuel})", f"(= (capacity gen) {self.capacity})", *tank_facts]
        return write_problem(
            name, self.domain_name, {"generator": ["gen"], "tank": tanks}, init, ["(generator-ran)"]
        )

    domain_name = ""


_TANKS = Param("tanks", int, "1..8", "número de depósitos", minimum=1)
_SURPLUS = Param("surplus", float, "1..20", "combustible de sobra al terminar", minimum=0)


class GeneratorLinear(_GeneratorFamily):
    name = "generator-linear"
    collection = "smtplan/generator-linear"
    domain_name = "generator_linear"
    description = "generador con repostaje lineal (cada depósito aporta 20)"
    params = (_TANKS, _SURPLUS)

    def contributions(self, rng: random.Random, params: dict[str, Any]) -> list[float]:
        return [20.0] * params["tanks"]  # refuel: 10 unidades de tiempo a 2 por unidad


class GeneratorNonlinear(_GeneratorFamily):
    name = "generator-nonlinear"
    collection = "smtplan/generator-nonlinear"
    domain_name = "generator-nonlinear"
    description = "generador con repostaje no lineal (cada depósito aporta 100/3)"
    params = (_TANKS, _SURPLUS)
    capacity = 1600

    def contributions(self, rng: random.Random, params: dict[str, Any]) -> list[float]:
        return [100 / 3] * params["tanks"]  # ∫ 0.1·t² dt de 0 a 10

    def tank_facts(self, tank: str, contribution: float, params: dict[str, Any]) -> list[str]:
        return [f"(available {tank})", f"(= (ptime {tank}) 0)"]


class GeneratorEvents(_GeneratorFamily):
    name = "generator-events"
    collection = "smtplan/generator-events"
    domain_name = "generatorplus"
    description = "generador PDDL+ (proceso de repostaje y eventos de depósito vacío y desborde)"
    params = (
        _TANKS,
        _SURPLUS,
        Param(
            "tank-fuel",
            float,
            40,
            "combustible de cada depósito (un rango se sortea por depósito)",
            minimum=1,
            per_item=True,
        ),
    )
    capacity = 1600

    def contributions(self, rng: random.Random, params: dict[str, Any]) -> list[float]:
        param = self.param("tank-fuel")
        return [float(param.resolve(params["tank-fuel"], rng)) for _tank in range(params["tanks"])]

    def tank_facts(self, tank: str, contribution: float, params: dict[str, Any]) -> list[str]:
        return [
            f"(= (fuelInTank {tank}) {number(contribution)})",
            f"(= (ptime {tank}) 0)",
            f"(available {tank})",
        ]

    def write(self, name: str, tanks: list[str], fuel: str, tank_facts: list[str]) -> str:
        init = [
            f"(= (fuelLevel gen) {fuel})",
            f"(= (capacity gen) {self.capacity})",
            *tank_facts,
            "(safe gen)",
        ]
        return write_problem(
            name, self.domain_name, {"generator": ["gen"], "tank": tanks}, init, ["(generator-ran)"]
        )


class GeneratorToricelli(_GeneratorFamily):
    name = "generator-toricelli"
    collection = "smtplan/generator-toricelli"
    domain_name = "generator-toricelli"
    description = (
        "generador con repostaje según la ley de Torricelli (cada depósito se vacía entero)"
    )
    params = (
        _TANKS,
        _SURPLUS,
        Param(
            "tank-fuel",
            float,
            25,
            "combustible de cada depósito (un rango se sortea por depósito)",
            minimum=1,
            per_item=True,
        ),
        Param("flow", float, 0.4, "constante de flujo de los depósitos", minimum=0.01),
    )

    def contributions(self, rng: random.Random, params: dict[str, Any]) -> list[float]:
        param = self.param("tank-fuel")
        return [float(param.resolve(params["tank-fuel"], rng)) for _tank in range(params["tanks"])]

    def tank_facts(self, tank: str, contribution: float, params: dict[str, Any]) -> list[str]:
        root = round(math.sqrt(contribution), 6)
        return [
            f"(= (tank_fuel_level {tank}) {number(contribution)})",
            f"(= (sqrtvolinit {tank}) {number(root)})",
            f"(= (flow_constant {tank}) {number(params['flow'])})",
        ]

    def write(self, name: str, tanks: list[str], fuel: str, tank_facts: list[str]) -> str:
        init = [
            f"(= (gen_fuel_level generator) {fuel})",
            f"(= (capacity generator) {self.capacity})",
            *tank_facts,
            f"(= (runtime) {self.runtime})",
        ]
        return write_problem(
            name,
            self.domain_name,
            {"gen": ["generator"], "tank": tanks},
            init,
            ["(generator_ran generator)"],
            metric="minimize (total-time)",
        )


class GreenhouseGenerator(Generator):
    """Greenhouse (dominio propio): regar depósitos con el agua recogida de la lluvia.

    Una sola recogida (``collect-rain``, 4 unidades de tiempo) da 4 de reserva, 8 si llueve,
    y 1 más si el sensor sigue encendido al final; después ya no se puede recoger más (deja
    ``logged``). Riego: todos los depósitos reciben lo que dure, que no puede pasar de la
    reserva y se paga del presupuesto. Así que hay solución si cada objetivo de agua y el
    presupuesto llegan a la reserva máxima (5 sin lluvia, 9 con lluvia).
    """

    name = "greenhouse"
    collection = "propios/greenhouse"
    description = "invernadero (casos límite de PDDL 2.1 temporal)"
    params = (
        Param("tanks", int, "1..4", "número de depósitos", minimum=1),
        Param(
            "rain", str, "random", "si llueve: yes, no o random", choices=("yes", "no", "random")
        ),
    )

    def generate(
        self, params: dict[str, Any], seed: int, name: str, collection: Collection
    ) -> GeneratedProblem:
        rng = random.Random(seed)
        raining = params["rain"] == "yes" or (params["rain"] == "random" and rng.random() < 0.5)
        reserve = 9 if raining else 5
        tanks = [f"t{i + 1}" for i in range(params["tanks"])]
        targets = {tank: rng.randint(1, reserve) for tank in tanks}
        budget = rng.randint(max(targets.values()), reserve + 6)
        init = (["(raining)"] if raining else []) + ["(sensor-on)", "(idle)"]
        init += [f"(= (water {tank}) 0)" for tank in tanks]
        init += ["(= (reserve) 0)", f"(= (budget) {budget})"]
        goal = ["(logged)"] + [f"(>= (water {tank}) {target})" for tank, target in targets.items()]
        goal.append("(>= (budget) 0)")
        return GeneratedProblem(
            write_problem(name, "greenhouse", {"tank": tanks}, init, goal),
            notes={"raining": raining},
        )


OWN_GENERATORS: tuple[Generator, ...] = (
    CountersGenerator(),
    ZenotravelNumericGenerator(),
    CarGenerator(),
    GeneratorLinear(),
    GeneratorNonlinear(),
    GeneratorEvents(),
    GeneratorToricelli(),
    GreenhouseGenerator(),
)
