import { useEffect, useState } from 'react';
import { useApi } from '../../api/hooks';
import type { PlayerHeadshots } from '../../api/types';

const seasonName = (s: number) => `${s - 1}-${String(s).slice(2)}`;

/**
 * The player's official NBA.com headshot, with a picker for his photo from a given season and team (2014-15 on).
 * Images load straight from NBA.com. A season photo it doesn't have falls back to his latest photo, then to his initials.
 */
export function Headshot({ playerId, name }: { playerId: string; name: string }) {
  const { data } = useApi<PlayerHeadshots>(`/players/${playerId}/headshots`);
  const options = data?.seasons ?? [];
  const [pick, setPick] = useState('');                       // '' = newest season photo (or the latest photo)
  const [failed, setFailed] = useState<Set<string>>(new Set());
  useEffect(() => { setPick(''); setFailed(new Set()); }, [playerId]);

  if (!data) return <div className="headshot placeholder" aria-hidden="true" />;
  const chosen = pick ? options.find(o => `${o.season}-${o.team}` === pick) : options[options.length - 1];
  const candidates = [chosen?.url, data.latest].filter((u): u is string => !!u && !failed.has(u));
  const src = candidates[0];
  const initials = name.split(' ').filter(Boolean).slice(0, 2).map(w => w[0]).join('');
  const shownSeason = src && src === chosen?.url ? chosen : null;
  return (
    <figure className="headshot" id="pc-headshot">
      {src
        ? <img src={src} alt={`${name}${shownSeason ? `, ${seasonName(shownSeason.season)} ${shownSeason.team_name}` : ''}`} width={260} height={190}
            loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(f => new Set(f).add(src))} />
        : <div className="headshot-initials" aria-label={name}>{initials}</div>}
      <figcaption>
        {options.length > 0 && (
          <select id="pc-headshot-season" aria-label="Photo from season" value={pick} onChange={e => setPick(e.target.value)}>
            <option value="">Newest photo</option>
            {[...options].reverse().map(o => (
              <option key={`${o.season}-${o.team}`} value={`${o.season}-${o.team}`}>{seasonName(o.season)} &middot; {o.team}</option>
            ))}
          </select>
        )}
        <span className="headshot-credit">
          {src && chosen && src !== chosen.url ? 'No photo for that season · ' : ''}Photo: {data.credit}
        </span>
      </figcaption>
    </figure>
  );
}
