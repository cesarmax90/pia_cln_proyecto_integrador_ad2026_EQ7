from datetime import UTC, date, datetime, timedelta
from enum import Enum

import pytest

from src.domain.comun import TransicionInvalida
from src.domain.especificaciones import (
    CancelacionSinPenalizacion,
    ClienteActivo,
    CombustibleFaltante,
    ContextoCancelacion,
    ContextoCliente,
    ContextoDeposito,
    ContextoExtension,
    ContextoRetraso,
    DevolucionTardia,
    ExtensionConAnticipacion,
    ExtensionDentroDelLimiteDelAgente,
    LicenciaVigente,
    NoShowVencido,
    Predicado,
    SinIncidencias,
    TarjetaValida,
    cliente_apto,
    deposito_liberable,
    extension_autorizable_por_agente,
)
from src.domain.maquina_estados import MaquinaEstados
from src.domain.valores import DiferenciasInspeccion

T0 = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)


class E(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class TestMaquinaEstados:
    m = MaquinaEstados("Demo", {(E.A, "ir"): E.B, (E.B, "ir"): E.C})

    def test_transicion_valida_e_invalida(self):
        assert self.m.siguiente(E.A, "ir") == E.B
        with pytest.raises(TransicionInvalida) as exc:
            self.m.siguiente(E.C, "ir")
        assert "desde el estado C" in str(exc.value)

    def test_consultas(self):
        assert self.m.puede(E.A, "ir") and not self.m.puede(E.A, "volver")
        assert self.m.eventos_permitidos(E.B) == ["ir"]
        assert self.m.estados() == {E.A, E.B, E.C}


class TestComposicion:
    siempre, nunca = Predicado("siempre", lambda _: True), Predicado("nunca", lambda _: False)

    def test_and_or_not(self):
        assert (self.siempre & self.siempre).es_satisfecha_por(1)
        assert not (self.siempre & self.nunca).es_satisfecha_por(1)
        assert (self.siempre | self.nunca).es_satisfecha_por(1)
        assert not (self.nunca | self.nunca).es_satisfecha_por(1)
        assert (~self.nunca).es_satisfecha_por(1) and not (~self.siempre).es_satisfecha_por(1)

    def test_fallas_explican_que_parte_no_se_cumplio(self):
        assert (self.siempre & self.nunca).fallas(1) == ["nunca"]
        assert (self.nunca | self.nunca).fallas(1) == ["nunca", "nunca"]
        assert (self.siempre | self.nunca).fallas(1) == []
        assert (~self.siempre).fallas(1) == ["NOT siempre"]
        assert "AND" in (self.siempre & self.nunca).nombre


def ctx_cliente(**kw):
    base = dict(licencia_vigencia=date(2030, 1, 1), tiene_tarjeta_valida=True, activo=True, fecha_renta=date(2026, 11, 6))
    return ContextoCliente(**{**base, **kw})


class TestEspecificacionesNovaRent:
    def test_cliente_apto_combina_tres_reglas(self):
        assert cliente_apto().es_satisfecha_por(ctx_cliente())
        assert cliente_apto().fallas(ctx_cliente(activo=False)) == ["ClienteActivo"]
        assert cliente_apto().fallas(ctx_cliente(licencia_vigencia=date(2026, 11, 5), tiene_tarjeta_valida=False)) == [
            "LicenciaVigente", "TarjetaValida"]
        assert LicenciaVigente().es_satisfecha_por(ctx_cliente(licencia_vigencia=date(2026, 11, 6)))  # límite
        assert ClienteActivo().es_satisfecha_por(ctx_cliente()) and TarjetaValida().es_satisfecha_por(ctx_cliente())

    @pytest.mark.parametrize("faltan_h, gratis", [(48, True), (24, True), (23.99, False), (1, False), (-1, False)])
    def test_cancelacion_gratuita_desde_24_horas(self, faltan_h, gratis):
        c = ContextoCancelacion(T0 + timedelta(hours=faltan_h), T0)
        assert CancelacionSinPenalizacion(24).es_satisfecha_por(c) is gratis

    @pytest.mark.parametrize("despues_h, vencido", [(1.99, False), (2, True), (5, True), (-1, False)])
    def test_no_show_a_las_2_horas(self, despues_h, vencido):
        c = ContextoCancelacion(T0, T0 + timedelta(hours=despues_h))
        assert NoShowVencido(2).es_satisfecha_por(c) is vencido

    @pytest.mark.parametrize("horas, ok", [(1, True), (48, True), (49, False), (0, False), (-3, False)])
    def test_limite_de_extension_del_agente(self, horas, ok):
        assert ExtensionDentroDelLimiteDelAgente(48).es_satisfecha_por(ContextoExtension(T0, horas, T0)) is ok

    @pytest.mark.parametrize("faltan_h, ok", [(3, True), (2, True), (1.99, False), (0, False)])
    def test_extension_con_anticipacion_de_2_horas(self, faltan_h, ok):
        c = ContextoExtension(T0 + timedelta(hours=faltan_h), 24, T0)
        assert ExtensionConAnticipacion(2).es_satisfecha_por(c) is ok

    def test_extension_autorizable_compone_dos_reglas(self):
        spec = extension_autorizable_por_agente(48, 2)
        assert spec.es_satisfecha_por(ContextoExtension(T0 + timedelta(hours=5), 24, T0))
        assert spec.fallas(ContextoExtension(T0 + timedelta(hours=5), 72, T0)) == ["ExtensionHasta48h"]
        assert len(spec.fallas(ContextoExtension(T0 + timedelta(hours=1), 72, T0))) == 2

    @pytest.mark.parametrize("min_tarde, tardia", [(0, False), (29, False), (30, True), (90, True), (-10, False)])
    def test_devolucion_tardia_con_tolerancia_de_29_minutos(self, min_tarde, tardia):
        c = ContextoRetraso(T0, T0 + timedelta(minutes=min_tarde))
        assert DevolucionTardia(29).es_satisfecha_por(c) is tardia

    @pytest.mark.parametrize("faltan, cobra", [(0, False), (1, False), (2, True), (8, True)])
    def test_combustible_faltante_mayor_a_un_octavo(self, faltan, cobra):
        assert CombustibleFaltante(1).es_satisfecha_por(DiferenciasInspeccion(0, faltan)) is cobra

    def test_deposito_liberable_exige_plazo_y_ausencia_de_incidencias(self):
        def ctx(ahora_h, incid):
            return ContextoDeposito(T0, T0 + timedelta(hours=ahora_h), T0 + timedelta(days=7), incid)
        assert deposito_liberable().es_satisfecha_por(ctx(24 * 7, False))
        assert deposito_liberable().fallas(ctx(24, False)) == ["PlazoDeLiberacionCumplido"]
        assert deposito_liberable().fallas(ctx(24 * 7, True)) == ["SinIncidencias"]
        assert SinIncidencias().es_satisfecha_por(ctx(0, False))
