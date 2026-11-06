from datetime import UTC, date, datetime, timedelta

import pytest

from src.domain import eventos as ev
from src.domain.catalogo import CategoriaVehiculo, Cliente
from src.domain.comun import ErrorValidacion, PermisoDenegado, ReglaNegocioViolada, Rol, TransicionInvalida
from src.domain.contrato import ContratoRenta, EstadoContrato, EstadoExtension
from src.domain.inspeccion import InspeccionVehiculo, TipoInspeccion
from src.domain.limpieza import EstadoTarea, TareaLimpieza
from src.domain.liquidacion import EstadoCargo, EstadoDeposito, Liquidacion, TipoCargo
from src.domain.politicas import ParametrosNegocio, PoliticaCancelacion, PoliticaCargos, PoliticaExtension
from src.domain.reservacion import EstadoReservacion, OpcionRechazoUpgrade, Reservacion
from src.domain.valores import (
    CoberturaSeguro,
    DiferenciasInspeccion,
    Dinero,
    EvidenciaFoto,
    FirmaDigital,
    Kilometraje,
    Licencia,
    MetodoPagoRef,
    NivelCombustible,
    PeriodoRenta,
    ReferenciaPago,
    RegistroDanio,
)
from src.domain.vehiculo import EstadoVehiculo, Vehiculo
from src.infrastructure.adaptadores import CalendarioHabilMX

T0 = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
P = ParametrosNegocio()
CANCELACION, EXTENSION, CARGOS = PoliticaCancelacion(P), PoliticaExtension(P), PoliticaCargos(P)
ECO = CategoriaVehiculo("ECO", "Eco", 1, Dinero(500), Dinero(1500))
SUV = CategoriaVehiculo("SUV", "SUV", 3, Dinero(1000), Dinero(3000))
FOTO = EvidenciaFoto("u", T0)


def nombres(agregado):
    return [type(e).__name__ for e in agregado.recoger_eventos()]


def reservacion(inicio=T0 + timedelta(days=3)):
    return Reservacion.crear("R1", "C1", ECO, "S1", PeriodoRenta(inicio, inicio + timedelta(days=2)), T0)


class TestReservacion:
    def test_crear_emite_evento_y_valida(self):
        r = reservacion()
        assert nombres(r) == ["ReservacionCreada"] and r.estado == EstadoReservacion.CREADA
        with pytest.raises(ReglaNegocioViolada):
            Reservacion.crear("R", "C", ECO, "S", PeriodoRenta(T0 - timedelta(days=1), T0 + timedelta(days=1)), T0)
        with pytest.raises(ReglaNegocioViolada):
            deshabilitada = CategoriaVehiculo("X", "X", 9, Dinero(1), Dinero(1), habilitada=False)
            Reservacion.crear("R", "C", deshabilitada, "S", PeriodoRenta(T0 + timedelta(days=1), T0 + timedelta(days=2)), T0)

    def test_cancelacion_gratuita_con_24h_o_mas(self):
        r = reservacion(inicio=T0 + timedelta(hours=24))
        resultado = r.cancelar(T0, Rol.CLIENTE, CANCELACION)
        assert not resultado.penalizada and r.estado == EstadoReservacion.CANCELADA and r.penalizacion == Dinero.cero()

    def test_cancelacion_tardia_penaliza_un_dia(self):
        r = reservacion(inicio=T0 + timedelta(hours=23))
        resultado = r.cancelar(T0, Rol.AGENTE, CANCELACION)
        assert resultado.penalizada and r.penalizacion == Dinero(500)
        assert nombres(r)[-1] == "ReservacionCancelada"

    def test_no_se_cancela_dos_veces_ni_con_rol_ajeno(self):
        r = reservacion()
        with pytest.raises(PermisoDenegado):
            r.cancelar(T0, Rol.LIMPIEZA, CANCELACION)
        r.cancelar(T0, Rol.CLIENTE, CANCELACION)
        with pytest.raises(TransicionInvalida):
            r.cancelar(T0, Rol.CLIENTE, CANCELACION)

    def test_no_show_a_las_2_horas_exactas(self):
        inicio = T0 + timedelta(hours=1)
        r = reservacion(inicio=inicio)
        with pytest.raises(ReglaNegocioViolada):
            r.liberar_por_no_show(inicio + timedelta(hours=1, minutes=59), CANCELACION)
        r.liberar_por_no_show(inicio + timedelta(hours=2), CANCELACION)
        assert r.estado == EstadoReservacion.LIBERADA_NO_SHOW and "ReservacionLiberadaPorNoShow" in nombres(r)

    def test_upgrade_aceptado_conserva_tarifa_y_cambia_categoria_efectiva(self):
        r = reservacion()
        r.proponer_upgrade(ECO, SUV, T0)
        assert r.estado == EstadoReservacion.UPGRADE_OFRECIDO and r.categoria_efectiva_id == "SUV"
        r.aceptar_upgrade()
        assert r.estado == EstadoReservacion.UPGRADE_ACEPTADO and r.tarifa_diaria == Dinero(500)
        r.marcar_convertida()
        assert r.estado == EstadoReservacion.CONVERTIDA

    @pytest.mark.parametrize("opcion, estado", [
        (OpcionRechazoUpgrade.LISTA_ESPERA, EstadoReservacion.EN_LISTA_ESPERA),
        (OpcionRechazoUpgrade.REEMBOLSO, EstadoReservacion.CANCELADA),
    ])
    def test_rechazo_de_upgrade_restituye_la_categoria_reservada(self, opcion, estado):
        r = reservacion()
        r.proponer_upgrade(ECO, SUV, T0)
        r.rechazar_upgrade(opcion, T0)
        assert r.estado == estado and r.categoria_efectiva_id == "ECO"
        assert "UpgradeRechazado" in nombres(r)

    def test_upgrade_solo_a_categoria_superior_habilitada(self):
        r = reservacion()
        with pytest.raises(ReglaNegocioViolada):
            r.proponer_upgrade(ECO, CategoriaVehiculo("B", "B", 1, Dinero(1), Dinero(1)), T0)
        with pytest.raises(ReglaNegocioViolada):
            r.proponer_upgrade(SUV, SUV, T0)

    def test_upgrade_de_cortesia_solo_administracion(self):
        r = reservacion()
        with pytest.raises(PermisoDenegado):
            r.otorgar_upgrade_cortesia(SUV, Rol.AGENTE, "AGE", T0)
        r.otorgar_upgrade_cortesia(SUV, Rol.ADMINISTRACION, "ADM", T0)
        assert r.estado == EstadoReservacion.UPGRADE_ACEPTADO and "UpgradeCortesiaOtorgado" in nombres(r)

    def test_convertida_o_cancelada_no_vuelven_a_activarse(self):
        r = reservacion()
        r.cancelar(T0, Rol.SISTEMA, CANCELACION)
        with pytest.raises(TransicionInvalida):
            r.marcar_convertida()
        assert not r.esta_activa


def contrato(horas=48):
    return ContratoRenta.abrir(
        "CTR-R1", "R1", "C1", "V1", "ECO", "S1", PeriodoRenta(T0, T0 + timedelta(hours=horas)), Dinero(500), 200,
        Dinero(1500), ReferenciaPago("PAY-1"), "INS-1", T0,
    )


class TestContrato:
    def test_abrir_emite_evento_con_deposito(self):
        c = contrato()
        e = c.recoger_eventos()[0]
        assert isinstance(e, ev.ContratoAbierto) and e.deposito_monto == Dinero(1500).monto
        assert c.monto_base() == Dinero(1000)

    def test_monto_base_incluye_cobertura(self):
        c = contrato()
        c.cobertura = CoberturaSeguro("amplia", Dinero(100))
        assert c.monto_base() == Dinero(1200)

    def test_extension_de_hasta_48h_la_aprueba_el_agente(self):
        c = contrato()
        ext = c.solicitar_extension(24, "AGE", Rol.AGENTE, T0 + timedelta(hours=10), EXTENSION)
        assert ext.estado == EstadoExtension.APROBADA and c.periodo.fin == T0 + timedelta(hours=72)
        assert "RentaExtendida" in nombres(c)

    def test_extension_mayor_a_48h_queda_pendiente_y_la_aprueba_administracion(self):
        c = contrato()
        ext = c.solicitar_extension(72, "AGE", Rol.AGENTE, T0 + timedelta(hours=10), EXTENSION)
        assert ext.estado == EstadoExtension.PENDIENTE and c.periodo.fin == T0 + timedelta(hours=48)
        assert "ExtensionRequiereAutorizacion" in nombres(c)
        with pytest.raises(PermisoDenegado):
            c.aprobar_extension(ext.id, Rol.AGENTE, "AGE", T0 + timedelta(hours=11))
        c.aprobar_extension(ext.id, Rol.ADMINISTRACION, "ADM", T0 + timedelta(hours=11))
        assert c.periodo.fin == T0 + timedelta(hours=120) and ext.aprobada_por == "ADM"
        with pytest.raises(ReglaNegocioViolada):
            c.aprobar_extension(ext.id, Rol.ADMINISTRACION, "ADM", T0 + timedelta(hours=12))

    def test_administracion_extiende_directo_y_no_se_aprueba_tarde(self):
        c = contrato()
        assert c.solicitar_extension(100, "ADM", Rol.ADMINISTRACION, T0, EXTENSION).estado == EstadoExtension.APROBADA
        c2 = contrato()
        ext = c2.solicitar_extension(72, "AGE", Rol.AGENTE, T0, EXTENSION)
        with pytest.raises(ReglaNegocioViolada):
            c2.aprobar_extension(ext.id, Rol.ADMINISTRACION, "ADM", T0 + timedelta(hours=48))
        with pytest.raises(ReglaNegocioViolada):
            c2.aprobar_extension("no-existe", Rol.ADMINISTRACION, "ADM", T0)

    def test_extension_exige_2h_de_anticipacion_y_rol_operativo(self):
        c = contrato()
        with pytest.raises(ReglaNegocioViolada):
            c.solicitar_extension(24, "AGE", Rol.AGENTE, T0 + timedelta(hours=46, minutes=1), EXTENSION)
        c.solicitar_extension(24, "AGE", Rol.AGENTE, T0 + timedelta(hours=46), EXTENSION)  # límite exacto
        with pytest.raises(PermisoDenegado):
            c.solicitar_extension(24, "C1", Rol.CLIENTE, T0, EXTENSION)

    def test_conductor_adicional_requiere_licencia_vigente(self):
        c = contrato()
        c.agregar_conductor_adicional("K1", "Ana", Licencia("L", date(2030, 1, 1)), date(2026, 11, 6))
        assert len(c.conductores) == 1
        with pytest.raises(ReglaNegocioViolada):
            c.agregar_conductor_adicional("K2", "Beto", Licencia("L2", date(2026, 1, 1)), date(2026, 11, 6))

    def test_devolucion_y_cierre_siguen_el_ciclo_de_vida(self):
        c = contrato()
        c.registrar_devolucion(T0 + timedelta(hours=49))
        assert c.estado == EstadoContrato.DEVUELTO and c.devolucion_real == T0 + timedelta(hours=49)
        assert c.condiciones().devolucion_real is not None
        with pytest.raises(TransicionInvalida):
            c.solicitar_extension(24, "AGE", Rol.AGENTE, T0, EXTENSION)
        with pytest.raises(TransicionInvalida):
            c.registrar_devolucion(T0)
        c.cerrar(T0)
        assert c.estado == EstadoContrato.CERRADO and "ContratoCerrado" in nombres(c)


def inspeccion(tipo=TipoInspeccion.ENTREGA, km=1000, octavos=8, danios=(), fotos=(FOTO,), contrato_id="CTR-R1"):
    return InspeccionVehiculo.registrar(
        "I1", contrato_id, "V1", tipo, "PAT", NivelCombustible(octavos), Kilometraje(km), tuple(fotos), tuple(danios), T0)


RAYON = RegistroDanio("puerta", "Rayón", (FOTO,))


class TestInspeccion:
    def test_sin_fotos_se_rechaza(self):
        with pytest.raises(ReglaNegocioViolada):
            inspeccion(fotos=())

    def test_firmar_la_hace_inmutable_y_emite_evento_de_entrega(self):
        i = inspeccion()
        i.agregar_danio(RAYON)
        i.firmar(FirmaDigital("Cliente", T0), T0)
        assert i.esta_firmada and nombres(i) == ["InspeccionEntregaFirmada"]
        with pytest.raises(ReglaNegocioViolada):
            i.firmar(FirmaDigital("Cliente", T0), T0)
        with pytest.raises(ReglaNegocioViolada):
            i.agregar_danio(RAYON)

    def test_la_devolucion_emite_evento_al_registrarse(self):
        assert nombres(inspeccion(TipoInspeccion.DEVOLUCION)) == ["InspeccionDevolucionCompletada"]

    def test_comparar_detecta_km_combustible_y_danios_nuevos(self):
        entrega = inspeccion(danios=[RAYON])
        golpe = RegistroDanio("cofre", "Golpe", (FOTO,))
        devolucion = inspeccion(TipoInspeccion.DEVOLUCION, km=1450, octavos=5, danios=[RAYON, golpe])
        d = devolucion.comparar_contra(entrega)
        assert (d.km_recorridos, d.octavos_faltantes) == (450, 3) and d.danios_nuevos == (golpe,)

    def test_comparar_valida_tipos_y_contrato(self):
        entrega, devolucion = inspeccion(), inspeccion(TipoInspeccion.DEVOLUCION)
        with pytest.raises(ReglaNegocioViolada):
            entrega.comparar_contra(devolucion)
        with pytest.raises(ReglaNegocioViolada):
            inspeccion(TipoInspeccion.DEVOLUCION, contrato_id="OTRO").comparar_contra(entrega)

    def test_la_devolucion_no_puede_tener_menos_km_que_la_entrega(self):
        with pytest.raises(ErrorValidacion):
            inspeccion(TipoInspeccion.DEVOLUCION, km=900).comparar_contra(inspeccion(km=1000))


def condiciones(retraso=timedelta(0)):
    c = contrato()
    c.registrar_devolucion(c.periodo.fin + retraso)
    return c.condiciones()


def liquidacion():
    return Liquidacion.abrir("L1", "CTR-R1", Dinero(1500), ReferenciaPago("PAY-1"))


class TestLiquidacion:
    def test_calcular_cargos_crea_cargos_y_danios_pendientes(self):
        liq = liquidacion()
        golpe = RegistroDanio("cofre", "Golpe", (FOTO,))
        assert liq.calcular_cargos(DiferenciasInspeccion(500, 3, (golpe,)), condiciones(timedelta(hours=1)), CARGOS, T0)
        tipos = [c.tipo for c in liq.cargos]
        assert tipos == [TipoCargo.RETRASO, TipoCargo.KILOMETRAJE, TipoCargo.COMBUSTIBLE, TipoCargo.DANIO]
        assert liq.danios_por_aprobar() == 1 and liq.tiene_incidencias()
        assert liq.total_cargos() == Dinero("20.83") + Dinero(300) + Dinero(150)  # el daño aún no suma
        assert nombres(liq) == ["CargosCalculados"]

    def test_calcular_es_idempotente(self):
        liq = liquidacion()
        liq.calcular_cargos(DiferenciasInspeccion(500, 0), condiciones(), CARGOS, T0)
        liq.recoger_eventos()
        assert liq.calcular_cargos(DiferenciasInspeccion(900, 0), condiciones(), CARGOS, T0) is False
        assert len(liq.cargos) == 1 and nombres(liq) == []

    def test_solo_administracion_fija_el_monto_del_danio(self):
        liq = liquidacion()
        liq.calcular_cargos(DiferenciasInspeccion(0, 0, (RAYON,)), condiciones(), CARGOS, T0)
        cargo_id = liq.cargos[0].id
        with pytest.raises(PermisoDenegado):
            liq.aprobar_cargo_danio(cargo_id, Dinero(800), Rol.AGENTE)
        with pytest.raises(ReglaNegocioViolada):
            liq.aprobar_cargo_danio(cargo_id, Dinero.cero(), Rol.ADMINISTRACION)
        liq.aprobar_cargo_danio(cargo_id, Dinero(800), Rol.ADMINISTRACION)
        assert liq.total_cargos() == Dinero(800) and liq.cargos[0].estado == EstadoCargo.APLICADO
        with pytest.raises(TransicionInvalida):
            liq.aprobar_cargo_danio(cargo_id, Dinero(900), Rol.ADMINISTRACION)

    def test_solo_los_cargos_por_danio_requieren_aprobacion(self):
        liq = liquidacion()
        liq.calcular_cargos(DiferenciasInspeccion(500, 0), condiciones(), CARGOS, T0)
        with pytest.raises(ReglaNegocioViolada):
            liq.aprobar_cargo_danio(liq.cargos[0].id, Dinero(5), Rol.ADMINISTRACION)
        with pytest.raises(ReglaNegocioViolada):
            liq.aprobar_cargo_danio("no-existe", Dinero(5), Rol.ADMINISTRACION)

    def test_disputa_y_resolucion(self):
        liq = liquidacion()
        liq.calcular_cargos(DiferenciasInspeccion(500, 0), condiciones(), CARGOS, T0)
        cid = liq.cargos[0].id
        liq.disputar_cargo(cid, "no manejé tanto", T0)
        assert liq.cargos[0].estado == EstadoCargo.DISPUTADO and liq.tiene_incidencias()
        assert liq.total_cargos() == Dinero.cero()
        with pytest.raises(ReglaNegocioViolada):
            liq.disputar_cargo(cid, "otra vez", T0)
        with pytest.raises(PermisoDenegado):
            liq.resolver_disputa(cid, "ANULADO", "AGE", Rol.AGENTE, T0)
        with pytest.raises(ReglaNegocioViolada):
            liq.resolver_disputa(cid, "TAL VEZ", "ADM", Rol.ADMINISTRACION, T0)
        liq.resolver_disputa(cid, "CONFIRMADO", "ADM", Rol.ADMINISTRACION, T0)
        assert liq.cargos[0].estado == EstadoCargo.APLICADO and liq.cargos[0].disputa.resuelta_por == "ADM"
        with pytest.raises(ReglaNegocioViolada):  # la resolución es definitiva
            liq.disputar_cargo(cid, "ya resuelto", T0)

    def test_anular_un_cargo_lo_saca_del_total(self):
        liq = liquidacion()
        liq.calcular_cargos(DiferenciasInspeccion(500, 0), condiciones(), CARGOS, T0)
        liq.disputar_cargo(liq.cargos[0].id, "m", T0)
        liq.resolver_disputa(liq.cargos[0].id, "ANULADO", "ADM", Rol.ADMINISTRACION, T0)
        assert liq.total_cargos().es_cero() and not liq.tiene_incidencias()

    def test_deposito_se_libera_a_5_dias_habiles_sin_incidencias(self):
        liq = liquidacion()
        cal = CalendarioHabilMX()
        with pytest.raises(ReglaNegocioViolada):
            liq.liberar_deposito(T0, cal, P)  # cargos no calculados
        liq.calcular_cargos(DiferenciasInspeccion(0, 0), condiciones(), CARGOS, T0)
        devuelta = liq.devuelta_en  # domingo 8-nov-2026 09:00 UTC
        antes = datetime(2026, 11, 12, 23, 59, tzinfo=UTC)
        with pytest.raises(ReglaNegocioViolada, match="Plazo"):
            liq.liberar_deposito(antes, cal, P)
        liq.liberar_deposito(datetime(2026, 11, 13, 0, 0, tzinfo=UTC), cal, P)
        assert liq.deposito.estado == EstadoDeposito.LIBERADO and devuelta.date() == date(2026, 11, 8)
        with pytest.raises(ReglaNegocioViolada):
            liq.liberar_deposito(datetime(2026, 11, 20, tzinfo=UTC), cal, P)

    def test_con_danio_pendiente_el_deposito_se_retiene(self):
        liq = liquidacion()
        liq.calcular_cargos(DiferenciasInspeccion(0, 0, (RAYON,)), condiciones(), CARGOS, T0)
        with pytest.raises(ReglaNegocioViolada, match="SinIncidencias"):
            liq.liberar_deposito(datetime(2026, 12, 31, tzinfo=UTC), CalendarioHabilMX(), P)
        assert liq.es_elegible_para_liberar()


class TestVehiculoYLimpieza:
    def test_ciclo_completo_del_vehiculo(self):
        v = Vehiculo("V1", "P", "ECO", "S1", Kilometraje(1000))
        v.asignar_a_entrega(); v.marcar_rentado()
        v.registrar_devolucion(Kilometraje(1300), "S2")
        assert (v.estado, v.kilometraje.valor, v.sucursal_id) == (EstadoVehiculo.EN_LIMPIEZA, 1300, "S2")
        v.marcar_disponible(T0)
        assert v.estado == EstadoVehiculo.DISPONIBLE and nombres(v) == ["VehiculoListoParaRenta"]

    def test_solo_un_vehiculo_disponible_se_asigna(self):
        v = Vehiculo("V1", "P", "ECO", "S1", Kilometraje(0), EstadoVehiculo.RENTADO)
        with pytest.raises(TransicionInvalida):
            v.asignar_a_entrega()
        v2 = Vehiculo("V2", "P", "ECO", "S1", Kilometraje(0))
        v2.asignar_a_entrega(); v2.liberar_asignacion()
        assert v2.estado == EstadoVehiculo.DISPONIBLE

    def test_el_kilometraje_no_retrocede(self):
        v = Vehiculo("V1", "P", "ECO", "S1", Kilometraje(1000), EstadoVehiculo.RENTADO)
        with pytest.raises(ReglaNegocioViolada):
            v.registrar_devolucion(Kilometraje(900), "S1")

    def test_tarea_de_limpieza(self):
        t = TareaLimpieza("T1", "V1", T0)
        assert t.horas_de_rotacion is None
        with pytest.raises(PermisoDenegado):
            t.completar("AGE", Rol.AGENTE, T0)
        t.completar("LIM", Rol.LIMPIEZA, T0 + timedelta(hours=3))
        assert t.estado == EstadoTarea.COMPLETADA and t.horas_de_rotacion == 3
        with pytest.raises(TransicionInvalida):
            t.completar("LIM", Rol.LIMPIEZA, T0)
        assert nombres(t) == ["TareaLimpiezaCompletada"]


class TestCliente:
    def cliente(self, **kw):
        base = dict(id="C1", nombre="Ana", fecha_nacimiento=date(2000, 11, 6), licencia=Licencia("L", date(2030, 1, 1)),
                    metodo_pago=MetodoPagoRef("tok", "1234"))
        return Cliente(**{**base, **kw})

    def test_edad_y_conductor_joven(self):
        c = self.cliente()
        assert c.edad_en(date(2026, 11, 5)) == 25 and c.edad_en(date(2026, 11, 6)) == 26
        assert c.es_conductor_joven(date(2024, 11, 6)) and not c.es_conductor_joven(date(2026, 11, 6))

    def test_puede_rentar_y_motivos(self):
        assert self.cliente().puede_rentar(date(2026, 11, 6))
        malo = self.cliente(activo=False, metodo_pago=None, licencia=Licencia("L", date(2026, 1, 1)))
        assert not malo.puede_rentar(date(2026, 11, 6))
        assert malo.motivos_no_apto(date(2026, 11, 6)) == ["ClienteActivo", "LicenciaVigente", "TarjetaValida"]

    def test_requiere_id_y_nombre(self):
        with pytest.raises(ErrorValidacion):
            self.cliente(id="")
