"""El índice del catálogo, generado a partir de las fichas y del análisis, en inglés
(``dominios/INDEX.md``) y en español (``dominios/INDICE.md``).

Se regenera con ``pddldomains index``; ``pddldomains index --check`` (y los tests) avisan si
no está al día.
"""

from collections import Counter
from typing import Any

from pddldomains.analysis import CollectionAnalysis
from pddldomains.catalog import Catalog
from pddldomains.features import LEVELS, TAGS
from pddldomains.i18n import localized, translate

#: Fichero del índice en cada idioma.
INDEX_FILES = {"en": "INDEX.md", "es": "INDICE.md"}


def render_index(catalog: Catalog, analyses: dict[str, CollectionAnalysis], lang: str) -> str:
    """El texto del índice en el idioma ``lang``."""

    def t(text: str, **values: Any) -> str:
        return translate(lang, text, **values)

    other = "es" if lang == "en" else "en"
    docs = "docs/en/catalog.md" if lang == "en" else "docs/es/catalogo.md"
    collections = list(catalog)
    problems = sum(len(c.tasks) for c in collections)
    plans = sum(1 for c in collections for task in c.tasks if task.plan is not None)
    lines = [
        "# " + t("Índice del catálogo"),
        "",
        "<!-- " + t("Generado con `pddldomains index`: no editar a mano.") + " -->",
        "",
        # El enlace al otro índice va en el idioma de ese índice.
        f"[Versión en español]({INDEX_FILES[other]})"
        if lang == "en"
        else f"[English version]({INDEX_FILES[other]})",
        "",
        t(
            "{collections} colecciones, {problems} problemas y {plans} planes de referencia.",
            collections=len(collections),
            problems=problems,
            plans=plans,
        ),
        t(
            "Los tipos se deducen de lo que usa cada dominio con sus problemas (no de lo que "
            "declaran); ver `pddldomains types` y `{docs}`. Las erratas corregidas están en la "
            "ficha (`info.toml`) de cada colección.",
            docs=docs,
        ),
        "",
        "## " + t("Por tipo"),
        "",
        "| "
        + t("Tipo")
        + " | "
        + t("Colecciones")
        + " | "
        + t("Problemas")
        + " | "
        + t("Qué es")
        + " |",
        "|------|------------:|----------:|--------|",
    ]
    by_tag: Counter[str] = Counter()
    problems_by_tag: Counter[str] = Counter()
    for collection in collections:
        analysis = analyses[collection.id]
        for tag in analysis.tags:
            by_tag[tag] += 1
        for task in analysis.tasks:
            for tag in task.tags:
                problems_by_tag[tag] += 1
    for tag, description in TAGS.items():
        if by_tag[tag]:
            lines.append(f"| `{tag}` | {by_tag[tag]} | {problems_by_tag[tag]} | {t(description)} |")
    lines += [
        "",
        "## " + t("Por versión de PDDL"),
        "",
        t(
            "Cada colección está en el nivel más alto de lo que usa (ver `pddldomains levels`). "
            "Un planificador que llega al nivel N tiene que poder con los niveles 1 a N: "
            "`pddldomains dataset --max-level N`."
        ),
        "",
        "| "
        + " | ".join(
            (
                t("Nivel"),
                t("Versión"),
                t("Añade"),
                t("Colecciones"),
                t("Problemas"),
                t("Hasta aquí"),
            )
        )
        + " |",
        "|------:|---------|-------|------------:|----------:|-----------:|",
    ]
    cumulative = 0
    for level in LEVELS:
        members = [c for c in collections if analyses[c.id].level == level.number]
        in_level = sum(
            1 for c in collections for task in analyses[c.id].tasks if task.level == level.number
        )
        cumulative += in_level
        lines.append(
            f"| {level.number} | {level.name} | {t(level.description)} | {len(members)} | "
            f"{in_level} | {cumulative} |"
        )
    for level in LEVELS:
        members = [c for c in collections if analyses[c.id].level == level.number]
        if members:
            links = ", ".join(f"[{c.id}]({c.id}/info.toml)" for c in members)
            lines += ["", f"**{level.number} · {level.name}**: {links}"]
    origins: dict[str, list[str]] = {}
    for collection in collections:
        origins.setdefault(collection.origin, []).append(collection.id)
    header = (
        t("Colección"),
        t("Tipos"),
        t("Nivel"),
        t("Problemas"),
        t("Erratas"),
        t("Descripción"),
    )
    for origin, ids in origins.items():
        lines += [
            "",
            f"## {origin}",
            "",
            "| " + " | ".join(header) + " |",
            "|-----------|-------|-------|----------:|--------:|-------------|",
        ]
        for collection_id in ids:
            collection = catalog.collections[collection_id]
            analysis = analyses[collection_id]
            count = str(len(collection.tasks))
            with_plans = sum(1 for task in collection.tasks if task.plan is not None)
            if with_plans:
                count += " " + t("({count} con plan)", count=with_plans)
            errata = len(collection.info.get("errata", []))
            description = localized(collection.info, "description", lang=lang).replace("|", "\\|")
            link = f"[{collection.name}]({collection_id}/info.toml)"
            tags = " ".join(f"`{tag}`" for tag in analysis.tags)
            version = f"{analysis.level} ({LEVELS[analysis.level - 1].name})"
            lines.append(
                f"| {link} | {tags} | {version} | {count} | {errata or ''} | {description} |"
            )
    return "\n".join(lines) + "\n"
