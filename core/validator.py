"""
Validador de partida doble.

Valida que cada comprobante y el total global cuadren (débitos = créditos).
Retorna un reporte estructurado con el estado de cada comprobante.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResultadoComprobante:
    consecutivo: str
    total_debito: float
    total_credito: float

    @property
    def diferencia(self) -> float:
        return round(abs(self.total_debito - self.total_credito), 2)

    @property
    def cuadra(self) -> bool:
        return self.diferencia <= 1.0  # tolerancia $1 COP por redondeos


@dataclass
class ReporteValidacion:
    comprobantes: list[ResultadoComprobante] = field(default_factory=list)

    @property
    def gran_total_debitos(self) -> float:
        return round(sum(c.total_debito for c in self.comprobantes if c.cuadra), 2)

    @property
    def gran_total_creditos(self) -> float:
        return round(sum(c.total_credito for c in self.comprobantes if c.cuadra), 2)

    @property
    def diferencia_global(self) -> float:
        return round(abs(self.gran_total_debitos - self.gran_total_creditos), 2)

    @property
    def global_cuadra(self) -> bool:
        return self.diferencia_global <= 1.0

    @property
    def todos_cuadran(self) -> bool:
        return all(c.cuadra for c in self.comprobantes) and self.global_cuadra

    @property
    def comprobantes_invalidos(self) -> list[ResultadoComprobante]:
        return [c for c in self.comprobantes if not c.cuadra]

    def resumen_texto(self) -> str:
        """Genera el reporte en texto para mostrar al usuario."""
        lineas = [
            "VALIDACIÓN DE PARTIDA DOBLE",
            f"{'Consecutivo':<14} {'Débitos':>14} {'Créditos':>14} {'Diferencia':>14} Estado",
            "-" * 65,
        ]
        for c in self.comprobantes:
            estado = "✓" if c.cuadra else "✗"
            lineas.append(
                f"{c.consecutivo:<14} "
                f"${c.total_debito:>13,.0f} "
                f"${c.total_credito:>13,.0f} "
                f"${c.diferencia:>13,.0f}  {estado}"
            )
        lineas.append("-" * 65)
        estado_global = "✓" if self.global_cuadra else "✗"
        lineas.append(
            f"{'TOTAL':<14} "
            f"${self.gran_total_debitos:>13,.0f} "
            f"${self.gran_total_creditos:>13,.0f} "
            f"${self.diferencia_global:>13,.0f}  {estado_global}"
        )

        if not self.todos_cuadran:
            lineas.append("")
            for c in self.comprobantes_invalidos:
                lineas.append(f"  ⚠ {c.consecutivo} no cuadra — diferencia ${c.diferencia:,.0f}.")
            if not self.global_cuadra:
                lineas.append("  ⛔ Importación bloqueada hasta resolver diferencias.")
        else:
            lineas.append("")
            lineas.append("  ✅ Todos los comprobantes cuadran. Listo para generar importación.")

        return "\n".join(lineas)


# ── Función principal ─────────────────────────────────────────────────────────

def validar_movimientos(movimientos: list[dict]) -> ReporteValidacion:
    """
    Valida una lista de movimientos contables.

    Cada movimiento debe tener:
        {
            "consecutivo": str,
            "debito": float,
            "credito": float,
        }

    Retorna un ReporteValidacion con el estado por comprobante y global.
    """
    # Agrupar por consecutivo
    grupos: dict[str, tuple[float, float]] = {}
    for mov in movimientos:
        consec = str(mov.get("Consecutivo comprobante", mov.get("consecutivo", "SIN_CONSEC")))
        deb = float(mov.get("Débito", mov.get("debito", 0)) or 0)
        cre = float(mov.get("Crédito", mov.get("credito", 0)) or 0)
        td, tc = grupos.get(consec, (0.0, 0.0))
        grupos[consec] = (round(td + deb, 2), round(tc + cre, 2))

    reporte = ReporteValidacion()
    for consec, (td, tc) in grupos.items():
        reporte.comprobantes.append(
            ResultadoComprobante(consecutivo=consec, total_debito=td, total_credito=tc)
        )
    return reporte
