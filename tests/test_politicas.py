from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.domain.catalogo import CategoriaVehiculo
from src.domain.comun import ReglaNegocioViolada, Rol
from src.domain.politicas import (
    DecisionExtension,
    ParametrosNegocio,
    PoliticaCancelacion,
    PoliticaCargos,
    PoliticaExtension,
    PoliticaUpgrade,
    ServicioDisponibilidad,
)
from src.domain.valores import CondicionesContrato, DiferenciasInspeccion, Dinero, Kilometraje, PeriodoRenta
from src.domain.vehiculo import Vehiculo

T0 = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
P = ParametrosNegocio()


def condiciones(dias=2, devolucion=None, km_dia=200, tarifa=480):
    fin = T0 + timedelta(days=dias)
    return CondicionesContrato(PeriodoRenta(T0, fin), devolucion if devolucion is not None else fin, km_dia, "ECO", Dinero(tarifa))


class TestCargoPorRetraso:
    politica = PoliticaCargos(P)

    @pytest.mark.parametrize("min_tarde", [-30, 0, 29])
    def test_dentro_de_la_tolerancia_no_hay_cargo(self, min_tarde):
        c = condiciones(devolucion=T0 + timedelta(days=2, minutes=min_tarde))
        assert self.politica.cargo_retraso(c) is None

    @pytest.mark.parametrize("min_tarde, horas", [(30, 1), (60, 1), (61, 2), (150, 3)])
    def test_se_cobra_por_hora_iniciada(self, min_tarde, horas):
        cargo = self.politica.cargo_retraso(condiciones(devolucion=T0 + timedelta(days=2, minutes=min_tarde)))
        assert cargo.tipo == "RETRASO" and cargo.monto == Dinero(480).dividido_entre(24).por(horas)

    def test_el_cargo_tiene_tope_de_un_dia_de_tarifa(self):
        cargo = self.politica.cargo_retraso(condiciones(devolucion=T0 + timedelta(days=2, hours=40)))
        assert cargo.monto == Dinero(480)

    def test_exige_devolucion_real(self):
        c = CondicionesContrato(PeriodoRenta(T0, T0 + timedelta(days=1)), None, 200, "ECO", Dinero(480))
        with pytest.raises(ReglaNegocioViolada):
            self.politica.cargo_retraso(c)


class TestCargoPorKilometraje:
    politica = PoliticaCargos(P)

    @pytest.mark.parametrize("km, cobrado", [(0, None), (399, None), (400, None), (401, 3), (500, 300)])
    def test_incluidos_200_km_por_dia_y_3_pesos_por_excedente(self, km, cobrado):
        cargo = self.politica.cargo_kilometraje(DiferenciasInspeccion(km, 0), condiciones(dias=2))
        assert (cargo.monto.monto if cargo else None) == (Decimal(cobrado).quantize(Decimal("0.01")) if cobrado else None)

    def test_dias_facturables_se_redondean_hacia_arriba(self):
        c = CondicionesContrato(PeriodoRenta(T0, T0 + timedelta(hours=25)), None, 200, "ECO", Dinero(480))
        assert self.politica.cargo_kilometraje(DiferenciasInspeccion(400, 0), c) is None  # 25 h = 2 días = 400 km
        assert self.politica.cargo_kilometraje(DiferenciasInspeccion(401, 0), c).monto == Dinero(3)
        un_dia = CondicionesContrato(PeriodoRenta(T0, T0 + timedelta(hours=24)), None, 200, "ECO", Dinero(480))
        assert self.politica.cargo_kilometraje(DiferenciasInspeccion(201, 0), un_dia).monto == Dinero(3)


class TestCargoPorCombustible:
    politica = PoliticaCargos(P)

    @pytest.mark.parametrize("faltan, monto", [(0, None), (1, None), (2, 100), (4, 200)])
    def test_sin_cargo_hasta_un_octavo(self, faltan, monto):
        cargo = self.politica.cargo_combustible(DiferenciasInspeccion(0, faltan))
        assert (int(cargo.monto.monto) if cargo else None) == monto

    def test_calcular_combina_los_tres_cargos(self):
        cargos = self.politica.calcular(DiferenciasInspeccion(500, 3), condiciones(devolucion=T0 + timedelta(days=2, hours=1)))
        assert [c.tipo for c in cargos] == ["RETRASO", "KILOMETRAJE", "COMBUSTIBLE"]
        assert self.politica.calcular(DiferenciasInspeccion(10, 0), condiciones()) == []


class TestPoliticaCancelacion:
    politica = PoliticaCancelacion(P)

    def test_gratis_con_24_horas_y_penaliza_despues(self):
        assert not self.politica.evaluar(T0 + timedelta(hours=24), T0, Dinero(500)).penalizada
        r = self.politica.evaluar(T0 + timedelta(hours=23), T0, Dinero(500))
        assert r.penalizada and r.penalizacion == Dinero(500)

    def test_parametros_configurables(self):
        p = PoliticaCancelacion(ParametrosNegocio(horas_cancelacion_gratuita=48, dias_penalizacion=2, horas_no_show=1))
        assert p.evaluar(T0 + timedelta(hours=30), T0, Dinero(100)).penalizacion == Dinero(200)
        assert p.no_show_vencido(T0, T0 + timedelta(hours=1))
        assert not self.politica.no_show_vencido(T0, T0 + timedelta(hours=1, minutes=59))


class TestPoliticaExtension:
    politica = PoliticaExtension(P)
    fin = T0 + timedelta(days=2)

    @pytest.mark.parametrize("rol, horas, esperado", [
        (Rol.AGENTE, 24, DecisionExtension.APROBAR), (Rol.AGENTE, 48, DecisionExtension.APROBAR),
        (Rol.AGENTE, 49, DecisionExtension.REQUIERE_ADMINISTRACION),
        (Rol.ADMINISTRACION, 200, DecisionExtension.APROBAR),
    ])
    def test_quien_autoriza(self, rol, horas, esperado):
        assert self.politica.decidir(rol, horas, self.fin, T0) == esperado

    def test_exige_anticipacion_y_horas_positivas(self):
        with pytest.raises(ReglaNegocioViolada):
            self.politica.decidir(Rol.AGENTE, 24, self.fin, self.fin - timedelta(hours=1))
        with pytest.raises(ReglaNegocioViolada):
            self.politica.decidir(Rol.AGENTE, 0, self.fin, T0)
        assert self.politica.decidir(Rol.AGENTE, 24, self.fin, self.fin - timedelta(hours=2))


def categoria(id_, nivel, habilitada=True):
    return CategoriaVehiculo(id_, id_, nivel, Dinero(100 * nivel), Dinero(300 * nivel), habilitada=habilitada)


class TestUpgradeYDisponibilidad:
    def test_categoria_superior_es_la_habilitada_de_menor_nivel_mayor(self):
        cats = [categoria("A", 1), categoria("B", 2, habilitada=False), categoria("C", 3), categoria("D", 4)]
        assert PoliticaUpgrade.categoria_superior(cats[0], cats).id == "C"
        assert PoliticaUpgrade.categoria_superior(cats[3], cats) is None

    def test_unidades_disponibles_nunca_son_negativas(self):
        assert ServicioDisponibilidad.unidades_disponibles(5, 2, 1) == 2
        assert ServicioDisponibilidad.unidades_disponibles(1, 3, 3) == 0
        assert ServicioDisponibilidad.hay_unidad(2, 1, 0) and not ServicioDisponibilidad.hay_unidad(2, 1, 1)

    def test_asigna_la_unidad_con_menos_kilometros(self):
        vs = [Vehiculo("V2", "p2", "ECO", "S", Kilometraje(500)), Vehiculo("V1", "p1", "ECO", "S", Kilometraje(500)),
              Vehiculo("V3", "p3", "ECO", "S", Kilometraje(900))]
        assert ServicioDisponibilidad.asignar_unidad(vs).id == "V1"
        assert ServicioDisponibilidad.asignar_unidad([]) is None
