"use client";

import { useState, useEffect, useCallback } from "react";
import { usePrices } from "@/lib/use-prices";
import { getPortfolio, getWatchlist, getPortfolioHistory } from "@/lib/api";
import type { Portfolio, PortfolioSnapshot } from "@/lib/types";
import Header from "@/components/Header";
import Watchlist from "@/components/Watchlist";
import TickerChart from "@/components/TickerChart";
import Heatmap from "@/components/Heatmap";
import PnlChart from "@/components/PnlChart";
import PositionsTable from "@/components/PositionsTable";
import TradeBar from "@/components/TradeBar";
import ChatPanel from "@/components/ChatPanel";

export default function Home() {
  const { prices, priceHistory, status } = usePrices();
  const [portfolio, setPortfolio] = useState<Portfolio>({
    cash_balance: 10000,
    total_value: 10000,
    positions: [],
  });
  const [watchlistTickers, setWatchlistTickers] = useState<string[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([]);

  const refreshPortfolio = useCallback(async () => {
    try {
      const p = await getPortfolio();
      setPortfolio(p);
    } catch {
      // API not ready yet
    }
  }, []);

  const refreshWatchlist = useCallback(async () => {
    try {
      const items = await getWatchlist();
      setWatchlistTickers(items.map((w) => w.ticker));
    } catch {
      // API not ready yet
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const h = await getPortfolioHistory();
      setSnapshots(h);
    } catch {
      // API not ready yet
    }
  }, []);

  const refreshAll = useCallback(() => {
    refreshPortfolio();
    refreshWatchlist();
    refreshHistory();
  }, [refreshPortfolio, refreshWatchlist, refreshHistory]);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshPortfolio, 5000);
    const historyInterval = setInterval(refreshHistory, 30000);
    return () => {
      clearInterval(interval);
      clearInterval(historyInterval);
    };
  }, [refreshAll, refreshPortfolio, refreshHistory]);

  // Update position current prices from SSE
  const positionsWithLivePrices = portfolio.positions.map((pos) => {
    const livePrice = prices[pos.ticker]?.price;
    if (livePrice && livePrice !== pos.current_price) {
      const currentPrice = livePrice;
      const unrealizedPnl = (currentPrice - pos.avg_cost) * pos.quantity;
      const pnlPercent = ((currentPrice - pos.avg_cost) / pos.avg_cost) * 100;
      const marketValue = currentPrice * pos.quantity;
      return { ...pos, current_price: currentPrice, unrealized_pnl: unrealizedPnl, pnl_percent: pnlPercent, market_value: marketValue };
    }
    return pos;
  });

  const liveTotalValue =
    portfolio.cash_balance +
    positionsWithLivePrices.reduce((sum, p) => sum + p.market_value, 0);

  return (
    <div className="h-screen flex flex-col">
      <Header
        totalValue={liveTotalValue}
        cashBalance={portfolio.cash_balance}
        status={status}
      />

      <div className="flex-1 flex min-h-0">
        {/* Left column: Watchlist */}
        <div className="w-72 flex-shrink-0 border-r border-border flex flex-col">
          <div className="px-3 py-1.5 text-xs font-semibold text-text-secondary border-b border-border uppercase tracking-wider">
            Watchlist
          </div>
          <div className="flex-1 min-h-0">
            <Watchlist
              prices={prices}
              priceHistory={priceHistory}
              watchlistTickers={watchlistTickers}
              selectedTicker={selectedTicker}
              onSelectTicker={setSelectedTicker}
              onWatchlistChange={refreshWatchlist}
            />
          </div>
        </div>

        {/* Center column: Charts + Portfolio */}
        <div className="flex-1 flex flex-col min-h-0">
          {/* Top: Ticker chart */}
          <div className="h-[40%] border-b border-border">
            <TickerChart
              ticker={selectedTicker}
              priceHistory={selectedTicker ? priceHistory[selectedTicker] || [] : []}
            />
          </div>

          {/* Middle: Heatmap + PnL chart side by side */}
          <div className="h-[30%] flex border-b border-border">
            <div className="flex-1 border-r border-border flex flex-col">
              <div className="px-3 py-1 text-xs font-semibold text-text-secondary border-b border-border uppercase tracking-wider">
                Heatmap
              </div>
              <div className="flex-1 min-h-0">
                <Heatmap positions={positionsWithLivePrices} />
              </div>
            </div>
            <div className="flex-1 flex flex-col">
              <div className="px-3 py-1 text-xs font-semibold text-text-secondary border-b border-border uppercase tracking-wider">
                P&L
              </div>
              <div className="flex-1 min-h-0">
                <PnlChart snapshots={snapshots} />
              </div>
            </div>
          </div>

          {/* Bottom: Positions table */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="px-3 py-1 text-xs font-semibold text-text-secondary border-b border-border uppercase tracking-wider">
              Positions
            </div>
            <div className="flex-1 min-h-0">
              <PositionsTable positions={positionsWithLivePrices} />
            </div>
          </div>

          {/* Trade bar */}
          <TradeBar onTradeExecuted={refreshAll} />
        </div>

        {/* Right column: Chat */}
        <div className="w-80 flex-shrink-0">
          <ChatPanel onActionExecuted={refreshAll} />
        </div>
      </div>
    </div>
  );
}
