import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { apiGet, apiSend } from '../api/client';
import type { Favorites } from '../api/types';
import { useAuth } from '../auth';

/** Top-right: "Sign in" link, or the user's name with a small menu. */
export function AccountMenu() {
  const { user, ready, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);
  useEffect(() => setOpen(false), [location.pathname]);

  if (!ready) return <div className="account-menu" />;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <div className="account-menu"><Link className="pill-btn" to={`/login?next=${next}`} id="sign-in-link">Sign in</Link></div>;
  }
  return (
    <div className="account-menu" ref={ref}>
      <button type="button" className="pill-btn account-button" id="account-button" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        {user.display_name} &#9662;
      </button>
      {open && (
        <div className="account-dropdown" role="menu">
          <Link to={`/u/${user.username}`} role="menuitem">My profile</Link>
          <Link to="/lineups" role="menuitem">My lineups</Link>
          <Link to="/account" role="menuitem">Settings</Link>
          <button type="button" role="menuitem" onClick={async () => { await signOut(); navigate('/'); }}>Sign out</button>
        </div>
      )}
    </div>
  );
}

/** Star toggle for a player or team. Signed-out users are sent to sign in. */
export function FavoriteButton({ kind, refId, label }: { kind: 'player' | 'team'; refId: string; label: string }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) { setOn(false); return; }
    let live = true;
    apiGet<Favorites>('/me/favorites', { fresh: true }).then(f => {
      if (!live) return;
      setOn(kind === 'player' ? f.players.some(p => p.player_id === refId) : f.teams.some(t => t.slug === refId));
    }, () => {});
    return () => { live = false; };
  }, [user, kind, refId]);

  const toggle = async () => {
    if (!user) { navigate(`/login?next=${encodeURIComponent(location.pathname + location.search)}`); return; }
    setBusy(true);
    try {
      await apiSend(on ? 'DELETE' : 'PUT', `/me/favorites/${kind}/${encodeURIComponent(refId)}`);
      setOn(!on);
    } finally { setBusy(false); }
  };
  return (
    <button type="button" className={`pill-btn favorite-btn ${on ? 'active' : ''}`} onClick={toggle} disabled={busy}
            aria-pressed={on} title={on ? `Remove ${label} from favorites` : `Add ${label} to favorites`}>
      {on ? '\u2605 Favorited' : '\u2606 Favorite'}
    </button>
  );
}

/** "Save comparison" with a title, note and public toggle. */
export function SaveComparison({ kind, a, b, defaultTitle }: { kind: 'players' | 'teams'; a: string; b: string; defaultTitle: string }) {
  const { user } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(defaultTitle);
  const [note, setNote] = useState('');
  const [isPublic, setPublic] = useState(false);
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | string>('idle');

  useEffect(() => { setTitle(defaultTitle); setState('idle'); }, [defaultTitle]);

  if (!user) {
    return <Link className="pill-btn" to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}>Sign in to save this comparison</Link>;
  }
  if (!open) return (
    <span className="form-row">
      <button type="button" className="pill-btn" id="save-comparison" onClick={() => { setOpen(true); setState('idle'); }}>Save comparison</button>
      {state === 'saved' && <span className="form-ok">Saved. <Link to="/account">See your saved comparisons</Link></span>}
    </span>
  );

  const save = async () => {
    setState('saving');
    try {
      await apiSend('POST', '/me/comparisons', { kind, a, b, params: location.search.replace(/^\?/, ''), title, note, is_public: isPublic });
      setState('saved');
      setOpen(false);
    } catch (e) { setState((e as Error).message); }
  };
  return (
    <div className="save-form" id="save-comparison-form">
      <input value={title} onChange={e => setTitle(e.target.value)} maxLength={100} placeholder="Title" aria-label="Title" />
      <textarea value={note} onChange={e => setNote(e.target.value)} maxLength={1000} placeholder="Note (optional)" aria-label="Note" rows={2} />
      <label className="check"><input type="checkbox" checked={isPublic} onChange={e => setPublic(e.target.checked)} /> Show on my public profile</label>
      <div className="form-row">
        <button type="button" className="pill-btn active" onClick={save} disabled={!title.trim() || state === 'saving'}>Save</button>
        <button type="button" className="pill-btn" onClick={() => setOpen(false)}>Cancel</button>
        {state !== 'idle' && state !== 'saving' && <span className="form-error">{state}</span>}
      </div>
    </div>
  );
}

export function SavedNotice() {
  return <span className="form-ok">Saved</span>;
}
