import pytest
from pydantic import ValidationError

from app.features.record.sources.models import StudentInfo


def test_modelos_son_inmutables():
    info = StudentInfo(student_name="Ana", program_name="Ingenieria", program_code="123")
    with pytest.raises(ValidationError):
        info.student_name = "Otra"  # type: ignore[misc]
