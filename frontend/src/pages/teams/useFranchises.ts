import { useMemo } from 'react';
import { fromColumns } from '../../api/client';
import { useApi } from '../../api/hooks';
import type { TeamSeason } from '../../api/types';
import { buildFranchises, type Franchise } from './geo';

/** Every franchise lineage, from /teams/geo (one cached request shared by all team views). */
export function useFranchises() {
  const { data, error } = useApi<{ columns: string[]; rows: unknown[][] }>('/teams/geo');
  return useMemo(() => {
    if (!data) return { franchises: undefined, bySlug: undefined, error };
    const franchises = buildFranchises(fromColumns<TeamSeason>(data));
    const bySlug = new Map<string, Franchise>([...franchises.values()].map(f => [f.slug, f]));
    return { franchises, bySlug, error };
  }, [data, error]);
}
