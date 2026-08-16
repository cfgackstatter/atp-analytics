/** Build a shareable PNG: meta + player legend + Chart.js bitmap. */

export interface ChartExportLegendItem {
  name: string;
  color: string;
}

export interface ChartExportOptions {
  chartCanvas: HTMLCanvasElement;
  legend: ChartExportLegendItem[];
  subtitle: string;
  filename: string;
}

const PAGE = '#f3f6f4';
const SURFACE = '#ffffff';
const INK = '#14231c';
const MUTED = '#5a6d64';
const LINE = '#d2ddd7';

const PAD = 24;

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
  const gapX = 18;
  const gapY = 10;
  const swatch = 12;
  const textGap = 8;
  const rowHeight = 18;
  const rows: { items: ChartExportLegendItem[]; width: number }[] = [];
  let row: ChartExportLegendItem[] = [];
  let rowWidth = 0;

  ctx.font = '600 13px Manrope, "Segoe UI", sans-serif';

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
    rows.length === 0 ? 0 : rows.length * rowHeight + Math.max(0, rows.length - 1) * gapY;
  return { height, rows };
}

function drawLegend(
  ctx: CanvasRenderingContext2D,
  rows: { items: ChartExportLegendItem[]; width: number }[],
  x: number,
  y: number,
  maxWidth: number
) {
  const gapX = 18;
  const gapY = 10;
  const swatch = 12;
  const textGap = 8;
  const rowHeight = 18;

  ctx.font = '600 13px Manrope, "Segoe UI", sans-serif';
  ctx.textBaseline = 'middle';

  let cy = y;
  for (const row of rows) {
    let cx = x + Math.max(0, (maxWidth - row.width) / 2);
    for (const item of row.items) {
      ctx.fillStyle = item.color;
      roundRect(ctx, cx, cy + (rowHeight - swatch) / 2, swatch, 3, 1.5);
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

/** Composite chart + legend into a PNG and trigger a download. */
export function downloadChartPng({
  chartCanvas,
  legend,
  subtitle,
  filename,
}: ChartExportOptions): void {
  const chartW = chartCanvas.width;
  const chartH = chartCanvas.height;
  if (!chartW || !chartH) {
    throw new Error('Chart is not ready to export');
  }

  const exportScale = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
  const contentW = Math.max(720, Math.round(chartW / (window.devicePixelRatio || 1)));
  const chartDrawW = contentW;
  const chartDrawH = Math.round((chartH / chartW) * chartDrawW);

  const measure = document.createElement('canvas').getContext('2d');
  if (!measure) throw new Error('Canvas unsupported');

  const legendLayout = layoutLegend(measure, legend, contentW);
  const metaH = 22;
  const legendBlock = legendLayout.height > 0 ? legendLayout.height + 12 : 0;
  const totalW = contentW + PAD * 2;
  const totalH = PAD + metaH + legendBlock + chartDrawH + PAD;

  const out = document.createElement('canvas');
  out.width = Math.round(totalW * exportScale);
  out.height = Math.round(totalH * exportScale);
  const ctx = out.getContext('2d');
  if (!ctx) throw new Error('Canvas unsupported');

  ctx.scale(exportScale, exportScale);
  ctx.fillStyle = PAGE;
  ctx.fillRect(0, 0, totalW, totalH);

  roundRect(ctx, PAD / 2, PAD / 2, totalW - PAD, totalH - PAD, 10);
  ctx.fillStyle = SURFACE;
  ctx.fill();
  ctx.strokeStyle = LINE;
  ctx.lineWidth = 1;
  ctx.stroke();

  let y = PAD;
  ctx.fillStyle = MUTED;
  ctx.font = '500 12px Manrope, "Segoe UI", sans-serif';
  ctx.textBaseline = 'top';
  ctx.fillText(subtitle, PAD, y);

  y += metaH;
  if (legendLayout.height > 0) {
    drawLegend(ctx, legendLayout.rows, PAD, y, contentW);
    y += legendBlock;
  }

  // Watermark is already painted on the chart canvas.
  ctx.drawImage(chartCanvas, PAD, y, chartDrawW, chartDrawH);

  const link = document.createElement('a');
  link.download = filename.endsWith('.png') ? filename : `${filename}.png`;
  link.href = out.toDataURL('image/png');
  link.click();
}
