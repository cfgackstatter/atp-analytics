/** Social-ready PNG export: fixed 16:9 canvas, thicker chart styling for capture. */

import { setChartWatermarkExportMode } from './chartWatermark';

export interface ChartExportLegendItem {
  name: string;
  color: string;
}

/** Minimal chart surface used for social PNG capture (avoids Chart.js generic fights). */
export interface ExportableChart {
  canvas: HTMLCanvasElement;
  data: { datasets: unknown[] };
  options: { scales?: Record<string, unknown> };
  resize: () => void;
  update: (mode?: string) => void;
}

export interface ChartExportOptions {
  chart: ExportableChart;
  chartWrap: HTMLElement;
  legend: ChartExportLegendItem[];
  subtitle: string;
  filename: string;
}

const PAGE = '#f3f6f4';
const SURFACE = '#ffffff';
const INK = '#14231c';
const MUTED = '#5a6d64';
const COURT = '#1a5c45';
const LINE = '#d2ddd7';

/** Standard landscape size that works well on X, Instagram, Reddit, LinkedIn, etc. */
export const SOCIAL_WIDTH = 1600;
export const SOCIAL_HEIGHT = 900;

/**
 * Type is sized for phone feeds: a 1600px-wide image often displays ~350–400px
 * wide, so canvas text must be ~3–4× normal UI size to stay readable unexpanded.
 */
const PAD = 44;
const BRAND = 'TennisRank.net';
const BRAND_PX = 44;
const SUBTITLE_PX = 28;
const LEGEND_PX = 28;
const AXIS_TITLE_PX = 28;
const AXIS_TICK_PX = 24;
const LINE_PX = 7;
const MARKER_BORDER_PX = 5;
const MARKER_SCALE = 1.7;

const FONT =
  'Manrope, "Segoe UI", system-ui, -apple-system, sans-serif';
const DISPLAY_FONT =
  'Fraunces, Georgia, "Times New Roman", serif';

type MutableDataset = {
  type?: string;
  borderWidth?: number;
  hoverBorderWidth?: number;
  pointRadius?: number | number[];
  pointHoverRadius?: number | number[];
};

type MutableFont = { size?: number; weight?: string | number };

type MutableScale = {
  title?: { font?: MutableFont };
  ticks?: { font?: MutableFont };
};

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

function layoutLegend(
  ctx: CanvasRenderingContext2D,
  legend: ChartExportLegendItem[],
  maxWidth: number
): { height: number; rows: { items: ChartExportLegendItem[]; width: number }[] } {
  const gapX = 28;
  const gapY = 14;
  const swatch = 22;
  const textGap = 12;
  const rowHeight = 34;
  const rows: { items: ChartExportLegendItem[]; width: number }[] = [];
  let row: ChartExportLegendItem[] = [];
  let rowWidth = 0;

  ctx.font = `600 ${LEGEND_PX}px ${FONT}`;

  for (const item of legend) {
    const textW = ctx.measureText(item.name).width;
    const itemW = swatch + textGap + textW;
    const next = row.length === 0 ? itemW : rowWidth + gapX + itemW;
    if (row.length > 0 && next > maxWidth) {
      rows.push({ items: row, width: rowWidth });
      row = [item];
      rowWidth = itemW;
    } else {
      row.push(item);
      rowWidth = next;
    }
  }
  if (row.length) rows.push({ items: row, width: rowWidth });

  const height =
    rows.length === 0
      ? 0
      : rows.length * rowHeight + Math.max(0, rows.length - 1) * gapY;
  return { height, rows };
}

function drawLegend(
  ctx: CanvasRenderingContext2D,
  rows: { items: ChartExportLegendItem[]; width: number }[],
  x: number,
  y: number,
  maxWidth: number
) {
  const gapX = 28;
  const gapY = 14;
  const swatch = 22;
  const textGap = 12;
  const rowHeight = 34;
  const barH = 7;

  ctx.font = `600 ${LEGEND_PX}px ${FONT}`;
  ctx.textBaseline = 'middle';

  let cy = y;
  for (const row of rows) {
    let cx = x + Math.max(0, (maxWidth - row.width) / 2);
    for (const item of row.items) {
      ctx.fillStyle = item.color;
      roundRect(ctx, cx, cy + (rowHeight - barH) / 2, swatch, barH, 3);
      ctx.fill();

      ctx.fillStyle = INK;
      ctx.fillText(item.name, cx + swatch + textGap, cy + rowHeight / 2);
      const textW = ctx.measureText(item.name).width;
      cx += swatch + textGap + textW + gapX;
    }
    cy += rowHeight + gapY;
  }
}

export function slugifyExportPart(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
}

export function buildChartExportFilename(parts: string[]): string {
  const body = parts
    .map(slugifyExportPart)
    .filter(Boolean)
    .join('-')
    .slice(0, 120);
  return `tennisrank-${body || 'chart'}.png`;
}

type DatasetSnapshot = {
  borderWidth?: number;
  hoverBorderWidth?: number;
  pointRadius?: number | number[];
  pointHoverRadius?: number | number[];
};

type FontSnapshot = { size?: number; weight?: string | number };

function readFont(font: MutableFont | undefined): FontSnapshot {
  if (!font) return {};
  return { size: font.size, weight: font.weight };
}

function writeFont(
  font: MutableFont | undefined,
  size: number,
  weight?: string | number
) {
  if (!font) return;
  font.size = size;
  if (weight != null) font.weight = weight;
}

/** Thicker lines / larger type for social capture; returns restore(). */
function applySocialChartTheme(chart: ExportableChart): () => void {
  const datasets = chart.data.datasets as MutableDataset[];
  const dsSnap: DatasetSnapshot[] = datasets.map(ds => ({
    borderWidth: ds.borderWidth,
    hoverBorderWidth: ds.hoverBorderWidth,
    pointRadius: ds.pointRadius,
    pointHoverRadius: ds.pointHoverRadius,
  }));

  const scales = (chart.options.scales || {}) as Record<
    string,
    MutableScale | undefined
  >;

  const ensureFont = (scaleKey: 'x' | 'y', which: 'title' | 'ticks') => {
    const scale = scales[scaleKey];
    if (!scale) return undefined;
    if (which === 'title') {
      if (!scale.title) scale.title = {};
      if (!scale.title.font) scale.title.font = {};
      return scale.title.font;
    }
    if (!scale.ticks) scale.ticks = {};
    if (!scale.ticks.font) scale.ticks.font = {};
    return scale.ticks.font;
  };

  const xTitle = ensureFont('x', 'title');
  const yTitle = ensureFont('y', 'title');
  const xTicks = ensureFont('x', 'ticks');
  const yTicks = ensureFont('y', 'ticks');
  const fontSnap = {
    xTitle: readFont(xTitle),
    yTitle: readFont(yTitle),
    xTicks: readFont(xTicks),
    yTicks: readFont(yTicks),
  };

  datasets.forEach(ds => {
    const isScatter = ds.type === 'scatter';
    if (isScatter) {
      const r = typeof ds.pointRadius === 'number' ? ds.pointRadius : 5;
      ds.borderWidth = MARKER_BORDER_PX;
      ds.hoverBorderWidth = MARKER_BORDER_PX;
      ds.pointRadius = Math.max(r * MARKER_SCALE, r + 4);
      ds.pointHoverRadius = Math.max(r * MARKER_SCALE + 2, r + 6);
    } else {
      ds.borderWidth = LINE_PX;
      ds.pointRadius = 0;
      ds.pointHoverRadius = 0;
    }
  });

  writeFont(xTitle, AXIS_TITLE_PX, 600);
  writeFont(yTitle, AXIS_TITLE_PX, 600);
  writeFont(xTicks, AXIS_TICK_PX, 500);
  writeFont(yTicks, AXIS_TICK_PX, 500);

  // Fewer ticks so large labels don’t collide in the feed crop.
  const xTicksOpt = scales.x?.ticks as { maxTicksLimit?: number } | undefined;
  const yTicksOpt = scales.y?.ticks as { maxTicksLimit?: number } | undefined;
  const prevXMax = xTicksOpt?.maxTicksLimit;
  const prevYMax = yTicksOpt?.maxTicksLimit;
  if (xTicksOpt) xTicksOpt.maxTicksLimit = 8;
  if (yTicksOpt) yTicksOpt.maxTicksLimit = 7;

  setChartWatermarkExportMode(true);

  return () => {
    datasets.forEach((ds, i) => {
      const s = dsSnap[i];
      if (!s) return;
      ds.borderWidth = s.borderWidth;
      ds.hoverBorderWidth = s.hoverBorderWidth;
      ds.pointRadius = s.pointRadius;
      ds.pointHoverRadius = s.pointHoverRadius;
    });
    if (fontSnap.xTitle.size != null) {
      writeFont(xTitle, fontSnap.xTitle.size, fontSnap.xTitle.weight);
    }
    if (fontSnap.yTitle.size != null) {
      writeFont(yTitle, fontSnap.yTitle.size, fontSnap.yTitle.weight);
    }
    if (fontSnap.xTicks.size != null) {
      writeFont(xTicks, fontSnap.xTicks.size, fontSnap.xTicks.weight);
    }
    if (fontSnap.yTicks.size != null) {
      writeFont(yTicks, fontSnap.yTicks.size, fontSnap.yTicks.weight);
    }
    if (xTicksOpt) xTicksOpt.maxTicksLimit = prevXMax;
    if (yTicksOpt) yTicksOpt.maxTicksLimit = prevYMax;
    setChartWatermarkExportMode(false);
  };
}

function headerHeights(legendH: number): {
  brandH: number;
  subH: number;
  legendBlock: number;
  headerH: number;
} {
  const brandH = 52;
  const subH = 40;
  const legendBlock = legendH > 0 ? legendH + 20 : 0;
  return {
    brandH,
    subH,
    legendBlock,
    headerH: brandH + subH + legendBlock,
  };
}

/**
 * Render a 1600×900 PNG with brand, subtitle, legend, and a high-res chart.
 * Temporarily restyles/resizes the live chart off-screen for capture.
 */
export function downloadChartPng({
  chart,
  chartWrap,
  legend,
  subtitle,
  filename,
}: ChartExportOptions): void {
  const measure = document.createElement('canvas').getContext('2d');
  if (!measure) throw new Error('Canvas unsupported');

  const contentW = SOCIAL_WIDTH - PAD * 2;
  const legendLayout = layoutLegend(measure, legend, contentW);
  const { brandH, subH, legendBlock, headerH } = headerHeights(
    legendLayout.height
  );
  const chartDrawW = contentW;
  const chartDrawH = SOCIAL_HEIGHT - PAD * 2 - headerH;
  if (chartDrawH < 200) {
    throw new Error('Export layout too small for chart');
  }

  const prevCss = chartWrap.style.cssText;
  const restoreTheme = applySocialChartTheme(chart);

  try {
    // Park the chart off-screen at the export pixel size so capture is sharp
    // and aspect matches the social frame (no UI flash in the viewport).
    chartWrap.style.cssText = [
      'position:fixed',
      'left:-10000px',
      'top:0',
      `width:${chartDrawW}px`,
      `height:${chartDrawH}px`,
      'opacity:1',
      'pointer-events:none',
      'z-index:-1',
    ].join(';');

    chart.resize();
    chart.update('none');

    const chartCanvas = chart.canvas;
    if (!chartCanvas.width || !chartCanvas.height) {
      throw new Error('Chart is not ready to export');
    }

    const out = document.createElement('canvas');
    out.width = SOCIAL_WIDTH;
    out.height = SOCIAL_HEIGHT;
    const ctx = out.getContext('2d');
    if (!ctx) throw new Error('Canvas unsupported');

    ctx.fillStyle = PAGE;
    ctx.fillRect(0, 0, SOCIAL_WIDTH, SOCIAL_HEIGHT);

    roundRect(ctx, PAD / 2, PAD / 2, SOCIAL_WIDTH - PAD, SOCIAL_HEIGHT - PAD, 14);
    ctx.fillStyle = SURFACE;
    ctx.fill();
    ctx.strokeStyle = LINE;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    let y = PAD;

    ctx.fillStyle = COURT;
    ctx.font = `700 ${BRAND_PX}px ${DISPLAY_FONT}`;
    ctx.textBaseline = 'top';
    ctx.fillText(BRAND, PAD, y);
    y += brandH;

    ctx.fillStyle = MUTED;
    ctx.font = `600 ${SUBTITLE_PX}px ${FONT}`;
    const maxSubW = contentW;
    let sub = subtitle;
    while (ctx.measureText(sub).width > maxSubW && sub.length > 8) {
      sub = `${sub.slice(0, -2)}…`;
    }
    ctx.fillText(sub, PAD, y);
    y += subH;

    if (legendLayout.height > 0) {
      drawLegend(ctx, legendLayout.rows, PAD, y, contentW);
      y += legendBlock;
    }

    ctx.drawImage(chartCanvas, PAD, y, chartDrawW, chartDrawH);

    const link = document.createElement('a');
    link.download = filename.endsWith('.png') ? filename : `${filename}.png`;
    link.href = out.toDataURL('image/png');
    link.click();
  } finally {
    chartWrap.style.cssText = prevCss;
    restoreTheme();
    chart.resize();
    chart.update('none');
  }
}
