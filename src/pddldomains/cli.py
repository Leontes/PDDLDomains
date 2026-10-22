"""Interfaz de línea de comandos de pddldomains.

Subcomandos:

* ``list``: las colecciones del catálogo con sus tipos (admite los filtros de ``dataset``).
* ``info COLECCIÓN``: la ficha, el análisis y los problemas de una colección.
* ``types``: los tipos con los que se clasifican los dominios.
* ``levels``: la escala de versiones de PDDL y cuántos dominios hay en cada nivel.
* ``dataset [DEFINICIÓN]``: un dataset (de ``datasets/`` o con filtros), como lista, CSV o
  JSON, o exportado a un directorio.
* ``index``: regenera el índice del catálogo (``dominios/INDEX.md`` e ``INDICE.md``).
* ``lint [OBJETIVO...]``: revisa dominios y problemas (del catálogo o cualquier ruta).
* ``validate DOMINIO PROBLEMA PLAN...``: valida planes con VAL.
* ``sources {check,diff,fetch}``: compara el catálogo con los ficheros originales y trae
  más problemas del origen.
* ``generate GENERADOR``: genera problemas aleatorios (``generate --list`` los enumera).
* ``trace DOMINIO PROBLEMA PLAN``: la traza de un plan (sus estados) en JSON, degradada si se
  pide.

Los textos salen en inglés o en español (``--lang``, ver :mod:`pddldomains.i18n`).

Códigos de salida: 0 todo bien; 1 hay hallazgos (errores de la revisión, planes no válidos,
diferencias sin documentar…); 2 entrada no válida.
"""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pddldomains import __version__
from pddldomains.analysis import Analyzer
from pddldomains.catalog import (
    Catalog,
    CatalogError,
    Collection,
    Task,
    is_domain_file,
    read_collection,
)
from pddldomains.datasets import (
    Dataset,
    DatasetError,
    build_dataset,
    export,
    find_definition,
    load_definition,
    selection_from_options,
    to_csv,
    to_json,
    to_lines,
)
from pddldomains.features import LEVELS, TAGS, level_reasons, parse_level
from pddldomains.i18n import ENV_VAR, LANGUAGES, _, localized
from pddldomains.index import INDEX_FILES, render_index
from pddldomains.lint import Finding, lint_domain, lint_problem, summarize
from pddldomains.pddl import Domain
from pddldomains.sources import SourceError
from pddldomains.traces import MAX_ATOMS, UNIVERSES

#: Código de salida cuando hay hallazgos.
EXIT_FINDINGS = 1
#: Código de salida cuando la entrada no es válida.
EXIT_INVALID_INPUT = 2


def _requirement(value: str) -> str:
    return value if value.startswith(":") else f":{value}"


def _level(value: str) -> int:
    try:
        return parse_level(value).number
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _tag(value: str) -> str:
    if value not in TAGS:
        raise argparse.ArgumentTypeError(
            _("tipo desconocido '{value}' (ver 'pddldomains types')", value=value)
        )
    return value


def parse_numbers(text: str) -> list[int]:
    """``"1-3,7"`` → ``[1, 2, 3, 7]``."""
    numbers: list[int] = []
    for part in text.split(","):
        start, _dash, end = part.strip().partition("-")
        try:
            first, last = int(start), int(end or start)
        except ValueError as error:
            raise argparse.ArgumentTypeError(_("rango no válido: '{part}'", part=part)) from error
        numbers.extend(range(first, last + 1))
    return numbers


def add_filters(parser: argparse.ArgumentParser) -> None:
    """Las opciones de filtrado comunes a ``list`` y ``dataset``."""
    group = parser.add_argument_group(_("filtros (los de [[select]] en las definiciones)"))
    group.add_argument(
        "--collection",
        action="append",
        dest="collections",
        metavar=_("PATRÓN"),
        help=_("colecciones (admite comodines: 'ipc-2011/*'); repetible"),
    )
    group.add_argument(
        "--exclude-collection",
        action="append",
        dest="exclude_collections",
        metavar=_("PATRÓN"),
        help=_("colecciones que no; repetible"),
    )
    group.add_argument(
        "--type",
        action="append",
        dest="types",
        type=_tag,
        metavar=_("TIPO"),
        help=_("tipo que tienen que tener los problemas (todos los dados)"),
    )
    group.add_argument(
        "--exclude-type",
        action="append",
        dest="exclude_types",
        type=_tag,
        metavar=_("TIPO"),
        help=_("tipo que no pueden tener; repetible"),
    )
    group.add_argument(
        "--requirement",
        action="append",
        dest="requirements",
        type=_requirement,
        metavar="REQ",
        help=_("requisito usado (':durative-actions'); repetible"),
    )
    group.add_argument(
        "--exclude-requirement",
        action="append",
        dest="exclude_requirements",
        type=_requirement,
        metavar="REQ",
        help=_("requisito que no; repetible"),
    )
    group.add_argument(
        "--level",
        action="append",
        dest="levels",
        type=_level,
        metavar=_("NIVEL"),
        help=_("nivel de versión de PDDL, número o nombre (3, 'PDDL 2.1'); repetible"),
    )
    group.add_argument(
        "--min-level",
        type=_level,
        metavar=_("NIVEL"),
        help=_("nivel mínimo de versión de PDDL"),
    )
    group.add_argument(
        "--max-level",
        type=_level,
        metavar=_("NIVEL"),
        help=_("nivel máximo: lo que soporta un planificador que llega a esa versión"),
    )
    group.add_argument(
        "--problems",
        action="append",
        metavar=_("PATRÓN"),
        help=_("nombres de problema ('p0*'); repetible"),
    )
    group.add_argument("--min-objects", type=int, metavar="N")
    group.add_argument("--max-objects", type=int, metavar="N")
    group.add_argument("--max-kb", type=float, metavar="KB", help=_("tamaño máximo del problema"))
    group.add_argument("--with-plan", action="store_true", help=_("solo con plan de referencia"))
    group.add_argument(
        "--per-collection",
        type=int,
        metavar="N",
        help=_("como mucho N problemas por colección"),
    )
    group.add_argument(
        "--order",
        choices=["first", "random", "smallest"],
        help=_("orden para --per-collection (por defecto, first)"),
    )
    group.add_argument("--seed", type=int, help=_("semilla del orden aleatorio"))


_FILTER_KEYS = {
    "collections": "collections",
    "exclude_collections": "exclude-collections",
    "types": "types",
    "exclude_types": "exclude-types",
    "requirements": "requirements",
    "exclude_requirements": "exclude-requirements",
    "levels": "levels",
    "min_level": "min-level",
    "max_level": "max-level",
    "problems": "problems",
    "min_objects": "min-objects",
    "max_objects": "max-objects",
    "max_kb": "max-kb",
    "with_plan": "with-plan",
    "per_collection": "per-collection",
    "order": "order",
    "seed": "seed",
}


def _selection(args: argparse.Namespace) -> dict[str, Any]:
    return selection_from_options({key: getattr(args, attr) for attr, key in _FILTER_KEYS.items()})


def build_parser() -> argparse.ArgumentParser:
    """Construye el analizador de argumentos de la CLI (en el idioma actual)."""
    parser = argparse.ArgumentParser(
        prog="pddldomains",
        description=_("Catálogo de dominios PDDL: clasificación, datasets, revisión y generadores"),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--lang",
        choices=LANGUAGES,
        help=_(
            "idioma de los mensajes (por defecto, el de {var} o la configuración regional)",
            var=ENV_VAR,
        ),
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        metavar="DIR",
        help=_("directorio del catálogo (por defecto, dominios/ o $PDDL_DOMINIOS)"),
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar=_("COMANDO"))

    list_cmd = commands.add_parser("list", help=_("lista las colecciones con sus tipos"))
    add_filters(list_cmd)
    list_cmd.add_argument("--format", choices=["table", "json", "ids"], default="table")

    info = commands.add_parser("info", help=_("ficha, análisis y problemas de una colección"))
    info.add_argument("collection", help=_("identificador (o su parte final si no es ambigua)"))
    info.add_argument("--format", choices=["text", "json"], default="text")

    commands.add_parser("types", help=_("los tipos con los que se clasifican los dominios"))
    commands.add_parser(
        "levels",
        help=_("la escala de versiones de PDDL y cuántos dominios hay en cada nivel"),
        description=_(
            "Los niveles son las versiones de PDDL en orden, de STRIPS a PDDL+. Cada dominio "
            "está en el nivel más alto de lo que usa; un planificador que llega al nivel N "
            "tiene que poder con los niveles 1 a N (--max-level N en list y dataset)."
        ),
    )

    dataset = commands.add_parser(
        "dataset",
        help=_("lista o exporta un dataset"),
        description=_(
            "Un dataset es una definición de datasets/ (o un .toml), o una selección hecha con "
            "los filtros. Sin --export, escribe la lista de problemas."
        ),
    )
    dataset.add_argument("definition", nargs="?", help=_("nombre en datasets/ o ruta a un .toml"))
    add_filters(dataset)
    dataset.add_argument(
        "--format",
        choices=["lines", "csv", "json"],
        default="lines",
        help=_("lines: '<dominio> <problema>' por línea (por defecto)"),
    )
    dataset.add_argument(
        "--relative",
        action="store_true",
        help=_("rutas relativas al catálogo en lugar de absolutas"),
    )
    dataset.add_argument(
        "-o", "--output", type=Path, help=_("fichero de salida (por defecto, stdout)")
    )
    dataset.add_argument(
        "--export",
        type=Path,
        metavar="DIR",
        help=_("copia los problemas a DIR/<grupo>/ con un dataset.json"),
    )
    dataset.add_argument(
        "--link", action="store_true", help=_("con --export, enlaces en vez de copias")
    )
    dataset.add_argument(
        "--force", action="store_true", help=_("con --export, aunque DIR no esté vacío")
    )
    dataset.add_argument(
        "--list-definitions",
        action="store_true",
        help=_("enumera las definiciones de datasets/"),
    )

    index = commands.add_parser(
        "index", help=_("regenera el índice del catálogo (dominios/INDEX.md e INDICE.md)")
    )
    index.add_argument("--check", action="store_true", help=_("solo comprueba que está al día"))

    lint = commands.add_parser(
        "lint",
        help=_("revisa dominios y problemas"),
        description=_(
            "Revisa colecciones del catálogo (por identificador), problemas "
            "(<colección>/<problema>) o rutas: un directorio con domain.pddl y problemas, un "
            "dominio o un problema (con --domain o con el domain.pddl de su directorio). Sin "
            "objetivos, revisa todo el catálogo."
        ),
    )
    lint.add_argument("targets", nargs="*", metavar=_("OBJETIVO"))
    lint.add_argument("--domain", type=Path, help=_("dominio de los problemas sueltos"))
    lint.add_argument(
        "-v", "--verbose", action="store_true", help=_("incluye los hallazgos 'info'")
    )
    lint.add_argument("--errors-only", action="store_true", help=_("solo los errores"))
    lint.add_argument("--val", action="store_true", help=_("además, comprueba la sintaxis con VAL"))
    lint.add_argument("--format", choices=["text", "json"], default="text")

    validate = commands.add_parser(
        "validate",
        help=_("valida planes con VAL"),
        description=_(
            "Valida planes con VAL leyendo el veredicto del texto (su código de salida no es "
            "fiable). Con --reference, valida los planes de referencia de colecciones o "
            "datasets."
        ),
    )
    validate.add_argument(
        "files", nargs="*", metavar=_("FICHERO"), help=_("DOMINIO PROBLEMA PLAN [PLAN...]")
    )
    validate.add_argument(
        "--task", help=_("<colección>/<problema> del catálogo en lugar de DOMINIO PROBLEMA")
    )
    validate.add_argument(
        "--reference",
        action="append",
        metavar=_("OBJETIVO"),
        help=_("colección o dataset cuyos planes de referencia validar; repetible"),
    )
    validate.add_argument(
        "-t", "--tolerance", type=float, help=_("tolerancia de VAL (por defecto, 0.01)")
    )
    validate.add_argument(
        "-m",
        "--memory",
        type=int,
        metavar="MB",
        help=_("límite de memoria de VAL (por defecto, el 80 %% de la disponible)"),
    )
    validate.add_argument(
        "-v", "--verbose", action="store_true", help=_("muestra la salida de VAL")
    )

    sources = commands.add_parser("sources", help=_("ficheros originales de las colecciones"))
    sources_commands = sources.add_subparsers(
        dest="sources_command", required=True, metavar=_("ACCIÓN")
    )
    check = sources_commands.add_parser("check", help=_("compara el catálogo con los originales"))
    check.add_argument("collections", nargs="*", metavar=_("COLECCIÓN"))
    diff = sources_commands.add_parser("diff", help=_("diferencias original → catálogo"))
    diff.add_argument("collection", metavar=_("COLECCIÓN"))
    diff.add_argument("files", nargs="*", metavar=_("FICHERO"), help=_("solo estos ficheros"))
    fetch = sources_commands.add_parser("fetch", help=_("trae problemas del origen al catálogo"))
    fetch.add_argument("collection", metavar=_("COLECCIÓN"))
    fetch.add_argument(
        "--problems",
        type=parse_numbers,
        metavar=_("RANGO"),
        help=_("números de problema ('3-20', '1,5'); por defecto, todos los del origen"),
    )
    fetch.add_argument("--overwrite", action="store_true", help=_("sobrescribe los que ya existen"))

    from pddldomains.generators.cli import add_generate_parser

    add_generate_parser(commands)

    trace = commands.add_parser(
        "trace",
        help=_("traza de un plan: sus estados, en JSON"),
        description=_(
            "Ejecuta un plan y escribe en JSON los estados por los que pasa, con las acciones. "
            "Puede quitar información (huecos), estados enteros y añadir ruido, de forma "
            "reproducible. Ver docs/es/trazas.md."
        ),
    )
    trace.add_argument(
        "files", nargs="*", metavar=_("FICHERO"), help=_("DOMINIO PROBLEMA PLAN, o PLAN con --task")
    )
    trace.add_argument(
        "--task",
        help=_(
            "<colección>/<problema> del catálogo en lugar de DOMINIO PROBLEMA "
            "(sin PLAN, el plan de referencia)"
        ),
    )
    trace.add_argument(
        "-o", "--output", type=Path, metavar=_("FICHERO"), help=_("dónde escribir la traza")
    )
    trace.add_argument("--compact", action="store_true", help=_("JSON en una sola línea"))
    degradation = trace.add_argument_group(_("degradación (porcentajes de 0 a 100)"))
    degradation.add_argument(
        "--missing",
        type=_percent,
        default=0.0,
        metavar="%",
        help=_("átomos y valores numéricos de cada estado que pasan a ser desconocidos"),
    )
    degradation.add_argument(
        "--missing-states",
        type=_percent,
        default=0.0,
        metavar="%",
        help=_("estados que faltan enteros"),
    )
    degradation.add_argument(
        "--noise",
        type=_percent,
        default=0.0,
        metavar="%",
        help=_("átomos observados que se invierten y valores numéricos que se alteran"),
    )
    degradation.add_argument(
        "--numeric-noise",
        type=float,
        default=10.0,
        metavar="%",
        help=_("cuánto se altera como mucho un valor numérico con ruido (por defecto, 10)"),
    )
    degradation.add_argument(
        "--seed", type=int, default=0, help=_("semilla de la degradación (por defecto, 0)")
    )
    trace.add_argument(
        "--world",
        choices=["closed", "open"],
        default="closed",
        help=_("closed: no se listan los átomos falsos (por defecto); open: se listan"),
    )
    trace.add_argument(
        "--universe",
        choices=UNIVERSES,
        default="dynamic",
        help=_(
            "átomos de los que se da el valor: dynamic, los de predicados que cambian más los "
            "estáticos ciertos al principio (por defecto); typed, todos los que encajan con los "
            "tipos"
        ),
    )
    trace.add_argument("--planner", help=_("planificador que dio el plan (procedencia)"))
    trace.add_argument("--planner-config", help=_("configuración del planificador (procedencia)"))
    trace.add_argument("--planner-seed", type=int, help=_("semilla del planificador (procedencia)"))
    trace.add_argument(
        "--val", action="store_true", help=_("valida además el plan con VAL y anota su veredicto")
    )
    trace.add_argument(
        "--max-atoms",
        type=int,
        default=MAX_ATOMS,
        metavar="N",
        help=_("átomos posibles como mucho (por defecto, {default})", default=MAX_ATOMS),
    )
    return parser


def _percent(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = -1.0
    if not 0 <= number <= 100:
        raise argparse.ArgumentTypeError(
            _("se esperaba un porcentaje de 0 a 100: '{value}'", value=value)
        )
    return number


# --- Comandos ----------------------------------------------------------------------------


def _catalog(args: argparse.Namespace) -> Catalog:
    return Catalog(args.catalog)


def cmd_list(args: argparse.Namespace) -> int:
    catalog = _catalog(args)
    selection = _selection(args)
    dataset = build_dataset({"select": [selection]}, catalog)
    counts: dict[str, int] = {}
    for entry in dataset.entries:
        counts[entry.task.collection] = counts.get(entry.task.collection, 0) + 1
    analyzer = Analyzer(catalog)
    rows = []
    for collection_id, count in counts.items():
        analysis = analyzer.analyze(catalog.collections[collection_id])
        rows.append((collection_id, count, analysis.level, analysis.tags))
    if args.format == "json":
        data = [
            {"id": i, "problems": n, "level": lvl, "version": LEVELS[lvl - 1].name, "tags": t}
            for i, n, lvl, t in rows
        ]
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif args.format == "ids":
        for row in rows:
            print(row[0])
    else:
        width = max((len(r[0]) for r in rows), default=10)
        print(f"{_('COLECCIÓN'):{width}}  {_('PROBLEMAS'):>9}  {_('NIVEL'):12} {_('TIPOS')}")
        for collection_id, count, level, tags in rows:
            name = f"{level} {LEVELS[level - 1].name}"
            print(f"{collection_id:{width}}  {count:9}  {name:12} {' '.join(tags)}")
        total = sum(r[1] for r in rows)
        print(
            "\n"
            + _(
                "{collections} colecciones, {problems} problemas",
                collections=len(rows),
                problems=total,
            )
        )
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    catalog = _catalog(args)
    collection = catalog.find(args.collection)
    analyzer = Analyzer(catalog)
    analysis = analyzer.analyze(collection)
    analyzer.save()
    info = collection.info
    if args.format == "json":
        from dataclasses import asdict

        print(
            json.dumps(
                {"id": collection.id, "info": info, "analysis": asdict(analysis)},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    print(f"{collection.id} — {localized(info, 'title', collection.name)}")
    if "description" in info:
        print(f"  {localized(info, 'description')}")
    if "authors" in info:
        print("  " + _("Autores: {authors}", authors=localized(info, "authors")))
    origin = info.get("origin", {})
    if origin:
        line = _("Origen: {source}", source=localized(origin, "source"))
        if "repository" in origin:
            line += (
                f" — {origin['repository']} @ {origin.get('commit', '')}, {origin.get('path', '')}"
            )
        print(f"  {line}")
    if "notes" in info:
        print("  " + _("Notas: {notes}", notes=localized(info, "notes")))
    level = LEVELS[analysis.level - 1]
    reasons = level_reasons(frozenset(analysis.used))
    why = " " + _("por {requirements}", requirements=" ".join(reasons)) if reasons else ""
    print(
        "  "
        + _(
            "Dominio: {domain}   Tipos: {tags}",
            domain=analysis.domain_name,
            tags=" ".join(analysis.tags),
        )
    )
    print("  " + _("Nivel: {level}", level=level) + why)
    declared = " ".join(analysis.declared) or _("(ninguno: :strips)")
    used = " ".join(analysis.used) or _("(solo STRIPS)")
    print("  " + _("Requisitos declarados: {requirements}", requirements=declared))
    print("  " + _("Requisitos usados:     {requirements}", requirements=used))
    print(
        "  "
        + _(
            "Operadores: {operators}, predicados: {predicates}, funciones: {functions}",
            operators=analysis.operators,
            predicates=analysis.predicates,
            functions=analysis.functions,
        )
    )
    for errata in info.get("errata", []):
        mark = "*" if errata.get("kind") == "requirements" else "‡"
        files = ", ".join(errata.get("files", []))
        print(
            "  "
            + _(
                "Errata ({mark}) {files}: {description}",
                mark=mark,
                files=files,
                description=localized(errata, "description"),
            )
        )
    for error in analysis.errors:
        print(f"  ERROR: {error}")
    print(
        f"\n  {_('PROBLEMA'):10} {'KB':>7} {_('OBJETOS'):>8} {'INIT':>7} {_('OBJETIVOS'):>9}  "
        f"{_('PLAN')}"
    )
    for task in collection.tasks:
        stats = analysis.task(task.name)
        plan = _("sí") if task.plan else ""
        print(
            f"  {task.name:10} {stats.size / 1024:7.1f} {stats.objects:8} {stats.init:7} "
            f"{stats.goals:9}  {plan}"
        )
    return 0


def cmd_types(args: argparse.Namespace) -> int:
    catalog = _catalog(args)
    analyses = Analyzer(catalog).analyze_all()
    print(f"{_('TIPO'):15} {_('COLECCIONES'):>11} {_('PROBLEMAS'):>9}  {_('DESCRIPCIÓN')}")
    for tag, description in TAGS.items():
        collections = sum(1 for a in analyses.values() if tag in a.tags)
        problems = sum(1 for a in analyses.values() for t in a.tasks if tag in t.tags)
        print(f"{tag:15} {collections:11} {problems:9}  {_(description)}")
    return 0


def cmd_levels(args: argparse.Namespace) -> int:
    catalog = _catalog(args)
    analyses = Analyzer(catalog).analyze_all()
    print(
        f"{_('NIVEL'):14} {_('COLECCIONES'):>11} {_('PROBLEMAS'):>9}  {_('HASTA AQUÍ'):>10}  "
        f"{_('AÑADE')}"
    )
    cumulative = 0
    for level in LEVELS:
        collections = sum(1 for a in analyses.values() if a.level == level.number)
        problems = sum(1 for a in analyses.values() for t in a.tasks if t.level == level.number)
        cumulative += problems
        name = f"{level.number} {level.name}"
        print(f"{name:14} {collections:11} {problems:9}  {cumulative:10}  {_(level.description)}")
    return 0


def cmd_dataset(args: argparse.Namespace) -> int:
    if args.list_definitions:
        from pddldomains.datasets import DATASETS_DIR

        for path in sorted(DATASETS_DIR.glob("*.toml")):
            description = " ".join(localized(load_definition(path), "description").split())
            print(f"{path.stem:22} {description}")
        return 0
    catalog = _catalog(args)
    selection = _selection(args)
    if args.definition:
        path = find_definition(args.definition)
        definition = load_definition(path)
        if selection:  # los filtros de la línea de comandos restringen la definición
            definition = {
                **definition,
                "select": [{**s, **selection} for s in definition.get("select", [])],
            }
        dataset = build_dataset(definition, catalog, name=path.stem)
        if selection:
            dataset = _restrict(dataset, selection, catalog)
    else:
        dataset = build_dataset({"select": [selection]}, catalog, name="selection")
    if args.export:
        written = export(dataset, args.export, link=args.link, force=args.force)
        message = _(
            "{problems} problemas en {groups} grupos: {files} ficheros en {path}",
            problems=len(dataset),
            groups=len(dataset.groups()),
            files=written,
            path=args.export,
        )
        print(message, file=sys.stderr)
        return 0
    relative = catalog.root if args.relative else None
    render = {"lines": to_lines, "csv": to_csv, "json": to_json}[args.format]
    text = render(dataset, relative_to=relative)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(
            _("{problems} problemas en {path}", problems=len(dataset), path=args.output),
            file=sys.stderr,
        )
    else:
        sys.stdout.write(text)
    return 0


def _restrict(dataset: Dataset, selection: dict[str, Any], catalog: Catalog) -> Dataset:
    """Aplica los filtros de la línea de comandos también a los grupos explícitos."""
    allowed = {
        (e.task.collection, e.task.name)
        for e in build_dataset(
            {
                "select": [
                    {
                        k: v
                        for k, v in selection.items()
                        if k not in ("per-collection", "order", "seed")
                    }
                ]
            },
            catalog,
        ).entries
    }
    entries = [e for e in dataset.entries if (e.task.collection, e.task.name) in allowed]
    return Dataset(dataset.name, dataset.description, entries)


def cmd_index(args: argparse.Namespace) -> int:
    catalog = _catalog(args)
    analyses = Analyzer(catalog).analyze_all()
    outdated = 0
    for lang, name in INDEX_FILES.items():
        text = render_index(catalog, analyses, lang)
        path = catalog.root / name
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if args.check:
            if current != text:
                print(
                    _("{path} no está al día: ejecute 'pddldomains index'", path=path),
                    file=sys.stderr,
                )
                outdated += 1
            else:
                print(_("{path} está al día", path=path))
        elif current != text:
            path.write_text(text, encoding="utf-8")
            print(_("{path} actualizado", path=path))
        else:
            print(_("{path} ya estaba al día", path=path))
    return EXIT_FINDINGS if outdated else 0


# --- lint --------------------------------------------------------------------------------


def _lint_targets(args: argparse.Namespace) -> list[tuple[Path, list[Path]]]:
    """Los pares (dominio, problemas) a revisar."""
    if not args.targets:
        return [pair for c in _catalog(args) for pair in _collection_pairs(c)]
    pairs: list[tuple[Path, list[Path]]] = []
    catalog: Catalog | None = None
    for target in args.targets:
        path = Path(target)
        if path.is_dir():
            pairs.extend(_collection_pairs(read_collection(path, path.name)))
        elif path.is_file():
            if is_domain_file(path) and args.domain is None:
                pairs.append((path, []))
            else:
                domain = args.domain or _sibling_domain(path)
                pairs.append((domain, [path]))
        else:
            catalog = catalog or _catalog(args)
            try:
                pairs.extend(_collection_pairs(catalog.find(target)))
            except CatalogError:
                task = catalog.find_task(target)
                pairs.append((task.domain, [task.problem]))
    merged: dict[Path, list[Path]] = {}
    for domain, problems in pairs:
        merged.setdefault(domain, []).extend(p for p in problems if p not in merged.get(domain, []))
    return list(merged.items())


def _collection_pairs(collection: Collection) -> list[tuple[Path, list[Path]]]:
    pairs: dict[Path, list[Path]] = {d: [] for d in collection.domain_files()}
    for task in collection.tasks:
        pairs.setdefault(task.domain, []).append(task.problem)
    return list(pairs.items())


def _sibling_domain(problem: Path) -> Path:
    own = problem.with_name(f"domain-{problem.name}")
    if own.exists():
        return own
    shared = problem.with_name("domain.pddl")
    if shared.exists():
        return shared
    raise CatalogError(_("no se encuentra el dominio de {path}: use --domain", path=problem))


def cmd_lint(args: argparse.Namespace) -> int:
    findings: list[Finding] = []
    pairs = _lint_targets(args)
    for domain_path, problems in pairs:
        domain, domain_findings = lint_domain(domain_path)
        findings.extend(domain_findings)
        for problem in problems:
            if domain is not None:
                findings.extend(lint_problem(problem, domain))
            if args.val:
                findings.extend(_val_findings(domain_path, problem))
        if args.val and not problems:
            findings.extend(_val_findings(domain_path, None))
    if not args.verbose:
        findings = [f for f in findings if f.level != "info"]
    if args.errors_only:
        findings = [f for f in findings if f.level == "error"]
    counts = summarize(findings)
    if args.format == "json":
        data = [
            {
                "file": str(f.path),
                "line": f.line,
                "level": f.level,
                "code": f.code,
                "message": f.message,
            }
            for f in findings
        ]
        print(json.dumps({"summary": counts, "findings": data}, indent=2, ensure_ascii=False))
    else:
        base = Path.cwd()
        for finding in findings:
            print(finding.format(base))
        files = len(pairs) + sum(len(problems) for _domain, problems in pairs)
        summary = _(
            "{files} ficheros revisados: {errors} errores, {warnings} avisos",
            files=files,
            errors=counts["error"],
            warnings=counts["warning"],
        )
        if args.verbose:
            summary += _(", {count} info", count=counts["info"])
        print("\n" + summary, file=sys.stderr)
    return EXIT_FINDINGS if counts["error"] else 0


def _val_findings(domain: Path, problem: Path | None) -> list[Finding]:
    from pddldomains.val import parse_check

    result = parse_check(domain, problem)
    target = problem or domain
    return [
        Finding(message.file or target, message.line, message.level, "val-parser", message.text)
        for message in result.messages
    ]


# --- validate ----------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    from pddldomains.val import validate

    jobs: list[tuple[Path, Path, Path]] = []
    if args.reference:
        catalog = _catalog(args)
        for target in args.reference:
            jobs.extend(
                (t.domain, t.problem, t.plan)
                for t in _reference_tasks(catalog, target)
                if t.plan is not None
            )
    if args.task:
        task = _catalog(args).find_task(args.task)
        if not args.files:
            raise CatalogError(_("con --task hay que dar al menos un plan"))
        jobs.extend((task.domain, task.problem, Path(plan)) for plan in args.files)
    elif args.files:
        if len(args.files) < 3:
            raise CatalogError(_("se esperaba DOMINIO PROBLEMA PLAN [PLAN...]"))
        domain, problem, *plans = (Path(f) for f in args.files)
        jobs.extend((domain, problem, plan) for plan in plans)
    if not jobs:
        raise CatalogError(
            _("no hay nada que validar (dé DOMINIO PROBLEMA PLAN, --task o --reference)")
        )
    verdicts = {"valid": _("válido"), "invalid": _("NO VÁLIDO"), "error": "ERROR"}
    failures = 0
    for domain, problem, plan in jobs:
        result = validate(
            domain,
            problem,
            plan,
            tolerance=args.tolerance,
            memory_mb=args.memory,
            verbose=args.verbose,
        )
        value = " " + _("(valor {value:g})", value=result.value) if result.value is not None else ""
        detail = "" if result.valid else f": {result.message}"
        print(f"{plan}: {verdicts[result.verdict]}{value}{detail}")
        if result.violated:
            print("  " + _("preferencias violadas: {names}", names=" ".join(result.violated)))
        if args.verbose:
            print(result.output)
        failures += not result.valid
    if len(jobs) > 1:
        message = _(
            "{valid} de {total} planes válidos", valid=len(jobs) - failures, total=len(jobs)
        )
        print("\n" + message, file=sys.stderr)
    return EXIT_FINDINGS if failures else 0


def _reference_tasks(catalog: Catalog, target: str) -> list[Task]:
    try:
        collection = catalog.find(target)
        tasks = collection.tasks
    except CatalogError:
        dataset = build_dataset(load_definition(find_definition(target)), catalog)
        tasks = list(dataset)
    return [t for t in tasks if t.plan is not None]


# --- trace -------------------------------------------------------------------------------


def cmd_trace(args: argparse.Namespace) -> int:
    from pddldomains.traces import (
        Degradation,
        Provenance,
        TraceError,
        generate_trace,
        write_trace,
    )

    catalog = None
    if args.task:
        catalog = _catalog(args)
        task = catalog.find_task(args.task)
        if len(args.files) > 1:
            raise CatalogError(_("con --task se espera como mucho un plan"))
        if args.files:
            plan = Path(args.files[0])
        elif task.plan is not None:
            plan = task.plan
        else:
            raise CatalogError(_("'{task}' no tiene plan de referencia: dé el plan", task=task.id))
        domain, problem = task.domain, task.problem
    elif len(args.files) == 3:
        domain, problem, plan = (Path(f) for f in args.files)
        if args.catalog:
            catalog = _catalog(args)
    else:
        raise CatalogError(_("se esperaba DOMINIO PROBLEMA PLAN, o --task <colección>/<problema>"))
    degradation = Degradation(
        missing=args.missing,
        missing_states=args.missing_states,
        noise=args.noise,
        numeric_noise=args.numeric_noise,
        seed=args.seed,
    )
    provenance = Provenance(args.planner, args.planner_config, args.planner_seed)
    try:
        trace = generate_trace(
            domain,
            problem,
            plan,
            degradation=degradation,
            world=args.world,
            universe=args.universe,
            provenance=provenance,
            max_atoms=args.max_atoms,
            validate_with_val=args.val,
            catalog=catalog,
        )
    except TraceError as error:
        print(f"error: {plan}: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as stream:
            write_trace(trace, stream, compact=args.compact)
    else:
        write_trace(trace, sys.stdout, compact=args.compact)
    execution = trace["execution"]
    if not execution["goal_reached"]:
        print(_("aviso: el plan no alcanza el objetivo"), file=sys.stderr)
    if execution["val"] not in (None, "valid"):
        print(
            _("aviso: VAL no da el plan por válido ({verdict})", verdict=execution["val"]),
            file=sys.stderr,
        )
    return 0 if execution["goal_reached"] and execution["val"] in (None, "valid") else EXIT_FINDINGS


# --- sources -----------------------------------------------------------------------------


def cmd_sources(args: argparse.Namespace) -> int:
    from pddldomains import sources

    catalog = _catalog(args)
    if args.sources_command == "check":
        targets = [catalog.find(c) for c in args.collections] if args.collections else list(catalog)
        problems = 0
        for collection in targets:
            if sources.Origin.from_info(collection.info) is None:
                print(_("{collection}: colección propia, sin origen", collection=collection.id))
                continue
            results = sources.compare(collection)
            same = sum(r.status == "same" for r in results)
            changed = [r for r in results if r.status == "changed"]
            missing = [r.name for r in results if r.status == "missing"]
            undocumented = [r.name for r in changed if not r.documented]
            line = _(
                "{collection}: {same} iguales, {changed} corregidos",
                collection=collection.id,
                same=same,
                changed=len(changed),
            )
            if undocumented:
                line += _(", SIN DOCUMENTAR: {files}", files=" ".join(undocumented))
            if missing:
                line += _(", SIN ORIGINAL: {files}", files=" ".join(missing))
            print(line)
            problems += bool(undocumented or missing)
        return EXIT_FINDINGS if problems else 0
    collection = catalog.find(args.collection)
    if args.sources_command == "diff":
        for result in sources.compare(collection):
            if args.files and result.name not in args.files:
                continue
            if result.status == "changed":
                sys.stdout.write(result.diff)
            elif result.status == "missing":
                print("# " + _("{name}: no está en el origen", name=result.name))
        return 0
    numbers = args.problems or sources.available_problems(collection)
    written = sources.fetch_problems(collection, numbers, overwrite=args.overwrite)
    for path in written:
        print(f"  {path.relative_to(catalog.root)}")
    print(
        _("{count} ficheros nuevos en {collection}", count=len(written), collection=collection.id),
        file=sys.stderr,
    )
    if written:
        fresh = read_collection(collection.path, collection.id)
        domains: dict[Path, Domain | None] = {}
        findings: list[Finding] = []
        for task in fresh.tasks:
            if task.problem not in written and task.domain not in written:
                continue
            if task.domain not in domains:
                domains[task.domain], found = lint_domain(task.domain)
                findings.extend(found)
            domain = domains[task.domain]
            if domain is not None:
                findings.extend(lint_problem(task.problem, domain))
        for finding in findings:
            if finding.level != "info":
                print(finding.format(Path.cwd()))
        counts = summarize(findings)
        message = _(
            "Revisión de lo nuevo: {errors} errores, {warnings} avisos (las correcciones hay que "
            "documentarlas en info.toml)",
            errors=counts["error"],
            warnings=counts["warning"],
        )
        print(message, file=sys.stderr)
    return 0


_COMMANDS = {
    "list": cmd_list,
    "info": cmd_info,
    "types": cmd_types,
    "levels": cmd_levels,
    "dataset": cmd_dataset,
    "index": cmd_index,
    "lint": cmd_lint,
    "validate": cmd_validate,
    "sources": cmd_sources,
    "trace": cmd_trace,
}


def _language_option(argv: Sequence[str]) -> str | None:
    """El valor de ``--lang`` en la línea de comandos, si lo hay (antes de construir la ayuda,
    que sale en ese idioma)."""
    for index, argument in enumerate(argv):
        if argument == "--lang" and index + 1 < len(argv):
            return argv[index + 1]
        if argument.startswith("--lang="):
            return argument.split("=", 1)[1]
    return None


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de la CLI."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    chosen = _language_option(arguments)
    if chosen in LANGUAGES:
        os.environ[ENV_VAR] = chosen
    parser = build_parser()
    args = parser.parse_args(arguments)
    if args.command == "generate":
        from pddldomains.generators.cli import cmd_generate

        handler = cmd_generate
    else:
        handler = _COMMANDS[args.command]
    try:
        return handler(args)
    except (CatalogError, DatasetError, SourceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
