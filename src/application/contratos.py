"""ContratoAppService: apertura, extensiones (US11, US12), devolución (US13-US16) y cierre."""
from __future__ import annotations

from datetime import date, timedelta

from ..domain.comun import ConflictoDisponibilidad, ReglaNegocioViolada, TransicionInvalida
from ..domain.contrato import ContratoRenta, EstadoContrato
from ..domain.inspeccion import TipoInspeccion
from ..domain.reservacion import MAQUINA_RESERVACION, EstadoReservacion
from ..domain.valores import CoberturaSeguro, Dinero, Licencia, PeriodoRenta
from ..domain.vehiculo import EstadoVehiculo
from .base import ServicioBase, contrato_id_de
from .dto import ContratoDTO, ExtensionDTO, contrato_dto, extension_dto
from .permisos import exigir, exigir_propietario
from .puertos import Actor
from .reservaciones import unidades_disponibles


class ContratoAppService(ServicioBase):
    def abrir_contrato(
        self, actor: Actor, folio: str, vehiculo_id: str, inspeccion_id: str,
        cobertura_tipo: str | None = None, cobertura_costo_diario: float | None = None,
    ) -> ContratoDTO:
        exigir(actor, "abrir_contrato")
        ahora = self.ctx.reloj.ahora()
        contrato_id = contrato_id_de(folio)
        with self.ctx.uow_factory() as uow:
            reservacion = uow.reservaciones.obtener(folio)
            if not MAQUINA_RESERVACION.puede(reservacion.estado, "marcar_convertida") or \
                    reservacion.estado == EstadoReservacion.EN_LISTA_ESPERA:
                raise TransicionInvalida(f"La reservación en estado {reservacion.estado.value} no puede convertirse en contrato")
            if uow.contratos.existe(contrato_id):
                raise ReglaNegocioViolada("La reservación ya tiene un contrato abierto")
            inspeccion = uow.inspecciones.obtener(inspeccion_id)
            if inspeccion.tipo != TipoInspeccion.ENTREGA or inspeccion.contrato_id != contrato_id:
                raise ReglaNegocioViolada("El checklist no corresponde a la entrega de esta reservación")
            if not inspeccion.esta_firmada:
                raise ReglaNegocioViolada("La entrega exige el checklist firmado por el cliente")
            if inspeccion.vehiculo_id != vehiculo_id:
                raise ReglaNegocioViolada("El vehículo no coincide con el checklist de entrega")
            vehiculo = uow.vehiculos.obtener(vehiculo_id)
            if vehiculo.estado != EstadoVehiculo.ASIGNADO:
                raise ReglaNegocioViolada("Solo un vehículo asignado puede entregarse")
            cliente = uow.clientes.obtener(reservacion.cliente_id)
            categoria = uow.categorias.obtener(reservacion.categoria_efectiva_id)
            cobertura = (
                CoberturaSeguro(cobertura_tipo, Dinero(cobertura_costo_diario or 0)) if cobertura_tipo else None
            )
            referencia = self.ctx.pasarela.retener_deposito(cliente.metodo_pago, categoria.deposito)
            contrato = ContratoRenta.abrir(
                contrato_id, folio, cliente.id, vehiculo_id, categoria.id, reservacion.sucursal_id,
                reservacion.periodo, reservacion.tarifa_diaria,  # upgrade sin costo: tarifa reservada
                categoria.km_incluido_por_dia, categoria.deposito, referencia, inspeccion_id, ahora, cobertura,
            )
            uow.contratos.guardar(contrato)
        self._publicar(uow)
        return contrato_dto(contrato)

    def obtener_contrato(self, actor: Actor, contrato_id: str) -> ContratoDTO:
        exigir(actor, "consultar_contrato")
        with self.ctx.uow_factory() as uow:
            c = uow.contratos.obtener(contrato_id)
            exigir_propietario(actor, c.cliente_id)
            return contrato_dto(c)

    # US11
    def extender_renta(self, actor: Actor, contrato_id: str, horas: int) -> ExtensionDTO:
        exigir(actor, "extender_renta")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            contrato = uow.contratos.obtener(contrato_id)
            self._exigir_disponibilidad(uow, contrato, horas)
            ext = contrato.solicitar_extension(horas, actor.id, actor.rol, ahora, self.ctx.politica_extension)
            uow.contratos.guardar(contrato)
        self._publicar(uow)
        return extension_dto(ext)

    # US12
    def aprobar_extension(self, actor: Actor, contrato_id: str, extension_id: str) -> ExtensionDTO:
        exigir(actor, "aprobar_extension")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            contrato = uow.contratos.obtener(contrato_id)
            horas = next((e.horas for e in contrato.extensiones if e.id == extension_id), None)
            if horas is not None:
                self._exigir_disponibilidad(uow, contrato, horas)
            ext = contrato.aprobar_extension(extension_id, actor.rol, actor.id, ahora)
            uow.contratos.guardar(contrato)
        self._publicar(uow)
        return extension_dto(ext)

    @staticmethod
    def _exigir_disponibilidad(uow, contrato: ContratoRenta, horas: int) -> None:
        """La extensión no puede chocar con reservaciones futuras de la misma categoría."""
        if horas <= 0:
            return
        ventana = PeriodoRenta(contrato.periodo.fin, contrato.periodo.fin + timedelta(hours=horas))
        if unidades_disponibles(uow, contrato.categoria_id, contrato.sucursal_id, ventana) < 1:
            raise ConflictoDisponibilidad("No hay disponibilidad para extender la renta en ese lapso")

    def agregar_conductor_adicional(
        self, actor: Actor, contrato_id: str, nombre: str, licencia_numero: str, licencia_vigencia: date
    ) -> ContratoDTO:
        exigir(actor, "agregar_conductor")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            contrato = uow.contratos.obtener(contrato_id)
            contrato.agregar_conductor_adicional(
                self.ctx.ids.nuevo("CON"), nombre, Licencia(licencia_numero, licencia_vigencia), ahora.date()
            )
            uow.contratos.guardar(contrato)
        return contrato_dto(contrato)

    # US13-US16: el cálculo de cargos lo dispara el evento VehiculoDevuelto
    def procesar_devolucion(self, actor: Actor, contrato_id: str) -> ContratoDTO:
        exigir(actor, "procesar_devolucion")
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            contrato = uow.contratos.obtener(contrato_id)
            if contrato.estado != EstadoContrato.ABIERTO:
                raise TransicionInvalida(f"El contrato en estado {contrato.estado.value} no admite devolución")
            if uow.inspecciones.obtener_devolucion(contrato_id) is None:
                raise ReglaNegocioViolada("Registre primero el checklist de devolución")
            contrato.registrar_devolucion(ahora)
            uow.contratos.guardar(contrato)
        self._publicar(uow)
        return contrato_dto(contrato)

    # handler de DepositoLiberado
    def cerrar_contrato(self, contrato_id: str) -> None:
        ahora = self.ctx.reloj.ahora()
        with self.ctx.uow_factory() as uow:
            contrato = uow.contratos.obtener(contrato_id)
            if contrato.estado == EstadoContrato.CERRADO:  # idempotente
                return
            contrato.cerrar(ahora)
            uow.contratos.guardar(contrato)
        self._publicar(uow)
