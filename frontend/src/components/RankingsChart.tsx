// frontend/src/components/RankingsChart.tsx

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  ScatterController,
} from 'chart.js';
import type { ChartData, ChartOptions, InteractionMode, Scale } from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import { format } from 'date-fns';
import type {
  DateRange,
  MetricMode,
  Player,
  RankingType,
  TournamentTitleType,
  XAxisMode,
} from '../types';
import {
  DATE_RANGES,
  TITLE_TYPES,
  TITLE_TYPE_LABELS,
  TITLE_TYPE_SHORT,
} from '../types';
import { ageAtDate, formatAge, hasBirthdate, parsePlayerDate } from '../utils/playerAge';
import { formatPoints } from '../utils/playerBio';
import {
  buildChartExportFilename,
  downloadChartPng,
} from '../utils/exportChartPng';
import { chartWatermarkPlugin } from '../utils/chartWatermark';

type ChartPoint = { x: string | number; y: number; date: string; rank: number; points: number };

interface RankingDataset {
  type: 'line' | 'scatter';
  label: string;
  data: ChartPoint[];
  borderColor: string;
  backgroundColor: string;
  playerId: string;
  tension?: number;
  borderWidth?: number;
  hoverBorderWidth?: number;
  hoverBackgroundColor?: string;
  pointRadius?: number;
  pointHoverRadius?: number;
  pointStyle?: string;
  showLine?: boolean;
  tournamentType?: string;
}

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  ScatterController,
  chartWatermarkPlugin
);

interface RankingData {
  rank: number;
  player_id: string;
  date: string;
  points: number;
}

function rangeStartDate(range: DateRange): Date {
  const now = new Date();
  switch (range) {
    case 'YTD':
      return new Date(now.getFullYear(), 0, 1);
    case '1Y':
      return new Date(new Date().setFullYear(now.getFullYear() - 1));
    case '3Y':
      return new Date(new Date().setFullYear(now.getFullYear() - 3));
    case '5Y':
      return new Date(new Date().setFullYear(now.getFullYear() - 5));
    case 'All':
      return new Date(0);
  }
}

function rankingInRange(
  rankings: RankingData[],
  playerIds: Set<string>,
  range: DateRange,
  metric: MetricMode
): boolean {
  const start = rangeStartDate(range).getTime();
  return rankings.some(d => {
    if (!playerIds.has(d.player_id) || new Date(d.date).getTime() < start) {
      return false;
    }
    return metric === 'points' ? d.points != null : d.rank != null;
  });
}

/** Smallest calendar window that still includes at least one ranking point. */
function bestDateRange(
  rankings: RankingData[],
  playerIds: Set<string>,
  metric: MetricMode
): DateRange {
  for (const range of DATE_RANGES) {
    if (rankingInRange(rankings, playerIds, range, metric)) return range;
  }
  return 'All';
}

interface Tournament {
  year: number;
  tournament_type: string;
  tournament_name: string;
  venue: string | null;
  start_date: string | null;
  end_date: string | null;
  singles_winner_id: string | null;
  doubles_winner_ids: string | null;
}

interface Props {
  data: RankingData[];
  players: Player[];
  playerColors: Record<string, string>;
  tournaments: Tournament[] | null | undefined;
  rankingType: RankingType;
  xAxisMode: XAxisMode;
  metric: MetricMode;
  dateRange: DateRange;
  onDateRangeChange: (range: DateRange) => void;
  rangePinned: boolean;
  onRangePinnedChange: (pinned: boolean) => void;
  titleTypes: TournamentTitleType[];
  onTitleTypesChange: (types: TournamentTitleType[]) => void;
}

interface TournamentWin {
  date: string;
  name: string;
  playerId: string;
  tournamentType: string;
  venue: string | null;
}

/** Hollow circles; size steps are more pronounced than the original 3/4/5/6. */
const TOURNAMENT_SIZES: Record<string, { radius: number; hoverRadius: number }> = {
  fu: { radius: 3, hoverRadius: 5 },
  ch: { radius: 5, hoverRadius: 7.5 },
  atp: { radius: 7.5, hoverRadius: 10 },
  gs: { radius: 11, hoverRadius: 14 },
};

function findClosestRankingDate(
  rankings: { date: string; rank: number }[],
  targetDate: string
): string | null {
  const t = new Date(targetDate).getTime();
  if (!Number.isFinite(t) || rankings.length === 0) return null;

  const sorted = [...rankings].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  const first = new Date(sorted[0].date).getTime();
  const last = new Date(sorted[sorted.length - 1].date).getTime();

  if (t < first || t > last) return null;

  let closestDate = null;
  let minDiff = Infinity;

  for (const ranking of sorted) {
    const rankDate = new Date(ranking.date).getTime();
    const diff = rankDate - t;

    if (diff >= 0 && diff < minDiff) {
      minDiff = diff;
      closestDate = ranking.date;
    }
  }

  return closestDate;
}

function toggleTitleType(
  current: TournamentTitleType[],
  type: TournamentTitleType
): TournamentTitleType[] {
  const has = current.includes(type);
  if (has) {
    return current.filter(t => t !== type);
  }
  return TITLE_TYPES.filter(t => t === type || current.includes(t));
}

function RankingsChart({
  data,
  players,
  playerColors,
  tournaments,
  rankingType,
  xAxisMode,
  metric,
  dateRange,
  onDateRangeChange,
  rangePinned,
  onRangePinnedChange,
  titleTypes,
  onTitleTypesChange,
}: Props) {
  const byAge = xAxisMode === 'age';
  const byPoints = metric === 'points';
  const chartRef = useRef<ChartJS<'line', ChartPoint[]>>(null);
  const chartWrapRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);

  const enabledTitles = useMemo(() => new Set(titleTypes), [titleTypes]);

  const safeTournaments: Tournament[] = Array.isArray(tournaments) ? tournaments : [];
  const birthdateByPlayer = Object.fromEntries(
    players.map(p => [p.player_id, p.birthdate ?? null])
  );
  const playerMap = Object.fromEntries(players.map(p => [p.player_id, p.player_name]));

  const eligiblePlayerIds = useMemo(
    () =>
      new Set(
        byAge
          ? players.filter(p => hasBirthdate(p.birthdate)).map(p => p.player_id)
          : players.map(p => p.player_id)
      ),
    [byAge, players]
  );

  // When the selected window has no points (e.g. retired player + default 1Y),
  // widen to the smallest range that still plots something.
  useEffect(() => {
    if (byAge || rangePinned) return;
    if (rankingInRange(data, eligiblePlayerIds, dateRange, metric)) return;
    const next = bestDateRange(data, eligiblePlayerIds, metric);
    if (next !== dateRange) onDateRangeChange(next);
  }, [
    byAge,
    rangePinned,
    data,
    eligiblePlayerIds,
    dateRange,
    metric,
    onDateRangeChange,
  ]);

  // Age mode overlays full careers; calendar windows (1Y, etc.) just shift
  // each player to a different age band with little/no overlap.
  const rangeStart = byAge ? rangeStartDate('All') : rangeStartDate(dateRange);

  const filteredData = data.filter(d => {
    if (!eligiblePlayerIds.has(d.player_id) || new Date(d.date) < rangeStart) {
      return false;
    }
    return byPoints ? d.points != null : d.rank != null;
  });

  const playerGroups = filteredData.reduce((acc, curr) => {
    if (!acc[curr.player_id]) acc[curr.player_id] = [];
    acc[curr.player_id].push(curr);
    return acc;
  }, {} as Record<string, RankingData[]>);

  const toX = (playerId: string, rankingDate: string): string | number | null => {
    if (!byAge) return rankingDate;
    return ageAtDate(birthdateByPlayer[playerId], rankingDate);
  };

  const getPlayerWins = (playerId: string): TournamentWin[] => {
    const id = String(playerId);
    return safeTournaments
      .filter(t => t.end_date)
      .filter(t => enabledTitles.has(t.tournament_type as TournamentTitleType))
      .filter(t => {
        if (rankingType === 'singles') {
          return t.singles_winner_id && String(t.singles_winner_id) === id;
        }
        return (
          t.doubles_winner_ids &&
          t.doubles_winner_ids.split(',').map(s => s.trim()).includes(id)
        );
      })
      .map(t => ({
        date: t.end_date as string,
        name: t.tournament_name,
        playerId: playerId,
        tournamentType: t.tournament_type,
        venue: t.venue,
      }));
  };

  const tournamentsByPlayerDate: Record<string, Map<string, TournamentWin[]>> = {};

  Object.keys(playerGroups).forEach(playerId => {
    const rankings = playerGroups[playerId]
      .filter(r => (byPoints ? r.points != null : r.rank != null) && r.date)
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

    const wins = getPlayerWins(playerId);
    const dateMap = new Map<string, TournamentWin[]>();

    wins.forEach(win => {
      const closestRankingDate = findClosestRankingDate(
        rankings.map(r => ({ date: r.date, rank: r.rank })),
        win.date
      );

      if (closestRankingDate) {
        if (!dateMap.has(closestRankingDate)) {
          dateMap.set(closestRankingDate, []);
        }
        dateMap.get(closestRankingDate)!.push(win);
      }
    });

    tournamentsByPlayerDate[playerId] = dateMap;
  });

  const lineDatasets: RankingDataset[] = [];
  const markerDatasets: RankingDataset[] = [];

  Object.entries(playerGroups).forEach(([playerId, rankings]) => {
    const sortedRankings = rankings
      .filter(r => (byPoints ? r.points != null : r.rank != null) && r.date)
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .map(r => {
        const x = toX(playerId, r.date);
        if (x == null) return null;
        return { ranking: r, x };
      })
      .filter((row): row is { ranking: RankingData; x: string | number } => row != null);

    if (sortedRankings.length === 0) return;

    if (byAge) {
      sortedRankings.sort((a, b) => Number(a.x) - Number(b.x));
    }

    const basePoints: ChartPoint[] = sortedRankings.map(({ ranking, x }) => ({
      x,
      y: byPoints ? ranking.points : ranking.rank,
      date: ranking.date,
      rank: ranking.rank,
      points: ranking.points,
    }));
    const color = playerColors[playerId];

    const playerTournamentMap = tournamentsByPlayerDate[playerId];

    const markersByType: Record<string, ChartPoint[]> = {};

    sortedRankings.forEach(({ ranking, x }) => {
      const tournamentsAtDate = playerTournamentMap.get(ranking.date);
      if (tournamentsAtDate && tournamentsAtDate.length > 0) {
        const typeOrder = ['gs', 'atp', 'ch', 'fu'];
        const sortedTournaments = [...tournamentsAtDate].sort((a, b) => {
          const indexA = typeOrder.indexOf(a.tournamentType);
          const indexB = typeOrder.indexOf(b.tournamentType);
          return indexA - indexB;
        });

        const primaryType = sortedTournaments[0].tournamentType;

        if (!markersByType[primaryType]) {
          markersByType[primaryType] = [];
        }
        markersByType[primaryType].push({
          x,
          y: byPoints ? ranking.points : ranking.rank,
          date: ranking.date,
          rank: ranking.rank,
          points: ranking.points,
        });
      }
    });

    lineDatasets.push({
      type: 'line' as const,
      label: playerMap[playerId] || playerId,
      data: basePoints,
      borderColor: color,
      backgroundColor: color,
      tension: 0,
      borderWidth: 3,
      pointRadius: 0,
      pointHoverRadius: 6,
      playerId,
    });

    Object.entries(markersByType).forEach(([tournamentType, markers]) => {
      const sizes = TOURNAMENT_SIZES[tournamentType] || TOURNAMENT_SIZES['atp'];

      markerDatasets.push({
        type: 'scatter' as const,
        label: `${playerMap[playerId]} Tournament Wins`,
        data: markers,
        borderColor: color,
        borderWidth: 3,
        hoverBorderWidth: 3,
        backgroundColor: 'white',
        hoverBackgroundColor: 'white',
        pointRadius: sizes.radius,
        pointHoverRadius: sizes.hoverRadius,
        pointStyle: 'circle',
        showLine: false,
        playerId,
        tournamentType,
      });
    });
  });

  const chartData = {
    datasets: [...markerDatasets, ...lineDatasets],
  } as ChartData<'line', ChartPoint[]>;

  const hasPlot = lineDatasets.length > 0;

  useEffect(() => {
    if (!hasPlot) return;
    const el = chartWrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      chartRef.current?.resize();
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [hasPlot]);

  const xScale = byAge
    ? {
        type: 'linear' as const,
        title: {
          display: true,
          text: 'Age',
          font: { size: 12, family: 'Manrope, sans-serif', weight: 500 },
          color: '#5a6d64',
        },
        ticks: {
          maxTicksLimit: 12,
          color: '#5a6d64',
          font: { family: 'Manrope, sans-serif', size: 11 },
          callback: (value: string | number) => {
            const n = typeof value === 'number' ? value : Number(value);
            return Number.isFinite(n) ? n.toFixed(n % 1 === 0 ? 0 : 1) : '';
          },
        },
        grid: {
          color: 'rgba(20, 35, 28, 0.06)',
        },
      }
    : {
        type: 'time' as const,
        time: {
          unit: 'month' as const,
        },
        ticks: {
          maxTicksLimit: 12,
          color: '#5a6d64',
          font: { family: 'Manrope, sans-serif', size: 11 },
        },
        title: {
          display: true,
          text: 'Date',
          font: { size: 12, family: 'Manrope, sans-serif', weight: 500 },
          color: '#5a6d64',
        },
        grid: {
          color: 'rgba(20, 35, 28, 0.06)',
        },
      };

  const yScale = byPoints
    ? {
        reverse: false,
        grace: '5%' as const,
        ticks: {
          maxTicksLimit: 10,
          color: '#5a6d64',
          font: { family: 'Manrope, sans-serif', size: 11 },
          callback: function (value: string | number) {
            const n = typeof value === 'number' ? value : Number(value);
            if (!Number.isFinite(n)) return '';
            return formatPoints(Math.round(n));
          },
        },
        afterDataLimits: (axis: Scale) => {
          if (axis.min < 0) axis.min = 0;
        },
        title: {
          display: true,
          text: 'Points',
          font: {
            size: 12,
            family: 'Manrope, sans-serif',
            weight: 500 as const,
          },
          color: '#5a6d64',
        },
        grid: {
          color: 'rgba(20, 35, 28, 0.06)',
        },
      }
    : {
        reverse: true,
        grace: '5%' as const,
        ticks: {
          stepSize: 1,
          maxTicksLimit: 10,
          color: '#5a6d64',
          font: { family: 'Manrope, sans-serif', size: 11 },
          callback: function (value: string | number) {
            const n = typeof value === 'number' ? value : Number(value);
            return Number.isInteger(n) && n >= 1 ? n : '';
          },
        },
        afterDataLimits: (axis: Scale) => {
          if (axis.min < 1) {
            axis.min = 0.5;
          }
          if (axis.max - axis.min < 10) {
            axis.max = Math.max(axis.min + 10, 10);
          }
        },
        title: {
          display: true,
          text: 'Rank',
          font: {
            size: 12,
            family: 'Manrope, sans-serif',
            weight: 500 as const,
          },
          color: '#5a6d64',
        },
        grid: {
          color: 'rgba(20, 35, 28, 0.06)',
        },
      };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'nearest' as InteractionMode,
      intersect: false,
      axis: 'x' as const,
    },
    plugins: {
      legend: {
        display: false,
      },
      title: {
        display: false,
      },
      tooltip: {
        enabled: false,
        external: function (context) {
          let tooltipEl = document.getElementById('chartjs-tooltip');

          if (!tooltipEl) {
            tooltipEl = document.createElement('div');
            tooltipEl.id = 'chartjs-tooltip';
            tooltipEl.style.background = 'var(--color-surface)';
            tooltipEl.style.borderRadius = '6px';
            tooltipEl.style.border = '1px solid var(--color-line)';
            tooltipEl.style.color = 'var(--color-ink)';
            tooltipEl.style.opacity = '1';
            tooltipEl.style.pointerEvents = 'none';
            tooltipEl.style.position = 'absolute';
            tooltipEl.style.transition = 'opacity .1s ease';
            tooltipEl.style.padding = '8px 10px';
            tooltipEl.style.fontSize = '12px';
            tooltipEl.style.fontFamily = 'var(--font-sans)';
            tooltipEl.style.zIndex = '1000';
            tooltipEl.style.lineHeight = '1.4';
            tooltipEl.style.maxWidth = '320px';
            document.body.appendChild(tooltipEl);
          }

          const tooltipModel = context.tooltip;

          if (tooltipModel.opacity === 0) {
            tooltipEl.style.opacity = '0';
            return;
          }

          const items = tooltipModel.dataPoints || [];
          const lineItems = items.filter(
            item => (item.dataset as unknown as RankingDataset).type !== 'scatter'
          );
          const sortedItems = [...lineItems].sort((a, b) => {
            const ya = a.parsed.y ?? 0;
            const yb = b.parsed.y ?? 0;
            // Rank: better (= lower) first; points: higher first
            return byPoints ? yb - ya : ya - yb;
          });

          if (sortedItems.length === 0) {
            tooltipEl.style.opacity = '0';
            return;
          }

          let innerHtml = '<div>';

          if (byAge) {
            const age = sortedItems[0]?.parsed?.x;
            if (typeof age === 'number' && Number.isFinite(age)) {
              innerHtml += `<div style="font-weight: bold; margin-bottom: 6px;">Age ${formatAge(age)}</div>`;
            }
          } else {
            const hoveredDate = sortedItems[0]?.parsed?.x
              ? new Date(sortedItems[0].parsed.x)
              : null;
            if (hoveredDate && !Number.isNaN(hoveredDate.getTime())) {
              innerHtml += `<div style="font-weight: bold; margin-bottom: 6px;">${format(hoveredDate, 'MMM dd, yyyy')}</div>`;
            }
          }

          sortedItems.forEach(item => {
            const dataset = item.dataset as unknown as RankingDataset;
            const playerId = dataset.playerId;
            const playerName = playerMap[playerId] || dataset.label;
            const color = dataset.borderColor;
            const point = dataset.data[item.dataIndex] as ChartPoint | undefined;
            const dateStr = point?.date;
            const rank = point?.rank ?? Math.round(item.parsed.y ?? 0);
            const points = point?.points;

            let line = `${playerName}`;
            if (byPoints) {
              line += `: ${formatPoints(Math.round(item.parsed.y ?? 0))} pts`;
              if (rank != null) line += ` · Rank ${rank}`;
            } else {
              line += `: Rank ${rank}`;
              if (points != null) line += ` · ${formatPoints(points)} pts`;
            }
            if (byAge && dateStr) {
              const parsed = parsePlayerDate(dateStr);
              if (parsed) {
                line += ` (${format(parsed, 'MMM yyyy')})`;
              }
            }

            innerHtml += `<div style="color: ${color}; margin-bottom: 3px;">${line}</div>`;

            const playerTournamentMap = tournamentsByPlayerDate[playerId];
            const tournamentsAtPoint = dateStr
              ? playerTournamentMap?.get(dateStr) || []
              : [];
            tournamentsAtPoint.forEach(tournament => {
              const typeLabel =
                TITLE_TYPE_LABELS[tournament.tournamentType as TournamentTitleType] ||
                tournament.tournamentType.toUpperCase();
              const venue = tournament.venue || '';

              let tournamentLine = tournament.name;
              if (typeLabel || venue) {
                tournamentLine += ' ·';
                if (typeLabel) {
                  tournamentLine += ` ${typeLabel}`;
                }
                if (venue) {
                  tournamentLine += ` · ${venue}`;
                }
              }

              innerHtml += `<div style="color: ${color}; margin-left: 6px; margin-bottom: 3px; opacity: 0.9;">${tournamentLine}</div>`;
            });
          });

          innerHtml += '</div>';
          tooltipEl.innerHTML = innerHtml;

          const position = context.chart.canvas.getBoundingClientRect();
          const tooltipWidth = tooltipEl.offsetWidth;
          const tooltipHeight = tooltipEl.offsetHeight;

          const chartLeft = position.left;
          const chartWidth = position.right - position.left;
          const chartHeight = position.bottom - position.top;

          const caretX = tooltipModel.caretX;
          const caretY = tooltipModel.caretY;

          const preferRight = caretX < chartWidth / 2;
          const preferTop = caretY > chartHeight / 2;

          let tooltipX: number;
          let tooltipY: number;

          if (preferRight) {
            tooltipX = chartLeft + window.pageXOffset + caretX + 15;
            if (tooltipX + tooltipWidth > window.innerWidth - 10) {
              tooltipX = chartLeft + window.pageXOffset + caretX - tooltipWidth - 15;
            }
          } else {
            tooltipX = chartLeft + window.pageXOffset + caretX - tooltipWidth - 15;
            if (tooltipX < 10) {
              tooltipX = chartLeft + window.pageXOffset + caretX + 15;
            }
          }

          if (preferTop) {
            tooltipY = position.top + window.pageYOffset + caretY - tooltipHeight - 15;
            if (tooltipY < window.pageYOffset + 10) {
              tooltipY = position.top + window.pageYOffset + caretY + 15;
            }
          } else {
            tooltipY = position.top + window.pageYOffset + caretY + 15;
            if (tooltipY + tooltipHeight > window.pageYOffset + window.innerHeight - 10) {
              tooltipY = position.top + window.pageYOffset + caretY - tooltipHeight - 15;
            }
          }

          tooltipX = Math.max(10, Math.min(tooltipX, window.innerWidth - tooltipWidth - 10));
          tooltipY = Math.max(
            window.pageYOffset + 10,
            Math.min(tooltipY, window.pageYOffset + window.innerHeight - tooltipHeight - 10)
          );

          tooltipEl.style.opacity = '1';
          tooltipEl.style.left = tooltipX + 'px';
          tooltipEl.style.top = tooltipY + 'px';
          tooltipEl.style.transform = 'none';
        },
      },
    },
    scales: {
      x: xScale,
      y: yScale,
    },
  };

  const handleDownloadPng = () => {
    const chart = chartRef.current;
    const canvas = chart?.canvas;
    if (!canvas || lineDatasets.length === 0) return;

    const legend = lineDatasets.map(ds => ({
      name: ds.label,
      color: String(ds.borderColor),
    }));

    const titleFilterLabel =
      titleTypes.length === TITLE_TYPES.length
        ? 'All titles'
        : titleTypes.length === 0
          ? 'No titles'
          : titleTypes.map(t => TITLE_TYPE_SHORT[t]).join('+');

    const subtitleParts = [
      rankingType === 'singles' ? 'Singles' : 'Doubles',
      byPoints ? 'Points' : 'Rank',
      byAge ? 'Age' : 'Date',
      byAge ? 'full careers' : dateRange,
      titleFilterLabel,
    ];

    const filename = buildChartExportFilename([
      rankingType,
      byPoints ? 'points' : 'rank',
      byAge ? 'age' : dateRange,
      ...legend.map(item => item.name),
    ]);

    setExporting(true);
    try {
      chart.update('none');
      downloadChartPng({
        chartCanvas: canvas,
        legend,
        subtitle: subtitleParts.join(' · '),
        filename,
      });
    } catch (err) {
      console.error('Chart PNG export failed', err);
    } finally {
      setExporting(false);
    }
  };

  const titleFilters = (
    <div
      className="inline-flex overflow-hidden rounded-md border border-line"
      role="group"
      aria-label="Tournament title types"
    >
      {TITLE_TYPES.map((type, index) => {
        const active = enabledTitles.has(type);
        return (
          <button
            key={type}
            type="button"
            title={`${TITLE_TYPE_LABELS[type]} titles`}
            onClick={() => onTitleTypesChange(toggleTitleType(titleTypes, type))}
            className={`shrink-0 px-2 py-1 text-xs font-medium transition-colors sm:px-2.5 sm:text-sm ${
              index > 0 ? 'border-l border-line' : ''
            } ${
              active
                ? 'bg-court text-white'
                : 'bg-surface text-muted hover:bg-court-soft hover:text-ink'
            }`}
          >
            {TITLE_TYPE_SHORT[type]}
          </button>
        );
      })}
    </div>
  );

  const dateRangeButtons = (
    <div
      className="inline-flex overflow-hidden rounded-md border border-line"
      role="group"
      aria-label="Date range"
    >
      {DATE_RANGES.map((range, index) => (
        <button
          key={range}
          type="button"
          onClick={() => {
            onRangePinnedChange(true);
            onDateRangeChange(range);
          }}
          className={`shrink-0 px-2.5 py-1 text-xs font-medium transition-colors sm:px-3 sm:text-sm ${
            index > 0 ? 'border-l border-line' : ''
          } ${
            dateRange === range
              ? 'bg-court text-white'
              : 'bg-surface text-muted hover:bg-court-soft hover:text-ink'
          }`}
        >
          {range}
        </button>
      ))}
    </div>
  );

  const rangeControls = (
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={handleDownloadPng}
          disabled={exporting || lineDatasets.length === 0}
          className="shrink-0 rounded-md border border-line bg-surface px-2.5 py-1 text-xs font-medium text-ink transition-colors hover:bg-court-soft disabled:cursor-not-allowed disabled:opacity-40 sm:text-sm"
        >
          {exporting ? 'Exporting…' : 'Download PNG'}
        </button>
        {titleFilters}
      </div>
      {byAge ? (
        <p className="min-w-0 text-right text-xs text-muted sm:text-sm">
          Full careers overlaid by age (date ranges apply in Date view).
        </p>
      ) : (
        <div className="min-w-0 overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {dateRangeButtons}
        </div>
      )}
    </div>
  );

  if (lineDatasets.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">{titleFilters}</div>
          {byAge ? (
            <p className="text-xs text-muted sm:text-sm">
              Full careers overlaid by age (date ranges apply in Date view).
            </p>
          ) : (
            <div className="overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {dateRangeButtons}
            </div>
          )}
        </div>
        <div className="flex flex-1 items-center justify-center text-center text-sm text-muted">
          {byAge
            ? 'No ranking points to plot by age for the selected players.'
            : 'No ranking points to plot in this range.'}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      {rangeControls}
      <div className="relative min-h-0 flex-1" ref={chartWrapRef}>
        <Line ref={chartRef} data={chartData} options={options} />
      </div>
    </div>
  );
}

export default RankingsChart;
