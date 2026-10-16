import logging
import re
import unicodedata
from typing import cast

from pydantic import SecretStr

from app.features.record.sources.gateway import PortalRecordSource
from app.features.record.sources.models import CursumSubject, HistoriaPage
from app.portal import auth
from app.portal.credentials import PortalCredentials
from app.portal.session import PortalSession
from models.academic import Subject
from scraper.base import AcademicHistoryFetcher, Authenticator, CurriculumFetcher

log = logging.getLogger(__name__)

_PASSING_GRADE = 3.0

# Notas textuales que indican materia aprobada sin nota numérica
# (típico de materias de 0 créditos: Formación Ciudadana, validaciones, etc.).
_PASSING_TEXT = {"APROBADA", "APROBADO", "VALIDADA", "VALIDADO", "SUFICIENTE", "CUMPLE"}


# Palabras que el pensum agrega o quita entre versiones sin que cambie la
# materia ("CONTROL ESTADÍSTICO DE (LA) CALIDAD").
_FILLER_WORDS = frozenset(
    {
        "DE",
        "DEL",
        "LA",
        "EL",
        "LOS",
        "LAS",
        "UN",
        "UNA",
        "UNOS",
        "UNAS",
        "Y",
        "EN",
        "A",
        "AL",
        "PARA",
        "THE",
        "OF",
    }
)


def _normalize_name(name: str) -> str:
    """Clave para comparar nombres de materia entre versiones: sin tildes, signos
    ni palabras de relleno. Conserva los romanos, que sí separan materias."""
    nfd = unicodedata.normalize("NFD", name.upper())
    ascii_name = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    words = re.sub(r"[^A-Z0-9]+", " ", ascii_name).split()
    return " ".join(w for w in words if w not in _FILLER_WORDS)


# Materias que el pensum renombró entre versiones y no coinciden por nombre.
# Solo se consultan si el nombre exacto no está en el pensum vigente.
_NAME_EQUIVALENTS: tuple[tuple[str, ...], ...] = (
    ("LECTOESCRITURA", "ESPAÑOL ACADÉMICO"),
    ("INGLÉS I", "ENGLISH 1"),
    ("INGLÉS II", "ENGLISH 2"),
    ("INGLÉS III", "ENGLISH 3"),
    ("INGLÉS IV", "ENGLISH 4"),
    ("INGLÉS V", "ENGLISH 5"),
    ("FORMACIÓN CIUDADANA Y CONSTITUCIONAL", "CÁTEDRA DE FORMACIÓN CIUDADANA Y CONSTITUCIONAL"),
)


def _build_aliases(groups: tuple[tuple[str, ...], ...]) -> dict[str, tuple[str, ...]]:
    aliases: dict[str, tuple[str, ...]] = {}
    for group in groups:
        keys = [_normalize_name(n) for n in group]
        for i, key in enumerate(keys):
            aliases[key] = tuple(k for j, k in enumerate(keys) if j != i)
    return aliases


_NAME_ALIASES = _build_aliases(_NAME_EQUIVALENTS)


class PortalScraper(Authenticator, CurriculumFetcher, AcademicHistoryFetcher):
    def __init__(self, session: PortalSession, pensum_version: int = 0):
        self._session = session
        self._source = PortalRecordSource(session)
        self._pensum_version = pensum_version
        self._student_cache: tuple[str, str, str] | None = None
        # Versión del pensum en la que el estudiante está matriculado (del selector
        # de programas, atributo data-version). None si no se pudo determinar.
        self._enrolled_version: int | None = None

    @classmethod
    def from_cookies(cls, cookies: dict[str, str], pensum_version: int = 0) -> "PortalScraper":
        return cls(PortalSession.from_cookies(cookies), pensum_version)

    def login(self, username: str, password: str) -> bool:
        credentials = PortalCredentials(username, SecretStr(password))
        valid = auth.login(self._session, credentials)
        if valid:
            self._session.credentials = credentials
        return valid

    def logout(self) -> None:
        if not self._session.closed:
            self._session.close()
        self._session.cookies.clear()
        self._student_cache = None
        # Los cachés de páginas viven en la fuente: se descartan con ella.
        self._source = PortalRecordSource(self._session)

    def _fetch_historia(self, program_code: str) -> HistoriaPage:
        page = self._source.historia(program_code)
        if page.selector is not None:
            self._enrolled_version = page.selector.version
        return page

    def fetch_enrolled_version(self, program_code: str) -> int | None:
        """Versión del pensum en la que el estudiante está matriculado para este
        programa, leída del selector de programas (data-version). Devuelve None
        si no hay selector (programa único) o no se pudo determinar."""
        if self._enrolled_version is None:
            self._fetch_historia(program_code)
        return self._enrolled_version

    def fetch_assigned_pensum_version(self, program_code: str) -> int | None:
        """Versión de pensum asignada al estudiante.

        Prioridad:
        1. data-version del selector de programas (historia)
        2. versión del pensum oficial en ayudame2: Programa ... (vN)
        """
        enrolled = self.fetch_enrolled_version(program_code)
        if enrolled:
            log.info("fetch_assigned_pensum_version: desde historia=%d", enrolled)
            return enrolled

        page_version, _ = self.fetch_elective_bank_requirements()
        if page_version:
            log.info("fetch_assigned_pensum_version: desde pensum oficial=%d", page_version)
            self._enrolled_version = page_version
            return page_version

        log.warning("fetch_assigned_pensum_version: no se pudo determinar")
        return None

    def validate_session(self) -> bool:
        return auth.validate(self._session)

    def _parse_grade(self, raw: str) -> float | None:
        raw = raw.strip()
        if raw.startswith("."):
            raw = "0" + raw
        try:
            return float(raw)
        except ValueError:
            return None

    def _fetch_semester_grades(self, sem_code: str) -> dict[str, tuple[float | None, str]]:
        result: dict[str, tuple[float | None, str]] = {}
        for row in self._source.semester_grades(sem_code):
            grade = self._parse_grade(row.raw_grade)
            if grade is not None:
                # Nota numérica: aprobada solo si alcanza el mínimo.
                if grade >= _PASSING_GRADE:
                    result[row.code] = (grade, row.name)
            elif row.raw_grade.upper() in _PASSING_TEXT:
                # Aprobada sin nota numérica (p.ej. materias de 0 créditos).
                result[row.code] = (None, row.name)
        return result

    def _fetch_semester_codes(self) -> list[str]:
        _, _, program_code = self.fetch_student_info()
        return self._fetch_historia(program_code).semester_codes

    def _fetch_passed_with_names(self) -> dict[str, tuple[float | None, str]]:
        sem_codes = self._fetch_semester_codes()
        log.info("_fetch_passed_with_names: %d semestres encontrados", len(sem_codes))
        passed: dict[str, tuple[float | None, str]] = {}
        for sem_code in sem_codes:
            passed.update(self._fetch_semester_grades(sem_code))
        log.info("_fetch_passed_with_names: %d materias aprobadas", len(passed))
        return passed

    def fetch_passed_subjects(self) -> dict[str, float | None]:
        return {code: grade for code, (grade, _) in self._fetch_passed_with_names().items()}

    def fetch_student_info(self) -> tuple[str, str, str]:
        if self._student_cache:
            return self._student_cache
        info = self._source.student_info()
        self._student_cache = (info.student_name, info.program_name, info.program_code)
        return self._student_cache

    def fetch_current_subjects(self) -> list[str]:
        return self._source.current_subject_codes()

    def fetch_program_info(self, program_code: str) -> tuple[int, list[int], int]:
        program = self._source.program(program_code)
        if program is None:
            return 0, [], 0
        # Cursum puede mandar null en versionActual o creditosGrado y hoy pasa tal cual.
        # La firma se conserva para el router; el PR 4 decide qué hacer con el null.
        return (
            cast(int, program.version_actual),
            program.versiones,
            cast(int, program.total_credits),
        )

    def fetch_elective_bank_requirements(self) -> tuple[int | None, dict[str, int]]:
        """Lee del pensum oficial (ayudame2) los mínimos por banco y la versión
        del plan del estudiante. Cursum no expone esos cupos; solo el catálogo.

        Returns:
            (pensum_version_en_página | None, {nombre_banco: créditos_mínimos})
        """
        pensum = self._source.official_pensum()
        if pensum is None:
            return None, {}
        return pensum.version, pensum.bank_minimums

    def resolve_total_credits(
        self,
        catalog_total: int,
        subjects: list[Subject],
    ) -> tuple[int, dict[str, int]]:
        """Total de grado acorde a la versión del pensum efectiva.

        Si el pensum oficial (misma versión) trae mínimos por banco:
            total = obligatorias + suma(mínimos por banco)
        Si no, cae a creditosGrado del catálogo Cursum.
        """
        page_version, bank_reqs = self.fetch_elective_bank_requirements()
        oblig = sum(s.credits for s in subjects if s.obligatoria)

        if bank_reqs and page_version == self._pensum_version:
            total = oblig + sum(bank_reqs.values())
            log.info(
                "resolve_total_credits: versión=%d oblig=%d electivas_min=%d -> %d "
                "(catálogo cursum=%d)",
                self._pensum_version,
                oblig,
                sum(bank_reqs.values()),
                total,
                catalog_total,
            )
            return total, bank_reqs

        log.info(
            "resolve_total_credits: fallback cursum=%d | page_version=%s efectiva=%d bancos=%d",
            catalog_total,
            page_version,
            self._pensum_version,
            len(bank_reqs),
        )
        return catalog_total, {}

    def _fetch_cursum_items(self) -> list[CursumSubject]:
        _, _, program_code = self.fetch_student_info()
        return self._source.curriculum(program_code, self._pensum_version)

    def _build_subject(
        self, item: CursumSubject, cursada: bool, nota: float | None, cursando: bool
    ) -> Subject:
        return Subject(
            code=item.code,
            name=item.name,
            credits=item.credits,
            semester=item.level,
            obligatoria=item.obligatoria,
            elective_bank=item.elective_bank,
            prerequisites=list(item.prerequisites),
            corequisites=list(item.corequisites),
            cursada=cursada,
            nota=nota,
            cursando=cursando,
        )

    def fetch_pensum_subjects(self) -> list[Subject]:
        return [
            self._build_subject(item, False, None, False) for item in self._fetch_cursum_items()
        ]

    def fetch_curriculum(self) -> list[Subject]:
        _, _, program_code = self.fetch_student_info()
        passed_with_names = self._fetch_passed_with_names()
        passed = {code: grade for code, (grade, _) in passed_with_names.items()}
        current = set(self.fetch_current_subjects())
        log.info(
            "fetch_curriculum: cursando=%d | program_code=%s pensum_version=%d",
            len(current),
            program_code,
            self._pensum_version,
        )

        cursum_items = self._fetch_cursum_items()
        if not cursum_items:
            return []

        cursum_codes = {item.code for item in cursum_items}
        name_to_code = {_normalize_name(item.name): item.code for item in cursum_items}
        homologation: dict[str, float | None] = {}
        for old_code, (grade, name) in passed_with_names.items():
            if old_code in cursum_codes:
                continue
            normalized = _normalize_name(name)
            if not normalized:
                continue
            new_code = name_to_code.get(normalized)
            if new_code is None:
                # Sin coincidencia directa: probamos los renombres conocidos.
                for alias in _NAME_ALIASES.get(normalized, ()):
                    new_code = name_to_code.get(alias)
                    if new_code:
                        break
            if new_code and new_code not in homologation:
                log.info("fetch_curriculum: homologación %s→%s (%s)", old_code, new_code, name)
                homologation[new_code] = grade

        subjects: list[Subject] = []
        for item in cursum_items:
            code = item.code
            is_cursada = code in passed or code in homologation
            nota = passed.get(code) or homologation.get(code)
            subjects.append(self._build_subject(item, is_cursada, nota, code in current))

        return subjects
