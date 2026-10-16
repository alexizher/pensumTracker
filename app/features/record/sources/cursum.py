"""Parsers puros de los JSON de Cursum (programas y plan de estudios)."""

import logging
from typing import Any, cast

from app.features.record.sources.models import CursumProgram, CursumSubject

log = logging.getLogger(__name__)


def parse_program(programs: object, program_code: str) -> CursumProgram | None:
    for p in cast(list[dict[str, Any]], programs):
        if str(p["codigo"]) == program_code:
            raw = p.get("versiones", "")
            return CursumProgram(
                code=program_code,
                version_actual=p.get("versionActual", 0),
                versiones=[int(v) for v in raw.split(",") if v.strip().isdigit()],
                total_credits=p.get("creditosGrado", 0),
            )
    return None


def parse_curriculum(items: object) -> list[CursumSubject]:
    if not isinstance(items, list):
        log.error(
            "parse_curriculum: cursum no devolvió lista, tipo=%s contenido=%r",
            type(items).__name__,
            str(items)[:200],
        )
        return []
    return [_build_subject(item) for item in items]


def _build_subject(item: dict) -> CursumSubject:
    reqs = item.get("requisitos", [])
    return CursumSubject(
        code=str(item["materia"]),
        name=item["nombreMateria"],
        credits=item["creditos"],
        level=item["nivel"],
        obligatoria=item.get("tipoMateria", "OBLIGATORIA") == "OBLIGATORIA",
        elective_bank=item.get("nombreBancoElectiva", "").strip() or None,
        prerequisites=[str(r["materiaRequisito"]) for r in reqs if r["tipoRequisito"] == "PRERREQ"],
        corequisites=[str(r["materiaRequisito"]) for r in reqs if r["tipoRequisito"] == "CORREQ"],
    )
