import { useEffect, useRef } from 'react'
import {
  createChart,
  ColorType,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  LineData,
  SeriesMarker,
  UTCTimestamp,
} from 'lightweight-charts'
import { Candle } from '@/types'

export interface ChartMarker {
  time: number
  position: 'aboveBar' | 'belowBar' | 'inBar'
  color: string
  shape: 'circle' | 'square' | 'arrowUp' | 'arrowDown'
  text?: string
}

export interface ChartPriceBand {
  label: string
  value: number
  color: string
}

interface CandleChartProps {
  candles: Candle[]
  symbol: string
  height?: number
  overlays?: {
    ma20?: boolean
    ma50?: boolean
    ema20?: boolean
  }
  markers?: ChartMarker[]
  priceBands?: ChartPriceBand[]
}

export function CandleChart({
  candles,
  symbol,
  height = 400,
  overlays,
  markers = [],
  priceBands = [],
}: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const ma20Ref = useRef<ISeriesApi<'Line'> | null>(null)
  const ma50Ref = useRef<ISeriesApi<'Line'> | null>(null)
  const ema20Ref = useRef<ISeriesApi<'Line'> | null>(null)
  const bandSeriesRef = useRef<ISeriesApi<'Line'>[]>([])

  useEffect(() => {
    if (!containerRef.current) return

    chartRef.current = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#111827' },
        textColor: '#9CA3AF',
      },
      grid: {
        vertLines: { color: '#1F2937' },
        horzLines: { color: '#1F2937' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#374151' },
      timeScale: { borderColor: '#374151', timeVisible: true },
      width: containerRef.current.clientWidth,
      height,
    })

    seriesRef.current = chartRef.current.addCandlestickSeries({
      upColor: '#10B981',
      downColor: '#EF4444',
      borderUpColor: '#10B981',
      borderDownColor: '#EF4444',
      wickUpColor: '#10B981',
      wickDownColor: '#EF4444',
    })

    ma20Ref.current = chartRef.current.addLineSeries({
      color: '#F59E0B',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    ma50Ref.current = chartRef.current.addLineSeries({
      color: '#60A5FA',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    ema20Ref.current = chartRef.current.addLineSeries({
      color: '#F472B6',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    })

    const handleResize = () => {
      if (chartRef.current && containerRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      bandSeriesRef.current = []
      chartRef.current?.remove()
    }
  }, [height])

  useEffect(() => {
    if (!seriesRef.current || !candles.length) return
    const data: CandlestickData[] = candles.map((c) => ({
      time: Math.floor(c.timestamp / 1000) as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    seriesRef.current.setData(data)
    chartRef.current?.timeScale().fitContent()
  }, [candles])

  useEffect(() => {
    if (!ma20Ref.current || !ma50Ref.current || !ema20Ref.current) return

    ma20Ref.current.applyOptions({ visible: overlays?.ma20 ?? false })
    ma50Ref.current.applyOptions({ visible: overlays?.ma50 ?? false })
    ema20Ref.current.applyOptions({ visible: overlays?.ema20 ?? false })

    if (!candles.length) {
      ma20Ref.current.setData([])
      ma50Ref.current.setData([])
      ema20Ref.current.setData([])
      return
    }

    ma20Ref.current.setData(buildMovingAverageSeries(candles, 20))
    ma50Ref.current.setData(buildMovingAverageSeries(candles, 50))
    ema20Ref.current.setData(buildExponentialMovingAverageSeries(candles, 20))
  }, [candles, overlays?.ema20, overlays?.ma20, overlays?.ma50])

  useEffect(() => {
    if (!seriesRef.current) return

    const markerData: SeriesMarker<UTCTimestamp>[] = markers.map((marker) => ({
      time: Math.floor(marker.time / 1000) as UTCTimestamp,
      position: marker.position,
      color: marker.color,
      shape: marker.shape,
      text: marker.text,
    }))

    seriesRef.current.setMarkers(markerData)
  }, [markers])

  useEffect(() => {
    if (!chartRef.current || !candles.length) {
      return
    }

    bandSeriesRef.current.forEach((series) => {
      chartRef.current?.removeSeries(series)
    })
    bandSeriesRef.current = []

    if (!priceBands.length) {
      return
    }

    const startTime = Math.floor(candles[0].timestamp / 1000) as UTCTimestamp
    const endTime = Math.floor(candles[candles.length - 1].timestamp / 1000) as UTCTimestamp

    bandSeriesRef.current = priceBands.map((band) => {
      const series = chartRef.current!.addLineSeries({
        color: band.color,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: band.label,
      })
      series.setData([
        { time: startTime, value: band.value },
        { time: endTime, value: band.value },
      ])
      return series
    })
  }, [candles, priceBands])

  return (
    <div className="relative">
      <div className="absolute top-2 left-2 text-sm font-bold text-white z-10">{symbol}</div>
      <div ref={containerRef} />
    </div>
  )
}

function buildMovingAverageSeries(candles: Candle[], period: number): LineData[] {
  const result: LineData[] = []

  for (let index = period - 1; index < candles.length; index += 1) {
    const window = candles.slice(index - period + 1, index + 1)
    const average = window.reduce((sum, candle) => sum + candle.close, 0) / period
    result.push({
      time: Math.floor(candles[index].timestamp / 1000) as UTCTimestamp,
      value: average,
    })
  }

  return result
}

function buildExponentialMovingAverageSeries(candles: Candle[], period: number): LineData[] {
  if (!candles.length) {
    return []
  }

  const multiplier = 2 / (period + 1)
  let ema = candles[0].close

  return candles.map((candle, index) => {
    if (index === 0) {
      ema = candle.close
    } else {
      ema = (candle.close - ema) * multiplier + ema
    }

    return {
      time: Math.floor(candle.timestamp / 1000) as UTCTimestamp,
      value: ema,
    }
  })
}
