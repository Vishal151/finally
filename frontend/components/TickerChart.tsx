"use client";

import { useRef, useEffect, useCallback } from "react";
import { createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";

interface TickerChartProps {
  ticker: string | null;
  priceHistory: number[];
}

export default function TickerChart({ ticker, priceHistory }: TickerChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const initChart = useCallback(() => {
    if (!containerRef.current) return;

    if (chartRef.current) {
      chartRef.current.remove();
    }

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#161b22" },
        textColor: "#8b949e",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#30363d" },
        horzLines: { color: "#30363d" },
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      timeScale: {
        borderColor: "#30363d",
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: "#30363d",
      },
      crosshair: {
        horzLine: { color: "#8b949e", style: 3 },
        vertLine: { color: "#8b949e", style: 3 },
      },
    });

    const series = chart.addLineSeries({
      color: "#209dd7",
      lineWidth: 2,
      crosshairMarkerRadius: 4,
      priceLineVisible: true,
      lastValueVisible: true,
    });

    chartRef.current = chart;
    seriesRef.current = series as ISeriesApi<"Line">;

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };
    const observer = new ResizeObserver(handleResize);
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const cleanup = initChart();
    return cleanup;
  }, [initChart, ticker]);

  useEffect(() => {
    if (!seriesRef.current || priceHistory.length === 0) return;

    const now = Math.floor(Date.now() / 1000);
    const data = priceHistory.map((price, i) => ({
      time: (now - (priceHistory.length - 1 - i)) as import("lightweight-charts").UTCTimestamp,
      value: price,
    }));

    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [priceHistory]);

  if (!ticker) {
    return (
      <div className="flex items-center justify-center h-full text-text-secondary text-sm">
        Select a ticker to view chart
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-1.5 text-sm font-semibold text-accent-yellow border-b border-border">
        {ticker}
      </div>
      <div ref={containerRef} className="flex-1 min-h-0" />
    </div>
  );
}
