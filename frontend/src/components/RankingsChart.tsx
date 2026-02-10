// frontend/src/components/RankingsChart.tsx

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
import type { InteractionMode } from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import { format } from 'date-fns';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
  ScatterController
);

interface RankingData {
  rank: number;
  player_id: string;
  date: string;
  points: number;
}

interface Player {
  player_id: string;
  player_name: string;
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
  rankingType: 'singles' | 'doubles';
}

interface TournamentWin {
  date: string;
  name: string;
  playerId: string;
  tournamentType: string;
  venue: string | null;
}

// Tournament type to marker size mapping
const TOURNAMENT_SIZES: Record<string, { radius: number; hoverRadius: number }> = {
  'fu': { radius: 4, hoverRadius: 6 },      // ITF - smallest
  'ch': { radius: 5, hoverRadius: 7 },      // Challengers
  'atp': { radius: 7, hoverRadius: 9 },     // ATP
  'gs': { radius: 9, hoverRadius: 11 },     // Grand Slam - largest
};

// Tournament type display names
const TOURNAMENT_TYPE_LABELS: Record<string, string> = {
  'atp': 'ATP',
  'ch': 'Challenger',
  'fu': 'ITF',
  'gs': 'Grand Slam',
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

function RankingsChart({ data, players, playerColors, tournaments, rankingType }: Props) {
  const safeTournaments: Tournament[] = Array.isArray(tournaments) ? tournaments : [];
  const playerMap = Object.fromEntries(players.map(p => [p.player_id, p.player_name]));

  const playerGroups = data.reduce((acc, curr) => {
    if (!acc[curr.player_id]) acc[curr.player_id] = [];
    acc[curr.player_id].push(curr);
    return acc;
  }, {} as Record<string, RankingData[]>);

  const getPlayerWins = (playerId: string): TournamentWin[] => {
    const id = String(playerId);
    return safeTournaments
      .filter(t => t.end_date)
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
      .filter(r => r.rank != null && r.date)
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

  const lineDatasets: any[] = [];
  const markerDatasets: any[] = [];

  Object.entries(playerGroups).forEach(([playerId, rankings]) => {
    const sortedRankings = rankings
      .filter(r => r.rank != null && r.date)
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

    if (sortedRankings.length === 0) return;

    const basePoints = sortedRankings.map(r => ({ x: r.date, y: r.rank }));
    const color = playerColors[playerId];

    const playerTournamentMap = tournamentsByPlayerDate[playerId];

    const markersByType: Record<string, Array<{ x: string; y: number; tournaments: TournamentWin[] }>> = {};

    sortedRankings.forEach(ranking => {
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
          x: ranking.date,
          y: ranking.rank,
          tournaments: tournamentsAtDate
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
        data: markers.map(m => ({ x: m.x, y: m.y })),
        borderColor: color,
        backgroundColor: color,
        pointRadius: sizes.radius,
        pointHoverRadius: sizes.hoverRadius,
        pointStyle: 'rectRot',
        showLine: false,
        playerId,
        tournamentType,
      });
    });
  });

  const chartData = {
    datasets: [...lineDatasets, ...markerDatasets],
  };

  const options = {
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
        external: function(context: any) {
          let tooltipEl = document.getElementById('chartjs-tooltip');

          if (!tooltipEl) {
            tooltipEl = document.createElement('div');
            tooltipEl.id = 'chartjs-tooltip';
            tooltipEl.style.background = 'rgba(255, 255, 255, 0.95)';
            tooltipEl.style.borderRadius = '3px';
            tooltipEl.style.border = '1px solid rgba(0, 0, 0, 0.1)';
            tooltipEl.style.color = 'black';
            tooltipEl.style.opacity = '1';
            tooltipEl.style.pointerEvents = 'none';
            tooltipEl.style.position = 'absolute';
            tooltipEl.style.transition = 'all .1s ease';
            tooltipEl.style.padding = '8px';
            tooltipEl.style.fontSize = '12px';
            tooltipEl.style.fontFamily = 'Arial, sans-serif';
            tooltipEl.style.zIndex = '1000';
            tooltipEl.style.lineHeight = '1.4';
            tooltipEl.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
            document.body.appendChild(tooltipEl);
          }

          const tooltipModel = context.tooltip;

          if (tooltipModel.opacity === 0) {
            tooltipEl.style.opacity = '0';
            return;
          }

          const items = tooltipModel.dataPoints || [];
          const lineItems = items.filter((item: any) => item.dataset.type !== 'scatter');
          const sortedItems = [...lineItems].sort((a: any, b: any) => a.parsed.y - b.parsed.y);

          if (sortedItems.length === 0) {
            tooltipEl.style.opacity = '0';
            return;
          }

          const hoveredDate = sortedItems[0]?.parsed?.x ? new Date(sortedItems[0].parsed.x) : null;

          // Build HTML with uniform formatting
          let innerHtml = '<div>';

          if (hoveredDate) {
            innerHtml += `<div style="font-weight: bold; margin-bottom: 6px;">${format(hoveredDate, 'MMM dd, yyyy')}</div>`;
          }

          sortedItems.forEach((item: any) => {
            const dataset = item.dataset;
            const playerId = dataset.playerId;
            const playerName = playerMap[playerId] || dataset.label;
            const rank = Math.round(item.parsed.y);
            const color = dataset.borderColor;
            const dateStr = dataset.data[item.dataIndex]?.x;

            innerHtml += `<div style="color: ${color}; margin-bottom: 3px;">${playerName}: Rank ${rank}</div>`;

            const playerTournamentMap = tournamentsByPlayerDate[playerId];
            const tournaments = playerTournamentMap?.get(dateStr) || [];
            tournaments.forEach(tournament => {
              const typeLabel = TOURNAMENT_TYPE_LABELS[tournament.tournamentType] || tournament.tournamentType.toUpperCase();
              const venue = tournament.venue || '';

              let tournamentLine = `🏆 ${tournament.name}`;
              if (typeLabel || venue) {
                tournamentLine += ' •';
                if (typeLabel) {
                  tournamentLine += ` ${typeLabel}`;
                }
                if (venue) {
                  tournamentLine += ` • ${venue}`;
                }
              }

              innerHtml += `<div style="color: ${color}; margin-left: 6px; margin-bottom: 3px;">${tournamentLine}</div>`;
            });
          });

          innerHtml += '</div>';
          tooltipEl.innerHTML = innerHtml;

          // Smart positioning to avoid blocking chart and stay in bounds
          const position = context.chart.canvas.getBoundingClientRect();
          const tooltipWidth = tooltipEl.offsetWidth;
          const tooltipHeight = tooltipEl.offsetHeight;

          // Get chart dimensions
          const chartLeft = position.left;
          const chartRight = position.right;
          const chartTop = position.top;
          const chartBottom = position.bottom;
          const chartWidth = chartRight - chartLeft;
          const chartHeight = chartBottom - chartTop;

          // Cursor position relative to chart
          const caretX = tooltipModel.caretX;
          const caretY = tooltipModel.caretY;

          // Calculate position preferences
          // Prefer right side if cursor is in left half, left side if in right half
          const preferRight = caretX < chartWidth / 2;

          // Prefer top if cursor is in bottom half, bottom if in top half
          const preferTop = caretY > chartHeight / 2;

          let tooltipX, tooltipY;

          // Horizontal positioning
          if (preferRight) {
            // Place to the right
            tooltipX = chartLeft + window.pageXOffset + caretX + 15;
            // Check if it goes off screen
            if (tooltipX + tooltipWidth > window.innerWidth - 10) {
              // Place to the left instead
              tooltipX = chartLeft + window.pageXOffset + caretX - tooltipWidth - 15;
            }
          } else {
            // Place to the left
            tooltipX = chartLeft + window.pageXOffset + caretX - tooltipWidth - 15;
            // Check if it goes off screen
            if (tooltipX < 10) {
              // Place to the right instead
              tooltipX = chartLeft + window.pageXOffset + caretX + 15;
            }
          }

          // Vertical positioning
          if (preferTop) {
            // Place above
            tooltipY = chartTop + window.pageYOffset + caretY - tooltipHeight - 15;
            // Check if it goes off screen
            if (tooltipY < window.pageYOffset + 10) {
              // Place below instead
              tooltipY = chartTop + window.pageYOffset + caretY + 15;
            }
          } else {
            // Place below
            tooltipY = chartTop + window.pageYOffset + caretY + 15;
            // Check if it goes off screen
            if (tooltipY + tooltipHeight > window.pageYOffset + window.innerHeight - 10) {
              // Place above instead
              tooltipY = chartTop + window.pageYOffset + caretY - tooltipHeight - 15;
            }
          }

          // Clamp to ensure it stays within viewport
          tooltipX = Math.max(10, Math.min(tooltipX, window.innerWidth - tooltipWidth - 10));
          tooltipY = Math.max(window.pageYOffset + 10, Math.min(tooltipY, window.pageYOffset + window.innerHeight - tooltipHeight - 10));

          tooltipEl.style.opacity = '1';
          tooltipEl.style.left = tooltipX + 'px';
          tooltipEl.style.top = tooltipY + 'px';
          tooltipEl.style.transform = 'none'; // Remove the centering transform
        },
      },
    },
    scales: {
      x: {
        type: 'time' as const,
        time: {
          unit: 'month' as const,
        },
        title: {
          display: true,
          text: 'Date',
          font: {
            size: 13,
          },
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.05)',
        },
      },
      y: {
        reverse: true,
        grace: '5%',
        ticks: {
          stepSize: 1,
          maxTicksLimit: 10,
          callback: function (value: any) {
            return Number.isInteger(value) && value >= 1 ? value : '';
          },
        },
        afterDataLimits: (axis: any) => {
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
            size: 13,
          },
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.05)',
        },
      },
    },
  };

  return (
    <div style={{ height: '450px' }}>
      <Line data={chartData} options={options} />
    </div>
  );
}

export default RankingsChart;