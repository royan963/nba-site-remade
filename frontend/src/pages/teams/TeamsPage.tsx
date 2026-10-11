import { useParams, Link } from 'react-router-dom';
import { ErrorNote, Loading, Panel, PlayButton, Pills, SeasonSlider, SectionHead, usePlayback } from '../../components/ui';
import { oneOf, useQueryNumber, useQueryParam } from '../../lib/useQuery';
import { ChampionsList } from './Champions';
import { TeamDetail } from './TeamDetail';
import { TeamMap } from './TeamMap';
import { useFranchises } from './useFranchises';

export default function TeamsPage() {
  const { franchise: slug } = useParams();
  const { franchises, bySlug, error } = useFranchises();
  if (error) return <section className="view active"><ErrorNote error={error} /></section>;
  if (!franchises || !bySlug) return <section className="view active"><Loading /></section>;
  const selected = slug ? bySlug.get(slug) : undefined;
  return <TeamsContent franchises={franchises} selectedSlug={slug} selected={selected} />;
}

function TeamsContent({ franchises, selected, selectedSlug }: {
  franchises: NonNullable<ReturnType<typeof useFranchises>['franchises']>;
  selected?: ReturnType<NonNullable<ReturnType<typeof useFranchises>['bySlug']>['get']>;
  selectedSlug?: string;
}) {
  const all = [...franchises.values()];
  const first = Math.min(...all.map(f => f.minSeason));
  const latest = Math.max(...all.map(f => f.maxSeason));
  const [season, setSeason] = useQueryNumber('season', latest);
  const [viewRaw, setView] = useQueryParam('view', 'map');
  const view = oneOf(viewRaw, ['map', 'list', 'champions'] as const, 'map');
  const { playing, toggle } = usePlayback(first, latest, season, setSeason, 200);
  const activeCount = all.filter(f => f.rows.some(r => r.season === season)).length;

  return (
    <section className="view active" id="view-teams">
      <SectionHead title="Team Explorer">
        Every franchise that's ever played in the NBA, mapped where it played. Scrub the timeline to watch the league expand and teams relocate; click any marker for its season-by-season history.
      </SectionHead>

      <div className="map-scoreboard">
        <div className="map-scoreboard-top">
          <div className="map-season-display">
            <span id="map-sb-season">{season}</span>
            <span className="era-label">{activeCount} team{activeCount === 1 ? '' : 's'} in the league</span>
          </div>
          <div className="playback-row" style={{ marginTop: 0 }}>
            <PlayButton playing={playing} onClick={toggle} />
            <Pills options={[{ value: 'map', label: 'Map' }, { value: 'list', label: 'List' }, { value: 'champions', label: 'Champions' }]} value={view} onChange={v => setView(v)} className="map-view-toggle" />
          </div>
        </div>
        <SeasonSlider min={first} max={latest} value={season} onChange={setSeason} ticks={[first, 1960, 1980, 2000, latest]} id="map-season-slider" />
      </div>

      {view === 'champions' ? <ChampionsList season={season} /> : view === 'map' ? (
        <>
          <div className="map-legend">
            <span className="legend-item"><span className="legend-dot dot-active" />Active in selected season</span>
            <span className="legend-item"><span className="legend-dot dot-inactive" />Other franchises (not yet founded / relocated / folded)</span>
            <span className="legend-item"><span className="legend-line" />Relocation path</span>
            <span className="legend-item"><span className="legend-leader" />Offset marker (shares a city with another team)</span>
          </div>
          <Panel id="map-panel"><TeamMap franchises={franchises} season={season} /></Panel>
        </>
      ) : (
        <div className="team-grid" id="team-grid">
          {all.map(f => (
            <Link key={f.slug} to={`/teams/${f.slug}`} className={`team-chip ${f.slug === selectedSlug ? 'active' : ''}`}>
              <div className="tc-name">{f.displayName}</div>
              <div className="tc-meta">{f.minSeason}&ndash;{f.maxSeason}{f.latest.status !== 'active' ? ' \u00b7 defunct' : ''}</div>
            </Link>
          ))}
        </div>
      )}

      {selectedSlug && !selected && <div className="no-data-note">No franchise matches &ldquo;{selectedSlug}&rdquo;.</div>}
      {selected && <TeamDetail key={selected.slug} franchise={selected} />}
    </section>
  );
}
