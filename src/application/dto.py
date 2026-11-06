"""DTOs de salida: los servicios nunca exponen entidades del dominio."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass
class DisponibilidadDTO:
    categoria_id: str
    categoria: str
    tarifa_diaria: Decimal
    disponibles: int


@dataclass
class ReservacionDTO:
    folio: str
    cliente_id: str
    categoria_id: str
    categoria_asignada_id: str | None
    sucursal_id: str
    inicio: datetime
    fin: datetime
    estado: str
    tarifa_diaria: Decimal
    penalizacion: Decimal | None


@dataclass
class CancelacionDTO:
    folio: str
    estado: str
    penalizada: bool
    penalizacion: Decimal


@dataclass
class EntregaDTO:
    folio: str
    vehiculo_id: str | None
    requiere_upgrade: bool
    categoria_superior_id: str | None
    mensaje: str


@dataclass
class FotoDTO:
    uri: str
    tomada_en: datetime


@dataclass
class DanioDTO:
    zona: str
    descripcion: str
    fotos: list[FotoDTO]


@dataclass
class InspeccionDTO:
    id: str
    contrato_id: str
    vehiculo_id: str
    tipo: str
    empleado_id: str
    combustible_octavos: int
    kilometraje: int
    fotos: list[FotoDTO]
    danios: list[DanioDTO]
    firmada: bool
    firmante: str | None


@dataclass
class ExtensionDTO:
    id: str
    horas: int
    estado: str
    aprobada_por: str | None


@dataclass
class ContratoDTO:
    id: str
    reservacion_folio: str
    cliente_id: str
    vehiculo_id: str
    categoria_id: str
    sucursal_id: str
    inicio: datetime
    fin: datetime
    estado: str
    tarifa_diaria: Decimal
    monto_base: Decimal
    extensiones: list[ExtensionDTO]
    conductores_adicionales: list[str]
    devolucion_real: datetime | None


@dataclass
class CargoDTO:
    id: str
    tipo: str
    monto: Decimal
    descripcion: str
    estado: str
    disputa_motivo: str | None
    disputa_resolucion: str | None


@dataclass
class LiquidacionDTO:
    id: str
    contrato_id: str
    cargos: list[CargoDTO]
    total_cargos: Decimal
    deposito_monto: Decimal
    deposito_estado: str
    cargos_calculados: bool
    tiene_incidencias: bool


@dataclass
class VehiculoDTO:
    id: str
    placa: str
    categoria_id: str
    sucursal_id: str
    kilometraje: int
    estado: str


@dataclass
class TareaLimpiezaDTO:
    id: str
    vehiculo_id: str
    estado: str
    creada_en: datetime
    completada_en: datetime | None


@dataclass
class EvidenciaDisputaDTO:
    contrato_id: str
    cargo_id: str
    entrega: InspeccionDTO
    devolucion: InspeccionDTO
    danios_nuevos: list[DanioDTO] = field(default_factory=list)


@dataclass
class ResumenFlotaDTO:
    sucursal_id: str
    total: int
    por_estado: dict[str, int]
    por_categoria: dict[str, int]


@dataclass
class ReporteOcupacionDTO:
    sucursal_id: str
    desde: datetime
    hasta: datetime
    flota_total: int
    ocupacion_pct: Decimal
    ingresos_renta: Decimal
    ingresos_cargos: Decimal
    rotacion_horas_promedio: Decimal | None
    vehiculos_por_estado: dict[str, int]


def _foto(f) -> FotoDTO:
    return FotoDTO(f.uri, f.tomada_en)


def _danio(d) -> DanioDTO:
    return DanioDTO(d.zona, d.descripcion, [_foto(f) for f in d.fotos])


def reservacion_dto(r) -> ReservacionDTO:
    return ReservacionDTO(
        r.folio, r.cliente_id, r.categoria_id, r.categoria_asignada_id, r.sucursal_id,
        r.periodo.inicio, r.periodo.fin, r.estado.value, r.tarifa_diaria.monto,
        r.penalizacion.monto if r.penalizacion else None,
    )


def inspeccion_dto(i) -> InspeccionDTO:
    return InspeccionDTO(
        i.id, i.contrato_id, i.vehiculo_id, i.tipo.value, i.empleado_id, i.nivel_combustible.octavos,
        i.kilometraje.valor, [_foto(f) for f in i.fotos], [_danio(d) for d in i.danios], i.esta_firmada,
        i.firma.firmante if i.firma else None,
    )


def extension_dto(e) -> ExtensionDTO:
    return ExtensionDTO(e.id, e.horas, e.estado.value, e.aprobada_por)


def contrato_dto(c) -> ContratoDTO:
    return ContratoDTO(
        c.id, c.reservacion_folio, c.cliente_id, c.vehiculo_id, c.categoria_id, c.sucursal_id,
        c.periodo.inicio, c.periodo.fin, c.estado.value, c.tarifa_diaria.monto, c.monto_base().monto,
        [extension_dto(e) for e in c.extensiones], [x.nombre for x in c.conductores], c.devolucion_real,
    )


def liquidacion_dto(liq) -> LiquidacionDTO:
    cargos = [
        CargoDTO(
            c.id, c.tipo.value, c.monto.monto, c.descripcion, c.estado.value,
            c.disputa.motivo if c.disputa else None, c.disputa.resolucion if c.disputa else None,
        )
        for c in liq.cargos
    ]
    return LiquidacionDTO(
        liq.id, liq.contrato_id, cargos, liq.total_cargos().monto, liq.deposito.monto.monto,
        liq.deposito.estado.value, liq.cargos_calculados, liq.tiene_incidencias(),
    )


def vehiculo_dto(v) -> VehiculoDTO:
    return VehiculoDTO(v.id, v.placa, v.categoria_id, v.sucursal_id, v.kilometraje.valor, v.estado.value)


def tarea_dto(t) -> TareaLimpiezaDTO:
    return TareaLimpiezaDTO(t.id, t.vehiculo_id, t.estado.value, t.creada_en, t.completada_en)
