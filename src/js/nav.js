// ===================================================================
// TAB NAVIGATION
// ===================================================================
// Scope to the top-level nav row ONLY (#main-tabs) — the Compare view has
// its own inner .tab-btn sub-tabs (Player Comparison / Team Comparison)
// living in a different .tabs container, which must NOT be caught by this
// handler, since they toggle .compare-mode-view, not .view.
$$('#main-tabs > .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('#main-tabs > .tab-btn').forEach(b => b.classList.remove('active'));
    $$('.view').forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    $('#view-' + btn.dataset.view).classList.add('active');
    // lazy-init charts on first view
    if (btn.dataset.view === 'evolution') initEvolutionView();
    if (btn.dataset.view === 'leaders') initLeadersView();
    if (btn.dataset.view === 'teams') { initTeamsView(); initTeamMap(); }
    if (btn.dataset.view === 'compare') { initCompareView(); }
  });
});
