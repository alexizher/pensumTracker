"""Tests de la homologación por nombre entre versiones del pensum.

Datos tomados del catálogo real de cursum (programa 504, Ingeniería de
Sistemas): la v3 trae 2517350 "FORMACIÓN CIUDADANA Y CONSTITUCIONAL" y la v5
la renombró a 2517450 "CÁTEDRA DE FORMACIÓN CIUDADANA Y CONSTITUCIONAL".
No tocan la red: se sustituyen las llamadas al portal.
"""
import pytest

from scraper.portal_scraper import PortalScraper, _normalize_name


def _item(code, name, credits=1, nivel=1):
    return {
        "materia": code,
        "nombreMateria": name,
        "creditos": credits,
        "nivel": nivel,
        "tipoMateria": "OBLIGATORIA",
        "nombreBancoElectiva": " ",
        "requisitos": [],
    }


def _scraper(cursum_items, passed, cursando=()):
    """PortalScraper con las respuestas del portal ya resueltas."""
    s = PortalScraper(cookies={})
    s.fetch_student_info = lambda: ("Estudiante", "INGENIERÍA DE SISTEMAS", "504")
    s._fetch_cursum_items = lambda: cursum_items
    s._fetch_passed_with_names = lambda: passed
    s.fetch_current_subjects = lambda: list(cursando)
    return s


def _por_codigo(subjects):
    return {s.code: s for s in subjects}


PENSUM_V5 = [
    _item("2517450", "CÁTEDRA DE FORMACIÓN CIUDADANA Y CONSTITUCIONAL"),
    _item("2508101", "PROGRAMACIÓN I", credits=3),
]


def test_catedra_renombrada_se_homologa():
    """El caso reportado: cursó 2517350, el pensum vigente trae 2517450."""
    s = _scraper(
        PENSUM_V5,
        {"2517350": (None, "FORMACIÓN CIUDADANA Y CONSTITUCIONAL")},
    )
    materias = _por_codigo(s.fetch_curriculum())
    assert materias["2517450"].cursada is True


def test_catedra_homologa_en_los_dos_sentidos():
    """Quien cursó la CÁTEDRA y pasó a un pensum con el nombre corto."""
    pensum_v73 = [_item("2517350", "FORMACIÓN CIUDADANA Y CONSTITUCIONAL", credits=0)]
    s = _scraper(
        pensum_v73,
        {"2517450": (4.2, "CÁTEDRA DE FORMACIÓN CIUDADANA Y CONSTITUCIONAL")},
    )
    materias = _por_codigo(s.fetch_curriculum())
    assert materias["2517350"].cursada is True
    assert materias["2517350"].nota == 4.2


def test_alias_no_desplaza_a_la_coincidencia_directa():
    """La v4 de varios programas trae las dos formas como materias separadas:
    el nombre exacto manda y el alias no debe robarle la homologación."""
    pensum_v4 = [
        _item("2517362", "FORMACIÓN CIUDADANA Y CONSTITUCIONAL"),
        _item("2517450", "CÁTEDRA DE FORMACIÓN CIUDADANA Y CONSTITUCIONAL"),
    ]
    s = _scraper(
        pensum_v4,
        {"2517350": (None, "FORMACIÓN CIUDADANA Y CONSTITUCIONAL")},
    )
    materias = _por_codigo(s.fetch_curriculum())
    assert materias["2517362"].cursada is True
    assert materias["2517450"].cursada is False


def test_ingles_sigue_homologando():
    s = _scraper(
        [_item("2599999", "ENGLISH 3")],
        {"2517103": (3.8, "INGLÉS III")},
    )
    assert _por_codigo(s.fetch_curriculum())["2599999"].cursada is True


def test_codigo_identico_no_pasa_por_el_nombre():
    s = _scraper(
        PENSUM_V5,
        {"2517450": (4.0, "CÁTEDRA DE FORMACIÓN CIUDADANA Y CONSTITUCIONAL")},
    )
    materias = _por_codigo(s.fetch_curriculum())
    assert materias["2517450"].cursada is True
    assert materias["2517450"].nota == 4.0


def test_materia_ajena_no_se_homologa():
    s = _scraper(PENSUM_V5, {"2504520": (4.0, "COMPORTAMIENTO QUÍMICO DE LOS MATERIALES")})
    assert all(not m.cursada for m in s.fetch_curriculum())


@pytest.mark.parametrize("a, b", [
    ("CONTROL ESTADÍSTICO DE CALIDAD", "CONTROL ESTADÍSTICO DE LA CALIDAD"),
    ("ESCULTURA CONTEMPORÁNEA EN LA INGENIERÍA", "LA ESCULTURA CONTEMPORÁNEA EN LA INGENIERÍA"),
    ("GENIUS OF THE INDUSTRY(HISTORY OF THE GREAT INVENTIONS)",
     "GENIUS OF THE INDUSTRY (HISTORY OF THE GREAT INVENTIONS)"),
    ("SOCIO-HUMANÍSTICA III", "SOCIO HUMANISTICA III"),
    ("AUTOCUIDADO,SALUD PÚBLICA, SEGURIDAD INDUSTRIAL Y ATENCIÓN DE EMERGENCIAS",
     "AUTOCUIDADO, SALUD PÚBLICA, SEGURIDAD INDUSTRIAL Y ATENCIÓN DE EMERGENCIAS"),
    ("FORMACION CIUDADANA Y CONSTITUCIONAL (TURBO)",
     "FORMACION CIUDADANA Y CONSTITUCIONAL- TURBO"),
    ("ARQUITECTURA DE SOFTWARE", "ARQUITECTURA DEL SOFTWARE"),
])
def test_variantes_de_redaccion_dan_la_misma_clave(a, b):
    assert _normalize_name(a) == _normalize_name(b)


@pytest.mark.parametrize("a, b", [
    ("TERMODINÁMICA I", "TERMODINÁMICA II"),
    ("SOCIO-HUMANÍSTICA I", "SOCIO-HUMANÍSTICA II"),
    ("COMPORTAMIENTO QUÍMICO DE LOS MATERIALES", "COMPORTAMIENTO MECÁNICO DE LOS MATERIALES"),
    ("LAB ELECTRÓNICA BÁSICA", "ELECTRÓNICA BÁSICA"),
    ("GEOPOLÍTICA MUNDIAL (ESPAÑOL)", "GEOPOLÍTICA MUNDIAL (INGLÉS)"),
    ("FORMACIÓN CIUDADANA Y CONSTITUCIONAL", "CÁTEDRA DE FORMACIÓN CIUDADANA Y CONSTITUCIONAL"),
])
def test_materias_distintas_no_colapsan(a, b):
    assert _normalize_name(a) != _normalize_name(b)
