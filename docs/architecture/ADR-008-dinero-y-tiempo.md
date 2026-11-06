# ADR-008 · Dinero con Decimal y tiempo con zona horaria

**Estado:** Aceptada

## Decisión
- `Dinero` encapsula `Decimal`, redondea a centavos (`ROUND_HALF_UP`), rechaza negativos y otras monedas. Nunca se usa `float` para importes; en base de datos se guarda en centavos enteros.
- Todos los `datetime` son **con zona horaria** (se rechazan los ingenuos) y se persisten en UTC.
- El tiempo y los identificadores son puertos (`Reloj`, `GeneradorIds`) y el calendario de días hábiles es otro (`CalendarioHabil`).

## Consecuencias
- (+) Las reglas de borde (29 min, 24 h exactas, 2 h exactas, 5 días hábiles) se prueban con un reloj fijo, sin `sleep` ni pruebas inestables.
- (+) Un reloj simulado por petición (`X-Ahora`, solo si `PERMITIR_RELOJ_SIMULADO=true`) permite demostrar una devolución tardía en vivo.
