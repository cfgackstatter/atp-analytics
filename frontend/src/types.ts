export interface Player {
  player_id: string;
  player_name: string;
  birthdate?: string | null;
}

export type RankingType = 'singles' | 'doubles';
export type XAxisMode = 'date' | 'age';
