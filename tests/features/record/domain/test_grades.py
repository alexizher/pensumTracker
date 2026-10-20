import pytest

from app.features.record.domain.grades import (
    PASSING_GRADE,
    PassedSubject,
    merge_passed,
    parse_grade,
    passed_subject,
)


@pytest.mark.parametrize(
    "raw, esperado",
    [(".5", 0.5), (" 4.2 ", 4.2), ("APROBADA", None), ("", None), ("3.0", 3.0)],
)
def test_parse_grade(raw, esperado):
    assert parse_grade(raw) == esperado


def test_umbral():
    assert PASSING_GRADE == 3.0


def test_nota_en_el_minimo_aprueba():
    assert passed_subject("A", "x", "3.0") == PassedSubject("A", "x", 3.0)


def test_nota_con_espacios_aprueba():
    assert passed_subject("A", "x", " 3.0 ") == PassedSubject("A", "x", 3.0)


@pytest.mark.parametrize("raw", ["2.99", "0", ".5", "PERDIDA", "", "N/A"])
def test_no_aprobada(raw):
    assert passed_subject("A", "x", raw) is None


@pytest.mark.parametrize("raw", ["aprobada", "APROBADO", "Validada", "suficiente", "CUMPLE"])
def test_texto_aprobatorio_sin_nota(raw):
    assert passed_subject("A", "x", raw) == PassedSubject("A", "x", None)


def test_merge_gana_el_ultimo_semestre():
    sem1 = [PassedSubject("A", "uno", 3.5), PassedSubject("B", "dos", 4.0)]
    sem2 = [PassedSubject("A", "uno", 4.5)]
    merged = merge_passed([sem1, sem2])
    assert merged == {
        "A": PassedSubject("A", "uno", 4.5),
        "B": PassedSubject("B", "dos", 4.0),
    }
    assert list(merged) == ["A", "B"]
