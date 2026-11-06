"""Pruebas de la API REST con TestClient: contrato de códigos HTTP, autorización y flujo completo."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api.main import crear_app
from src.config import Settings
from src.infrastructure.adaptadores import RelojSistema

from .escenario import AHORA, INICIO

FOTO = [{"nombre": "f.jpg", "contenido_base64": "eA=="}]


def h(actor_id, rol):
    return {"X-Actor-Id": actor_id, "X-Rol": rol}


AGE, PAT, LIM, ADM, SYS = h("AGE-01", "AGENTE"), h("PAT-01", "PATIO"), h("LIM-01", "LIMPIEZA"), h("ADM-01", "ADMINISTRACION"), h("SYS", "SISTEMA")
C1, C6 = h("C1", "CLIENTE"), h("C6", "CLIENTE")


@pytest.fixture
def cliente(servicios):
    with TestClient(crear_app(Settings(database_url="sqlite://", cargar_datos_demo=False), servicios=servicios)) as c:
        yield c


def reservar(cliente, headers=C1, cliente_id="C1", dias=2, inicio=INICIO):
    return cliente.post("/api/v1/reservaciones", headers=headers, json={
        "cliente_id": cliente_id, "categoria_id": "ECO", "sucursal_id": "SUC-MTY",
        "inicio": inicio.isoformat(), "fin": (inicio + timedelta(days=dias)).isoformat()})


class TestContratoDeLaApi:
    def test_salud_y_documentacion(self, cliente):
        r = cliente.get("/salud")
        assert r.status_code == 200 and r.json()["estado"] == "ok"
        assert cliente.get("/docs").status_code == 200
        spec = cliente.get("/openapi.json").json()
        assert spec["info"]["title"].startswith("NovaRent") and len(spec["paths"]) >= 30
        assert {"X-Actor-Id", "X-Rol"} <= {v["name"] for v in spec["components"]["securitySchemes"].values()}

    @pytest.mark.parametrize("headers", [{}, {"X-Actor-Id": "x"}, {"X-Actor-Id": "x", "X-Rol": "ROOT"}])
    def test_401_sin_identidad_valida(self, cliente, headers):
        r = cliente.get("/api/v1/categorias", headers=headers)
        assert r.status_code == 401 and r.json()["error"] == "http_401"

    def test_404_ruta_y_recurso(self, cliente):
        assert cliente.get("/no-existe").status_code == 404
        r = cliente.get("/api/v1/reservaciones/RES-NADA", headers=AGE)
        assert r.status_code == 404 and r.json() == {"error": "no_encontrado", "detalle": "Reservación RES-NADA no existe"}

    def test_422_validacion_de_entrada_con_campos_en_espanol(self, cliente):
        r = cliente.post("/api/v1/reservaciones", headers=C1, json={"cliente_id": "C1"})
        assert r.status_code == 422 and r.json()["error"] == "validacion_entrada"
        assert {d["campo"] for d in r.json()["detalle"]} >= {"body.categoria_id", "body.fin"}
        extra = cliente.post("/api/v1/reservaciones/R/entrega", headers=AGE, json={"licencia_numero": "x", "otro": 1})
        assert extra.status_code == 422

    def test_400_dato_mal_formado_de_dominio(self, cliente):
        r = reservar(cliente, dias=-1)
        assert r.status_code == 400 and r.json()["error"] == "validacion"
        naive = cliente.post("/api/v1/reservaciones", headers=C1, json={
            "cliente_id": "C1", "categoria_id": "ECO", "sucursal_id": "SUC-MTY", "inicio": "2026-11-06T09:00:00", "fin": "2026-11-07T09:00:00"})
        assert naive.status_code == 400 and "zona horaria" in naive.json()["detalle"]

    def test_422_regla_de_negocio_y_403_permiso(self, cliente):
        assert reservar(cliente, headers=h("C2", "CLIENTE"), cliente_id="C2").status_code == 422
        assert reservar(cliente, headers=C6, cliente_id="C1").status_code == 403
        r = cliente.post("/api/v1/reservaciones/liberar-no-shows", headers=C1)
        assert r.status_code == 403 and r.json()["error"] == "permiso_denegado"

    def test_409_conflicto_de_estado_y_de_disponibilidad(self, cliente):
        folio = reservar(cliente).json()["folio"]
        assert cliente.post(f"/api/v1/reservaciones/{folio}/cancelar", headers=C1).status_code == 200
        r = cliente.post(f"/api/v1/reservaciones/{folio}/cancelar", headers=C1)
        assert r.status_code == 409 and r.json()["error"] == "transicion_invalida"
        reservar(cliente), reservar(cliente, headers=C6, cliente_id="C6")
        r = reservar(cliente)
        assert r.status_code == 409 and r.json()["error"] == "sin_disponibilidad"

    def test_500_no_filtra_detalles_internos(self, servicios, monkeypatch):
        app = crear_app(Settings(database_url="sqlite://", cargar_datos_demo=False), servicios=servicios)
        monkeypatch.setattr(servicios.catalogo, "listar_categorias", lambda actor: 1 / 0)
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/api/v1/categorias", headers=AGE)
        assert r.status_code == 500 and r.json() == {"error": "error_interno", "detalle": "Ocurrió un error inesperado"}

    def test_validaciones_de_pydantic_en_cuerpos_anidados(self, cliente):
        r = cliente.post("/api/v1/inspecciones/entrega", headers=PAT, json={
            "folio": "R", "vehiculo_id": "V", "combustible_octavos": 9, "kilometraje": 1, "fotos": []})
        assert r.status_code == 422
        campos = {d["campo"] for d in r.json()["detalle"]}
        assert "body.combustible_octavos" in campos and "body.fotos" in campos


class TestFlujoPorHttp:
    def test_flujo_completo_de_renta_hasta_el_cierre(self, cliente, reloj):
        assert cliente.get("/api/v1/categorias", headers=C1).json()[0]["id"] == "ECO"
        assert cliente.get("/api/v1/sucursales", headers=C1).status_code == 200
        assert cliente.get("/api/v1/clientes/C1", headers=C1).json()["frecuente"] is True
        d = cliente.get("/api/v1/disponibilidad", headers=C1, params={
            "sucursal_id": "SUC-MTY", "inicio": INICIO.isoformat(), "fin": (INICIO + timedelta(days=2)).isoformat(), "categoria_id": "ECO"})
        assert d.json()[0]["disponibles"] == 2

        r = reservar(cliente)
        assert r.status_code == 201 and r.json()["estado"] == "CREADA"
        folio = r.json()["folio"]
        assert cliente.get(f"/api/v1/reservaciones/{folio}", headers=C1).json()["tarifa_diaria"] == "500.00"

        reloj.establecer(INICIO + timedelta(minutes=5))
        ent = cliente.post(f"/api/v1/reservaciones/{folio}/entrega", headers=AGE, json={"licencia_numero": "LIC-C1"})
        assert ent.status_code == 200 and not ent.json()["requiere_upgrade"]
        vehiculo = ent.json()["vehiculo_id"]
        insp = cliente.post("/api/v1/inspecciones/entrega", headers=PAT, json={
            "folio": folio, "vehiculo_id": vehiculo, "combustible_octavos": 8, "kilometraje": 1000, "fotos": FOTO, "danios": []})
        assert insp.status_code == 201
        firma = cliente.post(f"/api/v1/inspecciones/{insp.json()['id']}/firma", headers=C1, json={"firmante": "Cliente C1"})
        assert firma.json()["firmada"] is True
        contrato = cliente.post("/api/v1/contratos", headers=AGE, json={"folio": folio, "vehiculo_id": vehiculo, "inspeccion_id": insp.json()["id"]})
        assert contrato.status_code == 201
        cid = contrato.json()["id"]
        assert cliente.get(f"/api/v1/contratos/{cid}", headers=C1).json()["estado"] == "ABIERTO"
        assert cliente.get(f"/api/v1/vehiculos/{vehiculo}", headers=AGE).json()["estado"] == "RENTADO"
        assert cliente.get("/api/v1/sucursales/SUC-MTY/flota", headers=AGE).json()["por_estado"]["RENTADO"] == 1

        fin = datetime.fromisoformat(contrato.json()["fin"])
        reloj.establecer(fin - timedelta(hours=6))
        ext = cliente.post(f"/api/v1/contratos/{cid}/extensiones", headers=AGE, json={"horas": 72})
        assert ext.status_code == 201 and ext.json()["estado"] == "PENDIENTE"
        assert cliente.post(f"/api/v1/contratos/{cid}/extensiones/{ext.json()['id']}/aprobacion", headers=AGE).status_code == 403
        assert cliente.post(f"/api/v1/contratos/{cid}/extensiones/{ext.json()['id']}/aprobacion", headers=ADM).json()["estado"] == "APROBADA"
        conductor = cliente.post(f"/api/v1/contratos/{cid}/conductores", headers=AGE, json={
            "nombre": "Ana", "licencia_numero": "L1", "licencia_vigencia": "2030-01-01"})
        assert conductor.json()["conductores_adicionales"] == ["Ana"]

        nuevo_fin = datetime.fromisoformat(cliente.get(f"/api/v1/contratos/{cid}", headers=AGE).json()["fin"])
        reloj.establecer(nuevo_fin + timedelta(hours=1))
        dev = cliente.post(f"/api/v1/contratos/{cid}/inspeccion-devolucion", headers=PAT, json={
            "combustible_octavos": 5, "kilometraje": 2200, "fotos": FOTO,
            "danios": [{"zona": "puerta", "descripcion": "rayón", "fotos": FOTO}]})
        assert dev.status_code == 201
        assert cliente.post(f"/api/v1/contratos/{cid}/devolucion", headers=AGE).json()["estado"] == "DEVUELTO"
        liq = cliente.get(f"/api/v1/contratos/{cid}/liquidacion", headers=C1).json()
        tipos = {c["tipo"]: c for c in liq["cargos"]}
        assert set(tipos) == {"RETRASO", "KILOMETRAJE", "COMBUSTIBLE", "DANIO"} and liq["tiene_incidencias"]
        danio = tipos["DANIO"]["id"]
        base = f"/api/v1/contratos/{cid}/liquidacion/cargos/{danio}"
        assert cliente.post(f"{base}/aprobacion-danio", headers=ADM, json={"monto": "800.00"}).status_code == 200
        assert cliente.post(f"{base}/aprobacion-danio", headers=ADM, json={"monto": "-5"}).status_code == 422
        assert cliente.post(f"{base}/disputa", headers=C1, json={"motivo": "ya estaba"}).status_code == 200
        assert cliente.get(f"{base}/evidencia", headers=AGE).json()["danios_nuevos"][0]["zona"] == "puerta"
        res = cliente.post(f"{base}/resolucion", headers=ADM, json={"resolucion": "ANULADO"}).json()
        assert not res["tiene_incidencias"]

        tareas = cliente.get("/api/v1/limpieza/tareas", headers=LIM).json()
        assert len(tareas) == 1
        assert cliente.post(f"/api/v1/limpieza/tareas/{tareas[0]['id']}/completar", headers=LIM).json()["estado"] == "COMPLETADA"
        assert cliente.get(f"/api/v1/vehiculos/{vehiculo}", headers=AGE).json()["estado"] == "DISPONIBLE"

        reloj.establecer(nuevo_fin + timedelta(days=10))
        assert cliente.post("/api/v1/liquidaciones/liberar-depositos", headers=SYS).json() == {"liberadas": [liq["id"]]}
        assert cliente.get(f"/api/v1/contratos/{cid}", headers=AGE).json()["estado"] == "CERRADO"
        rep = cliente.get("/api/v1/reportes/ocupacion", headers=ADM, params={
            "sucursal_id": "SUC-MTY", "desde": "2026-11-01T00:00:00Z", "hasta": "2026-12-31T00:00:00Z"})
        assert rep.status_code == 200 and rep.json()["ingresos_renta"] == "2500.00"
        assert cliente.get("/api/v1/reportes/ocupacion", headers=ADM, params={
            "sucursal_id": "SUC-MTY", "desde": "2026-12-31T00:00:00Z", "hasta": "2026-11-01T00:00:00Z"}).status_code == 400

    def test_cancelacion_no_show_y_upgrade_de_cortesia(self, cliente, reloj):
        a = reservar(cliente).json()["folio"]
        b = reservar(cliente, headers=C6, cliente_id="C6", inicio=INICIO + timedelta(days=1)).json()["folio"]
        cancel = cliente.post(f"/api/v1/reservaciones/{b}/cancelar", headers=C6).json()
        assert cancel["penalizada"] is False
        cort = cliente.post(f"/api/v1/reservaciones/{a}/upgrade/cortesia", headers=ADM).json()
        assert cort["estado"] == "UPGRADE_ACEPTADO" and cort["categoria_asignada_id"] == "COMP"
        reloj.establecer(INICIO + timedelta(hours=3))
        assert cliente.post("/api/v1/reservaciones/liberar-no-shows", headers=SYS).json() == {"liberadas": [a]}
        assert cliente.post(f"/api/v1/reservaciones/{a}/upgrade/respuesta", headers=C1, json={"respuesta": "ACEPTAR"}).status_code == 409
        assert cliente.post(f"/api/v1/reservaciones/{a}/upgrade/respuesta", headers=C1, json={"respuesta": "TAL VEZ"}).status_code == 422


class TestRelojSimulado:
    def test_encabezado_x_ahora_solo_con_la_bandera_activada(self, servicios):
        servicios.ctx.reloj = RelojSistema()
        for svc in (servicios.reservaciones, servicios.entrega, servicios.inspecciones, servicios.contratos,
                    servicios.liquidaciones, servicios.flota, servicios.limpieza, servicios.reportes, servicios.catalogo):
            svc.ctx = servicios.ctx
        body = {"cliente_id": "C1", "categoria_id": "ECO", "sucursal_id": "SUC-MTY",
                "inicio": "2026-11-06T09:00:00Z", "fin": "2026-11-08T09:00:00Z"}
        with TestClient(crear_app(Settings(database_url="sqlite://", cargar_datos_demo=False, permitir_reloj_simulado=True), servicios=servicios)) as c:
            ok = c.post("/api/v1/reservaciones", headers={**C1, "X-Ahora": AHORA.isoformat()}, json=body)
            assert ok.status_code == 201
            tarde = c.post("/api/v1/reservaciones", headers={**C6, "X-Ahora": "2026-11-06T10:00:00Z"}, json={**body, "cliente_id": "C6"})
            assert tarde.status_code == 422 and "futuro" in tarde.json()["detalle"]
            malo = c.get("/api/v1/categorias", headers={**C1, "X-Ahora": "ayer"})
            assert malo.status_code == 400

    def test_sin_la_bandera_el_encabezado_se_ignora(self, cliente):
        r = cliente.get("/api/v1/categorias", headers={**C1, "X-Ahora": "ayer"})
        assert r.status_code == 200
