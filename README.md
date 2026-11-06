# NovaRent · Componentes de Lógica de Negocio (PIA)

Sistema de lógica de negocio para **NovaRent**, empresa de renta de automóviles por día: reservación, entrega con checklist y evidencia, contrato, extensiones, devolución, cargos automáticos (kilometraje, combustible, retraso, daños), disputas, depósito de garantía, limpieza y reportes.

| Dato | Valor |
| :--- | :--- |
| Curso | Componentes de Lógica de Negocio · FIME-UANL |
| Caso | Caso 07 · NovaRent |
| Integrantes | Arturo Sebastian Pérez Zapata (2142942) · Cesar Maximiliano Peña Mendoza (2144135) · Diego Alberto Sierra Mendoza (2143733) |
| Repositorio | `https://github.com/<usuario>/<repositorio>` *(completar)* |
| Aplicación desplegada | `https://<tu-servicio>.onrender.com/docs` *(completar tras el despliegue)* |
| Entrega | 06/11/2026 |

## Qué contiene
| Requisito del PIA | Dónde está |
| :--- | :--- |
| BRD, ≥ 15 historias con Gherkin, BPMN, glosario | [`docs/BRD.md`](docs/BRD.md) · [`docs/historias_usuario.md`](docs/historias_usuario.md) (20) · [`docs/bpmn.md`](docs/bpmn.md) · [`docs/glosario.md`](docs/glosario.md) |
| Diseño DDD/UML, patrones, SOLID, ADR | [`docs/architecture/`](docs/architecture/README.md) (diagramas Mermaid + 10 ADR) |
| ≥ 3 Specifications con AND/OR/NOT, máquina de estados, Domain Events | `src/domain/especificaciones.py` (11) · `maquina_estados.py` (5 máquinas) · `eventos.py` (19 eventos) |
| Validación de cantidades, disponibilidad, importes y transiciones | `Dinero`, `PeriodoRenta`, `ServicioDisponibilidad`, `MaquinaEstados` |
| API REST con OpenAPI y códigos 200/201/400/404/409/422 | `src/api` · [`docs/api/contrato.md`](docs/api/contrato.md) · [`docs/api/openapi.json`](docs/api/openapi.json) · `/docs` |
| Persistencia (PostgreSQL / SQLite) con Repository y Unit of Work | `src/infrastructure` |
| Pruebas unitarias, de integración y de API con cobertura ≥ 80 % | `tests/` → **354 pruebas, 98.5 % de cobertura** (356 pruebas en PostgreSQL) |
| Docker Compose (DB + App + Tests) | `docker-compose.yml` · `Dockerfile` |
| CI/CD | `.github/workflows/ci.yml` (ruff → pruebas en PostgreSQL → docker compose) |
| Trazabilidad BRD → regla → componente → prueba | [`docs/trazabilidad.md`](docs/trazabilidad.md) |
| Paquete de datos (120 casos + 20 transiciones) | [`docs/adaptacion_paquete_datos.md`](docs/adaptacion_paquete_datos.md) · `docs/evidencias/*.csv` |

## Ejecución rápida
### Con Docker Compose (recomendado)
```bash
cp .env.example .env            # opcional; todo tiene valor por omisión
docker compose up --build       # API en http://localhost:8000/docs
docker compose --profile tests up --build --exit-code-from tests --abort-on-container-exit tests
docker compose down -v
```

### Sin Docker (SQLite)
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn --factory src.api.main:crear_app --reload       # http://localhost:8000/docs
pytest --cov=src --cov-fail-under=80
ruff check src tests scripts
```
Al arrancar con `CARGAR_DATOS_DEMO=true` (valor por omisión) se cargan 2 sucursales, 20 categorías, 160 vehículos y 40 clientes desde `datos/*.csv`.

### Pruebas contra PostgreSQL
```bash
TEST_DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/novarent_test pytest
```

## Probar la API
1. Abre `/docs` → **Authorize** → captura `X-Actor-Id` (por ejemplo `AGE-01`) y `X-Rol` (`AGENTE`).
2. Actores demo: agente `AGE-01`, patio `PAT-01`, limpieza `LIM-01`, administración `ADM-01`, sistema `SYS` y clientes `REN-C001`…`REN-C040` (rol `CLIENTE`).
3. Demostración automática de todo el negocio (necesita `PERMITIR_RELOJ_SIMULADO=true`):
```bash
PERMITIR_RELOJ_SIMULADO=true uvicorn --factory src.api.main:crear_app
python scripts/demo_flujo.py http://localhost:8000
```
Guion paso a paso para la defensa: [`docs/guion_demo.md`](docs/guion_demo.md).

## Arquitectura en una vista
```mermaid
flowchart TD
    API["API REST - FastAPI"] --> APP["Application Services"]
    APP --> DOM["Dominio: Aggregates, Specifications,<br/>Maquinas de estado, Politicas, Eventos"]
    INFRA["Infraestructura: Repositorios, UoW,<br/>PostgreSQL, pasarela, evidencia"] -. "implementa puertos" .-> APP
    INFRA --> DOM
```
Detalle, diagramas de secuencia, estados y ER en [`docs/architecture/README.md`](docs/architecture/README.md).

## Estructura
```text
.
├── docs/                 BRD, historias, BPMN, glosario, trazabilidad, architecture/ (ADR), api/, evidencias/
├── src/
│   ├── domain/           reglas puras (sin frameworks)
│   ├── application/      casos de uso, permisos por rol, DTO, handlers de eventos
│   ├── infrastructure/   SQLAlchemy, repositorios, Unit of Work, adaptadores, datos demo
│   ├── api/              FastAPI: rutas, esquemas, errores
│   └── validacion_paquete/  ejecuta los 120 casos y 20 transiciones del paquete
├── tests/                354 pruebas (dominio, infraestructura, servicios, API, paquete de datos)
├── datos/                CSV del paquete de datos del PIA
├── scripts/              demo_flujo.py, exportar_openapi.py
├── docker/               inicialización de PostgreSQL para el perfil de pruebas
├── Dockerfile · docker-compose.yml · render.yaml · .env.example
└── .github/workflows/ci.yml
```

## Calidad
| Verificación | Resultado |
| :--- | :--- |
| `ruff check src tests scripts` | Sin errores |
| `pytest` (SQLite en memoria) | 354 pasan · 98.5 % de cobertura (líneas y ramas) |
| `pytest` (PostgreSQL 16 real) | 356 pasan · 98.5 % de cobertura |
| Paquete de datos | 120 casos y 20 transiciones ejecutados; 0 diferencias contra el oráculo independiente |
| Evidencia | [`docs/evidencias/`](docs/evidencias/) |

## Decisiones y supuestos a validar
Los valores que el BRD de U2 no fija (penalización por cancelación, tarifa por octavo de combustible, tarifa por hora de retraso, monto del depósito) están marcados como supuestos en [`docs/BRD.md` (Anexo C)](docs/BRD.md) y son parámetros configurables. Limitaciones conocidas: autenticación simulada con encabezados (ADR-007), eventos en proceso sin Outbox (ADR-005), sin migraciones versionadas (ADR-004) y cargo por conductor joven sin monto definido.

## Despliegue
`render.yaml` define el servicio web (Docker) y la base PostgreSQL gestionada. En Render: **New → Blueprint** → selecciona el repositorio. Después de desplegar, copia la URL en la tabla de arriba.
