import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { apiSend } from '../../api/client';
import { useApi } from '../../api/hooks';
import type { Favorites, Me, SavedComparison } from '../../api/types';
import { useAuth } from '../../auth';
import { Loading, NoData, Panel, SectionHead } from '../../components/ui';

export default function AccountPage() {
  const { user, ready } = useAuth();
  if (!ready) return <section className="view active"><Loading /></section>;
  if (!user) return <Navigate to="/login?next=/account" replace />;
  return <AccountContent user={user} />;
}

function AccountContent({ user }: { user: Me }) {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [reload, setReload] = useState(0);
  const { data: favs } = useApi<Favorites>('/me/favorites', { fresh: true, reloadKey: reload });
  const { data: comps } = useApi<SavedComparison[]>('/me/comparisons', { fresh: true, reloadKey: reload });

  const [profile, setProfile] = useState({ display_name: user.display_name, username: user.username, bio: user.bio });
  const [profileMsg, setProfileMsg] = useState('');
  const [pw, setPw] = useState({ current_password: '', new_password: '' });
  const [pwMsg, setPwMsg] = useState('');
  const [del, setDel] = useState('');
  const [delMsg, setDelMsg] = useState('');

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault();
    try { setUser(await apiSend<Me>('PATCH', '/auth/me', profile)); setProfileMsg('Saved'); } catch (err) { setProfileMsg((err as Error).message); }
  };
  const changePassword = async (e: FormEvent) => {
    e.preventDefault();
    try { await apiSend('POST', '/auth/password', pw); setPw({ current_password: '', new_password: '' }); setPwMsg('Password changed. Other devices were signed out.'); }
    catch (err) { setPwMsg((err as Error).message); }
  };
  const deleteAccount = async (e: FormEvent) => {
    e.preventDefault();
    if (!window.confirm('Delete your account, lineups and saved comparisons? This can\u2019t be undone.')) return;
    try { await apiSend('DELETE', '/auth/me', { password: del }); setUser(null); navigate('/'); } catch (err) { setDelMsg((err as Error).message); }
  };

  return (
    <section className="view active" id="view-account">
      <SectionHead title="Settings">Signed in as {user.email}. <Link to={`/u/${user.username}`}>View your public profile</Link></SectionHead>
      <div className="panel-row">
        <Panel>
          <SectionHead title="Profile" small />
          <form onSubmit={saveProfile} className="stack-form" id="profile-form">
            <label>Display name<input value={profile.display_name} onChange={e => setProfile(p => ({ ...p, display_name: e.target.value }))} maxLength={60} required /></label>
            <label>Username<input value={profile.username} onChange={e => setProfile(p => ({ ...p, username: e.target.value }))} required /></label>
            <label>Bio<textarea value={profile.bio} onChange={e => setProfile(p => ({ ...p, bio: e.target.value }))} maxLength={280} rows={3} /></label>
            <div className="form-row"><button className="pill-btn active" type="submit">Save profile</button>
              {profileMsg && <span className={profileMsg === 'Saved' ? 'form-ok' : 'form-error'}>{profileMsg}</span>}</div>
          </form>
        </Panel>
        <Panel>
          <SectionHead title="Password" small />
          <form onSubmit={changePassword} className="stack-form" id="password-form">
            <label>Current password<input type="password" autoComplete="current-password" value={pw.current_password} onChange={e => setPw(p => ({ ...p, current_password: e.target.value }))} required /></label>
            <label>New password<input type="password" autoComplete="new-password" minLength={10} value={pw.new_password} onChange={e => setPw(p => ({ ...p, new_password: e.target.value }))} required /></label>
            <div className="form-row"><button className="pill-btn active" type="submit">Change password</button>
              {pwMsg && <span className={pwMsg.startsWith('Password changed') ? 'form-ok' : 'form-error'}>{pwMsg}</span>}</div>
          </form>
        </Panel>
      </div>

      <Panel>
        <SectionHead title="Favorites" small />
        {!favs && <Loading />}
        {favs && favs.players.length + favs.teams.length === 0 && <NoData>No favorites yet. Use the &#9734; button on any player or team.</NoData>}
        <div className="chip-list">
          {favs?.players.map(p => <Link key={p.player_id} className="pill-btn" to={`/players/${p.player_id}`}>{p.player}</Link>)}
          {favs?.teams.map(t => <Link key={t.slug} className="pill-btn" to={`/teams/${t.slug}`}>{t.franchise}</Link>)}
        </div>
      </Panel>

      <Panel>
        <SectionHead title="Saved comparisons" small />
        {!comps && <Loading />}
        {comps?.length === 0 && <NoData>Nothing saved yet. Use &ldquo;Save comparison&rdquo; on any comparison.</NoData>}
        {comps?.map(c => (
          <div className="saved-row" key={c.id}>
            <div>
              <Link to={c.path} className="name-link">{c.title}</Link>{c.is_public && <span className="hof-badge">Public</span>}
              {c.note && <div className="similar-meta">{c.note}</div>}
            </div>
            <div className="form-row">
              <button type="button" className="pill-btn" onClick={async () => { await apiSend('PATCH', `/me/comparisons/${c.id}`, { is_public: !c.is_public }); setReload(r => r + 1); }}>
                {c.is_public ? 'Make private' : 'Make public'}</button>
              <button type="button" className="pill-btn" onClick={async () => { await apiSend('DELETE', `/me/comparisons/${c.id}`); setReload(r => r + 1); }}>Delete</button>
            </div>
          </div>
        ))}
      </Panel>

      <Panel className="danger-zone">
        <SectionHead title="Delete account" small>Permanently deletes your account, lineups, favorites and saved comparisons.</SectionHead>
        <form onSubmit={deleteAccount} className="form-row" id="delete-form">
          <input type="password" placeholder="Your password" autoComplete="current-password" value={del} onChange={e => setDel(e.target.value)} required />
          <button className="pill-btn danger" type="submit">Delete my account</button>
          {delMsg && <span className="form-error">{delMsg}</span>}
        </form>
      </Panel>
    </section>
  );
}
