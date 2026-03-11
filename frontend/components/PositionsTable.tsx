"use client";

import type { Position } from "@/lib/types";
import { formatCurrency, formatPercent, formatPrice } from "@/lib/format";

interface PositionsTableProps {
  positions: Position[];
}

export default function PositionsTable({ positions }: PositionsTableProps) {
  if (positions.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-secondary text-xs">
        No open positions
      </div>
    );
  }

  return (
    <div className="overflow-auto h-full">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-bg-card">
          <tr className="text-text-secondary border-b border-border">
            <th className="text-left py-1 px-2 font-medium">Ticker</th>
            <th className="text-right py-1 px-2 font-medium">Qty</th>
            <th className="text-right py-1 px-2 font-medium">Avg Cost</th>
            <th className="text-right py-1 px-2 font-medium">Price</th>
            <th className="text-right py-1 px-2 font-medium">P&L</th>
            <th className="text-right py-1 px-2 font-medium">%</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => (
            <tr key={pos.ticker} className="border-b border-border/50 hover:bg-bg-secondary/50">
              <td className="py-1.5 px-2 font-semibold text-accent-yellow">{pos.ticker}</td>
              <td className="py-1.5 px-2 text-right tabular-nums">{pos.quantity}</td>
              <td className="py-1.5 px-2 text-right tabular-nums">{formatPrice(pos.avg_cost)}</td>
              <td className="py-1.5 px-2 text-right tabular-nums">
                {formatPrice(pos.current_price)}
              </td>
              <td
                className={`py-1.5 px-2 text-right tabular-nums ${
                  pos.unrealized_pnl >= 0 ? "text-profit" : "text-loss"
                }`}
              >
                {formatCurrency(pos.unrealized_pnl)}
              </td>
              <td
                className={`py-1.5 px-2 text-right tabular-nums ${
                  pos.pnl_percent >= 0 ? "text-profit" : "text-loss"
                }`}
              >
                {formatPercent(pos.pnl_percent)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
