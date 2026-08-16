export interface Player {
  player_id: string;
  player_name: string;
  birthdate?: string | null;
  country?: string | null;
  birthplace?: string | null;
  height_cm?: number | null;
  weight_kg?: number | null;
  handedness?: string | null;
  backhand?: string | null;
  turned_pro?: number | null;
  coach?: string | null;
}

export type RankingType = 'singles' | 'doubles';
export type XAxisMode = 'date' | 'age';
export type MetricMode = 'rank' | 'points';
export type DateRange = 'YTD' | '1Y' | '3Y' | '5Y' | 'All';
export type TournamentTitleType = 'gs' | 'atp' | 'ch' | 'fu';

export const DATE_RANGES: readonly DateRange[] = [
  'YTD',
  '1Y',
  '3Y',
  '5Y',
  'All',
] as const;

export const TITLE_TYPES: readonly TournamentTitleType[] = [
  'gs',
  'atp',
  'ch',
  'fu',
] as const;

export const TITLE_TYPE_LABELS: Record<TournamentTitleType, string> = {
  gs: 'Grand Slam',
  atp: 'ATP',
  ch: 'Challenger',
  fu: 'ITF',
};

export const TITLE_TYPE_SHORT: Record<TournamentTitleType, string> = {
  gs: 'GS',
  atp: 'ATP',
  ch: 'Ch',
  fu: 'ITF',
};
