/** Live race vs. preseason prediction, for a season that is under way and has both. */
export type RaceView = 'live' | 'preseason';

export function RaceViewToggle({ id, view, onView }: { id: string; view: RaceView; onView: (v: RaceView) => void }) {
  return (
    <div className="proj-comps" id={id} role="group" aria-label="Which prediction" style={{ marginTop: 0, marginBottom: 12 }}>
      {(['live', 'preseason'] as const).map(v => (
        <button key={v} type="button" className={`pill-btn${view === v ? ' active' : ''}`} aria-pressed={view === v} onClick={() => onView(v)}>
          {v === 'live' ? 'Live (updated daily)' : 'Preseason (before game 1)'}
        </button>
      ))}
    </div>
  );
}
