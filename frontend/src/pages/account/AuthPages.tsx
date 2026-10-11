import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { apiGet } from '../../api/client';
import { useAuth } from '../../auth';
import { Panel, SectionHead } from '../../components/ui';

/** Only allow redirects to paths on this site (no "//evil.com" tricks). */
function safeNext(next: string | null) {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/';
}

export function LoginPage() {
  const { signIn, user } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get('next'));
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (user) navigate(next, { replace: true }); }, [user, next, navigate]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError('');
    try { await signIn(email, password); } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  return (
    <section className="view active auth-page">
      <Panel className="auth-card">
        <SectionHead title="Sign in" />
        <form onSubmit={submit} id="login-form">
          <label>Email<input type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button type="submit" className="pill-btn active" disabled={busy}>{busy ? 'Signing in\u2026' : 'Sign in'}</button>
        </form>
        <p className="auth-switch">New here? <Link to={`/signup?next=${encodeURIComponent(next)}`}>Create an account</Link></p>
      </Panel>
    </section>
  );
}

export function SignupPage() {
  const { signUp, user } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get('next'));
  const [form, setForm] = useState({ email: '', username: '', display_name: '', password: '' });
  const [usernameNote, setUsernameNote] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, [k]: e.target.value }));

  useEffect(() => { if (user) navigate(next, { replace: true }); }, [user, next, navigate]);
  useEffect(() => {
    const u = form.username.trim();
    if (u.length < 3) { setUsernameNote(''); return; }
    const t = setTimeout(() => {
      apiGet<{ available: boolean; reason: string | null }>(`/auth/username-available?username=${encodeURIComponent(u)}`, { fresh: true })
        .then(r => setUsernameNote(r.available ? 'Available' : r.reason || 'Not available'), () => {});
    }, 300);
    return () => clearTimeout(t);
  }, [form.username]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError('');
    try { await signUp(form); } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  return (
    <section className="view active auth-page">
      <Panel className="auth-card">
        <SectionHead title="Create an account">Save favorite players and teams, keep comparisons with notes, and build and share all-time lineups.</SectionHead>
        <form onSubmit={submit} id="signup-form">
          <label>Email<input type="email" autoComplete="email" value={form.email} onChange={set('email')} required /></label>
          <label>Username
            <input value={form.username} onChange={set('username')} autoComplete="username" required pattern="[A-Za-z0-9_]{3,20}"
                   title="3-20 letters, numbers or underscores" />
            {usernameNote && <span className={usernameNote === 'Available' ? 'form-ok' : 'form-error'}>{usernameNote}</span>}
          </label>
          <label><span className="label-text">Display name<span className="optional">(optional)</span></span><input value={form.display_name} onChange={set('display_name')} maxLength={60} /></label>
          <label>Password<input type="password" autoComplete="new-password" value={form.password} onChange={set('password')} required minLength={10} />
            <span className="hint">At least 10 characters. A few random words works well.</span></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button type="submit" className="pill-btn active" disabled={busy}>{busy ? 'Creating\u2026' : 'Create account'}</button>
        </form>
        <p className="auth-switch">Already have an account? <Link to={`/login?next=${encodeURIComponent(next)}`}>Sign in</Link></p>
      </Panel>
    </section>
  );
}
