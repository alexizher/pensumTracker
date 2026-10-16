from app.features.record.sources.historia import (
    parse_program_selector,
    parse_semester_codes,
    parse_semester_grades,
)
from app.features.record.sources.models import GradeRow
from tests.fakes.portal import fixture


def _selector(version_attr: str) -> str:
    return (
        '<select><option value="506" data-facultad="F" data-version="'
        + version_attr
        + '">Prog</option></select><form id="form2"></form>'
    )


def test_selector_lee_version_y_formulario() -> None:
    option = parse_program_selector(fixture("selector_programas.html"), "506")
    assert option is not None
    assert option.code == "506"
    assert option.version == 3
    assert option.form_data["programa"] == "506"
    assert option.form_data["mas_programas"] == "SI"
    assert option.form_data["api"] == "programasudea"


def test_selector_programa_ausente_devuelve_none() -> None:
    assert parse_program_selector(fixture("selector_programas.html"), "999") is None


def test_selector_sin_form2_devuelve_none() -> None:
    assert parse_program_selector('<select><option value="506">P</option></select>', "506") is None


def test_selector_version_vacia_o_no_numerica_es_none() -> None:
    for attr in ("", "v3"):
        option = parse_program_selector(_selector(attr), "506")
        assert option is not None
        assert option.version is None


def test_codigos_de_semestre_en_orden() -> None:
    assert parse_semester_codes(fixture("historia.html")) == ["20241", "20242"]


def test_notas_del_semestre_traen_la_nota_cruda() -> None:
    rows = parse_semester_grades(fixture("semestre_20241.html"))
    assert (
        GradeRow(code="2000110", name="FORMACIÓN CIUDADANA Y CONSTITUCIONAL", raw_grade="APROBADA")
        in rows
    )


def test_filas_incompletas_se_descartan_y_punto_inicial_llega_intacto() -> None:
    html = (
        "<table>"
        '<tr class="text-center"><td>[1] A</td><td>x</td></tr>'
        '<tr class="text-center"><td>sin codigo</td><td>x</td><td>4.0</td></tr>'
        '<tr class="text-center"><td>[2] B</td><td>x</td><td> .5 </td></tr>'
        "</table>"
    )
    assert parse_semester_grades(html) == [GradeRow(code="2", name="B", raw_grade=".5")]
