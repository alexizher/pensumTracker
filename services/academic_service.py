from collections import defaultdict
from models.academic import Subject, ElectiveBank, AcademicRecord


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
        unlocked = {s.code for s in subjects if s.cursada or s.cursando}
        bank_requirements = bank_requirements or {}

        # Progreso hacia el grado: las obligatorias cuentan completas, pero las
        # electivas solo cuentan hasta lo que el programa exige.
        # Preferimos cupos oficiales por banco (pensum ayudame2); si no hay,
        # caemos al agregado total_credits - obligatorias (catálogo Cursum).
        obligatorias_total = sum(s.credits for s in subjects if s.obligatoria)
        obligatorias_passed = sum(s.credits for s in subjects if s.obligatoria and s.cursada)

        bank_progress: dict[str, int] = defaultdict(int)
        electives_passed = 0
        electives_in_progress = 0
        for s in subjects:
            if s.obligatoria:
                continue
            if s.cursada:
                electives_passed += s.credits
                if s.elective_bank:
                    bank_progress[s.elective_bank] += s.credits
            elif s.cursando:
                electives_in_progress += s.credits
                if s.elective_bank:
                    bank_progress[s.elective_bank] += s.credits

        if bank_requirements:
            electives_required = sum(bank_requirements.values())
            elective_progress = sum(
                min(bank_progress.get(name, 0), req)
                for name, req in bank_requirements.items()
            )

            def bank_satisfied(bank: str | None) -> bool:
                if bank and bank in bank_requirements:
                    return bank_progress.get(bank, 0) >= bank_requirements[bank]
                if bank:
                    # Banco sin cupo de créditos (p.ej. práctica 0 cr):
                    # satisfecho si ya cursó o cursa alguna materia del banco.
                    return any(
                        (s.cursada or s.cursando) and s.elective_bank == bank
                        for s in subjects
                    )
                return all(
                    bank_progress.get(name, 0) >= req
                    for name, req in bank_requirements.items()
                )

            electives_satisfied = all(
                bank_satisfied(name) for name in bank_requirements
            )
        else:
            electives_required = max(0, total_credits - obligatorias_total)
            elective_progress = min(electives_passed, electives_required)
            electives_satisfied = (
                electives_passed + electives_in_progress >= electives_required
            )

            def bank_satisfied(bank: str | None) -> bool:
                return electives_satisfied

        enriched: list[Subject] = []
        for s in subjects:
            if s.cursada:
                status = "passed"
            elif s.cursando:
                status = "in_progress"
            elif all(p in unlocked for p in s.prerequisites):
                # Una electiva solo está "disponible" si su banco (o el cupo
                # agregado) aún necesita créditos.
                if not s.obligatoria and bank_satisfied(s.elective_bank):
                    status = "not_needed"
                else:
                    status = "available"
            else:
                status = "locked"
            enriched.append(s.model_copy(update={"status": status}))

        completed_credits = sum(s.credits for s in enriched if s.cursada)
        in_progress_credits = sum(s.credits for s in enriched if s.cursando and not s.cursada)
        progress_credits = min(
            total_credits,
            obligatorias_passed + elective_progress,
        )
        graduated = progress_credits >= total_credits

        bank_subjects: dict[str, list[Subject]] = defaultdict(list)
        for s in enriched:
            if s.elective_bank:
                bank_subjects[s.elective_bank].append(s)

        elective_banks: list[ElectiveBank] = []
        for bank_name, group in sorted(bank_subjects.items()):
            if bank_name in bank_requirements:
                required = bank_requirements[bank_name]
            else:
                # Sin cupo oficial: no inflar con todo el catálogo; 0 = informativo.
                required = 0 if bank_requirements else sum(s.credits for s in group)
            elective_banks.append(
                ElectiveBank(
                    name=bank_name,
                    credits_required=required,
                    credits_approved=sum(s.credits for s in group if s.cursada),
                    subject_codes=[s.code for s in group],
                )
            )

        return AcademicRecord(
            student_name=student_name,
            program_name=program_name,
            program_code=program_code,
            pensum_version=pensum_version,
            version_actual=version_actual,
            enrolled_version=enrolled_version,
            versiones=versiones,
            total_credits=total_credits,
            completed_credits=completed_credits,
            progress_credits=progress_credits,
            in_progress_credits=in_progress_credits,
            graduated=graduated,
            subjects=enriched,
            elective_banks=elective_banks,
        )
