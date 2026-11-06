"""Pruebas de integración de los Application Services (SQLite en memoria + bus de eventos real)."""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from src.application.comandos import FotoCmd
from src.application.puertos import Actor
from src.domain import eventos as ev
from src.domain.comun import (
    ConflictoDisponibilidad,
    ErrorValidacion,
    NoEncontrado,
    PermisoDenegado,
    ReglaNegocioViolada,
    Rol,
    TransicionInvalida,
)
from src.domain.valores import Kilometraje

from .escenario import ADMIN, AGENTE, AHORA, CLIENTE, INICIO, LIMPIEZA, OTRO_CLIENTE, PATIO, SISTEMA, danio, fotos

H = timedelta


def evento(servicios, tipo):
    return next(e for e in servicios.ctx.bus.historial if isinstance(e, tipo))


class TestReservaciones:
    def test_disponibilidad_descuenta_reservaciones_activas(self, servicios, flujo):
        d = servicios.reservaciones.buscar_disponibilidad(CLIENTE, "SUC-MTY", INICIO, INICIO + H(days=2), "ECO")
        assert d[0].disponibles == 2
        flujo.reservar()
        d = servicios.reservaciones.buscar_disponibilidad(CLIENTE, "SUC-MTY", INICIO, INICIO + H(days=2), "ECO")
        assert d[0].disponibles == 1
        todas = servicios.reservaciones.buscar_disponibilidad(CLIENTE, "SUC-MTY", INICIO, INICIO + H(days=2))
        assert [x.categoria_id for x in todas] == ["ECO", "COMP", "SUV"]  # PREM está deshabilitada

    def test_periodos_que_no_se_traslapan_no_restan(self, servicios, flujo):
        flujo.reservar()
        despues = servicios.reservaciones.buscar_disponibilidad(CLIENTE, "SUC-MTY", INICIO + H(days=2), INICIO + H(days=4), "ECO")
        assert despues[0].disponibles == 2

    def test_sin_unidades_no_se_puede_reservar(self, servicios, flujo):
        flujo.reservar("C1")
        flujo.reservar("C6")
        with pytest.raises(ConflictoDisponibilidad):
            flujo.reservar("C1")

    def test_validaciones_de_entrada(self, servicios, flujo):
        with pytest.raises(NoEncontrado):
            servicios.reservaciones.buscar_disponibilidad(CLIENTE, "SUC-XXX", INICIO, INICIO + H(days=1))
        with pytest.raises(ReglaNegocioViolada):
            flujo.reservar("C2")  # cliente inactivo
        with pytest.raises(ReglaNegocioViolada):
            flujo.reservar(categoria="PREM")  # categoría deshabilitada
        with pytest.raises(ReglaNegocioViolada):
            flujo.reservar(inicio=AHORA - H(hours=1))
        with pytest.raises(ErrorValidacion):
            servicios.reservaciones.crear_reservacion(CLIENTE, "C1", "ECO", "SUC-MTY", INICIO, INICIO - H(days=1))

    def test_un_cliente_no_reserva_ni_consulta_a_nombre_de_otro(self, servicios, flujo):
        with pytest.raises(PermisoDenegado):
            servicios.reservaciones.crear_reservacion(OTRO_CLIENTE, "C1", "ECO", "SUC-MTY", INICIO, INICIO + H(days=1))
        folio = flujo.reservar().folio
        with pytest.raises(PermisoDenegado):
            servicios.reservaciones.obtener_reservacion(OTRO_CLIENTE, folio)
        with pytest.raises(PermisoDenegado):
            servicios.reservaciones.cancelar_reservacion(OTRO_CLIENTE, folio)
        assert servicios.reservaciones.obtener_reservacion(AGENTE, folio).cliente_id == "C1"

    def test_cancelacion_gratuita_y_tardia(self, servicios, flujo):
        r = flujo.reservar(inicio=INICIO + H(days=1))  # faltan 47 h
        resultado = servicios.reservaciones.cancelar_reservacion(CLIENTE, r.folio)
        assert not resultado.penalizada and resultado.estado == "CANCELADA"
        r2 = flujo.reservar("C6")
        flujo.reloj.establecer(INICIO - H(hours=3))
        tardia = servicios.reservaciones.cancelar_reservacion(OTRO_CLIENTE, r2.folio)
        assert tardia.penalizada and tardia.penalizacion == Decimal("500.00")
        with pytest.raises(TransicionInvalida):
            servicios.reservaciones.cancelar_reservacion(OTRO_CLIENTE, r2.folio)

    def test_cancelar_libera_la_disponibilidad(self, servicios, flujo):
        r = flujo.reservar()
        servicios.reservaciones.cancelar_reservacion(CLIENTE, r.folio)
        d = servicios.reservaciones.buscar_disponibilidad(CLIENTE, "SUC-MTY", INICIO, INICIO + H(days=2), "ECO")
        assert d[0].disponibles == 2

    def test_job_de_no_show_libera_solo_las_vencidas(self, servicios, flujo):
        vencida, vigente = flujo.reservar(), flujo.reservar("C6", inicio=INICIO + H(days=1))
        flujo.reloj.establecer(INICIO + H(hours=1, minutes=59))
        assert servicios.reservaciones.liberar_no_shows(SISTEMA) == []
        flujo.reloj.establecer(INICIO + H(hours=2))
        assert servicios.reservaciones.liberar_no_shows(SISTEMA) == [vencida.folio]
        assert servicios.reservaciones.obtener_reservacion(AGENTE, vencida.folio).estado == "LIBERADA_NO_SHOW"
        assert servicios.reservaciones.obtener_reservacion(AGENTE, vigente.folio).estado == "CREADA"
        assert servicios.reservaciones.liberar_no_shows(SISTEMA) == []  # no repite

    def test_las_notificaciones_se_envian_por_el_bus(self, servicios, flujo):
        flujo.reservar()
        assert any(isinstance(e, ev.ReservacionCreada) for e in servicios.ctx.notificaciones.enviadas)


class TestEntregaYUpgrade:
    def test_entrega_asigna_la_unidad_con_menos_km(self, servicios, flujo):
        with servicios.ctx.uow_factory() as uow:
            v = uow.vehiculos.obtener("VEH-ECO-1")
            v.kilometraje = Kilometraje(5000)
            uow.vehiculos.guardar(v)
        folio = flujo.reservar().folio
        flujo.reloj.establecer(INICIO)
        ent = servicios.entrega.iniciar_entrega(AGENTE, folio, "LIC-C1")
        assert ent.vehiculo_id == "VEH-ECO-2" and not ent.requiere_upgrade
        assert servicios.flota.obtener_vehiculo(AGENTE, "VEH-ECO-2").estado == "ASIGNADO"

    @pytest.mark.parametrize("cliente_id, licencia, mensaje", [
        ("C1", "OTRA", "no coincide"), ("C4", "LIC-C4", "método de pago"), ("C3", "LIC-C3", "Cliente no apto"),
    ])
    def test_validacion_de_documentos_y_pago(self, servicios, flujo, cliente_id, licencia, mensaje):
        folio = flujo.reservar(cliente_id).folio
        with pytest.raises(ReglaNegocioViolada, match=mensaje):
            servicios.entrega.iniciar_entrega(AGENTE, folio, licencia)

    def test_cliente_que_se_inactiva_despues_no_recibe_unidad(self, servicios, flujo):
        folio = flujo.reservar().folio
        with servicios.ctx.uow_factory() as uow:
            c = uow.clientes.obtener("C1")
            c.activo = False
            uow.clientes.guardar(c)
        with pytest.raises(ReglaNegocioViolada, match="ClienteActivo"):
            servicios.entrega.iniciar_entrega(AGENTE, folio, "LIC-C1")

    def test_sin_unidad_se_ofrece_upgrade_sin_costo_y_conserva_la_tarifa(self, servicios, flujo, reloj):
        r1, r2 = flujo.reservar("C1"), flujo.reservar("C6")
        # las dos unidades ECO salen con r1 y r2; se "pierde" el cupo reservado de un tercer cliente
        for folio, cliente in ((r1.folio, "C1"), (r2.folio, "C6")):
            v, insp = flujo.entregar(folio, cliente)
            servicios.contratos.abrir_contrato(AGENTE, folio, v, insp.id)
        # una reservación posterior en otro horario, pero sin unidad física disponible hoy
        r3 = flujo.reservar("C1", inicio=INICIO + H(days=2), dias=1)
        reloj.establecer(INICIO + H(days=2, minutes=5))
        oferta = servicios.entrega.iniciar_entrega(AGENTE, r3.folio, "LIC-C1")
        assert oferta.requiere_upgrade and oferta.categoria_superior_id == "COMP" and oferta.vehiculo_id is None
        assert servicios.reservaciones.obtener_reservacion(AGENTE, r3.folio).estado == "UPGRADE_OFRECIDO"
        with pytest.raises(ReglaNegocioViolada, match="oferta de upgrade"):
            servicios.entrega.iniciar_entrega(AGENTE, r3.folio, "LIC-C1")
        aceptada = servicios.reservaciones.responder_upgrade(CLIENTE, r3.folio, "ACEPTAR")
        assert aceptada.estado == "UPGRADE_ACEPTADO" and aceptada.categoria_asignada_id == "COMP"
        ent = servicios.entrega.iniciar_entrega(AGENTE, r3.folio, "LIC-C1")
        assert ent.vehiculo_id == "VEH-COMP-1"
        insp = servicios.inspecciones.registrar_inspeccion_entrega(PATIO, r3.folio, ent.vehiculo_id, 8, 1000, fotos(), [])
        servicios.inspecciones.firmar_inspeccion_entrega(CLIENTE, insp.id, "C1")
        contrato = servicios.contratos.abrir_contrato(AGENTE, r3.folio, ent.vehiculo_id, insp.id)
        assert contrato.categoria_id == "COMP" and contrato.tarifa_diaria == Decimal("500.00")  # tarifa ECO: upgrade gratis

    def _reservacion_sin_unidad(self, flujo, reloj, servicios):
        r1, r2 = flujo.reservar("C1"), flujo.reservar("C6")
        for folio, cliente in ((r1.folio, "C1"), (r2.folio, "C6")):
            v, insp = flujo.entregar(folio, cliente)
            servicios.contratos.abrir_contrato(AGENTE, folio, v, insp.id)
        r3 = flujo.reservar("C1", inicio=INICIO + H(days=2), dias=1)
        reloj.establecer(INICIO + H(days=2, minutes=5))
        servicios.entrega.iniciar_entrega(AGENTE, r3.folio, "LIC-C1")
        return r3

    def test_rechazo_a_lista_de_espera_y_a_reembolso(self, servicios, flujo, reloj):
        r3 = self._reservacion_sin_unidad(flujo, reloj, servicios)
        en_espera = servicios.reservaciones.responder_upgrade(CLIENTE, r3.folio, "RECHAZAR_LISTA_ESPERA")
        assert en_espera.estado == "EN_LISTA_ESPERA" and en_espera.categoria_asignada_id is None
        with pytest.raises(TransicionInvalida):
            servicios.entrega.iniciar_entrega(AGENTE, r3.folio, "LIC-C1")
        assert evento(servicios, ev.UpgradeRechazado).opcion == "LISTA_ESPERA"

    def test_rechazo_con_reembolso_cancela(self, servicios, flujo, reloj):
        r3 = self._reservacion_sin_unidad(flujo, reloj, servicios)
        assert servicios.reservaciones.responder_upgrade(CLIENTE, r3.folio, "RECHAZAR_REEMBOLSO").estado == "CANCELADA"

    def test_respuesta_de_upgrade_invalida_o_sin_oferta(self, servicios, flujo):
        folio = flujo.reservar().folio
        with pytest.raises(ReglaNegocioViolada):
            servicios.reservaciones.responder_upgrade(CLIENTE, folio, "QUIZA")
        with pytest.raises(TransicionInvalida):
            servicios.reservaciones.responder_upgrade(CLIENTE, folio, "ACEPTAR")

    def test_sin_categoria_superior_con_unidades_no_hay_upgrade(self, servicios, flujo, reloj):
        r1 = flujo.reservar("C1", categoria="SUV")
        v, insp = flujo.entregar(r1.folio, "C1")
        servicios.contratos.abrir_contrato(AGENTE, r1.folio, v, insp.id)
        r2 = flujo.reservar("C6", categoria="SUV", inicio=INICIO + H(days=3), dias=1)
        reloj.establecer(INICIO + H(days=3, minutes=5))
        with pytest.raises(ConflictoDisponibilidad):
            servicios.entrega.iniciar_entrega(AGENTE, r2.folio, "LIC-C6")

    def test_upgrade_de_cortesia_lo_otorga_solo_administracion(self, servicios, flujo):
        folio = flujo.reservar().folio
        with pytest.raises(PermisoDenegado):
            servicios.reservaciones.otorgar_upgrade_cortesia(AGENTE, folio)
        r = servicios.reservaciones.otorgar_upgrade_cortesia(ADMIN, folio)
        assert r.estado == "UPGRADE_ACEPTADO" and r.categoria_asignada_id == "COMP"
        assert evento(servicios, ev.UpgradeCortesiaOtorgado).autorizado_por == "ADM-01"

    def test_cortesia_sin_categoria_superior(self, servicios, flujo):
        folio = flujo.reservar(categoria="SUV").folio
        with pytest.raises(ReglaNegocioViolada, match="categoría superior"):
            servicios.reservaciones.otorgar_upgrade_cortesia(ADMIN, folio)


class TestInspeccionYContrato:
    def test_inspeccion_exige_vehiculo_asignado_y_no_duplicarse(self, servicios, flujo):
        folio = flujo.reservar().folio
        with pytest.raises(ReglaNegocioViolada, match="no está asignado"):
            servicios.inspecciones.registrar_inspeccion_entrega(PATIO, folio, "VEH-ECO-1", 8, 1000, fotos(), [])
        flujo.reloj.establecer(INICIO)
        v = servicios.entrega.iniciar_entrega(AGENTE, folio, "LIC-C1").vehiculo_id
        with pytest.raises(ReglaNegocioViolada, match="al menos una foto"):
            servicios.inspecciones.registrar_inspeccion_entrega(PATIO, folio, v, 8, 1000, [], [])
        servicios.inspecciones.registrar_inspeccion_entrega(PATIO, folio, v, 8, 1000, fotos(), [])
        with pytest.raises(ReglaNegocioViolada, match="Ya existe"):
            servicios.inspecciones.registrar_inspeccion_entrega(PATIO, folio, v, 8, 1000, fotos(), [])

    def test_las_fotos_se_guardan_con_sello_de_tiempo_del_servidor(self, servicios, flujo):
        folio = flujo.reservar().folio
        flujo.reloj.establecer(INICIO)
        v = servicios.entrega.iniciar_entrega(AGENTE, folio, "LIC-C1").vehiculo_id
        insp = servicios.inspecciones.registrar_inspeccion_entrega(PATIO, folio, v, 8, 1000, fotos(2), [danio()])
        assert len(insp.fotos) == 2 and all(f.tomada_en == INICIO for f in insp.fotos)
        assert insp.danios[0].fotos[0].uri.startswith("evidencias/INS-")
        assert len(servicios.ctx.almacen.archivos) == 3  # la foto del daño no sobrescribe a "foto0.jpg"
        assert len({f.uri for f in insp.fotos} | {insp.danios[0].fotos[0].uri}) == 3

    def test_foto_con_base64_invalido(self, servicios, flujo):
        folio = flujo.reservar().folio
        flujo.reloj.establecer(INICIO)
        v = servicios.entrega.iniciar_entrega(AGENTE, folio, "LIC-C1").vehiculo_id
        with pytest.raises(ErrorValidacion, match="base64"):
            servicios.inspecciones.registrar_inspeccion_entrega(PATIO, folio, v, 8, 1000, [FotoCmd("x.jpg", "¡¡no!!")], [])

    def test_firma_solo_del_propietario_y_una_vez(self, servicios, flujo):
        folio = flujo.reservar().folio
        flujo.reloj.establecer(INICIO)
        v = servicios.entrega.iniciar_entrega(AGENTE, folio, "LIC-C1").vehiculo_id
        insp = servicios.inspecciones.registrar_inspeccion_entrega(PATIO, folio, v, 8, 1000, fotos(), [])
        with pytest.raises(PermisoDenegado):
            servicios.inspecciones.firmar_inspeccion_entrega(OTRO_CLIENTE, insp.id, "intruso")
        firmada = servicios.inspecciones.firmar_inspeccion_entrega(CLIENTE, insp.id, "Cliente C1")
        assert firmada.firmada and firmada.firmante == "Cliente C1"
        with pytest.raises(ReglaNegocioViolada):
            servicios.inspecciones.firmar_inspeccion_entrega(CLIENTE, insp.id, "otra vez")

    def test_abrir_contrato_exige_checklist_firmado_y_coherente(self, servicios, flujo):
        folio = flujo.reservar().folio
        flujo.reloj.establecer(INICIO)
        v = servicios.entrega.iniciar_entrega(AGENTE, folio, "LIC-C1").vehiculo_id
        insp = servicios.inspecciones.registrar_inspeccion_entrega(PATIO, folio, v, 8, 1000, fotos(), [])
        with pytest.raises(ReglaNegocioViolada, match="firmado"):
            servicios.contratos.abrir_contrato(AGENTE, folio, v, insp.id)
        servicios.inspecciones.firmar_inspeccion_entrega(CLIENTE, insp.id, "C1")
        with pytest.raises(ReglaNegocioViolada, match="vehículo no coincide"):
            servicios.contratos.abrir_contrato(AGENTE, folio, "VEH-ECO-2", insp.id)
        otro = flujo.reservar("C6", inicio=INICIO + H(days=1))
        with pytest.raises(ReglaNegocioViolada, match="no corresponde"):
            servicios.contratos.abrir_contrato(AGENTE, otro.folio, v, insp.id)

    def test_apertura_completa_dispara_las_reacciones_de_los_eventos(self, servicios, flujo):
        folio, vehiculo_id, contrato = flujo.abrir()
        assert contrato.id == f"CTR-{folio}" and contrato.estado == "ABIERTO" and contrato.monto_base == Decimal("1000.00")
        assert servicios.reservaciones.obtener_reservacion(AGENTE, folio).estado == "CONVERTIDA"
        assert servicios.flota.obtener_vehiculo(AGENTE, vehiculo_id).estado == "RENTADO"
        liq = servicios.liquidaciones.obtener_liquidacion(AGENTE, contrato.id)
        assert liq.deposito_monto == Decimal("1500.00") and liq.deposito_estado == "RETENIDO" and not liq.cargos_calculados
        assert len(servicios.ctx.pasarela.retenciones) == 1

    def test_no_se_abre_dos_veces_ni_con_banco_que_rechaza(self, servicios, flujo):
        folio, vehiculo_id, contrato = flujo.abrir()
        with pytest.raises(TransicionInvalida):  # la reservación ya fue convertida
            servicios.contratos.abrir_contrato(AGENTE, folio, vehiculo_id, "x")
        folio5 = flujo.reservar("C5", inicio=INICIO + H(days=1)).folio
        flujo.reloj.establecer(INICIO)
        v = servicios.entrega.iniciar_entrega(AGENTE, folio5, "LIC-C5").vehiculo_id
        insp = servicios.inspecciones.registrar_inspeccion_entrega(PATIO, folio5, v, 8, 1000, fotos(), [])
        servicios.inspecciones.firmar_inspeccion_entrega(Actor("C5", Rol.CLIENTE), insp.id, "C5")
        with pytest.raises(ReglaNegocioViolada, match="banco"):
            servicios.contratos.abrir_contrato(AGENTE, folio5, v, insp.id)
        with servicios.ctx.uow_factory() as uow:
            assert not uow.contratos.existe(f"CTR-{folio5}")  # rollback: no quedó contrato a medias

    def test_cobertura_de_seguro_suma_al_monto_base(self, servicios, flujo):
        folio = flujo.reservar().folio
        v, insp = flujo.entregar(folio)
        c = servicios.contratos.abrir_contrato(AGENTE, folio, v, insp.id, "amplia", 100)
        assert c.monto_base == Decimal("1200.00")

    def test_conductor_adicional(self, servicios, flujo):
        _, _, c = flujo.abrir()
        assert servicios.contratos.agregar_conductor_adicional(AGENTE, c.id, "Ana", "L-9", date(2030, 1, 1)).conductores_adicionales == ["Ana"]
        with pytest.raises(ReglaNegocioViolada):
            servicios.contratos.agregar_conductor_adicional(AGENTE, c.id, "Beto", "L-8", date(2020, 1, 1))

    def test_consultar_contrato_solo_el_propietario(self, servicios, flujo):
        _, _, c = flujo.abrir()
        assert servicios.contratos.obtener_contrato(CLIENTE, c.id).cliente_id == "C1"
        with pytest.raises(PermisoDenegado):
            servicios.contratos.obtener_contrato(OTRO_CLIENTE, c.id)
        with pytest.raises(PermisoDenegado):
            servicios.liquidaciones.obtener_liquidacion(OTRO_CLIENTE, c.id)


class TestExtensiones:
    def test_hasta_48h_la_aprueba_el_agente(self, servicios, flujo):
        _, _, c = flujo.abrir()
        flujo.reloj.establecer(c.fin - H(hours=10))
        ext = servicios.contratos.extender_renta(AGENTE, c.id, 24)
        assert ext.estado == "APROBADA"
        assert servicios.contratos.obtener_contrato(AGENTE, c.id).fin == c.fin + H(hours=24)
        assert servicios.contratos.obtener_contrato(AGENTE, c.id).monto_base == Decimal("1500.00")  # 3 días

    def test_mas_de_48h_requiere_administracion(self, servicios, flujo):
        _, _, c = flujo.abrir()
        flujo.reloj.establecer(c.fin - H(hours=10))
        ext = servicios.contratos.extender_renta(AGENTE, c.id, 72)
        assert ext.estado == "PENDIENTE"
        assert servicios.contratos.obtener_contrato(AGENTE, c.id).fin == c.fin
        with pytest.raises(PermisoDenegado):
            servicios.contratos.aprobar_extension(AGENTE, c.id, ext.id)
        aprobada = servicios.contratos.aprobar_extension(ADMIN, c.id, ext.id)
        assert aprobada.estado == "APROBADA" and aprobada.aprobada_por == "ADM-01"
        assert servicios.contratos.obtener_contrato(AGENTE, c.id).fin == c.fin + H(hours=72)
        assert evento(servicios, ev.ExtensionRequiereAutorizacion).horas == 72

    def test_la_extension_no_puede_chocar_con_reservaciones_futuras(self, servicios, flujo):
        _, _, c = flujo.abrir()
        flujo.reservar("C6", inicio=c.fin, dias=2)   # compromete la otra unidad ECO...
        flujo.reservar("C1", inicio=c.fin, dias=2)   # ...y la que hoy está rentada
        flujo.reloj.establecer(AHORA)
        flujo.reloj.establecer(c.fin - H(hours=5))
        with pytest.raises(ConflictoDisponibilidad):
            servicios.contratos.extender_renta(AGENTE, c.id, 24)

    def test_reglas_de_anticipacion(self, servicios, flujo):
        _, _, c = flujo.abrir()
        flujo.reloj.establecer(c.fin - H(hours=1))
        with pytest.raises(ReglaNegocioViolada, match="anticipación"):
            servicios.contratos.extender_renta(AGENTE, c.id, 24)
        with pytest.raises(PermisoDenegado):
            servicios.contratos.extender_renta(CLIENTE, c.id, 24)


class TestDevolucionYCargos:
    def test_ciclo_completo_con_cargos_disputa_limpieza_y_deposito(self, servicios, flujo):
        folio, vehiculo_id, c = flujo.abrir()
        flujo.devolver(c, retraso=H(hours=1), combustible=5, km=1500, danios=[danio()])
        liq = servicios.liquidaciones.obtener_liquidacion(AGENTE, c.id)
        tipos = {x.tipo: x for x in liq.cargos}
        assert tipos["RETRASO"].monto == Decimal("20.83") and tipos["KILOMETRAJE"].monto == Decimal("300.00")
        assert tipos["COMBUSTIBLE"].monto == Decimal("150.00") and tipos["DANIO"].estado == "PENDIENTE_APROBACION"
        assert liq.total_cargos == Decimal("470.83") and liq.tiene_incidencias
        assert servicios.contratos.obtener_contrato(AGENTE, c.id).estado == "DEVUELTO"
        assert servicios.flota.obtener_vehiculo(AGENTE, vehiculo_id).estado == "EN_LIMPIEZA"
        assert servicios.flota.obtener_vehiculo(AGENTE, vehiculo_id).kilometraje == 1500

        danio_id = tipos["DANIO"].id
        servicios.liquidaciones.aprobar_cargo_danio(ADMIN, c.id, danio_id, Decimal("800"))
        servicios.liquidaciones.disputar_cargo(CLIENTE, c.id, danio_id, "ya estaba rayada")
        evid = servicios.inspecciones.consultar_evidencia_disputa(AGENTE, c.id, danio_id)
        assert [d.zona for d in evid.danios_nuevos] == ["puerta"] and not evid.entrega.danios and evid.devolucion.danios
        res = servicios.liquidaciones.resolver_disputa(ADMIN, c.id, danio_id, "ANULADO")
        assert res.total_cargos == Decimal("470.83") and not res.tiene_incidencias

        tarea = servicios.limpieza.listar_abiertas(LIMPIEZA)[0]
        servicios.ctx.reloj.establecer(servicios.ctx.reloj.ahora() + H(hours=3))
        servicios.limpieza.marcar_vehiculo_listo(LIMPIEZA, tarea.id)
        assert servicios.flota.obtener_vehiculo(AGENTE, vehiculo_id).estado == "DISPONIBLE"

        flujo.reloj.establecer(datetime(2026, 11, 12, 23, 0, tzinfo=UTC))
        assert servicios.liquidaciones.liberar_depositos(SISTEMA) == []
        flujo.reloj.establecer(datetime(2026, 11, 13, 9, 0, tzinfo=UTC))
        assert servicios.liquidaciones.liberar_depositos(SISTEMA) == [f"LIQ-{folio}"]
        assert servicios.contratos.obtener_contrato(AGENTE, c.id).estado == "CERRADO"
        assert len(servicios.ctx.pasarela.liberaciones) == 1
        assert servicios.liquidaciones.liberar_depositos(SISTEMA) == []  # job idempotente

    def test_devolucion_a_tiempo_sin_novedades_no_genera_cargos(self, servicios, flujo):
        _, _, c = flujo.abrir()
        flujo.devolver(c, retraso=H(minutes=29), combustible=7, km=1400)  # 29 min, 1/8 y 400 km: todo dentro de lo permitido
        liq = servicios.liquidaciones.obtener_liquidacion(AGENTE, c.id)
        assert liq.cargos == [] and liq.total_cargos == Decimal("0.00") and liq.cargos_calculados

    def test_con_incidencia_el_deposito_no_se_libera(self, servicios, flujo):
        _, _, c = flujo.abrir()
        flujo.devolver(c, danios=[danio()])
        flujo.reloj.establecer(datetime(2027, 1, 1, tzinfo=UTC))
        assert servicios.liquidaciones.liberar_depositos(SISTEMA) == []

    def test_precondiciones_de_la_devolucion(self, servicios, flujo):
        _, _, c = flujo.abrir()
        with pytest.raises(ReglaNegocioViolada, match="checklist de devolución"):
            servicios.contratos.procesar_devolucion(AGENTE, c.id)
        with pytest.raises(ErrorValidacion, match="no puede ser menor"):
            servicios.inspecciones.registrar_inspeccion_devolucion(PATIO, c.id, 8, 900, fotos(), [])
        servicios.inspecciones.registrar_inspeccion_devolucion(PATIO, c.id, 8, 1200, fotos(), [])
        with pytest.raises(ReglaNegocioViolada, match="Ya existe"):
            servicios.inspecciones.registrar_inspeccion_devolucion(PATIO, c.id, 8, 1300, fotos(), [])
        servicios.contratos.procesar_devolucion(AGENTE, c.id)
        with pytest.raises(TransicionInvalida):
            servicios.contratos.procesar_devolucion(AGENTE, c.id)
        with pytest.raises(ReglaNegocioViolada, match="contrato abierto"):
            servicios.inspecciones.registrar_inspeccion_devolucion(PATIO, c.id, 8, 1300, fotos(), [])

    def test_disputas_solo_del_propietario_y_resolucion_de_administracion(self, servicios, flujo):
        _, _, c = flujo.abrir()
        flujo.devolver(c, km=1500)
        cargo = servicios.liquidaciones.obtener_liquidacion(AGENTE, c.id).cargos[0]
        with pytest.raises(PermisoDenegado):
            servicios.liquidaciones.disputar_cargo(OTRO_CLIENTE, c.id, cargo.id, "no es mío")
        with pytest.raises(PermisoDenegado):
            servicios.liquidaciones.resolver_disputa(AGENTE, c.id, cargo.id, "ANULADO")
        with pytest.raises(PermisoDenegado):
            servicios.liquidaciones.aprobar_cargo_danio(AGENTE, c.id, cargo.id, 10)
        with pytest.raises(ReglaNegocioViolada):
            servicios.inspecciones.consultar_evidencia_disputa(AGENTE, c.id, "no-existe")

    def test_liquidacion_inexistente_y_evidencia_incompleta(self, servicios, flujo):
        folio = flujo.reservar().folio
        v, insp = flujo.entregar(folio)
        with pytest.raises(NoEncontrado):
            servicios.liquidaciones.obtener_liquidacion(AGENTE, f"CTR-{folio}")
        c = servicios.contratos.abrir_contrato(AGENTE, folio, v, insp.id)
        with pytest.raises(ReglaNegocioViolada, match="no existe en la liquidación"):  # aún sin devolución ni cargos
            servicios.inspecciones.consultar_evidencia_disputa(AGENTE, c.id, f"LIQ-{folio}-C1")
        with pytest.raises(ReglaNegocioViolada, match="no existe en la liquidación"):
            servicios.inspecciones.consultar_evidencia_disputa(AGENTE, "CTR-RES-9999", "x")


class TestIdempotenciaDeHandlers:
    """Un evento entregado dos veces no debe duplicar efectos (ACT-F03 §3.4)."""

    def test_repetir_los_eventos_de_apertura_y_devolucion_no_cambia_nada(self, servicios, flujo):
        folio, vehiculo_id, c = flujo.abrir()
        flujo.devolver(c, combustible=5, km=1500)
        abierto, devuelto = evento(servicios, ev.ContratoAbierto), evento(servicios, ev.VehiculoDevuelto)
        antes = servicios.liquidaciones.obtener_liquidacion(AGENTE, c.id)
        servicios.reservaciones.marcar_convertida(folio)
        servicios.flota.marcar_rentado(abierto)
        servicios.liquidaciones.abrir_liquidacion(abierto)
        servicios.liquidaciones.calcular_cargos(devuelto)
        servicios.flota.registrar_devolucion_vehiculo(devuelto)
        servicios.limpieza.crear_tarea(devuelto)
        assert servicios.liquidaciones.obtener_liquidacion(AGENTE, c.id) == antes
        assert len(servicios.limpieza.listar_abiertas(LIMPIEZA)) == 1
        assert servicios.flota.obtener_vehiculo(AGENTE, vehiculo_id).estado == "EN_LIMPIEZA"

    def test_repetir_limpieza_y_cierre(self, servicios, flujo):
        _, vehiculo_id, c = flujo.abrir()
        flujo.devolver(c)
        tarea = servicios.limpieza.listar_abiertas(LIMPIEZA)[0]
        servicios.limpieza.marcar_vehiculo_listo(LIMPIEZA, tarea.id)
        servicios.flota.marcar_disponible(evento(servicios, ev.TareaLimpiezaCompletada))
        assert servicios.flota.obtener_vehiculo(AGENTE, vehiculo_id).estado == "DISPONIBLE"
        flujo.reloj.establecer(datetime(2026, 11, 20, tzinfo=UTC))
        servicios.liquidaciones.liberar_depositos(SISTEMA)
        servicios.contratos.cerrar_contrato(c.id)  # ya estaba cerrado
        assert servicios.contratos.obtener_contrato(AGENTE, c.id).estado == "CERRADO"
        with pytest.raises(TransicionInvalida):
            servicios.limpieza.marcar_vehiculo_listo(LIMPIEZA, tarea.id)

    def test_calcular_cargos_sin_checklists_falla_con_claridad(self, servicios, flujo):
        _, _, c = flujo.abrir()
        falso = ev.VehiculoDevuelto(AHORA, c.id, "V", AHORA)
        with pytest.raises(ReglaNegocioViolada, match="Faltan checklists"):
            servicios.liquidaciones.calcular_cargos(falso)


class TestPermisosPorRol:
    @pytest.mark.parametrize("actor, llamada", [
        (CLIENTE, lambda s: s.entrega.iniciar_entrega(CLIENTE, "R", "L")),
        (PATIO, lambda s: s.reservaciones.crear_reservacion(PATIO, "C1", "ECO", "SUC-MTY", INICIO, INICIO + H(days=1))),
        (AGENTE, lambda s: s.reportes.generar_reporte_ocupacion(AGENTE, "SUC-MTY", INICIO, INICIO + H(days=1))),
        (CLIENTE, lambda s: s.liquidaciones.liberar_depositos(CLIENTE)),
        (AGENTE, lambda s: s.reservaciones.liberar_no_shows(AGENTE)),
        (CLIENTE, lambda s: s.limpieza.marcar_vehiculo_listo(CLIENTE, "T")),
        (CLIENTE, lambda s: s.flota.consultar_flota(CLIENTE, "SUC-MTY")),
        (LIMPIEZA, lambda s: s.inspecciones.registrar_inspeccion_devolucion(LIMPIEZA, "C", 8, 1, fotos(), [])),
    ])
    def test_cada_caso_de_uso_rechaza_roles_no_autorizados(self, servicios, actor, llamada):
        with pytest.raises(PermisoDenegado, match="Roles permitidos"):
            llamada(servicios)


class TestConsultasYReportes:
    def test_resumen_de_flota_y_catalogo(self, servicios):
        r = servicios.flota.consultar_flota(AGENTE, "SUC-MTY")
        assert r.total == 4 and r.por_estado == {"DISPONIBLE": 4} and r.por_categoria == {"ECO": 2, "COMP": 1, "SUV": 1}
        assert len(servicios.catalogo.listar_categorias(CLIENTE)) == 4
        assert servicios.catalogo.obtener_cliente(CLIENTE, "C1").frecuente
        with pytest.raises(PermisoDenegado):
            servicios.catalogo.obtener_cliente(OTRO_CLIENTE, "C1")
        assert len(servicios.catalogo.listar_sucursales(CLIENTE)) == 2

    def test_reporte_de_ocupacion_ingresos_y_rotacion(self, servicios, flujo):
        _, _, c = flujo.abrir()
        flujo.devolver(c, retraso=H(hours=1), km=1500)
        tarea = servicios.limpieza.listar_abiertas(LIMPIEZA)[0]
        servicios.ctx.reloj.establecer(servicios.ctx.reloj.ahora() + H(hours=4))
        servicios.limpieza.marcar_vehiculo_listo(LIMPIEZA, tarea.id)
        rep = servicios.reportes.generar_reporte_ocupacion(
            ADMIN, "SUC-MTY", datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 12, 1, tzinfo=UTC))
        assert rep.flota_total == 4 and rep.ingresos_renta == Decimal("1000.00")
        assert rep.ingresos_cargos == Decimal("320.83") and rep.rotacion_horas_promedio == Decimal("4.00")
        horas_ocupadas, horas_totales = 48, 4 * 30 * 24
        assert rep.ocupacion_pct == Decimal(str(round(horas_ocupadas / horas_totales * 100, 2))).quantize(Decimal("0.01"))
        assert rep.vehiculos_por_estado["DISPONIBLE"] == 4

    def test_reporte_sin_datos_y_rango_invalido(self, servicios):
        rep = servicios.reportes.generar_reporte_ocupacion(ADMIN, "SUC-APO", INICIO, INICIO + H(days=1))
        assert rep.ocupacion_pct == 0 and rep.ingresos_renta == 0 and rep.rotacion_horas_promedio is None
        with pytest.raises(ErrorValidacion):
            servicios.reportes.generar_reporte_ocupacion(ADMIN, "SUC-MTY", INICIO, INICIO - H(days=1))
