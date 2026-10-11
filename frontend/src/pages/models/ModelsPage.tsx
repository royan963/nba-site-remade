import { NavLink, Navigate, useParams } from 'react-router-dom';
import { SectionHead } from '../../components/ui';
import { MvpPage } from './MvpPage';
import { ArchetypesPage } from './ArchetypesPage';
import { ProjectionsPage } from './ProjectionsPage';

const MODELS = [
  { slug: 'mvp', label: 'MVP Predictor' },
  { slug: 'archetypes', label: 'Player Archetypes' },
  { slug: 'projections', label: 'Career Projections' },
];

export default function ModelsPage() {
  const { model } = useParams();
  if (!MODELS.some(m => m.slug === model)) return <Navigate to="/models/mvp" replace />;
  return (
    <section className="view active" id="view-models">
      <SectionHead title="Models">Machine learning on 80 seasons of data. Each model is trained offline and tested on seasons it never saw.</SectionHead>
      <nav className="tabs" style={{ marginBottom: 24 }}>
        {MODELS.map(m => (
          <NavLink key={m.slug} to={`/models/${m.slug}`} className={({ isActive }) => `tab-btn ${isActive ? 'active' : ''}`}>{m.label}</NavLink>
        ))}
      </nav>
      {model === 'mvp' && <MvpPage />}
      {model === 'archetypes' && <ArchetypesPage />}
      {model === 'projections' && <ProjectionsPage />}
    </section>
  );
}
