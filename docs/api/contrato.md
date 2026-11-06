# Contrato de la API

La especificación completa y navegable está en `/docs` (Swagger UI) y `/openapi.json`; una copia versionada vive en [`openapi.json`](openapi.json) (se regenera con `python scripts/exportar_openapi.py`).

## Autenticación (simulada) y autorización
| Encabezado | Valor |
| :--- | :--- |
| `X-Actor-Id` | Identificador del actor, por ejemplo `AGE-01` o `REN-C001` |
| `X-Rol` | `CLIENTE`, `AGENTE`, `PATIO`, `LIMPIEZA`, `ADMINISTRACION` o `SISTEMA` |
| `X-Ahora` *(solo demo)* | Fecha ISO 8601 con zona horaria; fija la hora de la petición si `PERMITIR_RELOJ_SIMULADO=true` |

## Códigos de estado
| HTTP | Significado | `error` |
| :--- | :--- | :--- |
| 200 | Consulta o acción correcta | — |
| 201 | Recurso creado | — |
| 400 | Dato mal formado | `validacion` |
| 401 | Falta o es inválida la identidad | `http_401` |
| 403 | Rol no autorizado o recurso ajeno | `permiso_denegado` |
| 404 | No existe | `no_encontrado` |
| 409 | Transición inválida / sin disponibilidad | `transicion_invalida` · `sin_disponibilidad` |
| 422 | Regla de negocio o esquema de entrada | `regla_negocio` · `validacion_entrada` |
| 500 | Error inesperado | `error_interno` |

Cuerpo de error: `{"error": "regla_negocio", "detalle": "Cliente no apto: LicenciaVigente"}`.

## Recursos
Todos bajo `/api/v1` (salvo `/salud`). Los importes son cadenas decimales (`"382.00"`).

| Método y ruta | Historia | Roles |
| :--- | :--- | :--- |
| `GET /salud` | — | público |
| `GET /categorias` · `/sucursales` · `/clientes/{id}` | — | todos (cliente solo el suyo) |
| `GET /disponibilidad` | US01 | todos |
| `POST /reservaciones` | US02 | CLIENTE (propias), AGENTE, ADMINISTRACION |
| `GET /reservaciones/{folio}` | — | dueño, AGENTE, ADMINISTRACION… |
| `POST /reservaciones/{folio}/cancelar` | US03 | CLIENTE (propias), AGENTE, ADMINISTRACION, SISTEMA |
| `POST /reservaciones/liberar-no-shows` | US04 | SISTEMA, ADMINISTRACION |
| `POST /reservaciones/{folio}/entrega` | US05, US08 | AGENTE, ADMINISTRACION |
| `POST /reservaciones/{folio}/upgrade/respuesta` | US09 | CLIENTE (propias), AGENTE |
| `POST /reservaciones/{folio}/upgrade/cortesia` | US10 | ADMINISTRACION |
| `POST /inspecciones/entrega` | US06 | PATIO, AGENTE, ADMINISTRACION |
| `POST /inspecciones/{id}/firma` | US07 | CLIENTE (propio), AGENTE |
| `POST /contratos` · `GET /contratos/{id}` | apertura | AGENTE, ADMINISTRACION |
| `POST /contratos/{id}/extensiones` | US11 | AGENTE, ADMINISTRACION |
| `POST /contratos/{id}/extensiones/{ext}/aprobacion` | US12 | ADMINISTRACION |
| `POST /contratos/{id}/conductores` | — | AGENTE, ADMINISTRACION |
| `POST /contratos/{id}/inspeccion-devolucion` | US13 | PATIO, AGENTE, ADMINISTRACION |
| `POST /contratos/{id}/devolucion` | US14–US16 | AGENTE, ADMINISTRACION |
| `GET /contratos/{id}/liquidacion` | — | dueño, AGENTE, ADMINISTRACION |
| `POST …/cargos/{id}/aprobacion-danio` | — | ADMINISTRACION |
| `POST …/cargos/{id}/disputa` | US17 | CLIENTE (propio), AGENTE, ADMINISTRACION |
| `GET …/cargos/{id}/evidencia` | US17 | AGENTE, ADMINISTRACION |
| `POST …/cargos/{id}/resolucion` | US17 | ADMINISTRACION |
| `POST /liquidaciones/liberar-depositos` | US20 | SISTEMA, ADMINISTRACION |
| `GET /sucursales/{id}/flota` · `/vehiculos/{id}` | — | AGENTE, PATIO, LIMPIEZA, ADMINISTRACION |
| `GET /limpieza/tareas` · `POST /limpieza/tareas/{id}/completar` | US18 | LIMPIEZA, PATIO, ADMINISTRACION |
| `GET /reportes/ocupacion` | US19 | ADMINISTRACION |

## Ejemplo
```bash
curl -X POST http://localhost:8000/api/v1/reservaciones \
  -H "X-Actor-Id: REN-C001" -H "X-Rol: CLIENTE" -H "Content-Type: application/json" \
  -d '{"cliente_id":"REN-C001","categoria_id":"REN-P001","sucursal_id":"SUC-APODACA",
       "inicio":"2026-12-10T09:00:00Z","fin":"2026-12-12T09:00:00Z"}'
```
