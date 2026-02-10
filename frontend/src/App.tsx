// frontend/src/App.tsx
import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import RankingsChart from './components/RankingsChart';
import PlayerSearch from './components/PlayerSearch';

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
  venue: string | null;  // ← ADDED THIS
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

type RankingType = 'singles' | 'doubles';

function App() {
  const [rankingType, setRankingType] = useState<RankingType>('singles');
  const [selectedPlayers, setSelectedPlayers] = useState<Player[]>([]);
  const [rankingsData, setRankingsData] = useState<RankingData[]>([]);
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [loading, setLoading] = useState(false);

  // Create a stable color mapping based on player order in selectedPlayers
  const playerColors = useMemo(() => {
    return Object.fromEntries(
      selectedPlayers.map((player, index) => [
        player.player_id,
        PLAYER_COLORS[index % PLAYER_COLORS.length]
      ])
    );
  }, [selectedPlayers]);

  useEffect(() => {
    fetchTournaments();
  }, []);

  useEffect(() => {
    if (selectedPlayers.length > 0) {
      fetchRankings();
    } else {
      setRankingsData([]);
    }
  }, [selectedPlayers, rankingType]);

  const fetchTournaments = async () => {
    try {
      const response = await axios.get('/tournaments');
      const data = response.data;
      setTournaments(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error fetching tournaments:', error);
      setTournaments([]);
    }
  };

  const fetchRankings = async () => {
    const ids = selectedPlayers.map(p => p.player_id).join(',');
    
    setLoading(true);
    try {
      const response = await axios.get('/rankings/stored', {
        params: { 
          ranking_type: rankingType,
          player_ids: ids
        }
      });
      setRankingsData(response.data);
    } catch (error) {
      console.error('Error fetching rankings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddPlayer = (player: Player) => {
    if (!selectedPlayers.find(p => p.player_id === player.player_id)) {
      setSelectedPlayers([...selectedPlayers, player]);
    }
  };

  const handleRemovePlayer = (playerId: string) => {
    setSelectedPlayers(selectedPlayers.filter(p => p.player_id !== playerId));
  };

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
          <div className="flex gap-2">
            <div className="flex-1">
              <PlayerSearch onSelectPlayer={handleAddPlayer} />
            </div>
            <div className="flex gap-0 border border-gray-300 rounded-lg overflow-hidden">
              <button
                onClick={() => setRankingType('singles')}
                className={`px-4 py-3 font-medium transition-colors ${
                  rankingType === 'singles'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Singles
              </button>
              <button
                onClick={() => setRankingType('doubles')}
                className={`px-4 py-3 font-medium transition-colors border-l border-gray-300 ${
                  rankingType === 'doubles'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                Doubles
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
                    <button
                      onClick={() => handleRemovePlayer(player.player_id)}
                      className="hover:opacity-70 font-bold text-lg leading-none"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
            <p className="mt-3 text-gray-600">Loading rankings...</p>
          </div>
        )}

        {!loading && rankingsData.length > 0 && (
          <div className="bg-white rounded-lg shadow-lg p-5">
            <RankingsChart
              data={rankingsData}
              players={selectedPlayers}
              playerColors={playerColors}
              tournaments={tournaments}
              rankingType={rankingType}
            />
          </div>
        )}

        {!loading && selectedPlayers.length > 0 && rankingsData.length === 0 && (
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
