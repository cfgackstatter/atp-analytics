import type { Player } from '../types';
import { parsePlayerDate } from './playerAge';
import { format } from 'date-fns';

/**
 * Multi-line bio details for chip hover tooltips.
 * Not shown in the UI currently (kept for a possible later restore).
 */
export function playerBioLines(player: Player): string[] {
  const lines: string[] = [];

  if (player.country || player.birthplace) {
    lines.push(
      [player.country, player.birthplace].filter(Boolean).join(' · ')
    );
  }

  const birth = parsePlayerDate(player.birthdate ?? null);
  if (birth) {
    lines.push(`Born ${format(birth, 'd MMM yyyy')}`);
  }

  const body: string[] = [];
  if (player.height_cm != null) body.push(`${player.height_cm} cm`);
  if (player.weight_kg != null) body.push(`${player.weight_kg} kg`);
  if (body.length) lines.push(body.join(' · '));

  if (player.handedness) {
    lines.push(
      player.backhand
        ? `${player.handedness}, ${player.backhand}`
        : player.handedness
    );
  }

  if (player.turned_pro != null) {
    lines.push(`Turned pro ${player.turned_pro}`);
  }

  if (player.coach) {
    lines.push(`Coach: ${player.coach}`);
  }

  return lines;
}

export function formatPoints(points: number): string {
  return points.toLocaleString('en-US');
}
