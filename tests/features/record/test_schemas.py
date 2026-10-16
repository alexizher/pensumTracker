import app.features.record.schemas as schemas
import models.academic as academic


def test_models_reexporta_schemas() -> None:
    assert academic.Subject is schemas.Subject
    assert academic.ElectiveBank is schemas.ElectiveBank
    assert academic.AcademicRecord is schemas.AcademicRecord
