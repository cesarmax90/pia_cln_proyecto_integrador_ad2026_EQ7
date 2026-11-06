# ADR-009 · Configuración 12-Factor, Docker y CI

**Estado:** Aceptada

## Decisión
- Configuración por variables de entorno (`pydantic-settings`); `.env.example` documenta cada una; los parámetros de negocio también son variables.
- `Dockerfile` multi-etapa (`base`, `pruebas`, `produccion`) con usuario sin privilegios y `HEALTHCHECK` sobre `/salud`.
- `docker-compose.yml`: **db** (PostgreSQL 16 con healthcheck), **app** y **tests** (perfil `tests`, base separada `novarent_test`).
- GitHub Actions: `ruff` → pruebas en Python 3.11 y 3.12 **contra PostgreSQL** con `--cov-fail-under=80` → `docker compose` (pruebas y arranque con `/salud`).
- Despliegue: `render.yaml` (Blueprint con base gestionada). La URL de `DATABASE_URL` de Render (`postgres://`) se normaliza automáticamente.

## Consecuencias
- (+) El mismo comando de pruebas corre en la laptop (SQLite) y en CI/Docker (PostgreSQL).
- (−) `CARGAR_DATOS_DEMO=true` en producción es solo para la demostración del curso; debe apagarse en un despliegue real.
