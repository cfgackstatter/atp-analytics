/** Light corner watermark drawn onto the Chart.js canvas (exports included). */

import type { Chart, Plugin } from 'chart.js';

const LABEL = 'tennisrank.net';

let exportMode = false;

/** Slightly larger / stronger mark while capturing a social PNG. */
export function setChartWatermarkExportMode(on: boolean): void {
  exportMode = on;
}

export const chartWatermarkPlugin: Plugin = {
  id: 'tennisrankWatermark',
  afterDraw(chart: Chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;

    const base = Math.max(10, Math.min(12, chartArea.width / 70));
    const fontSize = exportMode
      ? Math.max(22, Math.min(28, chartArea.width / 40))
      : base;
    ctx.save();
    ctx.font = `500 ${fontSize}px Manrope, "Segoe UI", sans-serif`;
    ctx.fillStyle = exportMode
      ? 'rgba(26, 92, 69, 0.32)'
      : 'rgba(26, 92, 69, 0.18)';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'bottom';
    ctx.fillText(
      LABEL,
      chartArea.right - (exportMode ? 14 : 6),
      chartArea.bottom - (exportMode ? 14 : 6)
    );
    ctx.restore();
  },
};
