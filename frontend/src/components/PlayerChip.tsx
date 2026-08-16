import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { Player } from '../types';
import { playerBioLines } from '../utils/playerBio';
import { hasBirthdate } from '../utils/playerAge';

interface Props {
  player: Player;
  color: string;
  showNoDob?: boolean;
  onRemove: () => void;
}

function PlayerChip({ player, color, showNoDob = false, onRemove }: Props) {
  const tipId = useId();
  const chipRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const lines = playerBioLines(player);
  const hasTip = lines.length > 0;

  const updatePos = () => {
    const el = chipRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const tipWidth = 240;
    let left = rect.left;
    if (left + tipWidth > window.innerWidth - 8) {
      left = Math.max(8, window.innerWidth - tipWidth - 8);
    }
    setPos({ top: rect.bottom + 6, left });
  };

  useEffect(() => {
    if (!open) return;
    const onScrollOrResize = () => updatePos();
    window.addEventListener('scroll', onScrollOrResize, true);
    window.addEventListener('resize', onScrollOrResize);
    return () => {
      window.removeEventListener('scroll', onScrollOrResize, true);
      window.removeEventListener('resize', onScrollOrResize);
    };
  }, [open]);

  return (
    <>
      <div
        ref={chipRef}
        tabIndex={hasTip ? 0 : undefined}
        className="chip-enter flex shrink-0 items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-court/40"
        style={{
          backgroundColor: `${color}18`,
          color,
          borderColor: color,
        }}
        onMouseEnter={() => {
          if (!hasTip) return;
          updatePos();
          setOpen(true);
        }}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => {
          if (!hasTip) return;
          updatePos();
          setOpen(true);
        }}
        onBlur={() => setOpen(false)}
        aria-describedby={open && hasTip ? tipId : undefined}
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

      {open &&
        hasTip &&
        createPortal(
          <div
            id={tipId}
            role="tooltip"
            className="pointer-events-none fixed z-[1000] max-w-[240px] rounded-md border border-line bg-surface px-2.5 py-2 text-xs leading-snug text-ink shadow-md"
            style={{ top: pos.top, left: pos.left }}
          >
            <div className="mb-1 font-medium" style={{ color }}>
              {player.player_name}
            </div>
            {lines.map(line => (
              <div key={line} className="text-muted">
                {line}
              </div>
            ))}
          </div>,
          document.body
        )}
    </>
  );
}

export default PlayerChip;
