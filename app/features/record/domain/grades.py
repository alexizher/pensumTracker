"""Regla de nota aprobatoria y unión de materias aprobadas entre semestres."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

PASSING_GRADE: Final = 3.0

# Notas textuales que indican materia aprobada sin nota numérica
# (típico de materias de 0 créditos: Formación Ciudadana, validaciones, etc.).
PASSING_TEXT: Final = frozenset(
    {"APROBADA", "APROBADO", "VALIDADA", "VALIDADO", "SUFICIENTE", "CUMPLE"}
)


@dataclass(frozen=True)
class PassedSubject:
    code: str
    name: str
    grade: float | None


def parse_grade(raw: str) -> float | None:
    raw = raw.strip()
    if raw.startswith("."):
        raw = "0" + raw
    try:
        return float(raw)
    except ValueError:
        return None


def passed_subject(code: str, name: str, raw_grade: str) -> PassedSubject | None:
    grade = parse_grade(raw_grade)
    if grade is not None:
        # Nota numérica: aprobada solo si alcanza el mínimo.
        if grade >= PASSING_GRADE:
            return PassedSubject(code, name, grade)
    elif raw_grade.upper() in PASSING_TEXT:
        # Aprobada sin nota numérica (p.ej. materias de 0 créditos).
        return PassedSubject(code, name, None)
    return None


def merge_passed(semesters: Iterable[Iterable[PassedSubject]]) -> dict[str, PassedSubject]:
    """Une los semestres en orden; un código repetido queda con el último."""
    merged: dict[str, PassedSubject] = {}
    for semester in semesters:
        for subject in semester:
            merged[subject.code] = subject
    return merged
