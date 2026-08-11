// frontend/src/App.tsx
import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import RankingsChart from './components/RankingsChart';
import PlayerSearch from './components/PlayerSearch';
import type { Player, RankingType, XAxisMode } from './types';
import { hasBirthdate } from './utils/playerAge';

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

const PLAYER_COLORS = [
  '#3B82F6', // blue
  '#EF4444', // red
  '#10B981', // green
  '#F59E0B', // amber
  '#8B5CF6', // purple
  '#EC4899', // pink
];

function App() {
  const [rankingType, setRankingType] = useState<RankingType>('singles');
  const [xAxisMode, setXAxisMode] = useState<XAxisMode>('date');
  const [selectedPlayers, setSelectedPlayers] = useState<Player[]>([]);
  const [rankingsData, setRankingsData] = useState<RankingData[]>([]);
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [loading, setLoading] = useState(false);

  const playerColors = useMemo(() => {
    return Object.fromEntries(
      selectedPlayers.map((player, index) => [
        player.player_id,
        PLAYER_COLORS[index % PLAYER_COLORS.length]
      ])
    );
  }, [selectedPlayers]);

  const playersWithBirthdate = useMemo(
    () => selectedPlayers.filter(p => hasBirthdate(p.birthdate)),
    [selectedPlayers]
  );
  const canUseAgeAxis = playersWithBirthdate.length > 0;
  const effectiveXAxisMode: XAxisMode =
    xAxisMode === 'age' && canUseAgeAxis ? 'age' : 'date';

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
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedPlayers, rankingType]);

  const chartRankings = selectedPlayers.length > 0 ? rankingsData : [];

  const handleAddPlayer = (player: Player) => {
    if (!selectedPlayers.find(p => p.player_id === player.player_id)) {
      setSelectedPlayers([...selectedPlayers, player]);
    }
  };

  const handleRemovePlayer = (playerId: string) => {
    setSelectedPlayers(selectedPlayers.filter(p => p.player_id !== playerId));
  };

  const toggleBtn = (active: boolean, extra = '') =>
    `px-4 py-3 font-medium transition-colors ${extra} ${
      active
        ? 'bg-blue-600 text-white'
        : 'bg-white text-gray-700 hover:bg-gray-50'
    }`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <header className="flex items-center gap-3 mb-6">
          <img src="/logo.svg" alt="TennisRank" className="h-14" />
          <div>
            <h1 className="text-3xl font-bold text-gray-800">
              TennisRank.net
            </h1>
            <p className="text-sm text-gray-600">Track ATP rankings over time</p>
          </div>
        </header>

        <div className="bg-white rounded-lg shadow-lg p-5 mb-6">
          <div className="flex flex-wrap gap-2">
            <div className="flex-1 min-w-[16rem]">
              <PlayerSearch onSelectPlayer={handleAddPlayer} />
            </div>
            <div className="flex gap-0 border border-gray-300 rounded-lg overflow-hidden">
              <button
                onClick={() => setRankingType('singles')}
                className={toggleBtn(rankingType === 'singles')}
              >
                Singles
              </button>
              <button
                onClick={() => setRankingType('doubles')}
                className={toggleBtn(rankingType === 'doubles', 'border-l border-gray-300')}
              >
                Doubles
              </button>
            </div>
            <div className="flex gap-0 border border-gray-300 rounded-lg overflow-hidden">
              <button
                onClick={() => setXAxisMode('date')}
                className={toggleBtn(effectiveXAxisMode === 'date')}
              >
                Date
              </button>
              <button
                onClick={() => canUseAgeAxis && setXAxisMode('age')}
                disabled={!canUseAgeAxis}
                title={
                  canUseAgeAxis
                    ? 'Plot rankings by player age'
                    : 'Add a player with a known birthdate to use Age'
                }
                className={toggleBtn(
                  effectiveXAxisMode === 'age',
                  `border-l border-gray-300 ${!canUseAgeAxis ? 'opacity-40 cursor-not-allowed hover:bg-white' : ''}`
                )}
              >
                Age
              </button>
            </div>
          </div>

          {selectedPlayers.length > 0 && (
            <div className="mt-3">
              <div className="flex flex-wrap gap-2">
                {selectedPlayers.map((player) => (
                  <div
                    key={player.player_id}
                    className="px-3 py-1 rounded-full text-sm flex items-center gap-2 font-medium"
                    style={{
                      backgroundColor: playerColors[player.player_id] + '20',
                      color: playerColors[player.player_id],
                      border: `2px solid ${playerColors[player.player_id]}`,
                    }}
                  >
                    <span>{player.player_name}</span>
                    {effectiveXAxisMode === 'age' && !hasBirthdate(player.birthdate) && (
                      <span className="text-xs opacity-70">(no DOB)</span>
                    )}
                    <button
                      onClick={() => handleRemovePlayer(player.player_id)}
                      className="hover:opacity-70 font-bold text-lg leading-none"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
              {effectiveXAxisMode === 'age' &&
                playersWithBirthdate.length < selectedPlayers.length && (
                  <p className="mt-2 text-sm text-gray-500">
                    Age view shows {playersWithBirthdate.length} of{' '}
                    {selectedPlayers.length} players (birthdate required).
                  </p>
                )}
            </div>
          )}
        </div>

        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
            <p className="mt-3 text-gray-600">Loading rankings...</p>
          </div>
        )}

        {!loading && chartRankings.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-5">
            <RankingsChart
              data={chartRankings}
              players={selectedPlayers}
              playerColors={playerColors}
              tournaments={tournaments}
              rankingType={rankingType}
              xAxisMode={effectiveXAxisMode}
            />
          </div>
        )}

        {!loading && selectedPlayers.length > 0 && chartRankings.length === 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
            <p className="text-yellow-800">No ranking data found for selected players.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
export { PLAYER_COLORS };
