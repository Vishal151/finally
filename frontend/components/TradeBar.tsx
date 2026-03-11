"use client";

import { useState, useCallback } from "react";
import { executeTrade } from "@/lib/api";

interface TradeBarProps {
  onTradeExecuted: () => void;
}

export default function TradeBar({ onTradeExecuted }: TradeBarProps) {
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleTrade = useCallback(
    async (side: "buy" | "sell") => {
      const t = ticker.trim().toUpperCase();
      const q = parseFloat(quantity);
      if (!t || isNaN(q) || q <= 0) {
        setError("Enter valid ticker and quantity");
        return;
      }

      setLoading(true);
      setError(null);
      try {
        await executeTrade({ ticker: t, quantity: q, side });
        setTicker("");
        setQuantity("");
        onTradeExecuted();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Trade failed");
      } finally {
        setLoading(false);
      }
    },
    [ticker, quantity, onTradeExecuted]
  );

  return (
    <div className="flex items-center gap-2 p-2 border-t border-border bg-bg-card">
      <input
        type="text"
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder="Ticker"
        className="w-20 bg-bg-primary border border-border rounded px-2 py-1 text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:border-accent-blue"
      />
      <input
        type="number"
        value={quantity}
        onChange={(e) => setQuantity(e.target.value)}
        placeholder="Qty"
        min="0"
        step="1"
        className="w-20 bg-bg-primary border border-border rounded px-2 py-1 text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:border-accent-blue"
      />
      <button
        onClick={() => handleTrade("buy")}
        disabled={loading}
        className="bg-profit text-white text-xs font-semibold px-3 py-1 rounded hover:opacity-80 disabled:opacity-50"
      >
        Buy
      </button>
      <button
        onClick={() => handleTrade("sell")}
        disabled={loading}
        className="bg-loss text-white text-xs font-semibold px-3 py-1 rounded hover:opacity-80 disabled:opacity-50"
      >
        Sell
      </button>
      {error && <span className="text-loss text-[10px] ml-2">{error}</span>}
    </div>
  );
}
