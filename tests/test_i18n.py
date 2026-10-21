"""Idiomas: todo texto tiene traducción al inglés, con los mismos marcadores.

Los textos del código están en español y se traducen con la tabla ``EN`` de
``pddldomains/translations.py``. Estos tests fallan si un texto nuevo no tiene traducción,
si los marcadores ``{...}`` no coinciden, si sobra alguna traducción o si una ficha o una
definición de dataset no tiene su versión en inglés.
"""

import ast
import string
import tomllib
from pathlib import Path

import pytest

from pddldomains.catalog import Catalog
from pddldomains.cli import main
from pddldomains.datasets import DATASETS_DIR
from pddldomains.features import LEVELS, TAGS
from pddldomains.generators import GENERATORS
from pddldomains.generators.cli import _ORIGIN_LABELS
from pddldomains.i18n import _, language, localized
from pddldomains.lint import _LEVEL_LABELS
from pddldomains.translations import EN

SOURCE = Path(__file__).resolve().parent.parent / "src" / "pddldomains"


def literal_texts() -> dict[str, str]:
    """Los textos literales que se traducen en el código, con dónde aparecen.

    Son el primer argumento de ``_()`` (y de ``t()`` en ``index.py``) y el segundo de
    ``translate()``.
    """
    texts: dict[str, str] = {}
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            name = node.func.id
            if name == "_" or (name == "t" and path.name == "index.py"):
                argument = node.args[0] if node.args else None
            elif name == "translate":
                argument = node.args[1] if len(node.args) > 1 else None
            else:
                continue
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                texts.setdefault(argument.value, f"{path.name}:{node.lineno}")
            elif isinstance(argument, ast.JoinedStr):
                pytest.fail(f"{path.name}:{node.lineno}: f-string en una traducción")
    return texts


def data_texts() -> set[str]:
    """Los textos de datos que se traducen al mostrarlos."""
    texts = set(TAGS.values()) | {level.description for level in LEVELS}
    texts |= set(_LEVEL_LABELS.values()) - {"error", "info"}
    texts |= set(_ORIGIN_LABELS.values())
    for generator in GENERATORS.values():
        texts.add(generator.description)
        texts.update(param.help for param in generator.params)
        if generator.explanation():
            texts.add(generator.explanation())
    return texts


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_text_has_a_translation() -> None:
    missing = {text: where for text, where in literal_texts().items() if text not in EN}
    missing.update({text: "datos" for text in data_texts() if text not in EN})
    assert not missing, "\n".join(f"{where}: {text!r}" for text, where in missing.items())


def test_translations_keep_the_placeholders() -> None:
    wrong = [es for es, en in EN.items() if fields(es) != fields(en)]
    assert not wrong, wrong


def test_no_stale_translations() -> None:
    used = set(literal_texts()) | data_texts()
    stale = sorted(set(EN) - used)
    assert not stale, stale


def test_language_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("PDDLDOMAINS_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    assert language() == "en"
    monkeypatch.setenv("LANG", "es_ES.UTF-8")
    assert language() == "es"
    monkeypatch.setenv("LANG", "C.UTF-8")
    assert language() == "en"
    monkeypatch.setenv("PDDLDOMAINS_LANG", "es")
    assert language() == "es"
    assert _("{problems} problemas en {path}", problems=3, path="x") == "3 problemas en x"
    monkeypatch.setenv("PDDLDOMAINS_LANG", "en")
    assert _("{problems} problemas en {path}", problems=3, path="x") == "3 problems in x"


def test_localized_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    card = {"description": "Un robot", "description-en": "A robot"}
    assert localized(card, "description") == "A robot"
    assert localized(card, "description", lang="es") == "Un robot"
    monkeypatch.setenv("PDDLDOMAINS_LANG", "es")
    assert localized(card, "description") == "Un robot"
    assert (
        localized({"description": "Solo en español"}, "description", lang="en") == "Solo en español"
    )


def test_every_card_has_english_fields(catalog: Catalog) -> None:
    for collection in catalog:
        info = collection.info
        assert "description-en" in info, collection.id
        assert ("notes" in info) == ("notes-en" in info), collection.id
        for errata in info.get("errata", []):
            assert "description-en" in errata, collection.id


def test_every_dataset_definition_has_an_english_description() -> None:
    for path in DATASETS_DIR.glob("*.toml"):
        assert "description-en" in tomllib.loads(path.read_text()), path.name


def test_cli_in_both_languages(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info", "floor-tile-sequential-satisficing"]) == 0
    english = capsys.readouterr().out
    assert "Level: 3 (PDDL 2.1)" in english and "Robots painting the tiles" in english
    assert main(["--lang", "es", "info", "floor-tile-sequential-satisficing"]) == 0
    spanish = capsys.readouterr().out
    assert "Nivel: 3 (PDDL 2.1)" in spanish and "Robots que pintan las baldosas" in spanish
