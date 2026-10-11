import { NavLink, Navigate, useParams } from 'react-router-dom';
import { SectionHead } from '../../components/ui';
import { ComparePlayers } from './ComparePlayers';
import { CompareTeams } from './CompareTeams';

export default function ComparePage() {
  const { mode, a, b } = useParams();
  if (mode !== 'players' && mode !== 'teams') return <Navigate to="/compare/players" replace />;
  return (
    <section className="view active" id="view-compare">
      <SectionHead title="Compare">Stack two teams or two players against each other, across whichever window of time makes the comparison fair.</SectionHead>
      <nav className="tabs" id="compare-tabs" style={{ marginBottom: 24 }}>
        <NavLink to="/compare/players" className={() => `tab-btn ${mode === 'players' ? 'active' : ''}`}>Player Comparison</NavLink>
        <NavLink to="/compare/teams" className={() => `tab-btn ${mode === 'teams' ? 'active' : ''}`}>Team Comparison</NavLink>
      </nav>
      {mode === 'players' ? <ComparePlayers a={a} b={b} /> : <CompareTeams a={a} b={b} />}
    </section>
  );
}
