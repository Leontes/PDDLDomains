"""Idioma de los mensajes: inglés o español.

Los textos se escriben en español en el código y pasan por :func:`_`, que los traduce al
inglés con la tabla de :mod:`pddldomains.translations` si el idioma es el inglés. Los
mensajes con valores son plantillas de :meth:`str.format`::

    _("predicado '{name}' sin declarar", name=head)

El idioma es el inglés, salvo que diga otra cosa la variable de entorno
``PDDLDOMAINS_LANG`` (``es`` o ``en``; también la opción ``--lang`` de la CLI) o, si no está,
la configuración regional (``LANGUAGE``, ``LC_ALL``, ``LC_MESSAGES`` o ``LANG``, en ese orden):
un valor que empieza por ``es`` es el español.

``tests/test_i18n.py`` comprueba que todos los textos tienen traducción con los mismos
marcadores.
"""

import os
from collections.abc import Mapping
from typing import Any

#: Variable de entorno con el idioma (``es`` o ``en``).
ENV_VAR = "PDDLDOMAINS_LANG"
#: Idiomas admitidos.
LANGUAGES = ("en", "es")
_LOCALE_VARS = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")


def language() -> str:
    """El idioma actual: ``"en"`` o ``"es"``."""
    for var in (ENV_VAR, *_LOCALE_VARS):
        value = os.environ.get(var, "").strip().lower()
        if value:
            return "es" if value.startswith("es") else "en"
    return "en"


def translate(lang: str, text: str, **values: Any) -> str:
    """Traduce ``text`` (en español) al idioma ``lang`` y le pone los ``values``."""
    if lang == "en":
        from pddldomains.translations import EN

        text = EN.get(text, text)
    return text.format(**values) if values else text


def _(text: str, **values: Any) -> str:
    """Traduce ``text`` (en español) al idioma actual y le pone los ``values``."""
    return translate(language(), text, **values)


def localized(
    table: Mapping[str, Any], key: str, default: str = "", lang: str | None = None
) -> str:
    """El campo ``key`` de una ficha o una definición en el idioma ``lang`` (o el actual).

    En inglés se usa ``<key>-en`` si existe (``description-en``); si no, ``key``.
    """
    if (lang or language()) == "en" and f"{key}-en" in table:
        return str(table[f"{key}-en"])
    return str(table.get(key, default))
