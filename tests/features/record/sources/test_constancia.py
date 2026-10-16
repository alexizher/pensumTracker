from app.features.record.sources.constancia import parse_current_subjects, parse_student_info
from app.features.record.sources.models import StudentInfo
from tests.fakes.portal import fixture


def test_student_info_de_la_fixture() -> None:
    assert parse_student_info(fixture("constancia.html")) == StudentInfo(
        student_name="ANA PRUEBA", program_name="INGENIERÍA DE PRUEBA", program_code="506"
    )


def test_student_info_vacio_sin_coincidencias() -> None:
    assert parse_student_info("<html></html>") == StudentInfo(
        student_name="", program_name="", program_code=""
    )


def test_current_subjects_de_la_fixture() -> None:
    assert parse_current_subjects(fixture("constancia.html")) == ["2000300"]


def test_current_subjects_sin_h5_devuelve_lista_vacia() -> None:
    assert parse_current_subjects("<html><body><p>nada</p></body></html>") == []
