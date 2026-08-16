// frontend/src/App.tsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import RankingsChart from './components/RankingsChart';
import PlayerSearch from './components/PlayerSearch';
import PlayerChip from './components/PlayerChip';
import type {
  DateRange,
  MetricMode,
  Player,
  RankingType,
  TournamentTitleType,
  XAxisMode,
} from './types';
import { hasBirthdate } from './utils/playerAge';
import { buildShareSearch, parseShareUrl, replaceShareUrl } from './utils/shareUrl';

interface RankingData {
  rank: number;
  player_id: string;
  date: string;
  points: number;
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

/** Distinct series colors (kept clear of the court-green UI accent). */
const PLAYER_COLORS = [
  '#1d4e89',
  '#c1292e',
  '#d97706',
  '#0e7490',
  '#7c2d12',
  '#9f1239',
];

function BrandMark({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 600 220"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M60 180 Q100 140 180 160 Q260 180 340 90 Q380 50 420 60 Q470 75 430 130 Q420 145 410 150 Q400 155 395 140 Q390 120 410 110 Q440 95 470 110 Q500 125 520 165 Q530 185 510 200 Q490 215 465 200 Q440 185 450 150 Q460 120 500 120"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M540 70 Q550 60 560 70 Q570 80 560 90 Q550 100 540 90 Q530 80 540 70"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function segmentBtn(active: boolean, disabled = false) {
  return [
    'px-3 py-1.5 text-sm font-medium transition-colors whitespace-nowrap',
    disabled ? 'cursor-not-allowed opacity-40' : '',
    active
      ? 'bg-court text-white'
      : 'bg-surface text-ink hover:bg-court-soft',
  ]
    .filter(Boolean)
    .join(' ');
}

const initialShare = parseShareUrl(
  typeof window !== 'undefined' ? window.location.search : ''
);

function App() {
  const [rankingType, setRankingType] = useState<RankingType>(
    initialShare.rankingType
  );
  const [xAxisMode, setXAxisMode] = useState<XAxisMode>(initialShare.xAxisMode);
  const [metric, setMetric] = useState<MetricMode>(initialShare.metric);
  const [dateRange, setDateRange] = useState<DateRange>(initialShare.dateRange);
  const [rangePinned, setRangePinned] = useState(initialShare.rangeFromUrl);
  const [titleTypes, setTitleTypes] = useState<TournamentTitleType[]>(
    initialShare.titleTypes
  );
  const [selectedPlayers, setSelectedPlayers] = useState<Player[]>([]);
  const [rankingsData, setRankingsData] = useState<RankingData[]>([]);
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [loading, setLoading] = useState(false);
  const [hydrating, setHydrating] = useState(initialShare.playerIds.length > 0);
  const urlReady = useRef(initialShare.playerIds.length === 0);
  const selectionKeyRef = useRef<string | null>(null);

  const playerColors = useMemo(
    () =>
      Object.fromEntries(
        selectedPlayers.map((player, index) => [
          player.player_id,
          PLAYER_COLORS[index % PLAYER_COLORS.length],
        ])
      ),
    [selectedPlayers]
  );

  const playersWithBirthdate = useMemo(
    () => selectedPlayers.filter(p => hasBirthdate(p.birthdate)),
    [selectedPlayers]
  );
  const canUseAgeAxis = playersWithBirthdate.length > 0;
  const effectiveXAxisMode: XAxisMode =
    xAxisMode === 'age' && canUseAgeAxis ? 'age' : 'date';

  // Hydrate players from shareable URL
  useEffect(() => {
    if (initialShare.playerIds.length === 0) return;

    let cancelled = false;
    (async () => {
      try {
        const response = await axios.get('/players', {
          params: { ids: initialShare.playerIds.join(',') },
        });
        if (cancelled) return;
        const rows = Array.isArray(response.data) ? response.data : [];
        setSelectedPlayers(rows);
      } catch (error) {
        console.error('Error hydrating players from URL:', error);
      } finally {
        if (!cancelled) {
          setHydrating(false);
          urlReady.current = true;
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // After the first hydrated selection, unpin the range when players/type change
  // so empty windows can auto-widen again (URL-shared range stays pinned).
  useEffect(() => {
    if (hydrating) return;
    const key = `${rankingType}|${selectedPlayers
      .map(p => p.player_id)
      .sort()
      .join(',')}`;
    if (selectionKeyRef.current === null) {
      selectionKeyRef.current = key;
      return;
    }
    if (selectionKeyRef.current !== key) {
      selectionKeyRef.current = key;
      setRangePinned(false);
    }
  }, [selectedPlayers, rankingType, hydrating]);

  // Sync shareable URL
  useEffect(() => {
    if (!urlReady.current || hydrating) return;
    const search = buildShareSearch({
      playerIds: selectedPlayers.map(p => p.player_id),
      rankingType,
      xAxisMode: effectiveXAxisMode,
      metric,
      dateRange,
      titleTypes,
    });
    replaceShareUrl(search);
  }, [
    selectedPlayers,
    rankingType,
    effectiveXAxisMode,
    metric,
    dateRange,
    titleTypes,
    hydrating,
  ]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const response = await axios.get('/tournaments');
        if (cancelled) return;
        const data = response.data;
        setTournaments(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Error fetching tournaments:', error);
        if (!cancelled) setTournaments([]);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedPlayers.length === 0) {
      setRankingsData([]);
      setLoading(false);
      return;
    }

    const ids = selectedPlayers.map(p => p.player_id).join(',');
    let cancelled = false;

    (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setLoading(true);
      try {
        const response = await axios.get('/rankings/stored', {
          params: {
            ranking_type: rankingType,
            player_ids: ids,
          },
        });
        if (!cancelled) setRankingsData(response.data);
      } catch (error) {
        console.error('Error fetching rankings:', error);
        if (!cancelled) setRankingsData([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedPlayers, rankingType]);

  const chartRankings = selectedPlayers.length > 0 ? rankingsData : [];
  const hasPlayers = selectedPlayers.length > 0;
  const showChart = chartRankings.length > 0;
  const noDataForPlayers = !loading && !hydrating && hasPlayers && !showChart;

  const handleAddPlayer = (player: Player) => {
    if (!selectedPlayers.find(p => p.player_id === player.player_id)) {
      setSelectedPlayers([...selectedPlayers, player]);
    }
  };

  const handleRemovePlayer = (playerId: string) => {
    setSelectedPlayers(selectedPlayers.filter(p => p.player_id !== playerId));
  };

  const handleClearPlayers = () => {
    setSelectedPlayers([]);
    setRankingsData([]);
  };

  const handleDateRangeChange = useCallback((range: DateRange) => {
    setDateRange(range);
  }, []);

  const handleRangePinnedChange = useCallback((pinned: boolean) => {
    setRangePinned(pinned);
  }, []);

  const handleTitleTypesChange = useCallback((types: TournamentTitleType[]) => {
    setTitleTypes(types);
  }, []);

  return (
    <div className="flex h-dvh flex-col overflow-hidden text-ink">
      <header className="flex shrink-0 items-center gap-3 border-b border-line/80 bg-surface/90 px-4 py-2.5 backdrop-blur-sm sm:px-5">
        <BrandMark className="h-9 w-auto text-court sm:h-10" />
        <div className="min-w-0">
          <h1 className="font-display text-xl font-semibold leading-tight tracking-tight text-court-ink sm:text-2xl">
            TennisRank.net
          </h1>
          <p className="truncate text-xs text-muted sm:text-sm">
            ATP rankings over time
          </p>
        </div>
      </header>

      <section className="shrink-0 border-b border-line/80 bg-surface/80 px-4 py-3 sm:px-5">
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
          <PlayerSearch onSelectPlayer={handleAddPlayer} autoFocus />

          <div className="flex flex-wrap gap-2">
            <div
              className="inline-flex overflow-hidden rounded-md border border-line"
              role="group"
              aria-label="Ranking type"
            >
              <button
                type="button"
                onClick={() => setRankingType('singles')}
                className={segmentBtn(rankingType === 'singles')}
              >
                Singles
              </button>
              <button
                type="button"
                onClick={() => setRankingType('doubles')}
                className={`${segmentBtn(rankingType === 'doubles')} border-l border-line`}
              >
                Doubles
              </button>
            </div>

            <div
              className="inline-flex overflow-hidden rounded-md border border-line"
              role="group"
              aria-label="Chart metric"
            >
              <button
                type="button"
                onClick={() => setMetric('rank')}
                className={segmentBtn(metric === 'rank')}
              >
                Rank
              </button>
              <button
                type="button"
                onClick={() => setMetric('points')}
                className={`${segmentBtn(metric === 'points')} border-l border-line`}
              >
                Points
              </button>
            </div>

            <div
              className="inline-flex overflow-hidden rounded-md border border-line"
              role="group"
              aria-label="Chart x-axis"
            >
              <button
                type="button"
                onClick={() => setXAxisMode('date')}
                className={segmentBtn(effectiveXAxisMode === 'date')}
              >
                Date
              </button>
              <button
                type="button"
                onClick={() => canUseAgeAxis && setXAxisMode('age')}
                disabled={!canUseAgeAxis}
                title={
                  canUseAgeAxis
                    ? 'Plot rankings by player age'
                    : 'Add a player with a known birthdate to use Age'
                }
                className={`${segmentBtn(effectiveXAxisMode === 'age', !canUseAgeAxis)} border-l border-line`}
              >
                Age
              </button>
            </div>
          </div>
        </div>

        {hasPlayers && (
          <div className="mt-2.5 flex items-center gap-2">
            <div className="flex min-w-0 flex-1 gap-2 overflow-x-auto pb-0.5 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {selectedPlayers.map(player => (
                <PlayerChip
                  key={player.player_id}
                  player={player}
                  color={playerColors[player.player_id]}
                  showNoDob={effectiveXAxisMode === 'age'}
                  onRemove={() => handleRemovePlayer(player.player_id)}
                />
              ))}
            </div>
            <button
              type="button"
              onClick={handleClearPlayers}
              className="shrink-0 rounded-md border border-line bg-surface px-2.5 py-1 text-sm font-medium text-muted transition-colors hover:bg-court-soft hover:text-ink"
            >
              Clear all
            </button>
          </div>
        )}

        {effectiveXAxisMode === 'age' &&
          playersWithBirthdate.length < selectedPlayers.length && (
            <p className="mt-2 text-xs text-muted">
              Age view shows {playersWithBirthdate.length} of{' '}
              {selectedPlayers.length} players (birthdate required).
            </p>
          )}
      </section>

      <main className="relative flex min-h-0 flex-1 flex-col px-3 py-3 sm:px-5 sm:py-4">
        <div className="relative flex min-h-0 flex-1 flex-col rounded-md border border-line bg-surface">
          {(loading || hydrating) && (
            <div
              className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-surface/75 backdrop-blur-[1px]"
              role="status"
              aria-live="polite"
            >
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-court/25 border-t-court" />
              <p className="text-sm text-muted">
                {hydrating ? 'Loading shared chart…' : 'Loading rankings…'}
              </p>
            </div>
          )}

          {!hasPlayers && !loading && !hydrating && (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
              <p className="font-display text-lg text-court-ink">
                Compare ATP careers
              </p>
              <p className="max-w-sm text-sm text-muted">
                Search for a player to start the chart. Links stay in sync with
                your selection.
              </p>
            </div>
          )}

          {noDataForPlayers && (
            <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
              <p className="rounded-md bg-warn-bg px-4 py-3 text-sm text-warn-ink">
                No ranking data found for the selected players.
              </p>
            </div>
          )}

          {showChart && (
            <div className="flex min-h-0 flex-1 flex-col p-3 sm:p-4">
              <RankingsChart
                data={chartRankings}
                players={selectedPlayers}
                playerColors={playerColors}
                tournaments={tournaments}
                rankingType={rankingType}
                xAxisMode={effectiveXAxisMode}
                metric={metric}
                dateRange={dateRange}
                onDateRangeChange={handleDateRangeChange}
                rangePinned={rangePinned}
                onRangePinnedChange={handleRangePinnedChange}
                titleTypes={titleTypes}
                onTitleTypesChange={handleTitleTypesChange}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
export { PLAYER_COLORS };
