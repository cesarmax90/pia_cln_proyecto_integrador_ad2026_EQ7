# ADR-006 · API REST y contrato de errores

**Estado:** Aceptada

## Decisión
FastAPI con recursos en español bajo `/api/v1`, documentación OpenAPI automática (`/docs`, `/openapi.json`) y un único formato de error: `{"error": "<código>", "detalle": ...}`.

| HTTP | Cuándo | Código `error` |
| :--- | :--- | :--- |
| 200 / 201 | Consulta o acción correcta / recurso creado | — |
| 400 | Dato mal formado (periodo invertido, fecha sin zona horaria, km negativo) | `validacion` |
| 401 | Faltan `X-Actor-Id` / `X-Rol` o el rol no existe | `http_401` |
| 403 | El rol no puede ejecutar el caso de uso, o un cliente toca recursos ajenos | `permiso_denegado` |
| 404 | El recurso no existe | `no_encontrado` |
| 409 | Transición de estado inválida o sin disponibilidad | `transicion_invalida` · `sin_disponibilidad` |
| 422 | Regla de negocio violada, o cuerpo que no cumple el esquema | `regla_negocio` · `validacion_entrada` |
| 500 | Error inesperado (sin detalles internos) | `error_interno` |

## Consecuencias
- El dominio lanza excepciones tipadas sin conocer HTTP; **un solo mapa** (`ESTADO_HTTP`) las traduce.
- Los DTO de la capa de aplicación son directamente los `response_model` (no hay modelos duplicados).
- Los importes viajan como cadena decimal (`"382.00"`) para no perder precisión.
