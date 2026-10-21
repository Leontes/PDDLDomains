"""Subcomando ``generate``: genera problemas, los revisa y valida sus planes.

Escribe en el directorio de salida (por defecto ``salidas/generados/<generador>/``):

* ``domain.pddl`` (copia del dominio del catálogo; ``domain-pNN.pddl`` en las colecciones
  con un dominio por problema);
* ``pNN.pddl`` y, si el generador lo conoce, ``pNN.plan``;
* ``generation.json``: generador, colección, semillas y parámetros de cada problema, para
  repetir la generación.

Después revisa cada problema contra su dominio (``lint``) y, si hay plan y VAL está
compilado, lo valida.
"""

import argparse
import itertools
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from pddldomains import __version__
from pddldomains.catalog import ROOT, Catalog
from pddldomains.generators import GENERATORS, Generator, GeneratorError, find_generator
from pddldomains.i18n import _
from pddldomains.lint import Finding, lint_domain, lint_problem, summarize

#: Directorio de salida por defecto.
OUTPUT_DIR = ROOT / "salidas" / "generados"
#: Manifiesto de una generación.
MANIFEST = "generation.json"
#: Cómo se escribe cada origen (se traduce al mostrarlo).
_ORIGIN_LABELS = {"own": "propio", "ported": "portado"}


def add_generate_parser(commands: Any) -> None:
    """Añade el subcomando ``generate`` a la CLI."""
    generate = commands.add_parser(
        "generate",
        help=_("genera problemas aleatorios"),
        description=_(
            "Genera problemas para una colección del catálogo. Los parámetros admiten un valor "
            "(-p tanks=4), un rango aleatorio (-p tanks=2..8) o una serie (-p tanks=2,4,6: N "
            "problemas por valor)."
        ),
    )
    generate.add_argument(
        "generator",
        nargs="?",
        metavar=_("GENERADOR"),
        help=_("nombre del generador o colección para la que genera"),
    )
    generate.add_argument("--list", action="store_true", help=_("enumera los generadores"))
    generate.add_argument(
        "--params", action="store_true", help=_("muestra los parámetros del generador")
    )
    generate.add_argument(
        "-n",
        "--count",
        type=int,
        default=1,
        help=_("problemas por combinación de parámetros (por defecto, 1)"),
    )
    generate.add_argument(
        "-s", "--seed", type=int, default=1, help=_("semilla inicial (por defecto, 1)")
    )
    generate.add_argument(
        "-p",
        "--param",
        action="append",
        default=[],
        metavar=_("CLAVE=VALOR"),
        help=_("parámetro; repetible"),
    )
    generate.add_argument(
        "-o",
        "--output",
        type=Path,
        help=_("directorio de salida (por defecto, {path}/<generador>)", path=OUTPUT_DIR),
    )
    generate.add_argument(
        "--force", action="store_true", help=_("vacía el directorio de salida si no lo está")
    )
    generate.add_argument(
        "--no-check",
        action="store_true",
        help=_("no revisa los problemas ni valida los planes"),
    )


def _origin(generator: Generator) -> str:
    label = _ORIGIN_LABELS.get(generator.origin)
    return _(label) if label else generator.origin


def _list(catalog: Catalog) -> int:
    print(f"{_('GENERADOR'):20} {_('ORIGEN'):16} {_('COLECCIÓN'):45} {_('DESCRIPCIÓN')}")
    for generator in GENERATORS.values():
        reason = generator.unavailable()
        state = "  [" + _("no disponible: {reason}", reason=reason) + "]" if reason else ""
        collection = generator.collection or _("(cualquier clásica)")
        print(
            f"{generator.name:20} {_origin(generator):16} {collection:45} "
            f"{_(generator.description)}{state}"
        )
    return 0


def _show_params(generator: Generator) -> int:
    print(f"{generator.name}: {_(generator.description)}")
    collection = generator.collection or _("(la del parámetro collection)")
    print(
        "  "
        + _(
            "colección: {collection}; origen: {origin}",
            collection=collection,
            origin=_origin(generator),
        )
    )
    explanation = generator.explanation()
    if explanation:
        print()
        for line in _(explanation).splitlines():
            print(f"  {line}")
    print("\n  " + _("Parámetros:"))
    for param in generator.params:
        if param.default is None:
            default = _("obligatorio")
        else:
            default = _("por defecto {value}", value=param.default)
        choices = f" [{', '.join(param.choices)}]" if param.choices else ""
        print(f"    {param.name:16} {param.kind.__name__:5} {default:22} {_(param.help)}{choices}")
    return 0


def _raw_params(generator: Generator, options: list[str]) -> dict[str, list[str]]:
    """Los valores sin resolver de cada parámetro (una lista si es una serie)."""
    raw: dict[str, list[str]] = {p.name: [p.default] for p in generator.params}
    for option in options:
        key, sep, value = option.partition("=")
        if not sep:
            raise GeneratorError(_("se esperaba CLAVE=VALOR: '{option}'", option=option))
        param = generator.param(key.strip())
        values = [v.strip() for v in value.split(",")] if "," in value else [value.strip()]
        if param.per_item and len(values) > 1:
            raise GeneratorError(_("{name} no admite series", name=param.name))
        raw[param.name] = values
    missing = [name for name, values in raw.items() if values == [None]]
    if missing:
        raise GeneratorError(
            _(
                "falta el parámetro {names} (-p {first}=...)",
                names=", ".join(missing),
                first=missing[0],
            )
        )
    return raw


def _resolve(
    generator: Generator, combination: dict[str, Any], rng: random.Random
) -> dict[str, Any]:
    resolved = {}
    for param in generator.params:
        value = combination[param.name]
        if param.per_item:
            param.resolve(value, random.Random(0))  # solo para comprobar el valor
            resolved[param.name] = value
        else:
            resolved[param.name] = param.resolve(value, rng)
    generator.check(resolved)
    return resolved


def _tool_commit(generator: Generator) -> str | None:
    tool = getattr(generator, "tool", None)
    if tool is None:
        return None
    result = subprocess.run(
        ["git", "-C", str(tool), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def cmd_generate(args: argparse.Namespace) -> int:
    """Ejecuta el subcomando ``generate``."""
    catalog = Catalog(args.catalog)
    if args.list:
        return _list(catalog)
    if not args.generator:
        message = _("falta el generador (ver 'pddldomains generate --list')")
        print(f"error: {message}", file=sys.stderr)
        return 2
    try:
        return _generate(args, catalog)
    except GeneratorError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _generate(args: argparse.Namespace, catalog: Catalog) -> int:
    generator = find_generator(args.generator, catalog)
    if args.params:
        return _show_params(generator)
    reason = generator.unavailable()
    if reason:
        raise GeneratorError(f"{generator.name} {reason}")
    raw = _raw_params(generator, args.param)
    output = args.output or OUTPUT_DIR / generator.name
    if output.exists() and any(output.iterdir()):
        if not args.force:
            raise GeneratorError(_("{path} no está vacío (use --force para vaciarlo)", path=output))
        for old in (*output.glob("*.pddl"), *output.glob("*.plan"), *output.glob(MANIFEST)):
            old.unlink()
    output.mkdir(parents=True, exist_ok=True)
    combinations = [
        dict(zip(raw, values, strict=True)) for values in itertools.product(*raw.values())
    ]
    manifest: dict[str, Any] = {
        "generator": generator.name,
        "origin": generator.origin,
        "tool_commit": _tool_commit(generator),
        "pddldomains": __version__,
        "seed": args.seed,
        "count": args.count,
        "params": {k: v if len(v) > 1 else v[0] for k, v in raw.items()},
        "problems": [],
    }
    jobs = []
    index = 0
    for combination in combinations:
        for _repetition in range(args.count):
            jobs.append((index, combination))
            index += 1
    shared_domain: Path | None = None
    width = max(2, len(str(len(jobs))))
    for index, combination in jobs:
        seed = args.seed + index
        resolved = _resolve(generator, combination, random.Random(seed))
        collection = generator.collection_of(catalog, resolved)
        label = f"p{index + 1:0{width}d}"
        name = f"{generator.name}-{label}-s{seed}"
        result = generator.generate(resolved, seed, name, collection)
        domain = result.domain or collection.domain_files()[0]
        per_problem = len(collection.domain_files()) > 1
        if per_problem:
            shutil.copy2(domain, output / f"domain-{label}.pddl")
        elif shared_domain is None:
            shared_domain = domain
            shutil.copy2(domain, output / "domain.pddl")
        (output / f"{label}.pddl").write_text(result.problem, encoding="utf-8")
        if result.plan:
            (output / f"{label}.plan").write_text(result.plan, encoding="utf-8")
        manifest["collection"] = collection.id
        manifest["problems"].append(
            {
                "file": f"{label}.pddl",
                "name": name,
                "seed": seed,
                "params": resolved,
                "plan": f"{label}.plan" if result.plan else None,
                **({"notes": result.notes} if result.notes else {}),
            }
        )
        values = ", ".join(f"{k}={v}" for k, v in resolved.items())
        print(f"  {label}.pddl  {values}", file=sys.stderr)
    (output / MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    message = _(
        "{count} problemas de {generator} en {path}",
        count=len(jobs),
        generator=generator.name,
        path=output,
    )
    print(message, file=sys.stderr)
    if args.no_check:
        return 0
    return _check(output, manifest)


def _check(output: Path, manifest: dict[str, Any]) -> int:
    """Revisa los problemas generados y valida sus planes."""
    from pddldomains.val import find_tool, validate

    findings: list[Finding] = []
    invalid = 0
    validated = 0
    has_val = find_tool("Validate") is not None
    domains = {}
    for entry in manifest["problems"]:
        problem = output / entry["file"]
        own = output / f"domain-{problem.stem}.pddl"
        domain_path = own if own.exists() else output / "domain.pddl"
        if domain_path not in domains:
            domains[domain_path] = lint_domain(domain_path)[0]
        domain = domains[domain_path]
        if domain is not None:
            findings.extend(f for f in lint_problem(problem, domain) if f.level != "info")
        if entry["plan"] and has_val:
            result = validate(domain_path, problem, output / entry["plan"])
            validated += 1
            if not result.valid:
                invalid += 1
                print(
                    _(
                        "{name}: el plan generado NO es válido para VAL: {message}",
                        name=problem.name,
                        message=result.message,
                    )
                )
    for finding in findings:
        print(finding.format(Path.cwd()))
    counts = summarize(findings)
    line = _(
        "Revisión: {errors} errores, {warnings} avisos",
        errors=counts["error"],
        warnings=counts["warning"],
    )
    if validated:
        line += _(
            "; planes: {valid} de {total} válidos", valid=validated - invalid, total=validated
        )
    elif any(e["plan"] for e in manifest["problems"]) and not has_val:
        line += _("; planes sin validar (VAL no está compilado)")
    print(line, file=sys.stderr)
    return 1 if counts["error"] or invalid else 0
