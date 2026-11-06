# ADR-001 · Domain Model con Service Layer

**Estado:** Aceptada (Unidad 3, ratificada en el PIA)

## Contexto
NovaRent tiene reglas con estado y excepciones encadenadas (cancelación por horas, upgrades, extensiones por rol, cargos, disputas, depósito). Un Transaction Script concentraría cada flujo en una función con `if` anidados y duplicaría reglas entre casos de uso.

## Decisión
Domain Model rico (agregados con invariantes y eventos) más una capa de servicios de aplicación que orquesta transacciones, permisos y publicación de eventos.

## Consecuencias
- (+) Las reglas viven en un solo lugar y se prueban sin base de datos (las pruebas de dominio, ~120, no usan base de datos).
- (+) Un cambio de política (p. ej. 24 h → 48 h) es un parámetro, no una edición de código.
- (−) Más clases y más disciplina de capas que un CRUD; se compensa con la separación estricta `domain` / `application` / `infrastructure`.

## Alternativas descartadas
Transaction Script (se vuelve inmanejable con las excepciones del BRD); Active Record (acopla el dominio al ORM).
