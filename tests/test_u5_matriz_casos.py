"""Unidad 5 · Paso 9 (E9): casos de prueba de 3 reglas reales del PIA de NovaRent.

Cada prueba lleva un ID CP-U5-NN que enlaza con docs/evidencias/matriz_casos_u5.csv.
Las pruebas ejercitan el código real de `src/` (no una copia) y usan fechas fijas.

Reglas elegidas (BRD, Anexo A):
  R1  US14 · RN-03/RN-04  Cargo por kilometraje excedente (200 km/día, $3 por km)
  R2  US11/US12 · RN-07/RN-08/RN-09  Autorización de extensiones por rol
  R3  US03/US04 · RN-01/RN-02  Cancelación gratuita (24 h) y no-show (2 h)

Además: persistencia (commit/rollback con Unit of Work) y pasarela de pago simulada con Mock.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from src.application.base import contrato_id_de
from src.application.puertos import Actor
from src.composicion import construir_servicios
from src.config import Settings
from src.domain.catalogo import CategoriaVehiculo
from src.domain.comun import ErrorValidacion, ReglaNegocioViolada, Rol, TransicionInvalida
from src.domain.politicas import (
    DecisionExtension,
    ParametrosNegocio,
    PoliticaCancelacion,
    PoliticaCargos,
    PoliticaExtension,
)
from src.domain.reservacion import EstadoReservacion, Reservacion
from src.domain.valores import (
    CondicionesContrato,
    DiferenciasInspeccion,
    Dinero,
    Kilometraje,
    PeriodoRenta,
    ReferenciaPago,
)
from src.infrastructure.adaptadores import GeneradorIdsSecuencial, RelojFijo
from src.infrastructure.db import metadata

from .conftest import URL_PRUEBAS
from .escenario import AGENTE, AHORA, INICIO, Flujo, sembrar

P = ParametrosNegocio()
T0 = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)


# ============================================================ R1 · kilometraje (US14)
def _condiciones(dias):
    return CondicionesContrato(PeriodoRenta(T0, T0 + timedelta(days=dias)), None, 200, "ECO", Dinero(480))


@pytest.mark.parametrize(
    ("km", "dias", "monto_esperado"),
    [
        pytest.param(750, 3, 450, id="CP-U5-01"),   # éxito: 750 - 600 = 150 km x $3
        pytest.param(600, 3, None, id="CP-U5-03"),  # límite: exactamente lo incluido, sin cargo
        pytest.param(601, 3, 3, id="CP-U5-04"),     # límite: 1 km sobre lo incluido
    ],
)
def test_cargo_kilometraje(km, dias, monto_esperado):
    cargo = PoliticaCargos(P).cargo_kilometraje(DiferenciasInspeccion(km, 0), _condiciones(dias))
    if monto_esperado is None:
        assert cargo is None
    else:
        assert cargo.tipo == "KILOMETRAJE"
        assert cargo.monto == Dinero(monto_esperado)


def test_cp_u5_02_odometro_final_menor_al_inicial_es_error():
    with pytest.raises(ErrorValidacion, match="no puede ser menor"):
        Kilometraje(900).recorrido_desde(Kilometraje(1000))


# ============================================================ R2 · extensiones (US11/US12)
FIN = T0 + timedelta(days=2)


@pytest.mark.parametrize(
    ("rol", "horas", "anticipacion_h", "esperado"),
    [
        pytest.param(Rol.AGENTE, 24, 10, DecisionExtension.APROBAR, id="CP-U5-05"),  # éxito
        pytest.param(Rol.AGENTE, 48, 10, DecisionExtension.APROBAR, id="CP-U5-07"),  # límite: 48 h exactas
        pytest.param(Rol.AGENTE, 49, 10, DecisionExtension.REQUIERE_ADMINISTRACION, id="CP-U5-08"),  # límite: 48 h + 1
        pytest.param(Rol.AGENTE, 24, 2, DecisionExtension.APROBAR, id="CP-U5-09"),  # límite: 2 h exactas de anticipación
    ],
)
def test_decision_de_extension(rol, horas, anticipacion_h, esperado):
    ahora = FIN - timedelta(hours=anticipacion_h)
    assert PoliticaExtension(P).decidir(rol, horas, FIN, ahora) == esperado


def test_cp_u5_06_extension_con_menos_de_2_horas_es_error():
    ahora = FIN - timedelta(hours=1, minutes=58)
    with pytest.raises(ReglaNegocioViolada, match="anticipación"):
        PoliticaExtension(P).decidir(Rol.AGENTE, 24, FIN, ahora)


# ============================================================ R3 · cancelación y no-show (US03/US04)
CATEGORIA = CategoriaVehiculo("ECO", "Económico", 1, Dinero(500), Dinero(1500))
PERIODO = PeriodoRenta(INICIO, INICIO + timedelta(days=2))


def _reservacion(folio="R-U5"):
    return Reservacion.crear(folio, "C1", CATEGORIA, "SUC-MTY", PERIODO, AHORA)


@pytest.mark.parametrize(
    ("horas_antes", "penaliza", "penalizacion"),
    [
        pytest.param(48, False, 0, id="CP-U5-10"),            # éxito: cancelación gratuita
        pytest.param(24, False, 0, id="CP-U5-12"),            # límite: 24 h exactas, sin penalización
        pytest.param(23 + 59 / 60, True, 500, id="CP-U5-13"),  # límite: 23 h 59 min, penaliza 1 día
    ],
)
def test_cancelacion(horas_antes, penaliza, penalizacion):
    r = _reservacion()
    ahora = INICIO - timedelta(hours=horas_antes)
    resultado = r.cancelar(ahora, Rol.CLIENTE, PoliticaCancelacion(P))
    assert resultado.penalizada is penaliza
    assert resultado.penalizacion == Dinero(penalizacion)
    assert r.estado == EstadoReservacion.CANCELADA


def test_cp_u5_11_no_se_cancela_dos_veces():
    r = _reservacion()
    r.cancelar(INICIO - timedelta(hours=48), Rol.CLIENTE, PoliticaCancelacion(P))
    with pytest.raises(TransicionInvalida):
        r.cancelar(INICIO - timedelta(hours=47), Rol.CLIENTE, PoliticaCancelacion(P))


def test_cp_u5_14_no_show_a_las_2_horas_exactas_libera():  # límite
    r = _reservacion()
    r.liberar_por_no_show(INICIO + timedelta(hours=2), PoliticaCancelacion(P))
    assert r.estado == EstadoReservacion.LIBERADA_NO_SHOW


def test_cp_u5_15_no_show_antes_de_2_horas_es_error():
    r = _reservacion()
    with pytest.raises(ReglaNegocioViolada, match="no-show"):
        r.liberar_por_no_show(INICIO + timedelta(hours=1, minutes=58), PoliticaCancelacion(P))
    assert r.estado == EstadoReservacion.CREADA


# ============================================================ Persistencia (Unit of Work)
@pytest.fixture
def s(servicios):
    return servicios


def test_cp_u5_16_reservacion_cancelada_sobrevive_al_commit(s):
    with s.ctx.uow_factory() as uow:
        r = Reservacion.crear("R-U5", "C1", uow.categorias.obtener("ECO"), "SUC-MTY", PERIODO, AHORA)
        r.cancelar(INICIO - timedelta(hours=23), Rol.CLIENTE, PoliticaCancelacion(P))
        uow.reservaciones.guardar(r)
    with s.ctx.uow_factory() as uow:  # transacción nueva: lee lo realmente persistido
        guardada = uow.reservaciones.obtener("R-U5")
        assert guardada.estado == EstadoReservacion.CANCELADA
        assert guardada.penalizacion == Dinero(500)


def test_cp_u5_17_rollback_descarta_la_reservacion(s):
    with pytest.raises(RuntimeError):
        with s.ctx.uow_factory() as uow:
            uow.reservaciones.guardar(
                Reservacion.crear("R-U5", "C1", uow.categorias.obtener("ECO"), "SUC-MTY", PERIODO, AHORA)
            )
            raise RuntimeError("falla antes de confirmar")
    with s.ctx.uow_factory() as uow:
        assert not uow.reservaciones.existe("R-U5")


# ============================================================ Pasarela de pago simulada (Mock)
@pytest.fixture
def con_pasarela_mock():
    """Servicios reales con la pasarela sustituida por un Mock: nunca hay cobros reales."""
    pasarela = Mock(spec=["verificar_tarjeta", "retener_deposito", "liberar_deposito"])
    pasarela.verificar_tarjeta.return_value = True
    reloj = RelojFijo(AHORA)
    servicios = construir_servicios(
        Settings(database_url=URL_PRUEBAS, cargar_datos_demo=False), reloj=reloj,
        ids=GeneradorIdsSecuencial(), pasarela=pasarela, propagar_errores_bus=True,
    )
    if not URL_PRUEBAS.startswith("sqlite"):
        metadata.drop_all(servicios.motor)  # mismo aislamiento que conftest.py en una base compartida
        metadata.create_all(servicios.motor)
    sembrar(servicios)
    yield pasarela, servicios, Flujo(servicios, reloj)
    servicios.motor.dispose()


def _preparar_entrega(flujo):
    folio = flujo.reservar("C1").folio
    vehiculo_id, inspeccion = flujo.entregar(folio, "C1")
    return folio, vehiculo_id, inspeccion


def test_cp_u5_18_deposito_aprobado_abre_el_contrato(con_pasarela_mock):
    pasarela, servicios, flujo = con_pasarela_mock
    pasarela.retener_deposito.return_value = ReferenciaPago("MOCK-OK-1")
    folio, vehiculo_id, inspeccion = _preparar_entrega(flujo)

    contrato = servicios.contratos.abrir_contrato(AGENTE, folio, vehiculo_id, inspeccion.id)

    assert contrato.id
    pasarela.retener_deposito.assert_called_once()
    metodo, monto = pasarela.retener_deposito.call_args.args
    assert metodo.token == "tok_c1" and monto == Dinero(1500)  # depósito de la categoría ECO
    pasarela.liberar_deposito.assert_not_called()


def test_cp_u5_19_deposito_rechazado_no_deja_contrato_abierto(con_pasarela_mock):
    pasarela, servicios, flujo = con_pasarela_mock
    pasarela.retener_deposito.side_effect = ReglaNegocioViolada("El banco rechazó la retención")
    folio, vehiculo_id, inspeccion = _preparar_entrega(flujo)

    with pytest.raises(ReglaNegocioViolada, match="rechazó"):
        servicios.contratos.abrir_contrato(Actor("AGE-01", Rol.AGENTE), folio, vehiculo_id, inspeccion.id)

    pasarela.retener_deposito.assert_called_once()
    with servicios.ctx.uow_factory() as uow:
        assert not uow.contratos.existe(contrato_id_de(folio))
