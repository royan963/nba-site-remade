import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { apiGet, apiSend } from '../../api/client';
import { useApi } from '../../api/hooks';
import type { Lineup, LineupScore, PlayerLineupSeasons, PlayerSummary } from '../../api/types';
import { useAuth } from '../../auth';
import { PlayerSearch } from '../../components/PlayerSearch';
import { ErrorNote, HofBadge, Loading, Panel, SectionHead } from '../../components/ui';
import { HowItWorks, LineupScoreView } from './LineupScore';
import { PRESETS, formatPicks, parsePicks, type Pick } from './picks';

/** /lineups/new (picks live in ?p=, so an unsaved lineup is still a shareable link) and /lineups/:id/edit. */
export default function LineupBuilder() {
  const { lineupId } = useParams();
  const { data: existing, error } = useApi<Lineup>(lineupId ? `/lineups/${lineupId}` : null, { fresh: true });
  if (lineupId && error) return <section className="view active"><ErrorNote error={error} /></section>;
  if (lineupId && !existing) return <section className="view active"><Loading /></section>;
  if (existing && !existing.mine) return <section className="view active"><ErrorNote error={new Error('You can only edit your own lineups.')} /></section>;
  return <Builder key={lineupId ?? 'new'} existing={existing} />;
}

function Builder({ existing }: { existing?: Lineup }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [picks, setPicksState] = useState<Pick[]>(() =>
    existing ? existing.score.players.map(p => ({ player_id: p.player_id, season: p.season })) : parsePicks(params.get('p')));
  const [names, setNames] = useState<Record<string, PlayerSummary | { player: string; hof: boolean }>>(() =>
    Object.fromEntries((existing?.score.players ?? []).map(p => [p.player_id, { player: p.player, hof: p.hof }])));
  const [score, setScore] = useState<LineupScore | null>(null);
  const [scoreError, setScoreError] = useState('');
  const [form, setForm] = useState({ name: existing?.name ?? '', description: existing?.description ?? '', is_public: existing?.is_public ?? true });
  const [saveError, setSaveError] = useState('');
  const [saving, setSaving] = useState(false);

  const setPicks = (next: Pick[]) => {
    setPicksState(next);
    if (!existing) {            // keep a new lineup in the URL, readable: ?p=jordami01:1996,pippesc01
      const q = new URLSearchParams(window.location.search);
      q.delete('p');
      const rest = q.toString();
      const search = [next.length ? `p=${formatPicks(next)}` : '', rest].filter(Boolean).join('&');
      navigate({ search: search ? `?${search}` : '' }, { replace: true });
    }
  };

  // Score whenever the picks change (debounced).
  useEffect(() => {
    if (!picks.length) { setScore(null); return; }
    let live = true;
    const t = setTimeout(() => {
      apiSend<LineupScore>('POST', '/lineups/score', { players: picks }).then(
        s => { if (!live) return; setScore(s); setScoreError('');
               setNames(n => ({ ...n, ...Object.fromEntries(s.players.map(p => [p.player_id, { player: p.player, hof: p.hof }])) })); },
        e => live && setScoreError((e as Error).message));
    }, 200);
    return () => { live = false; clearTimeout(t); };
  }, [JSON.stringify(picks)]);   // eslint-disable-line react-hooks/exhaustive-deps

  const add = (p: PlayerSummary) => {
    if (picks.length >= 5 || picks.some(x => x.player_id === p.player_id)) return;
    setNames(n => ({ ...n, [p.player_id]: p }));
    setPicks([...picks, { player_id: p.player_id, season: null }]);
  };
  const remove = (id: string) => setPicks(picks.filter(p => p.player_id !== id));
  const setSeason = (id: string, season: number | null) => setPicks(picks.map(p => (p.player_id === id ? { ...p, season } : p)));

  const save = async () => {
    setSaving(true); setSaveError('');
    // Pin "best season" picks to the actual season so the saved lineup doesn't change if data does.
    const players = picks.map(p => ({ player_id: p.player_id, season: p.season ?? score?.players.find(x => x.player_id === p.player_id)?.season ?? null }));
    try {
      const saved = existing
        ? await apiSend<Lineup>('PUT', `/lineups/${existing.id}`, { ...form, players })
        : await apiSend<Lineup>('POST', '/lineups', { ...form, players });
      navigate(`/lineups/${saved.id}`);
    } catch (e) { setSaveError((e as Error).message); setSaving(false); }
  };

  return (
    <section className="view active" id="view-lineup-builder">
      <SectionHead title={existing ? `Edit \u201c${existing.name}\u201d` : 'Build an all-time lineup'}>
        Pick any five players from any era, and choose which of their seasons to use. The score compares every season with its own league, so eras can mix.
      </SectionHead>

      <div className="lineup-layout">
        <div>
          <Panel>
            <SectionHead title={`Your five (${picks.length}/5)`} small />
            <div id="lineup-slots">
              {picks.map((p, i) => (
                <Slot key={p.player_id} index={i} pick={p} name={names[p.player_id]} resolvedSeason={score?.players.find(x => x.player_id === p.player_id)?.season}
                      onSeason={s => setSeason(p.player_id, s)} onRemove={() => remove(p.player_id)} />
              ))}
            </div>
            {picks.length < 5 && (
              <div className="lineup-add">
                <PlayerSearch onSelect={add} placeholder={`Add player ${picks.length + 1}\u2026`} id="lineup-search" key={picks.length} />
              </div>
            )}
            {!existing && picks.length === 0 && (
              <div className="lineup-presets">
                <span className="pbp-subhead">Or start from</span>
                <div className="chart-controls">
                  {PRESETS.map(pr => <button key={pr.label} type="button" className="pill-btn" onClick={() => setPicks(parsePicks(pr.p))}>{pr.label}</button>)}
                </div>
              </div>
            )}
          </Panel>

          <Panel id="lineup-save">
            <SectionHead title={existing ? 'Save changes' : 'Save & share'} small />
            {!user ? (
              <p className="section-sub" style={{ margin: 0 }}>
                <Link to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}>Sign in</Link> to save this lineup to your profile. You can also just copy this page&rsquo;s link: the five players are in it.
              </p>
            ) : (
              <div className="stack-form">
                <label>Name<input id="lineup-name" value={form.name} maxLength={80} placeholder="e.g. My all-time starting five" onChange={e => setForm(f => ({ ...f, name: e.target.value }))} /></label>
                <label><span className="label-text">Description<span className="optional">(optional)</span></span>
                  <textarea value={form.description} maxLength={500} rows={2} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} /></label>
                <label className="check"><input type="checkbox" checked={form.is_public} onChange={e => setForm(f => ({ ...f, is_public: e.target.checked }))} /> Public: show on my profile and allow sharing</label>
                <div className="form-row">
                  <button type="button" className="pill-btn active" id="lineup-save-btn" disabled={picks.length !== 5 || !form.name.trim() || saving} onClick={save}>
                    {saving ? 'Saving\u2026' : existing ? 'Save changes' : 'Save lineup'}
                  </button>
                  {picks.length !== 5 && <span className="hint">Needs exactly five players.</span>}
                  {saveError && <span className="form-error">{saveError}</span>}
                </div>
              </div>
            )}
          </Panel>
        </div>

        <Panel className="lineup-score-panel">
          {scoreError && <ErrorNote error={new Error(scoreError)} />}
          {score ? <LineupScoreView score={score} /> : picks.length ? <Loading text={'Scoring\u2026'} /> : (
            <div className="empty-state" style={{ padding: '40px 10px' }}>
              <div className="big">Add a player to start</div>
              <div>Search on the left, or pick a preset.</div>
            </div>
          )}
          <HowItWorks />
        </Panel>
      </div>
    </section>
  );
}

function Slot({ index, pick, name, resolvedSeason, onSeason, onRemove }: {
  index: number; pick: Pick; name?: { player: string; hof: boolean }; resolvedSeason?: number;
  onSeason: (s: number | null) => void; onRemove: () => void;
}) {
  const [seasons, setSeasons] = useState<PlayerLineupSeasons | null>(null);
  useEffect(() => {
    let live = true;
    apiGet<PlayerLineupSeasons>(`/lineups/player-seasons/${pick.player_id}`).then(s => live && setSeasons(s), () => {});
    return () => { live = false; };
  }, [pick.player_id]);
  const best = seasons?.best_season;
  const options = useMemo(() => seasons?.seasons ?? [], [seasons]);
  return (
    <div className="lineup-slot" data-player={pick.player_id}>
      <span className="lineup-slot-num">{index + 1}</span>
      <div className="lineup-slot-name">
        <Link to={`/players/${pick.player_id}`} className="name-link">{name?.player ?? pick.player_id}</Link>{name?.hof && <HofBadge />}
      </div>
      <select aria-label="Season" value={pick.season ?? ''} onChange={e => onSeason(e.target.value ? parseInt(e.target.value, 10) : null)}>
        <option value="">Best season{best ? ` (${best})` : resolvedSeason ? ` (${resolvedSeason})` : ''}</option>
        {options.map(s => (
          <option key={s.season} value={s.season}>
            {`${s.season} \u00b7 ${s.teams.join('/')} \u00b7 ${s.pts ?? '\u2014'}/${s.trb ?? '\u2014'}/${s.ast ?? '\u2014'}${s.rating != null ? ` \u00b7 rating ${Math.round(s.rating)}` : ''}`}
          </option>
        ))}
      </select>
      <button type="button" className="pill-btn" aria-label={`Remove ${name?.player ?? pick.player_id}`} onClick={onRemove}>&times;</button>
    </div>
  );
}
