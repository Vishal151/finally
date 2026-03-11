"use client";

import type { ConnectionStatus } from "@/lib/use-prices";
import { formatCurrency } from "@/lib/format";

const STATUS_COLORS: Record<ConnectionStatus, string> = {
  connected: "bg-profit",
  reconnecting: "bg-accent-yellow",
  disconnected: "bg-loss",
};

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  connected: "Live",
  reconnecting: "Reconnecting",
  disconnected: "Disconnected",
};

interface HeaderProps {
  totalValue: number;
  cashBalance: number;
  status: ConnectionStatus;
}

export default function Header({ totalValue, cashBalance, status }: HeaderProps) {
  return (
    <header className="flex items-center justify-between px-4 py-2 border-b border-border bg-bg-card">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-bold text-accent-yellow tracking-wide">FinAlly</h1>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${STATUS_COLORS[status]}`} />
          <span className="text-xs text-text-secondary">{STATUS_LABELS[status]}</span>
        </div>
      </div>
      <div className="flex items-center gap-6 text-sm">
        <div>
          <span className="text-text-secondary mr-2">Portfolio</span>
          <span className="font-semibold text-accent-blue">{formatCurrency(totalValue)}</span>
        </div>
        <div>
          <span className="text-text-secondary mr-2">Cash</span>
          <span className="font-semibold">{formatCurrency(cashBalance)}</span>
        </div>
      </div>
    </header>
  );
}
