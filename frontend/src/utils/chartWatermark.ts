/** Light corner watermark drawn onto the Chart.js canvas (exports included). */

import type { Chart, Plugin } from 'chart.js';

const LABEL = 'tennisrank.net';

export const chartWatermarkPlugin: Plugin = {
  id: 'tennisrankWatermark',
  afterDraw(chart: Chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;

    const fontSize = Math.max(10, Math.min(12, chartArea.width / 70));
    ctx.save();
    ctx.font = `500 ${fontSize}px Manrope, "Segoe UI", sans-serif`;
    ctx.fillStyle = 'rgba(26, 92, 69, 0.18)';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'bottom';
    ctx.fillText(
      LABEL,
      chartArea.right - 6,
      chartArea.bottom - 6
    );
    ctx.restore();
  },
};
