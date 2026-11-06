"""FlotaAppService (reacciones a eventos y consultas) y LimpiezaAppService (US18)."""
from __future__ import annotations

from collections import Counter

from ..domain.eventos import ContratoAbierto, TareaLimpiezaCompletada, VehiculoDevuelto
from ..domain.limpieza import TareaLimpieza
from ..domain.vehiculo import EstadoVehiculo
from .base import ServicioBase
from .dto import ResumenFlotaDTO, TareaLimpiezaDTO, VehiculoDTO, tarea_dto, vehiculo_dto
from .permisos import exigir
from .puertos import Actor


class FlotaAppService(ServicioBase):
    # handler de ContratoAbierto
    def marcar_rentado(self, evento: ContratoAbierto) -> None:
        with self.ctx.uow_factory() as uow:
            v = uow.vehiculos.obtener(evento.vehiculo_id)
            if v.estado != EstadoVehiculo.ASIGNADO:  # idempotente: ya rentado o más adelante
                return
            v.marcar_rentado()
            uow.vehiculos.guardar(v)
        self._publicar(uow)

    # handler de VehiculoDevuelto
    def registrar_devolucion_vehiculo(self, evento: VehiculoDevuelto) -> None:
        with self.ctx.uow_factory() as uow:
            v = uow.vehiculos.obtener(evento.vehiculo_id)
            if v.estado != EstadoVehiculo.RENTADO:  # idempotente: ya devuelto o más adelante
                return
            devolucion = uow.inspecciones.obtener_devolucion(evento.contrato_id)
            contrato = uow.contratos.obtener(evento.contrato_id)
            v.registrar_devolucion(devolucion.kilometraje, contrato.sucursal_id)
            uow.vehiculos.guardar(v)
        self._publicar(uow)

    # handler de TareaLimpiezaCompletada
    def marcar_disponible(self, evento: TareaLimpiezaCompletada) -> None:
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            v = uow.vehiculos.obtener(evento.vehiculo_id)
            if v.estado != EstadoVehiculo.EN_LIMPIEZA:  # idempotente
                return
            v.marcar_disponible(ahora)
            uow.vehiculos.guardar(v)
        self._publicar(uow)

    def consultar_flota(self, actor: Actor, sucursal_id: str) -> ResumenFlotaDTO:
        exigir(actor, "consultar_flota")
        with self.ctx.uow_factory() as uow:
            uow.sucursales.obtener(sucursal_id)
            vehiculos = uow.vehiculos.listar_por_sucursal(sucursal_id)
        return ResumenFlotaDTO(
            sucursal_id, len(vehiculos),
            dict(Counter(v.estado.value for v in vehiculos)),
            dict(Counter(v.categoria_id for v in vehiculos)),
        )

    def obtener_vehiculo(self, actor: Actor, vehiculo_id: str) -> VehiculoDTO:
        exigir(actor, "consultar_flota")
        with self.ctx.uow_factory() as uow:
            return vehiculo_dto(uow.vehiculos.obtener(vehiculo_id))


class LimpiezaAppService(ServicioBase):
    # handler de VehiculoDevuelto: una tarea abierta por devolución
    def crear_tarea(self, evento: VehiculoDevuelto) -> None:
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            if uow.tareas.buscar_abierta_por_vehiculo(evento.vehiculo_id) is not None:  # idempotente
                return
            tarea = TareaLimpieza(self.ctx.ids.nuevo("LIM"), evento.vehiculo_id, ahora)
            uow.tareas.guardar(tarea)
        self._publicar(uow)

    # US18
    def marcar_vehiculo_listo(self, actor: Actor, tarea_id: str) -> TareaLimpiezaDTO:
        exigir(actor, "marcar_vehiculo_listo")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            tarea = uow.tareas.obtener(tarea_id)
            tarea.completar(actor.id, actor.rol, ahora)
            uow.tareas.guardar(tarea)
        self._publicar(uow)
        return tarea_dto(tarea)

    def listar_abiertas(self, actor: Actor) -> list[TareaLimpiezaDTO]:
        exigir(actor, "marcar_vehiculo_listo")
        with self.ctx.uow_factory() as uow:
            return [tarea_dto(t) for t in uow.tareas.listar_abiertas()]
