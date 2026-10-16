import json

import pytest

from app.features.record.sources.cursum import parse_curriculum, parse_program
from app.features.record.sources.models import CursumProgram
from tests.fakes.portal import fixture


def test_parse_program_encuentra_el_codigo():
    programs = json.loads(fixture("cursum_programas.json"))
    assert parse_program(programs, "506") == CursumProgram(
        code="506", version_actual=5, versiones=[3, 5], total_credits=30
    )


def test_parse_program_codigo_ausente_devuelve_none():
    assert parse_program(json.loads(fixture("cursum_programas.json")), "999") is None


def test_parse_program_elemento_sin_codigo_lanza_keyerror():
    with pytest.raises(KeyError):
        parse_program([{"nombre": "x"}], "506")


def test_parse_curriculum_prerrequisitos_y_bancos():
    subjects = {s.code: s for s in parse_curriculum(json.loads(fixture("cursum_pensum_506.json")))}
    assert subjects["2000500"].prerequisites == ["2000120"]
    banks = [s.elective_bank for s in subjects.values() if not s.obligatoria]
    assert banks and all(banks)


def test_parse_curriculum_objeto_en_vez_de_lista_devuelve_vacio():
    assert parse_curriculum({"error": "x"}) == []


def test_parse_curriculum_sin_creditos_lanza_keyerror():
    item = {"materia": 1, "nombreMateria": "A", "nivel": 1}
    with pytest.raises(KeyError):
        parse_curriculum([item])
