// Inline SVG sparkline for a KPI series.
//
// Drawn by hand rather than pulling in a charting library: these are single
// series with no axes, legend or interaction, and inline SVG keeps the bundle
// free of a dependency that would only be used here.

interface SparklineProps {
  values: number[];
  /** Stroke colour; defaults to the HELIX cyan. */
  color?: string;
  width?: number;
  height?: number;
  /** Draw a filled area under the line. */
  filled?: boolean;
  /** Value above which the line switches to the warning colour. */
  threshold?: number;
  warningColor?: string;
  label?: string;
}

export function Sparkline({
  values,
  color = '#00d4ff',
  width = 120,
  height = 32,
  filled = true,
  threshold,
  warningColor = '#ff4444',
  label,
}: SparklineProps) {
  if (values.length === 0) {
    return (
      <svg width={width} height={height} role="img" aria-label={label ?? 'no data'}>
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="currentColor"
          strokeOpacity={0.15}
          strokeDasharray="3 3"
        />
      </svg>
    );
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  // A flat series would divide by zero; give it a nominal range so it renders
  // as a centred straight line rather than collapsing to the top edge.
  const range = max - min || Math.abs(max) || 1;
  const padding = 2;
  const usableHeight = height - padding * 2;

  const points = values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
    const y = padding + usableHeight - ((value - min) / range) * usableHeight;
    return [x, y] as const;
  });

  const path = points
    .map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ');

  const latest = values[values.length - 1];
  const breaching = threshold !== undefined && latest > threshold;
  const stroke = breaching ? warningColor : color;
  const [lastX, lastY] = points[points.length - 1];
  const gradientId = `spark-${Math.round(lastX)}-${Math.round(lastY)}-${values.length}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={label ? `${label}: ${latest.toFixed(2)}` : undefined}
      className="overflow-visible"
    >
      {filled && (
        <>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <path
            d={`${path} L${width},${height} L0,${height} Z`}
            fill={`url(#${gradientId})`}
            stroke="none"
          />
        </>
      )}
      {threshold !== undefined && threshold >= min && threshold <= max && (
        <line
          x1={0}
          y1={padding + usableHeight - ((threshold - min) / range) * usableHeight}
          x2={width}
          y2={padding + usableHeight - ((threshold - min) / range) * usableHeight}
          stroke={warningColor}
          strokeOpacity={0.5}
          strokeDasharray="2 3"
          strokeWidth={1}
        />
      )}
      <path d={path} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r={2.5} fill={stroke} />
    </svg>
  );
}
