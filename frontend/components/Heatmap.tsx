"use client";

import type { Position } from "@/lib/types";
import { formatCurrency, formatPercent } from "@/lib/format";

interface HeatmapProps {
  positions: Position[];
}

function getColor(pnlPercent: number): string {
  if (pnlPercent > 5) return "#238636";
  if (pnlPercent > 2) return "#2ea043";
  if (pnlPercent > 0) return "#3fb950";
  if (pnlPercent > -2) return "#f85149";
  if (pnlPercent > -5) return "#da3633";
  return "#b62324";
}

export default function Heatmap({ positions }: HeatmapProps) {
  if (positions.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-secondary text-xs">
        No positions
      </div>
    );
  }

  const totalValue = positions.reduce((sum, p) => sum + p.market_value, 0);

  return (
    <div className="flex flex-wrap gap-1 p-2 h-full content-start">
      {positions.map((pos) => {
        const weight = totalValue > 0 ? (pos.market_value / totalValue) * 100 : 0;
        const minWidth = Math.max(60, weight * 2.5);

        return (
          <div
            key={pos.ticker}
            className="rounded px-2 py-1.5 flex flex-col justify-center text-center text-[10px] leading-tight"
            style={{
              backgroundColor: getColor(pos.pnl_percent),
              flexBasis: `${minWidth}px`,
              flexGrow: Math.max(1, Math.round(weight / 10)),
              minHeight: "48px",
            }}
          >
            <div className="font-bold text-white text-xs">{pos.ticker}</div>
            <div className="text-white/80">{formatPercent(pos.pnl_percent)}</div>
            <div className="text-white/60">{formatCurrency(pos.market_value)}</div>
          </div>
        );
      })}
    </div>
  );
}
