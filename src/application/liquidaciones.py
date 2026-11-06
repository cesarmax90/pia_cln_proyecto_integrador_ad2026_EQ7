"""LiquidacionAppService: apertura, cálculo de cargos (US14-US16), disputas (US17), depósito (US20)."""
from __future__ import annotations

from ..domain.comun import ReglaNegocioViolada, TransicionInvalida
from ..domain.eventos import ContratoAbierto, VehiculoDevuelto
from ..domain.liquidacion import Liquidacion
from ..domain.valores import Dinero, ReferenciaPago
from .base import ServicioBase, contrato_id_de, folio_de, liquidacion_id_de
from .dto import LiquidacionDTO, liquidacion_dto
from .permisos import exigir, exigir_propietario
from .puertos import Actor


class LiquidacionAppService(ServicioBase):
    # handler de ContratoAbierto
    def abrir_liquidacion(self, evento: ContratoAbierto) -> None:
        with self.ctx.uow_factory() as uow:
            if uow.liquidaciones.obtener_por_contrato(evento.contrato_id) is not None:  # idempotente
                return
            liquidacion = Liquidacion.abrir(
                liquidacion_id_de(evento.contrato_id), evento.contrato_id,
                Dinero(evento.deposito_monto), ReferenciaPago(evento.referencia_pago),
            )
            uow.liquidaciones.guardar(liquidacion)
        self._publicar(uow)

    # handler de VehiculoDevuelto (US14, US15, US16)
    def calcular_cargos(self, evento: VehiculoDevuelto) -> None:
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            contrato = uow.contratos.obtener(evento.contrato_id)
            entrega = uow.inspecciones.obtener_entrega(evento.contrato_id)
            devolucion = uow.inspecciones.obtener_devolucion(evento.contrato_id)
            liquidacion = uow.liquidaciones.obtener_por_contrato(evento.contrato_id)
            if entrega is None or devolucion is None or liquidacion is None:
                raise ReglaNegocioViolada("Faltan checklists o liquidación para calcular cargos")
            cambio = liquidacion.calcular_cargos(
                devolucion.comparar_contra(entrega), contrato.condiciones(), self.ctx.politica_cargos, ahora
            )
            if cambio:
                uow.liquidaciones.guardar(liquidacion)
        self._publicar(uow)

    def obtener_liquidacion(self, actor: Actor, contrato_id: str) -> LiquidacionDTO:
        exigir(actor, "consultar_liquidacion")
        with self.ctx.uow_factory() as uow:
            contrato = uow.contratos.obtener(contrato_id)
            exigir_propietario(actor, contrato.cliente_id)
            liquidacion = uow.liquidaciones.obtener_por_contrato(contrato_id)
            if liquidacion is None:
                raise ReglaNegocioViolada("El contrato aún no tiene liquidación")
            return liquidacion_dto(liquidacion)

    def _modificar(self, contrato_id: str, operacion) -> Liquidacion:
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            liquidacion = uow.liquidaciones.obtener_por_contrato(contrato_id)
            if liquidacion is None:
                raise ReglaNegocioViolada("El contrato aún no tiene liquidación")
            operacion(liquidacion, uow, ahora)
            uow.liquidaciones.guardar(liquidacion)
        self._publicar(uow)
        return liquidacion

    def aprobar_cargo_danio(self, actor: Actor, contrato_id: str, cargo_id: str, monto) -> LiquidacionDTO:
        exigir(actor, "aprobar_cargo_danio")
        liq = self._modificar(
            contrato_id, lambda liq, uow, ahora: liq.aprobar_cargo_danio(cargo_id, Dinero(monto), actor.rol)
        )
        return liquidacion_dto(liq)

    def disputar_cargo(self, actor: Actor, contrato_id: str, cargo_id: str, motivo: str) -> LiquidacionDTO:
        exigir(actor, "disputar_cargo")

        def operacion(liq, uow, ahora):
            exigir_propietario(actor, uow.contratos.obtener(contrato_id).cliente_id)
            liq.disputar_cargo(cargo_id, motivo, ahora)

        return liquidacion_dto(self._modificar(contrato_id, operacion))

    def resolver_disputa(self, actor: Actor, contrato_id: str, cargo_id: str, resolucion: str) -> LiquidacionDTO:
        exigir(actor, "resolver_disputa")
        liq = self._modificar(
            contrato_id,
            lambda liq, uow, ahora: liq.resolver_disputa(cargo_id, resolucion, actor.id, actor.rol, ahora),
        )
        return liquidacion_dto(liq)

    # US20 (job diario)
    def liberar_depositos(self, actor: Actor) -> list[str]:
        exigir(actor, "liberar_depositos")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            ids = uow.liquidaciones.buscar_elegibles_liberar()
        liberadas = []
        for liquidacion_id in ids:
            try:
                with self.ctx.uow_factory() as uow:  # una transacción por Aggregate
                    liq = uow.liquidaciones.obtener(liquidacion_id)
                    liq.liberar_deposito(ahora, self.ctx.calendario, self.ctx.parametros)
                    self.ctx.pasarela.liberar_deposito(liq.deposito.referencia)
                    uow.liquidaciones.guardar(liq)
                self._publicar(uow)
                liberadas.append(liquidacion_id)
            except (ReglaNegocioViolada, TransicionInvalida):
                continue
        return liberadas


__all__ = ["LiquidacionAppService", "contrato_id_de", "folio_de"]
