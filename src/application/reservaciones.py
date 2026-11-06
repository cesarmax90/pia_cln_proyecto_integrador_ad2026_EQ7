"""ReservacionAppService: US01, US02, US03, US04, US09, US10."""
from __future__ import annotations

from datetime import datetime

from ..domain.comun import ConflictoDisponibilidad, ReglaNegocioViolada, TransicionInvalida
from ..domain.politicas import PoliticaUpgrade, ServicioDisponibilidad
from ..domain.reservacion import MAQUINA_RESERVACION, EstadoReservacion, OpcionRechazoUpgrade, Reservacion
from ..domain.valores import PeriodoRenta
from .base import ServicioBase
from .dto import CancelacionDTO, DisponibilidadDTO, ReservacionDTO, reservacion_dto
from .permisos import exigir, exigir_propietario
from .puertos import Actor

RESPUESTAS_UPGRADE = ("ACEPTAR", "RECHAZAR_LISTA_ESPERA", "RECHAZAR_REEMBOLSO")


def unidades_disponibles(uow, categoria_id: str, sucursal_id: str, periodo: PeriodoRenta) -> int:
    return ServicioDisponibilidad.unidades_disponibles(
        uow.vehiculos.contar_flota(categoria_id, sucursal_id),
        uow.reservaciones.contar_traslapadas(categoria_id, sucursal_id, periodo),
        uow.contratos.contar_traslapados(categoria_id, sucursal_id, periodo),
    )


class ReservacionAppService(ServicioBase):
    # US01
    def buscar_disponibilidad(
        self, actor: Actor, sucursal_id: str, inicio: datetime, fin: datetime, categoria_id: str | None = None
    ) -> list[DisponibilidadDTO]:
        exigir(actor, "buscar_disponibilidad")
        periodo = PeriodoRenta(inicio, fin)
        with self.ctx.uow_factory() as uow:
            uow.sucursales.obtener(sucursal_id)
            categorias = (
                [uow.categorias.obtener(categoria_id)]
                if categoria_id
                else [c for c in uow.categorias.listar() if c.habilitada]
            )
            return [
                DisponibilidadDTO(c.id, c.nombre, c.tarifa_diaria.monto, unidades_disponibles(uow, c.id, sucursal_id, periodo))
                for c in categorias
            ]

    # US02
    def crear_reservacion(
        self, actor: Actor, cliente_id: str, categoria_id: str, sucursal_id: str, inicio: datetime, fin: datetime
    ) -> ReservacionDTO:
        exigir(actor, "crear_reservacion")
        exigir_propietario(actor, cliente_id)
        ahora = self.ctx.reloj.ahora()
        periodo = PeriodoRenta(inicio, fin)
        with self.ctx.uow_factory() as uow:
            cliente = uow.clientes.obtener(cliente_id)
            if not cliente.activo:
                raise ReglaNegocioViolada("El cliente no está activo")
            categoria = uow.categorias.obtener(categoria_id)
            if not categoria.habilitada:
                raise ReglaNegocioViolada("La categoría solicitada no está habilitada")
            uow.sucursales.obtener(sucursal_id)
            if unidades_disponibles(uow, categoria.id, sucursal_id, periodo) < 1:
                raise ConflictoDisponibilidad("No hay unidades disponibles de la categoría en ese periodo")
            reservacion = Reservacion.crear(
                self.ctx.ids.nuevo("RES"), cliente.id, categoria, sucursal_id, periodo, ahora
            )
            uow.reservaciones.guardar(reservacion)
        self._publicar(uow)
        return reservacion_dto(reservacion)

    def obtener_reservacion(self, actor: Actor, folio: str) -> ReservacionDTO:
        exigir(actor, "buscar_disponibilidad")
        with self.ctx.uow_factory() as uow:
            r = uow.reservaciones.obtener(folio)
            exigir_propietario(actor, r.cliente_id)
            return reservacion_dto(r)

    # US03
    def cancelar_reservacion(self, actor: Actor, folio: str) -> CancelacionDTO:
        exigir(actor, "cancelar_reservacion")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            r = uow.reservaciones.obtener(folio)
            exigir_propietario(actor, r.cliente_id)
            resultado = r.cancelar(ahora, actor.rol, self.ctx.politica_cancelacion)
            uow.reservaciones.guardar(r)
        self._publicar(uow)
        return CancelacionDTO(folio, r.estado.value, resultado.penalizada, resultado.penalizacion.monto)

    # US04 (job)
    def liberar_no_shows(self, actor: Actor) -> list[str]:
        exigir(actor, "liberar_no_shows")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            folios = uow.reservaciones.buscar_vencidas_no_show(ahora, self.ctx.parametros.horas_no_show)
        liberados = []
        for folio in folios:
            try:
                with self.ctx.uow_factory() as uow:  # una transacción por Aggregate
                    r = uow.reservaciones.obtener(folio)
                    r.liberar_por_no_show(ahora, self.ctx.politica_cancelacion)
                    uow.reservaciones.guardar(r)
                self._publicar(uow)
                liberados.append(folio)
            except (ReglaNegocioViolada, TransicionInvalida):
                continue
        return liberados

    # US09
    def responder_upgrade(self, actor: Actor, folio: str, respuesta: str) -> ReservacionDTO:
        exigir(actor, "responder_upgrade")
        if respuesta not in RESPUESTAS_UPGRADE:
            raise ReglaNegocioViolada(f"Respuesta inválida; use una de: {', '.join(RESPUESTAS_UPGRADE)}")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            r = uow.reservaciones.obtener(folio)
            exigir_propietario(actor, r.cliente_id)
            if respuesta == "ACEPTAR":
                r.aceptar_upgrade()
            else:
                opcion = (
                    OpcionRechazoUpgrade.LISTA_ESPERA if respuesta == "RECHAZAR_LISTA_ESPERA"
                    else OpcionRechazoUpgrade.REEMBOLSO
                )
                r.rechazar_upgrade(opcion, ahora)
            uow.reservaciones.guardar(r)
        self._publicar(uow)
        return reservacion_dto(r)

    # US10
    def otorgar_upgrade_cortesia(self, actor: Actor, folio: str) -> ReservacionDTO:
        exigir(actor, "otorgar_upgrade_cortesia")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            r = uow.reservaciones.obtener(folio)
            actual = uow.categorias.obtener(r.categoria_id)
            superior = PoliticaUpgrade.categoria_superior(actual, uow.categorias.listar())
            if superior is None:
                raise ReglaNegocioViolada("No existe una categoría superior habilitada")
            r.otorgar_upgrade_cortesia(superior, actor.rol, actor.id, ahora)
            uow.reservaciones.guardar(r)
        self._publicar(uow)
        return reservacion_dto(r)

    # handler de ContratoAbierto
    def marcar_convertida(self, folio: str) -> None:
        with self.ctx.uow_factory() as uow:
            r = uow.reservaciones.obtener(folio)
            if r.estado == EstadoReservacion.CONVERTIDA:  # idempotente
                return
            r.marcar_convertida()
            uow.reservaciones.guardar(r)
        self._publicar(uow)


def estado_permite_entrega(r: Reservacion) -> bool:
    return MAQUINA_RESERVACION.puede(r.estado, "marcar_convertida") and r.estado != EstadoReservacion.EN_LISTA_ESPERA


def exigir_estado_entregable(r: Reservacion) -> None:
    if r.estado == EstadoReservacion.UPGRADE_OFRECIDO:
        raise ReglaNegocioViolada("El cliente debe responder primero la oferta de upgrade")
    if not estado_permite_entrega(r):
        raise TransicionInvalida(f"La reservación en estado {r.estado.value} no puede entregarse")
