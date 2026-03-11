"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { PriceUpdate } from "@/lib/types";
import { formatPrice, formatPercent } from "@/lib/format";
import { addToWatchlist, removeFromWatchlist } from "@/lib/api";
import Sparkline from "./Sparkline";

interface WatchlistProps {
  prices: Record<string, PriceUpdate>;
  priceHistory: Record<string, number[]>;
  watchlistTickers: string[];
  selectedTicker: string | null;
  onSelectTicker: (ticker: string) => void;
  onWatchlistChange: () => void;
}

export default function Watchlist({
  prices,
  priceHistory,
  watchlistTickers,
  selectedTicker,
  onSelectTicker,
  onWatchlistChange,
}: WatchlistProps) {
  const [newTicker, setNewTicker] = useState("");
  const [adding, setAdding] = useState(false);
  const flashRef = useRef<Record<string, string>>({});
  const [flashKeys, setFlashKeys] = useState<Record<string, number>>({});

  const prevPricesRef = useRef<Record<string, number>>({});

  useEffect(() => {
    const newFlashes: Record<string, number> = {};
    for (const ticker of watchlistTickers) {
      const current = prices[ticker];
      if (!current) continue;
      const prev = prevPricesRef.current[ticker];
      if (prev !== undefined && prev !== current.price) {
        flashRef.current[ticker] = current.price > prev ? "flash-up" : "flash-down";
        newFlashes[ticker] = Date.now();
      }
      prevPricesRef.current[ticker] = current.price;
    }
    if (Object.keys(newFlashes).length > 0) {
      setFlashKeys((prev) => ({ ...prev, ...newFlashes }));
    }
  }, [prices, watchlistTickers]);

  const handleAdd = useCallback(async () => {
    const ticker = newTicker.trim().toUpperCase();
    if (!ticker) return;
    setAdding(true);
    try {
      await addToWatchlist(ticker);
      setNewTicker("");
      onWatchlistChange();
    } catch {
      // silently fail
    } finally {
      setAdding(false);
    }
  }, [newTicker, onWatchlistChange]);

  const handleRemove = useCallback(
    async (ticker: string) => {
      try {
        await removeFromWatchlist(ticker);
        onWatchlistChange();
      } catch {
        // silently fail
      }
    },
    [onWatchlistChange]
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 p-2 border-b border-border">
        <input
          type="text"
          value={newTicker}
          onChange={(e) => setNewTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="Add ticker..."
          className="flex-1 bg-bg-primary border border-border rounded px-2 py-1 text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:border-accent-blue"
        />
        <button
          onClick={handleAdd}
          disabled={adding}
          className="bg-accent-purple text-white text-xs px-2 py-1 rounded hover:opacity-80 disabled:opacity-50"
        >
          Add
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-secondary border-b border-border">
              <th className="text-left py-1 px-2 font-medium">Ticker</th>
              <th className="text-right py-1 px-2 font-medium">Price</th>
              <th className="text-right py-1 px-2 font-medium">Chg%</th>
              <th className="py-1 px-2 font-medium">Chart</th>
              <th className="py-1 px-1"></th>
            </tr>
          </thead>
          <tbody>
            {watchlistTickers.map((ticker) => {
              const data = prices[ticker];
              const price = data?.price ?? 0;
              const prevPrice = data?.prev_price ?? price;
              const changePct = prevPrice ? ((price - prevPrice) / prevPrice) * 100 : 0;
              const flash = flashRef.current[ticker];
              const flashKey = flashKeys[ticker] || 0;
              const history = priceHistory[ticker] || [];
              const isSelected = ticker === selectedTicker;

              return (
                <tr
                  key={`${ticker}-${flashKey}`}
                  onClick={() => onSelectTicker(ticker)}
                  className={`cursor-pointer border-b border-border/50 hover:bg-bg-secondary/50 ${
                    isSelected ? "bg-bg-secondary" : ""
                  } ${flash || ""}`}
                >
                  <td className="py-1.5 px-2 font-semibold text-accent-yellow">{ticker}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums">
                    {price > 0 ? formatPrice(price) : "--"}
                  </td>
                  <td
                    className={`py-1.5 px-2 text-right tabular-nums ${
                      changePct > 0
                        ? "text-profit"
                        : changePct < 0
                        ? "text-loss"
                        : "text-text-secondary"
                    }`}
                  >
                    {price > 0 ? formatPercent(changePct) : "--"}
                  </td>
                  <td className="py-1.5 px-2">
                    {history.length > 1 && <Sparkline data={history} />}
                  </td>
                  <td className="py-1.5 px-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemove(ticker);
                      }}
                      className="text-text-secondary hover:text-loss text-[10px]"
                      title="Remove"
                    >
                      x
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
