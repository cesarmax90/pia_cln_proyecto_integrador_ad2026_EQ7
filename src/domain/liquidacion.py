"""Aggregate Liquidacion: cuenta final del contrato (cargos, disputas y depósito)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Protocol

from .comun import RaizAgregado, ReglaNegocioViolada, Rol, exigir_rol
from .especificaciones import ContextoDeposito, deposito_liberable
from .eventos import CargoDisputado, CargosCalculados, DepositoLiberado, DisputaResuelta
from .maquina_estados import MaquinaEstados
from .politicas import ParametrosNegocio, PoliticaCargos
from .valores import (
    CondicionesContrato,
    DiferenciasInspeccion,
    Dinero,
    Disputa,
    ReferenciaPago,
)


class CalendarioHabil(Protocol):
    def sumar_dias_habiles(self, desde: date, dias: int) -> date: ...


class TipoCargo(str, Enum):
    KILOMETRAJE = "KILOMETRAJE"
    COMBUSTIBLE = "COMBUSTIBLE"
    RETRASO = "RETRASO"
    DANIO = "DANIO"


class EstadoCargo(str, Enum):
    PENDIENTE_APROBACION = "PENDIENTE_APROBACION"
    APLICADO = "APLICADO"
    DISPUTADO = "DISPUTADO"
    ANULADO = "ANULADO"


class EstadoDeposito(str, Enum):
    RETENIDO = "RETENIDO"
    LIBERADO = "LIBERADO"


EC = EstadoCargo
MAQUINA_CARGO = MaquinaEstados(
    "Cargo",
    {
        (EC.PENDIENTE_APROBACION, "aprobar"): EC.APLICADO,
        (EC.APLICADO, "disputar"): EC.DISPUTADO,
        (EC.DISPUTADO, "confirmar"): EC.APLICADO,
        (EC.DISPUTADO, "anular"): EC.ANULADO,
    },
)


@dataclass
class Cargo:
    id: str
    tipo: TipoCargo
    monto: Dinero
    descripcion: str
    estado: EstadoCargo = EstadoCargo.APLICADO
    disputa: Disputa | None = None


@dataclass
class Deposito:
    monto: Dinero
    referencia: ReferenciaPago
    estado: EstadoDeposito = EstadoDeposito.RETENIDO
    liberado_en: datetime | None = None


@dataclass
class Liquidacion(RaizAgregado):
    id: str
    contrato_id: str
    deposito: Deposito
    cargos: list[Cargo] = field(default_factory=list)
    cargos_calculados: bool = False
    devuelta_en: datetime | None = None

    @classmethod
    def abrir(cls, id: str, contrato_id: str, monto_deposito: Dinero, referencia: ReferenciaPago) -> Liquidacion:
        return cls(id, contrato_id, Deposito(monto_deposito, referencia))

    # ------------------------------------------------------------------ consultas
    def total_cargos(self) -> Dinero:
        total = Dinero.cero()
        for c in self.cargos:
            if c.estado == EstadoCargo.APLICADO:
                total = total + c.monto
        return total

    def danios_por_aprobar(self) -> int:
        return sum(1 for c in self.cargos if c.estado == EstadoCargo.PENDIENTE_APROBACION)

    def tiene_incidencias(self) -> bool:
        return any(
            (c.tipo == TipoCargo.DANIO and c.estado != EstadoCargo.ANULADO) or c.estado == EstadoCargo.DISPUTADO
            for c in self.cargos
        )

    def _cargo(self, cargo_id: str) -> Cargo:
        for c in self.cargos:
            if c.id == cargo_id:
                return c
        raise ReglaNegocioViolada(f"No existe el cargo {cargo_id}")

    # ------------------------------------------------------------------ cálculo
    def calcular_cargos(
        self, diferencias: DiferenciasInspeccion, condiciones: CondicionesContrato,
        politica: PoliticaCargos, ahora: datetime,
    ) -> bool:
        """Idempotente: si los cargos ya se calcularon no cambia nada y no emite eventos."""
        if self.cargos_calculados:
            return False
        for propuesto in politica.calcular(diferencias, condiciones):
            self.cargos.append(
                Cargo(self._nuevo_id(), TipoCargo(propuesto.tipo), propuesto.monto, propuesto.descripcion)
            )
        for danio in diferencias.danios_nuevos:
            # El monto del daño lo fija Administración: queda pendiente de aprobación.
            self.cargos.append(
                Cargo(self._nuevo_id(), TipoCargo.DANIO, Dinero.cero(),
                      f"Daño nuevo en {danio.zona}: {danio.descripcion}", EstadoCargo.PENDIENTE_APROBACION)
            )
        self.cargos_calculados = True
        self.devuelta_en = condiciones.devolucion_real
        self.registrar_evento(
            CargosCalculados(ahora, self.id, self.contrato_id, self.total_cargos().monto, self.danios_por_aprobar())
        )
        return True

    def _nuevo_id(self) -> str:
        return f"{self.id}-C{len(self.cargos) + 1}"

    def aprobar_cargo_danio(self, cargo_id: str, monto: Dinero, rol: Rol) -> None:
        exigir_rol(rol, {Rol.ADMINISTRACION}, "fijar el monto de un daño")
        cargo = self._cargo(cargo_id)
        if cargo.tipo != TipoCargo.DANIO:
            raise ReglaNegocioViolada("Solo los cargos por daño requieren aprobación de monto")
        if monto.es_cero():
            raise ReglaNegocioViolada("El monto del daño debe ser mayor a cero")
        cargo.estado = MAQUINA_CARGO.siguiente(cargo.estado, "aprobar")
        cargo.monto = monto

    # ------------------------------------------------------------------ disputas
    def disputar_cargo(self, cargo_id: str, motivo: str, ahora: datetime) -> None:
        cargo = self._cargo(cargo_id)
        if cargo.disputa is not None:
            raise ReglaNegocioViolada("El cargo ya fue disputado; la resolución es definitiva")
        cargo.estado = MAQUINA_CARGO.siguiente(cargo.estado, "disputar")
        cargo.disputa = Disputa(motivo, ahora)
        self.registrar_evento(CargoDisputado(ahora, self.id, cargo.id, motivo))

    def resolver_disputa(
        self, cargo_id: str, resolucion: str, resuelta_por: str, rol: Rol, ahora: datetime
    ) -> None:
        exigir_rol(rol, {Rol.ADMINISTRACION}, "resolver una disputa")
        if resolucion not in ("CONFIRMADO", "ANULADO"):
            raise ReglaNegocioViolada("La resolución debe ser CONFIRMADO o ANULADO")
        cargo = self._cargo(cargo_id)
        cargo.estado = MAQUINA_CARGO.siguiente(cargo.estado, "confirmar" if resolucion == "CONFIRMADO" else "anular")
        d = cargo.disputa
        cargo.disputa = Disputa(d.motivo, d.fecha, resolucion, resuelta_por)
        self.registrar_evento(DisputaResuelta(ahora, self.id, cargo.id, resolucion))

    # ------------------------------------------------------------------ depósito
    def liberar_deposito(
        self, ahora: datetime, calendario: CalendarioHabil, parametros: ParametrosNegocio
    ) -> None:
        """Se libera a 5 días hábiles de la devolución, sin incidencias."""
        if self.deposito.estado == EstadoDeposito.LIBERADO:
            raise ReglaNegocioViolada("El depósito ya fue liberado")
        if not self.cargos_calculados or self.devuelta_en is None:
            raise ReglaNegocioViolada("Aún no se calculan los cargos de la devolución")
        fecha = calendario.sumar_dias_habiles(self.devuelta_en.date(), parametros.dias_habiles_liberacion_deposito)
        contexto = ContextoDeposito(
            devuelta_en=self.devuelta_en,
            ahora=ahora,
            fecha_liberacion=datetime.combine(fecha, time.min, tzinfo=self.devuelta_en.tzinfo),
            tiene_incidencias=self.tiene_incidencias(),
        )
        spec = deposito_liberable()
        if not spec.es_satisfecha_por(contexto):
            raise ReglaNegocioViolada("El depósito no es liberable: " + ", ".join(spec.fallas(contexto)))
        self.deposito.estado = EstadoDeposito.LIBERADO
        self.deposito.liberado_en = ahora
        self.registrar_evento(DepositoLiberado(ahora, self.id, self.contrato_id, self.deposito.monto.monto))

    def es_elegible_para_liberar(self) -> bool:
        return self.deposito.estado == EstadoDeposito.RETENIDO and self.cargos_calculados
