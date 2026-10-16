"""Parsers puros de la historia académica (tsone, selector de programa y semestres)."""

import logging
import re

from bs4 import BeautifulSoup, Tag

from app.features.record.sources.models import GradeRow, ProgramOption

log = logging.getLogger(__name__)


def _attr(tag: Tag, name: str) -> str:
    value = tag.get(name)
    if value is None:
        return ""
    return value if isinstance(value, str) else " ".join(value)


def parse_program_selector(html: str, program_code: str) -> ProgramOption | None:
    soup = BeautifulSoup(html, "lxml")
    option = soup.find("option", {"value": program_code})
    if not isinstance(option, Tag):
        log.warning(
            "parse_program_selector: programa %s no encontrado en el selector", program_code
        )
        return None
    if not soup.find("form", {"id": "form2"}):
        log.warning("parse_program_selector: form2 no encontrado")
        return None
    # Versión del pensum en la que el estudiante está matriculado para este programa.
    try:
        version = int(_attr(option, "data-version") or 0) or None
    except ValueError:
        version = None
    form_data: dict[str, str] = {
        "facultad": _attr(option, "data-facultad"),
        "nombre_facultad": _attr(option, "data-nombre-facultad"),
        "programa": program_code,
        "nombre_programa": option.get_text(strip=True),
        "maximo_semestre": _attr(option, "data-maximo-semestre"),
        "version": _attr(option, "data-version"),
        "estado": _attr(option, "data-estado"),
        "tipo": _attr(option, "data-tipo"),
        "mas_programas": "SI",
        "api": "programasudea",
    }
    return ProgramOption(code=program_code, version=version, form_data=form_data)


def parse_semester_codes(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    codes = [_attr(el, "data-semestre") for el in soup.select("[data-semestre]")]
    return [c for c in codes if c]


def parse_semester_grades(html: str) -> list[GradeRow]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[GradeRow] = []
    for row in soup.select("table tr.text-center"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        match = re.match(r"\[(\w+)\]\s*(.*)", cells[0].get_text(strip=True))
        if not match:
            continue
        rows.append(
            GradeRow(
                code=match.group(1),
                name=match.group(2).strip(),
                raw_grade=cells[2].get_text(strip=True),
            )
        )
    return rows
