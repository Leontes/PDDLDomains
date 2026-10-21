"""Lectura de S-expresiones, la sintaxis de PDDL.

PDDL no distingue mayúsculas de minúsculas, así que los átomos se pasan a minúsculas. Los
comentarios (``;`` hasta el final de la línea) se descartan.

Las listas son :class:`SList`, que recuerdan dónde empiezan en el texto para poder dar el
número de línea en los mensajes (:class:`LineIndex`); los átomos son ``str``.
"""

import re
from bisect import bisect_right

from pddldomains.i18n import _

_TOKEN = re.compile(r";[^\n]*|\(|\)|[^\s();]+")
_NUMBER = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")


class SList(list["SExpr"]):
    """Lista de una S-expresión con la posición (en caracteres) de su paréntesis de apertura."""

    __slots__ = ("offset",)

    def __init__(self, offset: int) -> None:
        super().__init__()
        self.offset = offset


type SExpr = str | SList


class PDDLSyntaxError(Exception):
    """Error de sintaxis (paréntesis desequilibrados) en la posición ``offset``."""

    def __init__(self, message: str, offset: int) -> None:
        super().__init__(message)
        self.offset = offset


def parse(text: str) -> list[SExpr]:
    """Lee todas las S-expresiones de primer nivel de ``text``."""
    top: list[SExpr] = []
    stack: list[SList] = []
    current: list[SExpr] = top
    for match in _TOKEN.finditer(text):
        token = match.group()
        if token == "(":
            node = SList(match.start())
            current.append(node)
            stack.append(node)
            current = node
        elif token == ")":
            if not stack:
                raise PDDLSyntaxError(_("paréntesis de cierre sin abrir"), match.start())
            stack.pop()
            current = stack[-1] if stack else top
        elif token[0] != ";":
            current.append(token.lower())
    if stack:
        raise PDDLSyntaxError(_("paréntesis sin cerrar"), stack[-1].offset)
    return top


def is_number(token: SExpr) -> bool:
    """Indica si ``token`` es un número literal."""
    return isinstance(token, str) and _NUMBER.fullmatch(token) is not None


def to_text(node: SExpr, limit: int = 80) -> str:
    """Escribe ``node`` en una línea, recortada a ``limit`` caracteres, para los mensajes."""
    text = node if isinstance(node, str) else "(" + " ".join(to_text(n, 0) for n in node) + ")"
    return text if limit <= 0 or len(text) <= limit else text[: limit - 1] + "…"


class LineIndex:
    """Convierte posiciones de un texto en números de línea (desde 1)."""

    def __init__(self, text: str) -> None:
        self._starts = [0, *(m.end() for m in re.finditer("\n", text))]

    def line(self, offset: int) -> int:
        """Línea en la que está la posición ``offset``."""
        return bisect_right(self._starts, offset)
