"""Esquema relacional: columnas indexadas + documento JSON por Aggregate."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    TypeDecorator,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool


class UTCDateTime(TypeDecorator):
    """Guarda siempre UTC y devuelve datetimes con zona horaria (SQLite no conserva tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Solo se persisten datetimes con zona horaria")
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Centavos(TypeDecorator):
    """Dinero exacto: entero de centavos en la base (portable entre SQLite y PostgreSQL)."""

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else int((Decimal(str(value)) * 100).to_integral_value())

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(int(value)) / 100


metadata = MetaData()


def _tabla(nombre: str, *columnas) -> Table:
    return Table(nombre, metadata, Column("id", String(64), primary_key=True), *columnas,
                 Column("datos", JSON, nullable=False))


clientes = _tabla("clientes", Column("activo", Boolean), Column("frecuente", Boolean))
categorias = _tabla("categorias", Column("nivel", Integer, index=True), Column("habilitada", Boolean))
sucursales = _tabla("sucursales", Column("nombre", String(120)))
empleados = _tabla("empleados", Column("rol", String(20)), Column("sucursal_id", String(64)))
vehiculos = _tabla(
    "vehiculos", Column("categoria_id", String(64), index=True), Column("sucursal_id", String(64), index=True),
    Column("estado", String(20), index=True),
)
reservaciones = _tabla(
    "reservaciones", Column("cliente_id", String(64), index=True), Column("categoria_id", String(64), index=True),
    Column("sucursal_id", String(64), index=True), Column("estado", String(24), index=True),
    Column("inicio", UTCDateTime, index=True), Column("fin", UTCDateTime),
)
contratos = _tabla(
    "contratos", Column("reservacion_folio", String(64)), Column("cliente_id", String(64), index=True),
    Column("vehiculo_id", String(64), index=True), Column("categoria_id", String(64), index=True),
    Column("sucursal_id", String(64), index=True), Column("estado", String(20), index=True),
    Column("inicio", UTCDateTime), Column("fin", UTCDateTime), Column("monto_base", Centavos),
)
inspecciones = _tabla(
    "inspecciones", Column("contrato_id", String(64), index=True), Column("vehiculo_id", String(64)),
    Column("tipo", String(12)),
)
liquidaciones = _tabla(
    "liquidaciones", Column("contrato_id", String(64), index=True), Column("deposito_estado", String(12), index=True),
    Column("cargos_calculados", Boolean), Column("devuelta_en", UTCDateTime), Column("total_cargos", Centavos),
)
tareas_limpieza = _tabla(
    "tareas_limpieza", Column("vehiculo_id", String(64), index=True), Column("estado", String(12), index=True),
    Column("creada_en", UTCDateTime), Column("completada_en", UTCDateTime),
)


def normalizar_url(url: str) -> str:
    """Render/Heroku entregan 'postgres://...'; SQLAlchemy 2 + psycopg3 necesita 'postgresql+psycopg://'."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


def crear_motor(url: str) -> Engine:
    url = normalizar_url(url)
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool  # una sola conexión compartida (base en memoria)
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


def crear_esquema(motor: Engine) -> None:
    metadata.create_all(motor)


def ahora_utc() -> datetime:
    return datetime.now(UTC)
