# ADR-003 · Specification y máquina de estados declarativa

**Estado:** Aceptada

## Contexto
El PIA exige al menos tres Specifications combinables con AND/OR/NOT, una máquina de estados y Domain Events.

## Decisión
- **Specification:** clase base con `&`, `|`, `~` y `fallas()` que devuelve los nombres de las hojas que no se cumplen. Las especificaciones reciben un *contexto inmutable* (por ejemplo `ContextoCancelacion`), no el aggregate completo.
- **State Machine:** `MaquinaEstados` recibe una tabla `{(estado, evento): destino}`. Cada aggregate declara la suya como constante; sus métodos solo piden `siguiente()`.

## Consecuencias
- (+) `cliente_apto()` = `ClienteActivo & LicenciaVigente & TarjetaValida`; si falla, el error dice exactamente cuál (`"Cliente no apto: LicenciaVigente"`).
- (+) Los estados válidos se ven en una tabla y se dibujan tal cual (diagramas de la sección 3).
- (−) Los contextos añaden clases pequeñas; a cambio las reglas son puras y probables en una línea.
