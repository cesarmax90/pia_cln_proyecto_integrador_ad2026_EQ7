"""InspeccionAppService: US06, US07, US13, US17 (consulta de evidencia)."""
from __future__ import annotations

from ..domain.comun import ReglaNegocioViolada
from ..domain.contrato import EstadoContrato
from ..domain.inspeccion import InspeccionVehiculo, TipoInspeccion
from ..domain.reservacion import EstadoReservacion
from ..domain.valores import FirmaDigital, Kilometraje, NivelCombustible, RegistroDanio
from ..domain.vehiculo import EstadoVehiculo
from .base import ServicioBase, contrato_id_de, folio_de, liquidacion_id_de
from .comandos import DanioCmd, FotoCmd
from .dto import EvidenciaDisputaDTO, InspeccionDTO, _danio, inspeccion_dto
from .permisos import exigir, exigir_propietario
from .puertos import Actor


class InspeccionAppService(ServicioBase):
    def _danios(self, carpeta: str, danios: list[DanioCmd], ahora) -> tuple[RegistroDanio, ...]:
        return tuple(
            RegistroDanio(d.zona, d.descripcion, self._guardar_fotos(carpeta, d.fotos, ahora)) for d in danios
        )

    # US06
    def registrar_inspeccion_entrega(
        self, actor: Actor, folio: str, vehiculo_id: str, combustible_octavos: int, kilometraje: int,
        fotos: list[FotoCmd], danios: list[DanioCmd],
    ) -> InspeccionDTO:
        exigir(actor, "registrar_inspeccion")
        ahora = self.ctx.reloj.ahora()
        contrato_id = contrato_id_de(folio)
        with self.ctx.uow_factory() as uow:
            reservacion = uow.reservaciones.obtener(folio)
            if reservacion.estado not in (EstadoReservacion.CREADA, EstadoReservacion.UPGRADE_ACEPTADO):
                raise ReglaNegocioViolada(f"La reservación en estado {reservacion.estado.value} no admite entrega")
            vehiculo = uow.vehiculos.obtener(vehiculo_id)
            if vehiculo.estado != EstadoVehiculo.ASIGNADO or vehiculo.categoria_id != reservacion.categoria_efectiva_id:
                raise ReglaNegocioViolada("El vehículo no está asignado a esta entrega")
            if uow.inspecciones.obtener_entrega(contrato_id) is not None:
                raise ReglaNegocioViolada("Ya existe un checklist de entrega para este contrato")
            id_insp = self.ctx.ids.nuevo("INS")
            inspeccion = InspeccionVehiculo.registrar(
                id_insp, contrato_id, vehiculo_id, TipoInspeccion.ENTREGA, actor.id,
                NivelCombustible(combustible_octavos), Kilometraje(kilometraje),
                self._guardar_fotos(id_insp, fotos, ahora), self._danios(id_insp, danios, ahora), ahora,
            )
            uow.inspecciones.guardar(inspeccion)
        self._publicar(uow)
        return inspeccion_dto(inspeccion)

    # US07
    def firmar_inspeccion_entrega(self, actor: Actor, inspeccion_id: str, firmante: str) -> InspeccionDTO:
        exigir(actor, "firmar_inspeccion_entrega")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            inspeccion = uow.inspecciones.obtener(inspeccion_id)
            if inspeccion.tipo != TipoInspeccion.ENTREGA:
                raise ReglaNegocioViolada("Solo se firma el checklist de entrega")
            reservacion = uow.reservaciones.obtener(folio_de(inspeccion.contrato_id))
            exigir_propietario(actor, reservacion.cliente_id)
            inspeccion.firmar(FirmaDigital(firmante, ahora), ahora)
            uow.inspecciones.guardar(inspeccion)
        self._publicar(uow)
        return inspeccion_dto(inspeccion)

    # US13
    def registrar_inspeccion_devolucion(
        self, actor: Actor, contrato_id: str, combustible_octavos: int, kilometraje: int,
        fotos: list[FotoCmd], danios: list[DanioCmd],
    ) -> InspeccionDTO:
        exigir(actor, "registrar_inspeccion")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            contrato = uow.contratos.obtener(contrato_id)
            if contrato.estado != EstadoContrato.ABIERTO:
                raise ReglaNegocioViolada("Solo un contrato abierto admite checklist de devolución")
            entrega = uow.inspecciones.obtener_entrega(contrato_id)
            if entrega is None:
                raise ReglaNegocioViolada("El contrato no tiene checklist de entrega")
            if uow.inspecciones.obtener_devolucion(contrato_id) is not None:
                raise ReglaNegocioViolada("Ya existe un checklist de devolución para este contrato")
            Kilometraje(kilometraje).recorrido_desde(entrega.kilometraje)  # valida que no retroceda
            id_insp = self.ctx.ids.nuevo("INS")
            inspeccion = InspeccionVehiculo.registrar(
                id_insp, contrato_id, contrato.vehiculo_id, TipoInspeccion.DEVOLUCION, actor.id,
                NivelCombustible(combustible_octavos), Kilometraje(kilometraje),
                self._guardar_fotos(id_insp, fotos, ahora), self._danios(id_insp, danios, ahora), ahora,
            )
            uow.inspecciones.guardar(inspeccion)
        self._publicar(uow)
        return inspeccion_dto(inspeccion)

    # US17 (solo lectura)
    def consultar_evidencia_disputa(self, actor: Actor, contrato_id: str, cargo_id: str) -> EvidenciaDisputaDTO:
        exigir(actor, "consultar_evidencia")
        with self.ctx.uow_factory() as uow:
            liquidacion = uow.liquidaciones.obtener_por_contrato(contrato_id)
            if liquidacion is None or all(c.id != cargo_id for c in liquidacion.cargos):
                raise ReglaNegocioViolada(f"El cargo {cargo_id} no existe en la liquidación de {contrato_id}")
            entrega = uow.inspecciones.obtener_entrega(contrato_id)
            devolucion = uow.inspecciones.obtener_devolucion(contrato_id)
            if entrega is None or devolucion is None:
                raise ReglaNegocioViolada("Faltan checklists para comparar la evidencia")
            diferencias = devolucion.comparar_contra(entrega)
            return EvidenciaDisputaDTO(
                contrato_id, cargo_id, inspeccion_dto(entrega), inspeccion_dto(devolucion),
                [_danio(d) for d in diferencias.danios_nuevos],
            )


__all__ = ["InspeccionAppService", "liquidacion_id_de"]
