// ===================================================================
// COMPARE: top-level view bootstrap + sub-tab nav
// ===================================================================
let compareViewInitialized = false;

function initCompareView() {
  if (compareViewInitialized) return;
  compareViewInitialized = true;
  // team selectors are populated eagerly in app_part16.js at script-load time
  // (populateTeamSelectors()), so there's nothing else to lazy-init here —
  // this hook exists mainly for symmetry with the other views and as a
  // place to extend later if compare ever needs deferred setup.
}

$$('#view-compare > .tabs > .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    $$('#view-compare > .tabs > .tab-btn').forEach(b => b.classList.remove('active'));
    $$('.compare-mode-view').forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    $('#compare-' + btn.dataset.compareMode).classList.add('active');
  });
});
