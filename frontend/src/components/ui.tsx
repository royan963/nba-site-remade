import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { ChartConfiguration } from 'chart.js';
import { Chart } from '../lib/chart';

export function SectionHead({ title, small, children }: { title: string; small?: boolean; children?: ReactNode }) {
  return (
    <>
      <div className="section-head">
        <span className="court-dash" />
        <h2 className="section-title" style={small ? { fontSize: 16 } : undefined}>{title}</h2>
      </div>
      {children && <p className="section-sub">{children}</p>}
    </>
  );
}

export function Panel({ children, className = '', ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`panel ${className}`} {...rest}>{children}</div>;
}

export function HofBadge({ label = 'HOF' }: { label?: string }) {
  return <span className="hof-badge">{label}</span>;
}

export function Loading({ text = 'Loading\u2026' }: { text?: string }) {
  return <div className="no-data-note loading-note">{text}</div>;
}

export function ErrorNote({ error }: { error: Error }) {
  return <div className="no-data-note error-note">Couldn't load this from the API: {error.message}</div>;
}

export function NoData({ children }: { children: ReactNode }) {
  return <div className="no-data-note">{children}</div>;
}

export interface PillOption<T extends string> { value: T; label: string }

export function Pills<T extends string>({ options, value, onChange, id, className = '' }: {
  options: PillOption<T>[]; value: T; onChange: (v: T) => void; id?: string; className?: string;
}) {
  return (
    <div className={`chart-controls ${className}`} id={id}>
      {options.map(o => (
        <button key={o.value} type="button" data-value={o.value}
                className={`pill-btn ${o.value === value ? 'active' : ''}`} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Chart.js canvas. Rebuilds the chart whenever `config` changes. */
export function ChartCanvas({ config, tall, testId }: { config: ChartConfiguration; tall?: boolean; testId?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = new Chart(ref.current, config);
    (ref.current as HTMLCanvasElement & { chart?: Chart }).chart = chart;   // handy for tests/debugging
    return () => chart.destroy();
  }, [config]);
  return (
    <div className={`chart-wrap ${tall ? 'tall' : ''}`}>
      <canvas ref={ref} data-testid={testId} />
    </div>
  );
}

/** Steps `value` forward once per `ms` while playing; stops at `max`. */
export function usePlayback(min: number, max: number, value: number, setValue: (v: number) => void, ms = 110) {
  const [playing, setPlaying] = useState(false);
  const valueRef = useRef(value);
  valueRef.current = value;
  useEffect(() => {
    if (!playing) return;
    if (valueRef.current >= max) setValue(min);
    const id = setInterval(() => {
      const next = valueRef.current + 1;
      if (next > max) { setPlaying(false); return; }
      setValue(next);
    }, ms);
    return () => clearInterval(id);
  }, [playing, min, max, ms, setValue]);
  return { playing, toggle: () => setPlaying(p => !p) };
}

export function SeasonSlider({ min, max, value, onChange, ticks, id }: {
  min: number; max: number; value: number; onChange: (v: number) => void; ticks?: number[]; id?: string;
}) {
  const fill = max > min ? ((value - min) / (max - min)) * 100 : 100;
  const marks = ticks ?? [min, max];
  return (
    <>
      <input type="range" className="season-slider" id={id} min={min} max={max} step={1} value={value}
             style={{ '--fill': `${fill}%` } as React.CSSProperties}
             onChange={e => onChange(parseInt(e.target.value, 10))} />
      <div className="slider-ticks">{marks.map(t => <span key={t}>{t}</span>)}</div>
    </>
  );
}

export function PlayButton({ playing, onClick }: { playing: boolean; onClick: () => void }) {
  return (
    <button className="play-btn" type="button" aria-label={playing ? 'Pause' : 'Play timeline'} onClick={onClick}>
      {playing ? '\u275A\u275A' : '\u25B6'}
    </button>
  );
}

/** Renders its children only once they're near the screen (or right away when `eager`), so panels far down a page
 *  don't compete for the browser's few connections while the top of the page loads. */
export function WhenVisible({ children, eager = false, minHeight = 240 }: { children: ReactNode; eager?: boolean; minHeight?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [show, setShow] = useState(eager);
  useEffect(() => {
    if (show || !ref.current || typeof IntersectionObserver === 'undefined') { if (!show) setShow(true); return; }
    const io = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) { setShow(true); io.disconnect(); } }, { rootMargin: '600px 0px' });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [show]);
  return show ? <>{children}</> : <div ref={ref} style={{ minHeight }} />;
}
