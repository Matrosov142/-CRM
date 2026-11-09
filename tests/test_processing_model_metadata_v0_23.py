from pathlib import Path
from app.models import ProcessingJob, ProcessingOperation, ProcessingMaterial, QualityInspection, FinishedGoodsBatch

ROOT = Path(__file__).resolve().parents[1]


def test_processing_tables_are_registered_in_shared_sqlalchemy_metadata():
    from app.database import Base
    assert {"processing_jobs", "processing_operations", "processing_materials"}.issubset(Base.metadata.tables)


def test_processing_job_constraints_match_existing_migration():
    constraints = {c.name for c in ProcessingJob.__table__.constraints}
    assert "uq_processing_job_number" in constraints
    assert "fk_processing_job_order_same_company" in constraints
    assert "fk_processing_job_creator_same_company" in constraints
    assert "ck_processing_job_status" in constraints


def test_processing_operation_and_material_have_tenant_scoped_foreign_keys():
    op_constraints = {c.name for c in ProcessingOperation.__table__.constraints}
    mat_constraints = {c.name for c in ProcessingMaterial.__table__.constraints}
    assert "fk_processing_operation_job_same_company" in op_constraints
    assert "fk_processing_material_job_same_company" in mat_constraints
    assert "fk_processing_material_batch_same_company" in mat_constraints


def test_processing_models_match_original_migration_tables():
    migration = (ROOT / "migrations/versions/0017_processing_jobs.py").read_text()
    for table in ("processing_jobs", "processing_operations", "processing_materials"):
        assert f'"{table}"' in migration
    assert {"job_id", "company_id"}.issubset(ProcessingOperation.__table__.columns.keys())
    assert {"stock_batch_id", "planned_quantity", "unit_cost_snapshot"}.issubset(ProcessingMaterial.__table__.columns.keys())
