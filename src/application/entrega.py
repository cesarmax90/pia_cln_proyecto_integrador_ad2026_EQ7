"""EntregaAppService.iniciar_entrega: US05 (validación) y US08 (upgrade por falta de unidad)."""
from __future__ import annotations

from ..domain.comun import ConflictoDisponibilidad, ReglaNegocioViolada
from ..domain.politicas import PoliticaUpgrade, ServicioDisponibilidad
from ..domain.reservacion import EstadoReservacion
from .base import ServicioBase
from .dto import EntregaDTO
from .permisos import exigir
from .puertos import Actor
from .reservaciones import exigir_estado_entregable, unidades_disponibles


class EntregaAppService(ServicioBase):
    def iniciar_entrega(self, actor: Actor, folio: str, licencia_numero: str) -> EntregaDTO:
        exigir(actor, "iniciar_entrega")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            reservacion = uow.reservaciones.obtener(folio)
            exigir_estado_entregable(reservacion)
            cliente = uow.clientes.obtener(reservacion.cliente_id)

            # US05: documentos y método de pago (reglas en Cliente; aquí solo se coordina)
            if cliente.licencia.numero != licencia_numero:
                raise ReglaNegocioViolada("La licencia presentada no coincide con la del cliente")
            if cliente.metodo_pago is None or not self.ctx.pasarela.verificar_tarjeta(cliente.metodo_pago):
                raise ReglaNegocioViolada("El método de pago no es válido")
            if not cliente.puede_rentar(ahora.date()):
                raise ReglaNegocioViolada("Cliente no apto: " + ", ".join(cliente.motivos_no_apto(ahora.date())))

            categoria_id = reservacion.categoria_efectiva_id
            unidad = ServicioDisponibilidad.asignar_unidad(
                uow.vehiculos.buscar_disponibles(categoria_id, reservacion.sucursal_id)
            )
            if unidad is not None:
                unidad.asignar_a_entrega()
                uow.vehiculos.guardar(unidad)
                resultado = EntregaDTO(folio, unidad.id, False, None, "Unidad asignada; registre el checklist de entrega")
            else:
                resultado = self._ofrecer_upgrade(uow, reservacion, ahora)
        self._publicar(uow)
        return resultado

    def _ofrecer_upgrade(self, uow, reservacion, ahora) -> EntregaDTO:
        """US08: sin unidad en la categoría reservada, se propone la inmediata superior sin costo."""
        if reservacion.estado != EstadoReservacion.CREADA:
            raise ConflictoDisponibilidad("No hay unidades disponibles en la categoría asignada")
        actual = uow.categorias.obtener(reservacion.categoria_id)
        superior = PoliticaUpgrade.categoria_superior(actual, uow.categorias.listar())
        if superior is None or not uow.vehiculos.buscar_disponibles(superior.id, reservacion.sucursal_id):
            raise ConflictoDisponibilidad("No hay unidades en la categoría reservada ni en la superior")
        reservacion.proponer_upgrade(actual, superior, ahora)
        uow.reservaciones.guardar(reservacion)
        return EntregaDTO(
            reservacion.folio, None, True, superior.id,
            f"Sin unidad en {actual.nombre}: se ofrece upgrade sin costo a {superior.nombre}",
        )


__all__ = ["EntregaAppService", "unidades_disponibles"]
