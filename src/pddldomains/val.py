"""VAL (https://github.com/KCL-Planning/VAL): validar planes y comprobar la sintaxis.

``scripts/build_val.sh`` compila ``Validate`` y ``Parser`` en ``tools/bin/``; también se
buscan en la variable de entorno ``VAL_BIN`` (el directorio de los ejecutables) y en el
``PATH``.

**El código de salida de VAL no es fiable** (ver ``docs/es/val.md``): sale con 0 cuando no
puede leer el plan ("Bad plan file!", también si no existe) y con 1 cuando el plan no es
válido. Por eso el veredicto se lee del texto:

* ``valid``: VAL dice "Plan valid";
* ``invalid``: el plan se ha leído y no es válido (código 1);
* ``error``: VAL no ha dado veredicto (plan ilegible, fallo de segmentación, sin memoria,
  sin tiempo). Un error no dice nada del plan.

VAL puede necesitar mucha memoria con planes grandes (2,3 GB con storage p20 de la IPC
2006), así que se ejecuta con un límite duro de memoria virtual (``RLIMIT_AS``): por
defecto, el 80 % de la memoria disponible.
"""

import os
import re
import resource
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pddldomains.catalog import ROOT
from pddldomains.i18n import _

#: Directorio donde ``scripts/build_val.sh`` deja los ejecutables.
VAL_BIN_DIR = ROOT / "tools" / "bin"
#: Variable de entorno con otro directorio de ejecutables de VAL.
ENV_VAR = "VAL_BIN"
#: Tolerancia por defecto de VAL (``-t``): sucesos más cercanos cuentan como simultáneos.
DEFAULT_TOLERANCE = 0.01


def find_tool(name: str) -> Path | None:
    """Un ejecutable de VAL (``Validate`` o ``Parser``): ``$VAL_BIN``, ``tools/bin`` o ``PATH``."""
    directories = [Path(os.environ[ENV_VAR])] if ENV_VAR in os.environ else []
    directories.append(VAL_BIN_DIR)
    for directory in directories:
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    found = shutil.which(name)
    return Path(found) if found else None


def available_memory_mb() -> int:
    """La memoria disponible en MB (``MemAvailable`` de ``/proc/meminfo``)."""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 4096


def default_memory_mb() -> int:
    """El límite de memoria por defecto: el 80 % de la disponible."""
    return int(available_memory_mb() * 0.8)


@dataclass
class ValResult:
    """El resultado de validar un plan.

    Attributes:
        verdict: ``"valid"``, ``"invalid"`` o ``"error"``.
        message: resumen en una línea (el motivo, si no es válido).
        value: el valor del plan según la métrica ("Final value"), si VAL lo da.
        violated: preferencias violadas, si las hay.
        exit_code: código de salida de VAL.
        output: salida completa de VAL.
    """

    verdict: str
    message: str
    value: float | None = None
    violated: list[str] = field(default_factory=list)
    exit_code: int | None = None
    output: str = ""

    @property
    def valid(self) -> bool:
        """Si el plan es válido."""
        return self.verdict == "valid"


#: Motivos de un plan inválido, por orden de preferencia para el resumen.
_INVALID_REASONS = (
    "Goal not satisfied",
    "Plan failed to execute",
    "Mutex violation",
    "Unsatisfied precondition",
    "Invariant",
    "Failure to satisfy",
    "Plan invalid",
)


def parse_output(output: str, exit_code: int) -> ValResult:
    """Lee el veredicto de la salida de ``Validate``."""
    value_match = re.search(r"Final value: (\S+)", output)
    value = None
    if value_match:
        try:
            value = float(value_match.group(1))
        except ValueError:
            value = None
    violated = sorted(set(re.findall(r"Preference (\S+) violated", output, re.IGNORECASE)))
    if re.search(r"^Plan valid", output, re.MULTILINE):
        return ValResult("valid", _("plan válido"), value, violated, exit_code, output)
    if "Bad plan file" in output or "Bad plan description" in output:
        return ValResult(
            "error", _("VAL no ha podido leer el plan"), value, violated, exit_code, output
        )
    if "bad_alloc" in output:
        return ValResult("error", _("VAL se ha quedado sin memoria"), None, [], exit_code, output)
    if exit_code < 0 or exit_code == 139:
        return ValResult(
            "error",
            _("VAL ha fallado (fallo de segmentación); ver docs/es/val.md"),
            None,
            [],
            exit_code,
            output,
        )
    if exit_code == 1 or "Plan failed" in output or "Goal not satisfied" in output:
        reason = next((r for r in _INVALID_REASONS if r in output), _("plan no válido"))
        detail = _first_problem_line(output)
        message = f"{reason}: {detail}" if detail else reason
        return ValResult("invalid", message, value, violated, exit_code, output)
    last = output.strip().splitlines()[-1] if output.strip() else _("sin salida")
    message = _("VAL terminó con código {code}: {last}", code=exit_code, last=last)
    return ValResult("error", message, value, violated, exit_code, output)


def _first_problem_line(output: str) -> str:
    """La primera línea que explica el fallo (las de "Plan Repair Advice")."""
    lines = output.splitlines()
    for index, line in enumerate(lines):
        if "Plan Repair Advice" in line:
            for detail in lines[index + 1 :]:
                if detail.strip():
                    return detail.strip()
    return ""


def _limit_memory(megabytes: int) -> None:
    limit = megabytes * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def validate(
    domain: Path,
    problem: Path,
    plan: Path,
    *,
    tolerance: float | None = None,
    memory_mb: int | None = None,
    timeout: float | None = 300,
    verbose: bool = False,
) -> ValResult:
    """Valida ``plan`` con VAL (``Validate``)."""
    validate_bin = find_tool("Validate")
    if validate_bin is None:
        return ValResult("error", _("VAL no está compilado (scripts/build_val.sh)"))
    if not plan.exists():
        return ValResult("error", _("no existe el plan {path}", path=plan))
    command = [str(validate_bin)]
    if verbose:
        command.append("-v")
    if tolerance is not None:
        command += ["-t", str(tolerance)]
    command += [str(domain), str(problem), str(plan)]
    memory = memory_mb or default_memory_mb()
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
            preexec_fn=lambda: _limit_memory(memory),
        )
    except subprocess.TimeoutExpired:
        return ValResult("error", _("VAL no ha terminado en {seconds} s", seconds=timeout))
    return parse_output(process.stdout + process.stderr, process.returncode)


@dataclass(frozen=True)
class ValMessage:
    """Un mensaje de ``Parser`` de VAL.

    Attributes:
        level: ``"error"`` o ``"aviso"``.
        file: fichero al que se refiere, si lo dice.
        line: línea, si la dice (0 si no).
        text: el mensaje.
    """

    level: str
    file: Path | None
    line: int
    text: str


@dataclass
class ParseResult:
    """El resultado de comprobar un dominio y un problema con ``Parser`` de VAL.

    Attributes:
        ok: si VAL los ha leído sin errores.
        errors: número de errores que da VAL.
        warnings: número de avisos que da VAL.
        messages: los mensajes de VAL.
        exit_code: código de salida.
    """

    ok: bool
    errors: int
    warnings: int
    messages: list[ValMessage]
    exit_code: int | None


_PARSER_MESSAGE = re.compile(
    r"^(?P<file>\S+): line: (?P<line>\d+): (?P<kind>Warning|Error|Fatal Error)\b:?\s*(?P<text>.*)$",
    re.MULTILINE,
)


def parse_check(
    domain: Path, problem: Path | None = None, *, memory_mb: int | None = None, timeout: float = 120
) -> ParseResult:
    """Comprueba la sintaxis con ``Parser`` de VAL (que no necesita plan)."""
    parser_bin = find_tool("Parser")
    if parser_bin is None:
        message = ValMessage("error", None, 0, _("VAL no está compilado (scripts/build_val.sh)"))
        return ParseResult(False, 1, 0, [message], None)
    command = [str(parser_bin), str(domain)] + ([str(problem)] if problem else [])
    memory = memory_mb or default_memory_mb()
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
            preexec_fn=lambda: _limit_memory(memory),
        )
    except subprocess.TimeoutExpired:
        message = ValMessage(
            "error", None, 0, _("VAL no ha terminado en {seconds} s", seconds=timeout)
        )
        return ParseResult(False, 1, 0, [message], None)
    output = process.stdout + process.stderr
    counts = re.search(r"Errors:\s*(\d+),\s*warnings:\s*(\d+)", output)
    errors = int(counts.group(1)) if counts else 0
    warnings = int(counts.group(2)) if counts else 0
    messages = [
        ValMessage(
            "aviso" if match["kind"] == "Warning" else "error",
            Path(match["file"]),
            int(match["line"]),
            match["text"].strip(),
        )
        for match in _PARSER_MESSAGE.finditer(output)
    ]
    if not counts:
        text = _(
            "VAL terminó con código {code} sin leer los ficheros (ver docs/es/val.md)",
            code=process.returncode,
        )
        messages.append(ValMessage("error", None, 0, text))
        errors = max(errors, 1)
    return ParseResult(errors == 0, errors, warnings, messages, process.returncode)
