from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from src.domain.comun import ErrorValidacion
from src.domain.valores import (
    Dinero,
    Disputa,
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

T0 = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)


class TestDinero:
    def test_redondea_a_centavos_con_decimal(self):
        assert Dinero("10.005").monto == Decimal("10.01")
        assert Dinero(0.1 + 0.2).monto == Decimal("0.30")

    def test_suma_y_multiplicacion(self):
        assert (Dinero(100) + Dinero("50.50")).monto == Decimal("150.50")
        assert Dinero("3").por(100).monto == Decimal("300.00")

    def test_division_exacta_a_centavos(self):
        assert Dinero(382).dividido_entre(24).monto == Decimal("15.92")

    @pytest.mark.parametrize("valor", [-1, "abc", None])
    def test_rechaza_valores_invalidos(self, valor):
        with pytest.raises(ErrorValidacion):
            Dinero(valor)

    def test_rechaza_otra_moneda_y_divisor_invalido(self):
        with pytest.raises(ErrorValidacion):
            Dinero(1, "USD")
        with pytest.raises(ErrorValidacion):
            Dinero(1).dividido_entre(0)

    def test_igualdad_orden_y_texto(self):
        assert Dinero(5) == Dinero("5.00") and Dinero(5) < Dinero(6)
        assert Dinero.cero().es_cero()
        assert str(Dinero(1234.5)) == "$1,234.50 MXN"


class TestPeriodoRenta:
    def test_dias_son_bloques_de_24_horas_minimo_uno(self):
        assert PeriodoRenta(T0, T0 + timedelta(hours=3)).dias == 1
        assert PeriodoRenta(T0, T0 + timedelta(hours=24)).dias == 1
        assert PeriodoRenta(T0, T0 + timedelta(hours=25)).dias == 2
        assert PeriodoRenta(T0, T0 + timedelta(days=2)).dias == 2

    def test_fin_debe_ser_posterior_y_exige_zona_horaria(self):
        with pytest.raises(ErrorValidacion):
            PeriodoRenta(T0, T0)
        with pytest.raises(ErrorValidacion):
            PeriodoRenta(datetime(2026, 1, 1), datetime(2026, 1, 2, tzinfo=UTC))

    def test_extender_y_traslape(self):
        p = PeriodoRenta(T0, T0 + timedelta(days=1))
        assert p.extender(24).fin == T0 + timedelta(days=2)
        assert p.se_traslapa_con(PeriodoRenta(T0 + timedelta(hours=23), T0 + timedelta(days=2)))
        assert not p.se_traslapa_con(PeriodoRenta(T0 + timedelta(days=1), T0 + timedelta(days=2)))


class TestMedidas:
    def test_kilometraje(self):
        assert Kilometraje(1500).recorrido_desde(Kilometraje(1000)) == 500
        with pytest.raises(ErrorValidacion):
            Kilometraje(900).recorrido_desde(Kilometraje(1000))
        for malo in (-1, 1.5, True):
            with pytest.raises(ErrorValidacion):
                Kilometraje(malo)

    def test_combustible_en_octavos(self):
        assert NivelCombustible(5).faltante_respecto_a(NivelCombustible(8)) == 3
        assert NivelCombustible(8).faltante_respecto_a(NivelCombustible(5)) == 0
        for malo in (-1, 9, 2.5):
            with pytest.raises(ErrorValidacion):
                NivelCombustible(malo)


class TestIdentidadesYEvidencia:
    def test_licencia(self):
        lic = Licencia("L1", date(2026, 11, 6))
        assert lic.vigente_en(date(2026, 11, 6)) and not lic.vigente_en(date(2026, 11, 7))
        with pytest.raises(ErrorValidacion):
            Licencia("  ", date(2030, 1, 1))

    def test_metodo_pago_nunca_guarda_numero_de_tarjeta(self):
        assert MetodoPagoRef("tok_abc", "4242").ultimos4 == "4242"
        with pytest.raises(ErrorValidacion):
            MetodoPagoRef("4111111111111111", "1111")
        with pytest.raises(ErrorValidacion):
            MetodoPagoRef("tok_abc", "12")
        with pytest.raises(ErrorValidacion):
            MetodoPagoRef("", "1234")

    def test_referencia_pago_obligatoria(self):
        with pytest.raises(ErrorValidacion):
            ReferenciaPago("")

    def test_foto_exige_sello_de_tiempo_con_zona(self):
        with pytest.raises(ErrorValidacion):
            EvidenciaFoto("u", datetime(2026, 1, 1))
        with pytest.raises(ErrorValidacion):
            EvidenciaFoto("", T0)

    def test_danio_exige_foto_zona_y_descripcion(self):
        foto = EvidenciaFoto("u", T0)
        assert RegistroDanio("puerta", "rayón", (foto,)).clave == ("puerta", "rayón")
        with pytest.raises(ErrorValidacion):
            RegistroDanio("puerta", "rayón", ())
        with pytest.raises(ErrorValidacion):
            RegistroDanio("", "x", (foto,))

    def test_firma_y_disputa(self):
        with pytest.raises(ErrorValidacion):
            FirmaDigital("", T0)
        with pytest.raises(ErrorValidacion):
            Disputa("", T0)
