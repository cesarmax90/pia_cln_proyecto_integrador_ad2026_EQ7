import os

import pytest

from src.composicion import construir_servicios
from src.config import Settings
from src.infrastructure.adaptadores import GeneradorIdsSecuencial, RelojFijo
from src.infrastructure.db import metadata

from .escenario import AHORA, Flujo, sembrar

# Por defecto SQLite en memoria; con TEST_DATABASE_URL toda la suite corre contra PostgreSQL (docker compose).
URL_PRUEBAS = os.environ.get("TEST_DATABASE_URL", "sqlite://")


@pytest.fixture
def reloj():
    return RelojFijo(AHORA)


@pytest.fixture
def servicios(reloj):
    s = construir_servicios(
        Settings(database_url=URL_PRUEBAS, cargar_datos_demo=False), reloj=reloj,
        ids=GeneradorIdsSecuencial(), propagar_errores_bus=True,
    )
    if not URL_PRUEBAS.startswith("sqlite"):
        metadata.drop_all(s.motor)  # aislamiento entre pruebas en una base compartida
        metadata.create_all(s.motor)
    sembrar(s)
    yield s
    s.motor.dispose()


@pytest.fixture
def flujo(servicios, reloj):
    return Flujo(servicios, reloj)
