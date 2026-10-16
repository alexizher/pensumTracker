import logging
from typing import cast

from pydantic import SecretStr

from app.features.record.domain.grades import PassedSubject, merge_passed, passed_subject
from app.features.record.domain.homologation import homologate
from app.features.record.sources.gateway import PortalRecordSource, RecordSource
from app.features.record.sources.models import CursumSubject, HistoriaPage
from app.portal import auth
from app.portal.credentials import PortalCredentials
from app.portal.session import PortalSession
from models.academic import Subject
from scraper.base import AcademicHistoryFetcher, Authenticator, CurriculumFetcher

log = logging.getLogger(__name__)


class PortalScraper(Authenticator, CurriculumFetcher, AcademicHistoryFetcher):
    def __init__(self, session: PortalSession, pensum_version: int = 0):
        self._session = session
        self._source: RecordSource = PortalRecordSource(session)
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
        if page.selector_applied:
            self._enrolled_version = page.enrolled_version
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

    def _fetch_semester_grades(self, sem_code: str) -> dict[str, tuple[float | None, str]]:
        return {p.code: (p.grade, p.name) for p in self._passed_in_semester(sem_code)}

    def _passed_in_semester(self, sem_code: str) -> list[PassedSubject]:
        rows = self._source.semester_grades(sem_code)
        found = (passed_subject(r.code, r.name, r.raw_grade) for r in rows)
        return [p for p in found if p is not None]

    def _fetch_semester_codes(self) -> list[str]:
        _, _, program_code = self.fetch_student_info()
        return self._fetch_historia(program_code).semester_codes

    def _fetch_passed_with_names(self) -> dict[str, tuple[float | None, str]]:
        sem_codes = self._fetch_semester_codes()
        log.info("_fetch_passed_with_names: %d semestres encontrados", len(sem_codes))
        merged = merge_passed(self._passed_in_semester(sem_code) for sem_code in sem_codes)
        passed = {code: (p.grade, p.name) for code, p in merged.items()}
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

        passed_subjects = {
            code: PassedSubject(code, name, grade)
            for code, (grade, name) in passed_with_names.items()
        }
        homologation = homologate(passed_subjects, {item.code: item.name for item in cursum_items})

        subjects: list[Subject] = []
        for item in cursum_items:
            code = item.code
            is_cursada = code in passed or code in homologation
            nota = passed.get(code) or homologation.get(code)
            subjects.append(self._build_subject(item, is_cursada, nota, code in current))

        return subjects
