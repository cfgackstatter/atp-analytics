// frontend/src/components/PlayerSearch.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import useDebounce from '../hooks/useDebounce';

interface Player {
  player_id: string;
  player_name: string;
}

interface Props {
  onSelectPlayer: (player: Player) => void;
}

function PlayerSearch({ onSelectPlayer }: Props) {
  const [searchTerm, setSearchTerm] = useState('');
  const [suggestions, setSuggestions] = useState<Player[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debouncedSearch = useDebounce(searchTerm, 300);

  useEffect(() => {
    console.log('Debounced search:', debouncedSearch);
    
    const fetchSuggestions = async () => {
      if (debouncedSearch.length < 2) {
        setSuggestions([]);
        return;
      }

      try {
        console.log('Fetching suggestions for:', debouncedSearch);
        const response = await axios.get('/players/search', {
          params: { q: debouncedSearch }
        });
        
        console.log('API response:', response.data);
        
        if (Array.isArray(response.data)) {
          setSuggestions(response.data);
          console.log('Set suggestions:', response.data);
        } else {
          console.error('Unexpected response format:', response.data);
          setSuggestions([]);
        }
        setShowSuggestions(true);
      } catch (error) {
        console.error('Error fetching suggestions:', error);
        setSuggestions([]);
      }
    };

    fetchSuggestions();
  }, [debouncedSearch]);

  const handleSelect = (player: Player) => {
    onSelectPlayer(player);
    setSearchTerm('');
    setSuggestions([]);
    setShowSuggestions(false);
  };

  console.log('Rendering with suggestions:', suggestions, 'showSuggestions:', showSuggestions);

  return (
    <div className="relative">
      <input
        type="text"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        onFocus={() => setShowSuggestions(true)}
        placeholder="Type player name (e.g., Alcaraz, Djokovic)..."
        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-lg"
      />

      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-10 w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {suggestions.map(player => (
            <button
              key={player.player_id}
              onClick={() => handleSelect(player)}
              className="w-full px-4 py-3 text-left hover:bg-blue-50 transition-colors border-b border-gray-100 last:border-b-0"
            >
              <span className="text-gray-800 font-medium">{player.player_name}</span>
              <span className="text-gray-400 text-sm ml-2">({player.player_id})</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default PlayerSearch;
