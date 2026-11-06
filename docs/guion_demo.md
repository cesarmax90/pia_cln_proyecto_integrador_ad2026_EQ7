# Guion de demostración y defensa (≈ 10 minutos)

## Preparación (antes de la defensa)
```bash
PERMITIR_RELOJ_SIMULADO=true docker compose up --build     # o uvicorn local
python scripts/demo_flujo.py http://localhost:8000          # prueba de humo: debe terminar con "Demo completa"
```
Abre `http://localhost:8000/docs`, pulsa **Authorize** y deja a mano las identidades: `AGE-01 / AGENTE`, `PAT-01 / PATIO`, `ADM-01 / ADMINISTRACION`, `REN-C001 / CLIENTE`.

## Recorrido sugerido
| # | Qué mostrar | Qué decir | Dónde |
| :--- | :--- | :--- | :--- |
| 1 | `GET /salud` y `/docs` | Aplicación en PostgreSQL, OpenAPI generada, códigos HTTP documentados | Swagger |
| 2 | `GET /disponibilidad` y `POST /reservaciones` | La reservación garantiza categoría, no unidad (US01, US02) | Swagger |
| 3 | `POST /reservaciones/{folio}/entrega` con una licencia equivocada | Specification `cliente_apto` explica la falla: 422 con el motivo | Swagger |
| 4 | Checklist de entrega **sin fotos** → 422; con fotos → 201; firmar dos veces → 422 | Evidencia obligatoria con sello de tiempo; firmado = inmutable (N2, N8) | Swagger |
| 5 | `POST /contratos` | Depósito retenido; el evento `ContratoAbierto` convierte la reservación, renta el vehículo y abre la liquidación | Swagger |
| 6 | Extensión de 72 h como agente → PENDIENTE; aprobar como agente → 403; como administración → 200 | Autorización por rol en dominio y aplicación (N5) | Swagger |
| 7 | Devolución tardía con `X-Ahora` | 29 min de tolerancia, cobro por hora con tope; km a $3; combustible > 1/8 (N3) | `scripts/demo_flujo.py` |
| 8 | Disputa del daño y comparación de evidencia | La resolución es definitiva (US17) | Swagger |
| 9 | Limpieza → unidad DISPONIBLE; liberación del depósito a 5 días hábiles → contrato CERRADO | Cierre y trazabilidad (N7, N10) | `scripts/demo_flujo.py` |
| 10 | `pytest` y el reporte de cobertura | 354 pruebas, 98.5 %; la suite corre también en PostgreSQL y en CI | Terminal / GitHub Actions |

## Preguntas probables y respuestas
| Pregunta | Respuesta corta |
| :--- | :--- |
| ¿Por qué un aggregate por transacción? | Evita bloqueos largos y obliga a diseñar la consistencia entre aggregates con eventos; cada handler es idempotente (ADR-005) |
| ¿Qué pasa si un handler falla después del commit? | La reacción queda pendiente; es idempotente y se puede reintentar. Con más tiempo se añadiría Outbox |
| ¿Dónde están las reglas de negocio? | En `src/domain`; la API y la base de datos no deciden nada |
| ¿Cómo cambian las políticas (24 h, 48 h…)? | Son variables de entorno (`.env.example`); el código no cambia |
| ¿Cómo evitan cobrar de más? | `Dinero` con `Decimal`, cargos calculados por política pura y probados en sus bordes (29 min, 24 h exactas, 400 km, 1/8) |
| ¿Cómo garantizan la evidencia? | No existe un checklist sin fotos; las fotos tienen sello de tiempo del servidor, URIs únicas y el checklist firmado es inmutable |
| ¿Qué no implementaron? | Autenticación real (JWT), Outbox, migraciones con Alembic y el cargo por conductor joven (el BRD no define el monto) |
| ¿Cómo usaron el paquete de datos? | El dominio sale del BRD; los CSV alimentan la demo y los 120 casos y 20 transiciones se ejecutan contra un oráculo independiente (ADR-010) |
| ¿Cómo probaron contra PostgreSQL? | `TEST_DATABASE_URL` redirige toda la suite; CI la ejecuta con un servicio PostgreSQL |
