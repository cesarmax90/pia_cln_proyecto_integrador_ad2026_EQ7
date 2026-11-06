"""Demostración end-to-end por HTTP (solo biblioteca estándar).

Requiere el servidor con PERMITIR_RELOJ_SIMULADO=true y datos demo:
    PERMITIR_RELOJ_SIMULADO=true uvicorn --factory src.api.main:crear_app
    python scripts/demo_flujo.py [URL_BASE]
Recorre: reservar -> entregar -> contrato -> extensión -> devolución tardía -> cargos -> disputa -> limpieza -> depósito.
"""

import base64
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
AGENTE, PATIO, LIMPIEZA, ADMIN, SISTEMA = (
    ("AGE-01", "AGENTE"),
    ("PAT-01", "PATIO"),
    ("LIM-01", "LIMPIEZA"),
    ("ADM-01", "ADMINISTRACION"),
    ("SYS", "SISTEMA"),
)
CLIENTE = ("REN-C001", "CLIENTE")
FOTO = [{"nombre": "frente.jpg", "contenido_base64": base64.b64encode(b"foto").decode()}]
paso = 0


def iso(d: datetime) -> str:
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def llamar(metodo, ruta, actor, ahora, cuerpo=None, esperado=(200, 201)):
    global paso
    paso += 1
    headers = {"Content-Type": "application/json", "X-Actor-Id": actor[0], "X-Rol": actor[1], "X-Ahora": iso(ahora)}
    req = urllib.request.Request(
        BASE + ruta, method=metodo, headers=headers, data=json.dumps(cuerpo).encode() if cuerpo else None
    )
    try:
        with OPENER.open(req, timeout=30) as r:
            estado, datos = r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        estado, datos = e.code, json.loads(e.read())
    marca = "OK " if estado in esperado else "!! "
    print(f"{marca}{paso:02d} {metodo:4s} {ruta}  [{actor[1]}]  -> {estado}")
    if estado not in esperado:
        sys.exit(f"Respuesta inesperada: {json.dumps(datos, ensure_ascii=False)}")
    return datos


def main():
    t0 = datetime(2030, 3, 1, 10, 0, tzinfo=UTC)
    inicio, fin = t0 + timedelta(days=1, hours=-1), t0 + timedelta(days=3, hours=-1)
    suc, cat = "SUC-APODACA", "REN-P001"
    print(f"== Demo NovaRent en {BASE} ==\n-- Reservación")
    print(llamar("GET", "/salud", AGENTE, t0))
    disp = llamar(
        "GET", f"/api/v1/disponibilidad?sucursal_id={suc}&inicio={iso(inicio)}&fin={iso(fin)}&categoria_id={cat}", CLIENTE, t0
    )
    print("   disponibles:", disp[0]["disponibles"])
    res = llamar(
        "POST",
        "/api/v1/reservaciones",
        CLIENTE,
        t0,
        {"cliente_id": CLIENTE[0], "categoria_id": cat, "sucursal_id": suc, "inicio": iso(inicio), "fin": iso(fin)},
    )
    folio = res["folio"]
    print("   folio:", folio, "| tarifa diaria:", res["tarifa_diaria"])

    print("-- Entrega")
    llegada = inicio + timedelta(minutes=5)
    ent = llamar("POST", f"/api/v1/reservaciones/{folio}/entrega", AGENTE, llegada, {"licencia_numero": "LIC-REN-C001"})
    veh = ent["vehiculo_id"]
    print("   unidad asignada:", veh)
    insp = llamar(
        "POST",
        "/api/v1/inspecciones/entrega",
        PATIO,
        llegada,
        {"folio": folio, "vehiculo_id": veh, "combustible_octavos": 8, "kilometraje": 1000, "fotos": FOTO, "danios": []},
    )
    llamar("POST", f"/api/v1/inspecciones/{insp['id']}/firma", CLIENTE, llegada, {"firmante": "Arrendatario 01"})
    contrato = llamar(
        "POST", "/api/v1/contratos", AGENTE, llegada, {"folio": folio, "vehiculo_id": veh, "inspeccion_id": insp["id"]}
    )
    cid = contrato["id"]
    print("   contrato:", cid, "| monto base:", contrato["monto_base"])

    print("-- Extensión de 72 h (requiere Administración)")
    ahora = datetime.fromisoformat(contrato["fin"].replace("Z", "+00:00")) - timedelta(hours=6)
    ext = llamar("POST", f"/api/v1/contratos/{cid}/extensiones", AGENTE, ahora, {"horas": 72})
    print("   estado:", ext["estado"])
    llamar("POST", f"/api/v1/contratos/{cid}/extensiones/{ext['id']}/aprobacion", AGENTE, ahora, esperado=(403,))
    llamar("POST", f"/api/v1/contratos/{cid}/extensiones/{ext['id']}/aprobacion", ADMIN, ahora)

    print("-- Devolución tardía con combustible, kilometraje y un daño")
    nuevo_fin = datetime.fromisoformat(llamar("GET", f"/api/v1/contratos/{cid}", AGENTE, ahora)["fin"].replace("Z", "+00:00"))
    devolucion = nuevo_fin + timedelta(hours=1, minutes=10)
    llamar(
        "POST",
        f"/api/v1/contratos/{cid}/inspeccion-devolucion",
        PATIO,
        devolucion,
        {
            "combustible_octavos": 5,
            "kilometraje": 2200,
            "fotos": FOTO,
            "danios": [{"zona": "puerta", "descripcion": "rayón profundo", "fotos": FOTO}],
        },
    )
    llamar("POST", f"/api/v1/contratos/{cid}/devolucion", AGENTE, devolucion)
    liq = llamar("GET", f"/api/v1/contratos/{cid}/liquidacion", CLIENTE, devolucion)
    for c in liq["cargos"]:
        print(f"   {c['tipo']:12s} {c['monto']:>9s}  {c['estado']:22s} {c['descripcion']}")

    print("-- Disputa del daño")
    danio = next(c["id"] for c in liq["cargos"] if c["tipo"] == "DANIO")
    base = f"/api/v1/contratos/{cid}/liquidacion/cargos/{danio}"
    llamar("POST", f"{base}/aprobacion-danio", ADMIN, devolucion, {"monto": "800.00"})
    llamar("POST", f"{base}/disputa", CLIENTE, devolucion, {"motivo": "El rayón ya estaba al recibir la unidad"})
    evid = llamar("GET", f"{base}/evidencia", AGENTE, devolucion)
    print("   daños nuevos según la comparación:", [d["zona"] for d in evid["danios_nuevos"]])
    liq = llamar("POST", f"{base}/resolucion", ADMIN, devolucion, {"resolucion": "ANULADO"})
    print("   total de cargos tras la disputa:", liq["total_cargos"], "| incidencias:", liq["tiene_incidencias"])

    print("-- Limpieza y depósito")
    tarea = llamar("GET", "/api/v1/limpieza/tareas", LIMPIEZA, devolucion)[0]
    llamar("POST", f"/api/v1/limpieza/tareas/{tarea['id']}/completar", LIMPIEZA, devolucion + timedelta(hours=3))
    print("   unidad:", llamar("GET", f"/api/v1/vehiculos/{veh}", AGENTE, devolucion)["estado"])
    print(
        "   liberación a 1 día:",
        llamar("POST", "/api/v1/liquidaciones/liberar-depositos", SISTEMA, devolucion + timedelta(days=1)),
    )
    print(
        "   liberación a 10 días:",
        llamar("POST", "/api/v1/liquidaciones/liberar-depositos", SISTEMA, devolucion + timedelta(days=10)),
    )
    print("   contrato:", llamar("GET", f"/api/v1/contratos/{cid}", AGENTE, devolucion + timedelta(days=10))["estado"])

    print("-- Reporte")
    rep = llamar(
        "GET",
        f"/api/v1/reportes/ocupacion?sucursal_id={suc}&desde={iso(t0 - timedelta(days=1))}&hasta={iso(t0 + timedelta(days=30))}",
        ADMIN,
        t0,
    )
    print(
        "   ",
        {k: rep[k] for k in ("flota_total", "ocupacion_pct", "ingresos_renta", "ingresos_cargos", "rotacion_horas_promedio")},
    )
    print("\nDemo completa: reservación -> contrato -> cargos -> disputa -> limpieza -> depósito liberado -> contrato CERRADO.")


if __name__ == "__main__":
    main()
