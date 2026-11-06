# ADR-002 · Reportes con consultas directas (CQRS básico)

**Estado:** Aceptada (Unidad 3)

## Contexto
Los reportes de ocupación, ingresos y rotación (US19) recorren muchos registros. Hidratar aggregates para sumar sería lento y no aporta reglas de negocio.

## Decisión
`ReporteAppService` usa un puerto de lectura (`ConsultasLectura`) implementado con SQL directo sobre las **columnas indexadas** (`ConsultasSQL`). Las escrituras siguen pasando por el dominio.

## Consecuencias
- (+) Reportes baratos y sin efectos secundarios.
- (+) Por eso cada tabla duplica en columnas los campos que se consultan (`estado`, `sucursal_id`, `monto_base`, `total_cargos`…), ver ADR-004.
- (−) Dos caminos de acceso a datos; se mitiga probando el reporte contra un escenario completo.

> Nota editorial: en ACT-F03 el reporte se cita como "ADR-007" en un punto y "ADR-002" en otro; se unifica en ADR-002.
