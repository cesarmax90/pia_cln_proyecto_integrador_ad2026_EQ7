"""ReporteAppService (US19): consultas directas al read model, sin pasar por el Domain Model (ADR-002)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..domain.comun import ErrorValidacion
from .base import ServicioBase
from .dto import ReporteOcupacionDTO
from .permisos import exigir
from .puertos import Actor


class ReporteAppService(ServicioBase):
    def generar_reporte_ocupacion(
        self, actor: Actor, sucursal_id: str, desde: datetime, hasta: datetime
    ) -> ReporteOcupacionDTO:
        exigir(actor, "generar_reporte")
        if hasta <= desde:
            raise ErrorValidacion("El rango del reporte es inválido: 'hasta' debe ser posterior a 'desde'")
        datos = self.ctx.consultas.reporte_ocupacion(sucursal_id, desde, hasta)
        rotacion = datos["rotacion_horas_promedio"]
        return ReporteOcupacionDTO(
            sucursal_id, desde, hasta, datos["flota_total"], datos["ocupacion_pct"],
            datos["ingresos_renta"], datos["ingresos_cargos"],
            Decimal(str(rotacion)) if rotacion is not None else None, datos["vehiculos_por_estado"],
        )
