"""Read model para reportes (US19): SQL directo sobre columnas indexadas, sin hidratar agregados (ADR-002)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from ..domain.vehiculo import EstadoVehiculo
from . import db

_DOS = Decimal("0.01")


class ConsultasSQL:
    def __init__(self, fabrica_sesiones: sessionmaker):
        self._fabrica = fabrica_sesiones

    def reporte_ocupacion(self, sucursal_id: str, desde: datetime, hasta: datetime) -> dict:
        with self._fabrica() as s:
            v, c, liq, t = db.vehiculos, db.contratos, db.liquidaciones, db.tareas_limpieza
            estados = Counter(dict(s.execute(
                select(v.c.estado, func.count()).where(v.c.sucursal_id == sucursal_id).group_by(v.c.estado)
            ).all()))
            flota = sum(estados.values())

            # Ocupación: horas-vehículo contratadas dentro del rango / horas-vehículo disponibles
            filas = s.execute(
                select(c.c.inicio, c.c.fin).where(c.c.sucursal_id == sucursal_id, c.c.inicio < hasta, c.c.fin > desde)
            ).all()
            horas_ocupadas = sum((min(fin, hasta) - max(inicio, desde)).total_seconds() / 3600 for inicio, fin in filas)
            horas_totales = flota * (hasta - desde).total_seconds() / 3600
            ocupacion = (
                min(Decimal(100), Decimal(str(horas_ocupadas / horas_totales * 100))) if horas_totales else Decimal(0)
            ).quantize(_DOS, rounding=ROUND_HALF_UP)

            ingresos_renta = s.execute(
                select(func.sum(c.c.monto_base)).where(
                    c.c.sucursal_id == sucursal_id, c.c.inicio >= desde, c.c.inicio < hasta
                )
            ).scalar() or Decimal("0.00")
            ingresos_cargos = s.execute(
                select(func.sum(liq.c.total_cargos))
                .select_from(liq.join(c, liq.c.contrato_id == c.c.id))
                .where(c.c.sucursal_id == sucursal_id, liq.c.devuelta_en >= desde, liq.c.devuelta_en < hasta)
            ).scalar() or Decimal("0.00")

            tareas = s.execute(
                select(t.c.creada_en, t.c.completada_en)
                .select_from(t.join(v, t.c.vehiculo_id == v.c.id))
                .where(v.c.sucursal_id == sucursal_id, t.c.completada_en >= desde, t.c.completada_en < hasta)
            ).all()
            rotacion = (
                (sum((fin - ini).total_seconds() for ini, fin in tareas) / len(tareas) / 3600) if tareas else None
            )
        return {
            "flota_total": flota,
            "ocupacion_pct": ocupacion,
            "ingresos_renta": Decimal(ingresos_renta).quantize(_DOS),
            "ingresos_cargos": Decimal(ingresos_cargos).quantize(_DOS),
            "rotacion_horas_promedio": Decimal(str(rotacion)).quantize(_DOS) if rotacion is not None else None,
            "vehiculos_por_estado": {e.value: estados.get(e.value, 0) for e in EstadoVehiculo},
        }
