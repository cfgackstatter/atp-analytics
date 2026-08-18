import type { Player } from '../types';
import { hasBirthdate } from '../utils/playerAge';

interface Props {
  player: Player;
  color: string;
  showNoDob?: boolean;
  onRemove: () => void;
}

/** Selected-player chip. Bio hover tooltips intentionally omitted for now. */
function PlayerChip({ player, color, showNoDob = false, onRemove }: Props) {
  return (
    <div
      className="chip-enter flex shrink-0 items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-medium"
      style={{
        backgroundColor: `${color}18`,
        color,
        borderColor: color,
      }}
    >
      <span>{player.player_name}</span>
      {player.country && (
        <span className="text-xs opacity-70">{player.country}</span>
      )}
      {showNoDob && !hasBirthdate(player.birthdate) && (
        <span className="text-xs opacity-70">no DOB</span>
      )}
      <button
        type="button"
        onClick={onRemove}
        className="ml-0.5 text-base leading-none opacity-70 hover:opacity-100"
        aria-label={`Remove ${player.player_name}`}
      >
        ×
      </button>
    </div>
  );
}

export default PlayerChip;
