"use client";

import { useRef, useEffect, useCallback } from "react";
import { createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import type { PortfolioSnapshot } from "@/lib/types";

interface PnlChartProps {
  snapshots: PortfolioSnapshot[];
}

export default function PnlChart({ snapshots }: PnlChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

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
    });

    const series = chart.addAreaSeries({
      lineColor: "#ecad0a",
      topColor: "rgba(236, 173, 10, 0.3)",
      bottomColor: "rgba(236, 173, 10, 0.0)",
      lineWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = series as ISeriesApi<"Area">;

    const observer = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
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
  }, [initChart]);

  useEffect(() => {
    if (!seriesRef.current || snapshots.length === 0) return;

    const data = snapshots.map((s) => ({
      time: (Math.floor(new Date(s.recorded_at).getTime() / 1000)) as import("lightweight-charts").UTCTimestamp,
      value: s.total_value,
    }));

    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [snapshots]);

  if (snapshots.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-secondary text-xs">
        No portfolio history yet
      </div>
    );
  }

  return <div ref={containerRef} className="w-full h-full" />;
}
