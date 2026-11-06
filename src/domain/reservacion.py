"""Aggregate Reservacion: garantiza categoría, no unidad."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .catalogo import CategoriaVehiculo
from .comun import RaizAgregado, ReglaNegocioViolada, Rol, exigir_rol
from .eventos import (
    ReservacionCancelada,
    ReservacionCreada,
    ReservacionLiberadaPorNoShow,
    UpgradeCortesiaOtorgado,
    UpgradeOfrecido,
    UpgradeRechazado,
)
from .maquina_estados import MaquinaEstados
from .politicas import PoliticaCancelacion, ResultadoCancelacion
from .valores import Dinero, PeriodoRenta


class EstadoReservacion(str, Enum):
    CREADA = "CREADA"
    UPGRADE_OFRECIDO = "UPGRADE_OFRECIDO"
    UPGRADE_ACEPTADO = "UPGRADE_ACEPTADO"
    EN_LISTA_ESPERA = "EN_LISTA_ESPERA"
    CANCELADA = "CANCELADA"
    LIBERADA_NO_SHOW = "LIBERADA_NO_SHOW"
    CONVERTIDA = "CONVERTIDA"


class OpcionRechazoUpgrade(str, Enum):
    LISTA_ESPERA = "LISTA_ESPERA"
    REEMBOLSO = "REEMBOLSO"


R = EstadoReservacion
_ACTIVAS = (R.CREADA, R.UPGRADE_OFRECIDO, R.UPGRADE_ACEPTADO, R.EN_LISTA_ESPERA)
_TRANSICIONES = {
    (R.CREADA, "proponer_upgrade"): R.UPGRADE_OFRECIDO,
    (R.UPGRADE_OFRECIDO, "aceptar_upgrade"): R.UPGRADE_ACEPTADO,
    (R.UPGRADE_OFRECIDO, "rechazar_a_lista_espera"): R.EN_LISTA_ESPERA,
    (R.UPGRADE_OFRECIDO, "rechazar_con_reembolso"): R.CANCELADA,
    (R.CREADA, "otorgar_upgrade_cortesia"): R.UPGRADE_ACEPTADO,
    (R.UPGRADE_OFRECIDO, "otorgar_upgrade_cortesia"): R.UPGRADE_ACEPTADO,
    (R.EN_LISTA_ESPERA, "otorgar_upgrade_cortesia"): R.UPGRADE_ACEPTADO,
    (R.CREADA, "marcar_convertida"): R.CONVERTIDA,
    (R.UPGRADE_ACEPTADO, "marcar_convertida"): R.CONVERTIDA,
    (R.EN_LISTA_ESPERA, "marcar_convertida"): R.CONVERTIDA,
}
for _est in _ACTIVAS:
    _TRANSICIONES[(_est, "cancelar")] = R.CANCELADA
    _TRANSICIONES[(_est, "liberar_no_show")] = R.LIBERADA_NO_SHOW
MAQUINA_RESERVACION = MaquinaEstados("Reservacion", _TRANSICIONES)
ESTADOS_ACTIVOS = tuple(e.value for e in _ACTIVAS)


@dataclass
class Reservacion(RaizAgregado):
    folio: str
    cliente_id: str
    categoria_id: str
    sucursal_id: str
    periodo: PeriodoRenta
    tarifa_diaria: Dinero
    estado: EstadoReservacion = EstadoReservacion.CREADA
    categoria_asignada_id: str | None = None
    penalizacion: Dinero | None = None

    @classmethod
    def crear(
        cls, folio: str, cliente_id: str, categoria: CategoriaVehiculo, sucursal_id: str,
        periodo: PeriodoRenta, ahora: datetime,
    ) -> Reservacion:
        if not categoria.habilitada:
            raise ReglaNegocioViolada("La categoría solicitada no está habilitada")
        if periodo.inicio <= ahora:
            raise ReglaNegocioViolada("La reservación debe iniciar en el futuro")
        r = cls(folio, cliente_id, categoria.id, sucursal_id, periodo, categoria.tarifa_diaria)
        r.registrar_evento(ReservacionCreada(ahora, folio, cliente_id, categoria.id, sucursal_id))
        return r

    @property
    def categoria_efectiva_id(self) -> str:
        return self.categoria_asignada_id or self.categoria_id

    @property
    def esta_activa(self) -> bool:
        return self.estado in _ACTIVAS

    # ------------------------------------------------------------------ cancelación y no-show
    def cancelar(self, ahora: datetime, rol: Rol, politica: PoliticaCancelacion) -> ResultadoCancelacion:
        exigir_rol(rol, {Rol.CLIENTE, Rol.AGENTE, Rol.ADMINISTRACION, Rol.SISTEMA}, "cancelar una reservación")
        self.estado = MAQUINA_RESERVACION.siguiente(self.estado, "cancelar")
        resultado = politica.evaluar(self.periodo.inicio, ahora, self.tarifa_diaria)
        self.penalizacion = resultado.penalizacion
        self.registrar_evento(
            ReservacionCancelada(ahora, self.folio, resultado.penalizada, resultado.penalizacion.monto)
        )
        return resultado

    def liberar_por_no_show(self, ahora: datetime, politica: PoliticaCancelacion) -> None:
        """Se libera a las 2 h del inicio si el cliente no se presentó."""
        if not politica.no_show_vencido(self.periodo.inicio, ahora):
            raise ReglaNegocioViolada("Aún no vence la ventana de no-show")
        self.estado = MAQUINA_RESERVACION.siguiente(self.estado, "liberar_no_show")
        self.registrar_evento(
            ReservacionLiberadaPorNoShow(ahora, self.folio, self.categoria_efectiva_id, self.sucursal_id)
        )

    # ------------------------------------------------------------------ upgrade
    def proponer_upgrade(
        self, actual: CategoriaVehiculo, superior: CategoriaVehiculo, ahora: datetime
    ) -> None:
        """Upgrade solo a la categoría inmediata superior, sin costo (falta de unidad)."""
        if actual.id != self.categoria_id:
            raise ReglaNegocioViolada("La categoría actual no corresponde a la reservación")
        if not superior.habilitada or superior.nivel <= actual.nivel:
            raise ReglaNegocioViolada("El upgrade debe ser a una categoría superior habilitada")
        self.estado = MAQUINA_RESERVACION.siguiente(self.estado, "proponer_upgrade")
        self.categoria_asignada_id = superior.id
        self.registrar_evento(UpgradeOfrecido(ahora, self.folio, superior.id))

    def aceptar_upgrade(self) -> None:
        self.estado = MAQUINA_RESERVACION.siguiente(self.estado, "aceptar_upgrade")

    def rechazar_upgrade(self, opcion: OpcionRechazoUpgrade, ahora: datetime) -> None:
        evento = (
            "rechazar_a_lista_espera" if opcion == OpcionRechazoUpgrade.LISTA_ESPERA else "rechazar_con_reembolso"
        )
        self.estado = MAQUINA_RESERVACION.siguiente(self.estado, evento)
        self.categoria_asignada_id = None
        self.registrar_evento(UpgradeRechazado(ahora, self.folio, opcion.value))

    def otorgar_upgrade_cortesia(
        self, superior: CategoriaVehiculo, rol: Rol, autorizado_por: str, ahora: datetime
    ) -> None:
        """Upgrade de cortesía: solo Administración, fuera del flujo automático."""
        exigir_rol(rol, {Rol.ADMINISTRACION}, "otorgar un upgrade de cortesía")
        if not superior.habilitada:
            raise ReglaNegocioViolada("La categoría superior no está habilitada")
        self.estado = MAQUINA_RESERVACION.siguiente(self.estado, "otorgar_upgrade_cortesia")
        self.categoria_asignada_id = superior.id
        self.registrar_evento(UpgradeCortesiaOtorgado(ahora, self.folio, superior.id, autorizado_por))

    def marcar_convertida(self) -> None:
        self.estado = MAQUINA_RESERVACION.siguiente(self.estado, "marcar_convertida")
