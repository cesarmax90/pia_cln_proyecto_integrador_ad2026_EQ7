"""Se ejecuta solo cuando TEST_DATABASE_URL apunta a PostgreSQL (docker compose --profile tests)."""
import os
from decimal import Decimal

import pytest

pytestmark = pytest.mark.postgres

if not os.environ.get("TEST_DATABASE_URL", "").startswith("postgres"):
    pytest.skip("TEST_DATABASE_URL no apunta a PostgreSQL", allow_module_level=True)


def test_la_suite_corre_sobre_postgresql(servicios):
    assert servicios.motor.dialect.name == "postgresql"


def test_tipos_y_transacciones_en_postgresql(servicios, flujo):
    from sqlalchemy import select

    from src.infrastructure import db

    _, _, contrato = flujo.abrir()
    with servicios.ctx.uow_factory() as uow:
        monto = uow.session.execute(select(db.contratos.c.monto_base)).scalar_one()
        inicio = uow.session.execute(select(db.contratos.c.inicio)).scalar_one()
    assert monto == Decimal("1000.00") and inicio.tzinfo is not None and contrato.estado == "ABIERTO"
