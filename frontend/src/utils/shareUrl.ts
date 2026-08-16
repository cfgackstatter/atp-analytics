import type {
  DateRange,
  MetricMode,
  RankingType,
  TournamentTitleType,
  XAxisMode,
} from '../types';
import { DATE_RANGES, TITLE_TYPES } from '../types';

export interface ShareState {
  playerIds: string[];
  rankingType: RankingType;
  xAxisMode: XAxisMode;
  metric: MetricMode;
  dateRange: DateRange;
  titleTypes: TournamentTitleType[];
  /** True when `range` was present in the URL (don't auto-widen away from it). */
  rangeFromUrl: boolean;
}

function parseRankingType(value: string | null): RankingType {
  return value === 'doubles' ? 'doubles' : 'singles';
}

function parseXAxisMode(value: string | null): XAxisMode {
  return value === 'age' ? 'age' : 'date';
}

function parseMetric(value: string | null): MetricMode {
  return value === 'points' ? 'points' : 'rank';
}

function parseDateRange(value: string | null): DateRange {
  if (value && (DATE_RANGES as readonly string[]).includes(value)) {
    return value as DateRange;
  }
  return '1Y';
}

function parseTitleTypes(value: string | null): TournamentTitleType[] {
  if (value == null || value === '') {
    return [...TITLE_TYPES];
  }
  if (value === 'none' || value === '0') {
    return [];
  }
  if (value === 'all') {
    return [...TITLE_TYPES];
  }
  const allowed = new Set<string>(TITLE_TYPES);
  const parsed = value
    .split(',')
    .map(s => s.trim().toLowerCase())
    .filter((t): t is TournamentTitleType => allowed.has(t));
  // Preserve canonical order
  return TITLE_TYPES.filter(t => parsed.includes(t));
}

export function parseShareUrl(search: string): ShareState {
  const params = new URLSearchParams(
    search.startsWith('?') ? search.slice(1) : search
  );
  const playersRaw = params.get('players') || params.get('p') || '';
  const playerIds = playersRaw
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);

  const rangeParam = params.get('range');

  return {
    playerIds,
    rankingType: parseRankingType(params.get('type')),
    xAxisMode: parseXAxisMode(params.get('axis')),
    metric: parseMetric(params.get('metric')),
    dateRange: parseDateRange(rangeParam),
    titleTypes: parseTitleTypes(params.get('titles')),
    rangeFromUrl: rangeParam != null && rangeParam !== '',
  };
}

export function buildShareSearch(state: {
  playerIds: string[];
  rankingType: RankingType;
  xAxisMode: XAxisMode;
  metric: MetricMode;
  dateRange: DateRange;
  titleTypes: TournamentTitleType[];
}): string {
  const params = new URLSearchParams();

  if (state.playerIds.length > 0) {
    params.set('players', state.playerIds.join(','));
  }
  if (state.rankingType !== 'singles') {
    params.set('type', state.rankingType);
  }
  if (state.xAxisMode !== 'date') {
    params.set('axis', state.xAxisMode);
  }
  if (state.metric !== 'rank') {
    params.set('metric', state.metric);
  }
  if (state.dateRange !== '1Y') {
    params.set('range', state.dateRange);
  }

  const allTitles =
    state.titleTypes.length === TITLE_TYPES.length &&
    TITLE_TYPES.every(t => state.titleTypes.includes(t));
  if (!allTitles) {
    params.set(
      'titles',
      state.titleTypes.length === 0 ? 'none' : state.titleTypes.join(',')
    );
  }

  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export function replaceShareUrl(search: string): void {
  const path = window.location.pathname;
  const target = search ? `${path}${search}` : path;
  const current = `${path}${window.location.search}`;
  if (current !== target) {
    window.history.replaceState(null, '', target);
  }
}
