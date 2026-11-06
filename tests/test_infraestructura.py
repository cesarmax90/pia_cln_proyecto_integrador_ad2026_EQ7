import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.composicion import construir_servicios
from src.config import Settings
from src.domain import eventos as ev
from src.domain.comun import ErrorValidacion, NoEncontrado, ReglaNegocioViolada, Rol
from src.domain.contrato import ContratoRenta
from src.domain.inspeccion import InspeccionVehiculo, TipoInspeccion
from src.domain.politicas import ParametrosNegocio, PoliticaExtension
from src.domain.reservacion import Reservacion
from src.domain.valores import (
    Dinero,
    EvidenciaFoto,
    Kilometraje,
    MetodoPagoRef,
    NivelCombustible,
    PeriodoRenta,
    ReferenciaPago,
    RegistroDanio,
)
from src.infrastructure import db
from src.infrastructure.adaptadores import (
    AlmacenEvidenciaDisco,
    AlmacenEvidenciaMemoria,
    BusEventosEnMemoria,
    CalendarioHabilMX,
    GeneradorIdsSecuencial,
    GeneradorIdsUuid,
    NotificadorRegistro,
    PasarelaPagoSimulada,
    RelojFijo,
    RelojSistema,
)
from src.infrastructure.datos_demo import cargar_demo
from src.infrastructure.db import crear_motor, normalizar_url
from src.infrastructure.serializacion import codificar, decodificar

from .escenario import INICIO

T0 = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)


class TestSerializacion:
    def test_ida_y_vuelta_de_un_contrato_completo(self):
        c = ContratoRenta.abrir("CTR-1", "R1", "C1", "V1", "ECO", "S1", PeriodoRenta(T0, T0 + timedelta(days=2)),
                                Dinero(500), 200, Dinero(1500), ReferenciaPago("PAY-1"), "INS-1", T0)
        c.solicitar_extension(100, "ADM", Rol.ADMINISTRACION, T0, PoliticaExtension(ParametrosNegocio()))
        json_ = codificar(c)
        assert isinstance(json_["tarifa_diaria"]["monto"], str) and json_["estado"] == "ABIERTO"
        copia = decodificar(ContratoRenta, json_)
        assert copia == c and copia.periodo.fin.tzinfo is not None

    def test_ida_y_vuelta_de_inspeccion_con_tuplas_anidadas(self):
        foto = EvidenciaFoto("u", T0)
        i = InspeccionVehiculo.registrar("I", "C", "V", TipoInspeccion.ENTREGA, "E", NivelCombustible(7), Kilometraje(10),
                                         (foto,), (RegistroDanio("z", "d", (foto,)),), T0)
        assert decodificar(InspeccionVehiculo, codificar(i)) == i

    def test_decodificar_ignora_none_y_tipos_simples(self):
        assert decodificar(int, None) is None and decodificar(str, "x") == "x"
        assert decodificar(date, "2026-11-06") == date(2026, 11, 6)


class TestRepositorios:
    def test_obtener_inexistente_lanza_no_encontrado(self, servicios):
        with servicios.ctx.uow_factory() as uow:
            with pytest.raises(NoEncontrado, match="Cliente X no existe"):
                uow.clientes.obtener("X")

    def test_guardar_dos_veces_actualiza_en_lugar_de_duplicar(self, servicios):
        with servicios.ctx.uow_factory() as uow:
            v = uow.vehiculos.obtener("VEH-ECO-1")
            v.kilometraje = Kilometraje(2000)
            uow.vehiculos.guardar(v)
        with servicios.ctx.uow_factory() as uow:
            assert uow.vehiculos.obtener("VEH-ECO-1").kilometraje.valor == 2000
            assert uow.vehiculos.contar_flota("ECO", "SUC-MTY") == 2

    def test_rollback_ante_excepcion_no_persiste_nada(self, servicios):
        with pytest.raises(RuntimeError):
            with servicios.ctx.uow_factory() as uow:
                v = uow.vehiculos.obtener("VEH-ECO-1")
                v.kilometraje = Kilometraje(9999)
                uow.vehiculos.guardar(v)
                raise RuntimeError("falla a mitad de la transacción")
        with servicios.ctx.uow_factory() as uow:
            assert uow.vehiculos.obtener("VEH-ECO-1").kilometraje.valor == 1000

    def test_los_eventos_solo_existen_si_hubo_commit(self, servicios):
        with servicios.ctx.uow_factory() as uow:
            r = Reservacion.crear("R9", "C1", uow.categorias.obtener("ECO"), "SUC-MTY",
                                  PeriodoRenta(INICIO, INICIO + timedelta(days=1)), INICIO - timedelta(days=1))
            uow.reservaciones.guardar(r)
        assert [type(e) for e in uow.eventos] == [ev.ReservacionCreada]

    def test_catalogos_ordenados(self, servicios):
        with servicios.ctx.uow_factory() as uow:
            assert [c.nivel for c in uow.categorias.listar()] == [1, 2, 3, 4]
            assert [s.id for s in uow.sucursales.listar()] == ["SUC-APO", "SUC-MTY"]
            assert len(uow.vehiculos.listar_por_sucursal("SUC-MTY")) == 4

    def test_datetimes_regresan_con_zona_utc_desde_las_columnas(self, servicios, flujo):
        flujo.reservar()
        with servicios.ctx.uow_factory() as uow:
            inicio = uow.session.execute(select(db.reservaciones.c.inicio)).scalar_one()
        assert inicio == INICIO and inicio.tzinfo is not None

    def test_dinero_se_guarda_en_centavos_exactos(self, servicios, flujo):
        _, _, contrato = flujo.abrir()
        with servicios.ctx.uow_factory() as uow:
            monto = uow.session.execute(select(db.contratos.c.monto_base)).scalar_one()
        assert monto == Decimal("1000.00")

    def test_no_se_persisten_datetimes_sin_zona(self):
        from src.infrastructure.db import UTCDateTime
        with pytest.raises(ValueError):
            UTCDateTime().process_bind_param(datetime(2026, 1, 1), None)
        assert UTCDateTime().process_bind_param(None, None) is None
        assert UTCDateTime().process_result_value(None, None) is None
        assert UTCDateTime().process_result_value(datetime(2026, 1, 1), None).tzinfo is UTC


class TestMotor:
    @pytest.mark.parametrize("entrada, esperada", [
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///x.db", "sqlite:///x.db"),
    ])
    def test_normaliza_la_url_de_base_de_datos(self, entrada, esperada):
        assert normalizar_url(entrada) == esperada

    def test_sqlite_en_memoria_comparte_una_sola_conexion(self):
        motor = crear_motor("sqlite://")
        assert motor.pool.__class__.__name__ == "StaticPool"


class TestCalendarioHabil:
    cal = CalendarioHabilMX()

    def test_5_dias_habiles_saltan_fin_de_semana_y_festivos(self):
        assert self.cal.sumar_dias_habiles(date(2026, 11, 8), 5) == date(2026, 11, 13)        # desde domingo
        assert self.cal.sumar_dias_habiles(date(2026, 11, 9), 5) == date(2026, 11, 17)        # lun 16 es festivo
        assert self.cal.sumar_dias_habiles(date(2026, 12, 24), 1) == date(2026, 12, 28)       # 25-dic festivo
        assert self.cal.sumar_dias_habiles(date(2026, 11, 6), 0) == date(2026, 11, 6)

    def test_festivos_y_extras(self):
        assert date(2026, 11, 16) in self.cal.festivos(2026) and date(2026, 2, 2) in self.cal.festivos(2026)
        extra = CalendarioHabilMX({date(2026, 11, 10)})
        assert not extra.es_habil(date(2026, 11, 10)) and self.cal.es_habil(date(2026, 11, 10))

    def test_no_acepta_dias_negativos(self):
        with pytest.raises(ErrorValidacion):
            self.cal.sumar_dias_habiles(date(2026, 11, 6), -1)


class TestAdaptadores:
    def test_pasarela_simulada(self):
        p = PasarelaPagoSimulada()
        assert p.verificar_tarjeta(MetodoPagoRef("tok_ok", "1111")) and not p.verificar_tarjeta(MetodoPagoRef("tok_rechazada", "1111"))
        ref = p.retener_deposito(MetodoPagoRef("tok_ok", "1111"), Dinero(100))
        assert ref.id_externo == "PAY-000001" and len(p.retenciones) == 1
        with pytest.raises(ReglaNegocioViolada):
            p.retener_deposito(MetodoPagoRef("tok_sin_fondos", "1111"), Dinero(100))
        p.liberar_deposito(ref)
        assert p.liberaciones == [ref]

    def test_almacen_de_evidencia_sanea_nombres(self, tmp_path):
        mem = AlmacenEvidenciaMemoria()
        assert mem.guardar("INS-1", "../../etc/passwd", b"x") == "evidencias/INS-1/.._.._etc_passwd"
        disco = AlmacenEvidenciaDisco(tmp_path)
        uri = disco.guardar("INS 1", "foto frente.jpg", b"abc")
        assert (tmp_path / uri).read_bytes() == b"abc" and tmp_path in (tmp_path / uri).parents

    def test_bus_aisla_errores_de_handlers(self, caplog):
        bus = BusEventosEnMemoria()
        llamados = []
        bus.suscribir(ev.TareaLimpiezaCompletada, lambda e: 1 / 0)
        bus.suscribir(ev.TareaLimpiezaCompletada, llamados.append)
        evento = ev.TareaLimpiezaCompletada(T0, "T", "V")
        with caplog.at_level(logging.ERROR):
            bus.publicar([evento])
        assert llamados == [evento] and len(bus.errores) == 1 and bus.historial == [evento]

    def test_bus_puede_propagar_errores_en_pruebas(self):
        bus = BusEventosEnMemoria(propagar_errores=True)
        bus.suscribir(ev.TareaLimpiezaCompletada, lambda e: 1 / 0)
        with pytest.raises(ZeroDivisionError):
            bus.publicar([ev.TareaLimpiezaCompletada(T0, "T", "V")])

    def test_relojes_e_identificadores(self):
        fijo = RelojFijo(T0)
        fijo.avanzar(hours=2)
        assert fijo.ahora() == T0 + timedelta(hours=2)
        token = RelojSistema.fijar_para_la_peticion(T0)
        assert RelojSistema().ahora() == T0
        RelojSistema.restablecer(token)
        assert RelojSistema().ahora() != T0
        ids = GeneradorIdsSecuencial()
        assert [ids.nuevo("RES"), ids.nuevo("RES"), ids.nuevo("INS")] == ["RES-0001", "RES-0002", "INS-0001"]
        assert GeneradorIdsUuid().nuevo("RES").startswith("RES-")

    def test_notificador_registra(self):
        n = NotificadorRegistro()
        n.enviar(ev.ContratoCerrado(T0, "C"))
        assert len(n.enviadas) == 1


class TestDatosDemo:
    def test_carga_los_csv_y_es_idempotente(self):
        s = construir_servicios(Settings(database_url="sqlite://", cargar_datos_demo=False))
        resumen = cargar_demo(s.ctx.uow_factory, "datos")
        assert resumen == {"sucursales": 2, "empleados": 4, "clientes": 40, "categorias": 20, "vehiculos": 160}
        assert cargar_demo(s.ctx.uow_factory, "datos") == {}
        with s.ctx.uow_factory() as uow:
            inactivos = [c for c in (uow.clientes.obtener(f"REN-C{n:03d}") for n in range(1, 41)) if not c.activo]
            assert inactivos and all(not c.puede_rentar(date(2026, 11, 6)) for c in inactivos)
            cats = uow.categorias.listar()
            assert cats[0].tarifa_diaria <= cats[-1].tarifa_diaria and cats[0].nivel == 1


class TestConfig:
    def test_parametros_desde_variables_de_entorno(self, monkeypatch):
        monkeypatch.setenv("TOLERANCIA_RETRASO_MIN", "15")
        monkeypatch.setenv("TARIFA_KM_EXCEDENTE", "4.50")
        monkeypatch.setenv("DATABASE_URL", "sqlite://")
        settings = Settings(_env_file=None)
        p = settings.parametros_negocio()
        assert p.tolerancia_retraso_min == 15 and p.tarifa_km_excedente == Dinero("4.50")
        assert settings.database_url == "sqlite://"
