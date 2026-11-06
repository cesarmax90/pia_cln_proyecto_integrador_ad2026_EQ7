"""Aggregate InspeccionVehiculo: checklist con fotos y firma (inmutable una vez firmado)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .comun import RaizAgregado, ReglaNegocioViolada
from .eventos import InspeccionDevolucionCompletada, InspeccionEntregaFirmada
from .valores import (
    DiferenciasInspeccion,
    EvidenciaFoto,
    FirmaDigital,
    Kilometraje,
    NivelCombustible,
    RegistroDanio,
)


class TipoInspeccion(str, Enum):
    ENTREGA = "ENTREGA"
    DEVOLUCION = "DEVOLUCION"


@dataclass
class InspeccionVehiculo(RaizAgregado):
    id: str
    contrato_id: str
    vehiculo_id: str
    tipo: TipoInspeccion
    empleado_id: str
    nivel_combustible: NivelCombustible
    kilometraje: Kilometraje
    registrada_en: datetime
    fotos: tuple[EvidenciaFoto, ...] = field(default_factory=tuple)
    danios: tuple[RegistroDanio, ...] = field(default_factory=tuple)
    firma: FirmaDigital | None = None

    @classmethod
    def registrar(
        cls, id: str, contrato_id: str, vehiculo_id: str, tipo: TipoInspeccion, empleado_id: str,
        nivel_combustible: NivelCombustible, kilometraje: Kilometraje, fotos: tuple[EvidenciaFoto, ...],
        danios: tuple[RegistroDanio, ...], ahora: datetime,
    ) -> InspeccionVehiculo:
        """100 % de los checklists llevan evidencia fotográfica con sello de tiempo."""
        if len(fotos) < 1:
            raise ReglaNegocioViolada("Todo checklist requiere al menos una foto de evidencia")
        insp = cls(id, contrato_id, vehiculo_id, tipo, empleado_id, nivel_combustible, kilometraje,
                   ahora, tuple(fotos), tuple(danios))
        if tipo == TipoInspeccion.DEVOLUCION:
            insp.registrar_evento(InspeccionDevolucionCompletada(ahora, id, contrato_id, vehiculo_id))
        return insp

    @property
    def esta_firmada(self) -> bool:
        return self.firma is not None

    def firmar(self, firma: FirmaDigital, ahora: datetime) -> None:
        """Firmada = inmutable. La entrega exige la firma del cliente."""
        if self.esta_firmada:
            raise ReglaNegocioViolada("El checklist ya fue firmado y es inmutable")
        self.firma = firma
        if self.tipo == TipoInspeccion.ENTREGA:
            self.registrar_evento(InspeccionEntregaFirmada(ahora, self.id, self.contrato_id, self.vehiculo_id))

    def agregar_danio(self, danio: RegistroDanio) -> None:
        if self.esta_firmada:
            raise ReglaNegocioViolada("No se puede modificar un checklist firmado")
        self.danios = (*self.danios, danio)

    def comparar_contra(self, entrega: InspeccionVehiculo) -> DiferenciasInspeccion:
        if self.tipo != TipoInspeccion.DEVOLUCION or entrega.tipo != TipoInspeccion.ENTREGA:
            raise ReglaNegocioViolada("Se compara una devolución contra la entrega del mismo contrato")
        if self.contrato_id != entrega.contrato_id:
            raise ReglaNegocioViolada("Las inspecciones pertenecen a contratos distintos")
        previos = {d.clave for d in entrega.danios}
        nuevos = tuple(d for d in self.danios if d.clave not in previos)
        return DiferenciasInspeccion(
            km_recorridos=self.kilometraje.recorrido_desde(entrega.kilometraje),
            octavos_faltantes=self.nivel_combustible.faltante_respecto_a(entrega.nivel_combustible),
            danios_nuevos=nuevos,
        )
