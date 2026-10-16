from app.features.record.domain.record import build_record
from models.academic import AcademicRecord, Subject


class AcademicRecordBuilder:
    def build(
        self,
        student_name: str,
        program_name: str,
        program_code: str,
        pensum_version: int,
        version_actual: int,
        versiones: list[int],
        total_credits: int,
        subjects: list[Subject],
        bank_requirements: dict[str, int] | None = None,
        enrolled_version: int | None = None,
    ) -> AcademicRecord:
        return build_record(
            student_name=student_name,
            program_name=program_name,
            program_code=program_code,
            pensum_version=pensum_version,
            version_actual=version_actual,
            versiones=versiones,
            total_credits=total_credits,
            subjects=subjects,
            bank_requirements=bank_requirements,
            enrolled_version=enrolled_version,
        )
