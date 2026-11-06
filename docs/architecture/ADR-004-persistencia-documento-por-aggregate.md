# ADR-004 · Persistencia: un documento por aggregate con columnas indexadas

**Estado:** Aceptada

## Contexto
Los aggregates contienen entidades y value objects anidados (cargos, extensiones, fotos, daños). Mapear cada uno a tablas relacionales con un ORM clásico exige mapeos imperativos y rompe la pureza del dominio.

## Decisión
SQLAlchemy 2 (Core). Una tabla por aggregate con (a) `id`, (b) **columnas escalares indexadas** para consultar y (c) una columna `datos JSON` con el estado completo. Un serializador genérico (`serializacion.py`) convierte dataclasses ⇄ JSON usando las anotaciones de tipo. Las migraciones del curso se resuelven con `create_all` al arrancar.

## Consecuencias
- (+) Una transacción = un aggregate = una fila; el dominio no se contamina con el ORM.
- (+) Funciona igual en SQLite (desarrollo) y PostgreSQL (producción): **toda la suite se ejecuta en ambos motores**.
- (+) Dinero exacto (centavos enteros) y fechas UTC con `TypeDecorator`.
- (−) No hay integridad referencial entre tablas ni migraciones versionadas. Mejora futura: Alembic y claves foráneas sobre las columnas de referencia.

## Alternativas descartadas
ORM con mapeo imperativo (más código y más fricción con dataclasses); MongoDB (agrega otra tecnología de infraestructura sin necesidad).
