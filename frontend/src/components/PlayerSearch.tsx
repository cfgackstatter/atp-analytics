// frontend/src/components/PlayerSearch.tsx
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import axios from 'axios';
import useDebounce from '../hooks/useDebounce';
import type { Player } from '../types';
import { hasBirthdate } from '../utils/playerAge';

interface Props {
  onSelectPlayer: (player: Player) => void;
  autoFocus?: boolean;
}

function PlayerSearch({ onSelectPlayer, autoFocus = false }: Props) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [suggestions, setSuggestions] = useState<Player[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [loading, setLoading] = useState(false);
  const debouncedSearch = useDebounce(searchTerm, 300);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (debouncedSearch.length < 2) {
        setSuggestions([]);
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const response = await axios.get('/players/search', {
          params: { q: debouncedSearch },
        });
        if (cancelled) return;
        const rows = Array.isArray(response.data) ? response.data : [];
        setSuggestions(rows);
        setActiveIndex(rows.length > 0 ? 0 : -1);
        setOpen(true);
      } catch (error) {
        console.error('Error fetching suggestions:', error);
        if (!cancelled) {
          setSuggestions([]);
          setActiveIndex(-1);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [debouncedSearch]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setActiveIndex(-1);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, []);

  const selectPlayer = (player: Player) => {
    onSelectPlayer({
      player_id: player.player_id,
      player_name: player.player_name,
      birthdate: player.birthdate ?? null,
    });
    setSearchTerm('');
    setSuggestions([]);
    setOpen(false);
    setActiveIndex(-1);
    inputRef.current?.focus();
  };

  const showList = open && (suggestions.length > 0 || loading || debouncedSearch.length >= 2);

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      setOpen(false);
      setActiveIndex(-1);
      return;
    }

    if (!showList || suggestions.length === 0) {
      if (event.key === 'ArrowDown' && suggestions.length > 0) {
        setOpen(true);
        setActiveIndex(0);
      }
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(i => (i + 1) % suggestions.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(i => (i <= 0 ? suggestions.length - 1 : i - 1));
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      event.preventDefault();
      selectPlayer(suggestions[activeIndex]);
    }
  };

  return (
    <div className="relative min-w-0 flex-1" ref={rootRef}>
      <label className="sr-only" htmlFor={`${listId}-input`}>
        Search players
      </label>
      <input
        ref={inputRef}
        id={`${listId}-input`}
        type="text"
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          activeIndex >= 0 ? `${listId}-option-${activeIndex}` : undefined
        }
        autoComplete="off"
        autoFocus={autoFocus}
        value={searchTerm}
        onChange={e => {
          setSearchTerm(e.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          if (suggestions.length > 0 || searchTerm.length >= 2) setOpen(true);
        }}
        onKeyDown={onKeyDown}
        placeholder="Search players…"
        className="w-full rounded-md border border-line bg-surface px-3 py-2 text-[0.95rem] text-ink outline-none transition-colors placeholder:text-muted/70 focus:border-court focus:ring-2 focus:ring-court/25"
      />

      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="suggest-enter absolute z-30 mt-1.5 max-h-56 w-full overflow-y-auto rounded-md border border-line bg-surface"
        >
          {loading && suggestions.length === 0 && (
            <li className="px-3 py-2.5 text-sm text-muted">Searching…</li>
          )}
          {!loading && suggestions.length === 0 && debouncedSearch.length >= 2 && (
            <li className="px-3 py-2.5 text-sm text-muted">No players found</li>
          )}
          {suggestions.map((player, index) => {
            const active = index === activeIndex;
            return (
              <li key={player.player_id} role="presentation">
                <button
                  id={`${listId}-option-${index}`}
                  type="button"
                  role="option"
                  aria-selected={active}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => selectPlayer(player)}
                  className={`flex w-full items-baseline gap-2 px-3 py-2.5 text-left text-sm transition-colors ${
                    active ? 'bg-court-soft text-court-ink' : 'text-ink hover:bg-court-soft/60'
                  }`}
                >
                  <span className="font-medium">{player.player_name}</span>
                  {!hasBirthdate(player.birthdate) && (
                    <span className="text-xs text-muted">no birthdate</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default PlayerSearch;
