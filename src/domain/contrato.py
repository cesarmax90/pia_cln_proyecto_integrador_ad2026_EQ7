"""Aggregate ContratoRenta: acuerdo activo desde la entrega hasta la devolución."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from .comun import RaizAgregado, ReglaNegocioViolada, Rol, exigir_rol
from .eventos import (
    ContratoAbierto,
    ContratoCerrado,
    ExtensionRequiereAutorizacion,
    RentaExtendida,
    VehiculoDevuelto,
)
from .maquina_estados import MaquinaEstados
from .politicas import DecisionExtension, PoliticaExtension
from .valores import (
    CoberturaSeguro,
    CondicionesContrato,
    Dinero,
    Licencia,
    PeriodoRenta,
    ReferenciaPago,
)


class EstadoContrato(str, Enum):
    ABIERTO = "ABIERTO"
    DEVUELTO = "DEVUELTO"
    CERRADO = "CERRADO"


class EstadoExtension(str, Enum):
    PENDIENTE = "PENDIENTE"
    APROBADA = "APROBADA"


C = EstadoContrato
MAQUINA_CONTRATO = MaquinaEstados(
    "ContratoRenta",
    {
        (C.ABIERTO, "extender"): C.ABIERTO,
        (C.ABIERTO, "agregar_conductor"): C.ABIERTO,
        (C.ABIERTO, "registrar_devolucion"): C.DEVUELTO,
        (C.DEVUELTO, "cerrar"): C.CERRADO,
    },
)


@dataclass
class Extension:
    id: str
    horas: int
    solicitada_por: str
    solicitada_en: datetime
    estado: EstadoExtension = EstadoExtension.PENDIENTE
    aprobada_por: str | None = None


@dataclass
class ConductorAdicional:
    id: str
    nombre: str
    licencia: Licencia


@dataclass
class ContratoRenta(RaizAgregado):
    id: str
    reservacion_folio: str
    cliente_id: str
    vehiculo_id: str
    categoria_id: str
    sucursal_id: str
    periodo: PeriodoRenta
    tarifa_diaria: Dinero
    km_incluido_por_dia: int
    referencia_pago: ReferenciaPago
    inspeccion_entrega_id: str
    cobertura: CoberturaSeguro | None = None
    estado: EstadoContrato = EstadoContrato.ABIERTO
    extensiones: list[Extension] = field(default_factory=list)
    conductores: list[ConductorAdicional] = field(default_factory=list)
    devolucion_real: datetime | None = None

    # ------------------------------------------------------------------ apertura
    @classmethod
    def abrir(
        cls, id: str, reservacion_folio: str, cliente_id: str, vehiculo_id: str, categoria_id: str,
        sucursal_id: str, periodo: PeriodoRenta, tarifa_diaria: Dinero, km_incluido_por_dia: int,
        deposito: Dinero, referencia_pago: ReferenciaPago, inspeccion_entrega_id: str, ahora: datetime,
        cobertura: CoberturaSeguro | None = None,
    ) -> ContratoRenta:
        """Un contrato, una unidad. La entrega exige inspección firmada (validada por el servicio)."""
        c = cls(
            id, reservacion_folio, cliente_id, vehiculo_id, categoria_id, sucursal_id, periodo,
            tarifa_diaria, km_incluido_por_dia, referencia_pago, inspeccion_entrega_id, cobertura,
        )
        c.registrar_evento(
            ContratoAbierto(ahora, id, reservacion_folio, vehiculo_id, deposito.monto, referencia_pago.id_externo)
        )
        return c

    def condiciones(self) -> CondicionesContrato:
        return CondicionesContrato(
            periodo_pactado=self.periodo,
            devolucion_real=self.devolucion_real,
            km_incluido_por_dia=self.km_incluido_por_dia,
            categoria_id=self.categoria_id,
            tarifa_diaria=self.tarifa_diaria,
        )

    def monto_base(self) -> Dinero:
        total = self.tarifa_diaria.por(self.periodo.dias)
        if self.cobertura is not None:
            total = total + self.cobertura.costo_diario.por(self.periodo.dias)
        return total

    # ------------------------------------------------------------------ extensiones
    def solicitar_extension(
        self, horas: int, actor_id: str, rol: Rol, ahora: datetime, politica: PoliticaExtension
    ) -> Extension:
        exigir_rol(rol, {Rol.AGENTE, Rol.ADMINISTRACION}, "solicitar una extensión de renta")
        MAQUINA_CONTRATO.siguiente(self.estado, "extender")
        decision = politica.decidir(rol, horas, self.periodo.fin, ahora)
        ext = Extension(f"{self.id}-X{len(self.extensiones) + 1}", horas, actor_id, ahora)
        self.extensiones.append(ext)
        if decision == DecisionExtension.APROBAR:
            self._aplicar(ext, actor_id, ahora)
        else:
            self.registrar_evento(ExtensionRequiereAutorizacion(ahora, self.id, ext.id, horas))
        return ext

    def aprobar_extension(self, extension_id: str, rol: Rol, actor_id: str, ahora: datetime) -> Extension:
        exigir_rol(rol, {Rol.ADMINISTRACION}, "aprobar una extensión mayor a 48 h")
        ext = self._extension(extension_id)
        if ext.estado != EstadoExtension.PENDIENTE:
            raise ReglaNegocioViolada("La extensión ya fue aprobada")
        if ahora >= self.periodo.fin:
            raise ReglaNegocioViolada("La extensión pendiente ya venció junto con el contrato")
        self._aplicar(ext, actor_id, ahora)
        return ext

    def _extension(self, extension_id: str) -> Extension:
        for ext in self.extensiones:
            if ext.id == extension_id:
                return ext
        raise ReglaNegocioViolada(f"No existe la extensión {extension_id}")

    def _aplicar(self, ext: Extension, aprobada_por: str, ahora: datetime) -> None:
        ext.estado = EstadoExtension.APROBADA
        ext.aprobada_por = aprobada_por
        self.periodo = self.periodo.extender(ext.horas)
        self.registrar_evento(RentaExtendida(ahora, self.id, ext.horas, self.periodo.fin))

    # ------------------------------------------------------------------ conductores
    def agregar_conductor_adicional(self, id: str, nombre: str, licencia: Licencia, hoy: date) -> None:
        MAQUINA_CONTRATO.siguiente(self.estado, "agregar_conductor")
        if not licencia.vigente_en(hoy):
            raise ReglaNegocioViolada("El conductor adicional requiere licencia vigente")
        self.conductores.append(ConductorAdicional(id, nombre, licencia))

    # ------------------------------------------------------------------ devolución y cierre
    def registrar_devolucion(self, ahora: datetime) -> None:
        self.estado = MAQUINA_CONTRATO.siguiente(self.estado, "registrar_devolucion")
        self.devolucion_real = ahora
        self.registrar_evento(VehiculoDevuelto(ahora, self.id, self.vehiculo_id, ahora))

    def cerrar(self, ahora: datetime) -> None:
        self.estado = MAQUINA_CONTRATO.siguiente(self.estado, "cerrar")
        self.registrar_evento(ContratoCerrado(ahora, self.id))


def total_a_decimal(d: Dinero) -> Decimal:
    return d.monto
