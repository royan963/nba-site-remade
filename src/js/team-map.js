// ===================================================================
// TEAM MAP VIEW (D3 + topojson)
// ===================================================================
const GEO = toObjects(TEAM_GEO); // [{season, franchise, team_name, city, lat, lng, current_name, status, w, l, srs, o_rtg, d_rtg, pace, pts_per_game, playoffs, abbr, primary_color, secondary_color, badge_code}, ...]

// group geo rows by franchise lineage for relocation-path drawing
const geoByFranchise = new Map();
GEO.forEach(g => {
  if (!geoByFranchise.has(g.franchise)) geoByFranchise.set(g.franchise, []);
  geoByFranchise.get(g.franchise).push(g);
});
geoByFranchise.forEach(list => list.sort((a, b) => a.season - b.season));

// unique franchise list with full season span (for "team active in season X" checks)
const franchiseSpans = new Map(); // franchise -> {minSeason, maxSeason, rows: [...]}
geoByFranchise.forEach((rows, franchise) => {
  franchiseSpans.set(franchise, {
    minSeason: rows[0].season,
    maxSeason: rows[rows.length - 1].season,
    rows
  });
});

// distinct cities a franchise has occupied, in chronological order, deduped consecutive repeats
function franchiseCityPath(franchise) {
  const rows = geoByFranchise.get(franchise);
  const path = [];
  rows.forEach(r => {
    const last = path[path.length - 1];
    if (!last || last.city !== r.city) {
      path.push({ city: r.city, lat: r.lat, lng: r.lng, firstSeason: r.season });
    }
  });
  return path;
}

let mapProjection = null;
let mapPath = null;
let mapSvg = null;
let mapInitialized = false;
let mapPlaying = false;
let mapPlayInterval = null;

const MARKER_R_ACTIVE = 14;
const MARKER_R_INACTIVE = 8;

function initTeamMap() {
  if (mapInitialized) return;
  mapInitialized = true;

  const container = document.getElementById('us-map-container');
  const width = 760, height = 460;

  const topo = STATES_TOPOJSON;
  const statesGeo = topojson.feature(topo, topo.objects.states);
  // Exclude Alaska/Hawaii (not adjacent to the mainland) AND outlying
  // territories (Puerto Rico, Guam, etc.) — their far-flung bounding boxes
  // were badly skewing fitExtent's scale calculation for the whole map.
  const EXCLUDE_REGIONS = new Set([
    'Alaska', 'Hawaii', 'American Samoa', 'Guam',
    'Commonwealth of the Northern Mariana Islands',
    'Puerto Rico', 'United States Virgin Islands'
  ]);
  const usMainland = {
    type: 'FeatureCollection',
    features: statesGeo.features.filter(f => !EXCLUDE_REGIONS.has(f.properties.name))
  };

  const canadaTopo = CANADA_TOPOJSON;
  const canadaGeo = topojson.feature(canadaTopo, canadaTopo.objects.canada);

  // Fit to the continental US mainland, reserving headroom above for Canada
  // (which extends naturally from this same projection rather than being
  // independently fit — its full geometry reaches the Arctic and would
  // badly skew the scale if fit directly).
  mapProjection = d3.geoAlbers().fitExtent([[20, 120], [width - 20, height - 20]], usMainland);
  mapPath = d3.geoPath(mapProjection);

  mapSvg = d3.select(container).append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .attr('role', 'img')
    .attr('aria-label', 'Map of the United States and Canada showing NBA team locations by season');

  const tooltip = d3.select(container).append('div').attr('class', 'map-tooltip');

  mapSvg.append('g').attr('class', 'canada-layer')
    .append('path')
    .attr('class', 'state-path country-path')
    .attr('d', mapPath(canadaGeo));

  mapSvg.append('g').attr('class', 'states-layer')
    .selectAll('path')
    .data(usMainland.features)
    .join('path')
    .attr('class', 'state-path')
    .attr('d', mapPath);

  mapSvg.append('g').attr('class', 'relocation-layer');
  mapSvg.append('g').attr('class', 'leader-layer');
  mapSvg.append('g').attr('class', 'markers-layer');

  renderMapForSeason(LATEST_SEASON, tooltip);

  // wire up controls
  const slider = document.getElementById('map-season-slider');
  slider.addEventListener('input', () => {
    renderMapForSeason(parseInt(slider.value, 10), tooltip);
  });

  document.getElementById('map-play-btn').addEventListener('click', () => {
    mapPlaying = !mapPlaying;
    const btn = document.getElementById('map-play-btn');
    btn.innerHTML = mapPlaying ? '&#10074;&#10074;' : '&#9654;';
    if (mapPlaying) {
      if (parseInt(slider.value, 10) >= LATEST_SEASON) slider.value = FIRST_SEASON;
      mapPlayInterval = setInterval(() => {
        let v = parseInt(slider.value, 10) + 1;
        if (v > LATEST_SEASON) {
          clearInterval(mapPlayInterval);
          mapPlaying = false;
          btn.innerHTML = '&#9654;';
          return;
        }
        slider.value = v;
        renderMapForSeason(v, tooltip);
      }, 200);
    } else {
      clearInterval(mapPlayInterval);
    }
  });

  document.getElementById('map-toggle-map').addEventListener('click', () => setMapViewMode('map'));
  document.getElementById('map-toggle-grid').addEventListener('click', () => setMapViewMode('grid'));
}

function setMapViewMode(mode) {
  document.getElementById('map-toggle-map').classList.toggle('active', mode === 'map');
  document.getElementById('map-toggle-grid').classList.toggle('active', mode === 'grid');
  document.getElementById('map-panel').style.display = mode === 'map' ? 'block' : 'none';
  document.querySelector('.map-legend').style.display = mode === 'map' ? 'flex' : 'none';
  document.getElementById('team-grid').style.display = mode === 'grid' ? 'grid' : 'none';
}

function teamsActiveInSeason(season) {
  const active = [];
  franchiseSpans.forEach((span, franchise) => {
    const row = span.rows.find(r => r.season === season);
    if (row) active.push(row);
  });
  return active;
}

// Group markers that project to (nearly) the same point and fan them out in a
// small circle around the shared point, so co-located franchises (e.g. Lakers
// and Clippers, both in Los Angeles) are each independently visible and clickable.
function layoutMarkers(markerData) {
  // Step 1: exact-duplicate cities (e.g. Lakers & Clippers, both Los Angeles)
  // get fanned into a small ring around their shared true point.
  const SAME_LOCATION_DIST = 6; // px — essentially identical projected point
  const FAN_RADIUS = 24;        // px — ring radius for exact-duplicate clusters

  markerData.forEach(d => {
    const p = mapProjection([d.row.lng, d.row.lat]);
    d.trueX = p ? p[0] : -1000;
    d.trueY = p ? p[1] : -1000;
  });

  const buckets = new Map();
  markerData.forEach((d, i) => {
    const key = `${Math.round(d.trueX / SAME_LOCATION_DIST)}:${Math.round(d.trueY / SAME_LOCATION_DIST)}`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(i);
  });

  buckets.forEach(cluster => {
    if (cluster.length === 1) {
      const d = markerData[cluster[0]];
      d.x = d.trueX;
      d.y = d.trueY;
      return;
    }
    const cx = cluster.reduce((s, i) => s + markerData[i].trueX, 0) / cluster.length;
    const cy = cluster.reduce((s, i) => s + markerData[i].trueY, 0) / cluster.length;
    const clusterSize = cluster.length;
    const radius = clusterSize <= 2 ? FAN_RADIUS : FAN_RADIUS * (1 + (clusterSize - 2) * 0.35);
    cluster.forEach((idx, k) => {
      const angle = (-Math.PI / 2) + (k * 2 * Math.PI / clusterSize);
      const d = markerData[idx];
      d.x = cx + radius * Math.cos(angle);
      d.y = cy + radius * Math.sin(angle);
    });
  });

  // Step 2: gentle iterative repulsion for markers that are simply close
  // together (a dense region like the Northeast corridor or the 1950s
  // Midwest) without being exact duplicates. This nudges any pair still
  // closer than MIN_SEP apart, a little at a time, capped at a few passes
  // so it settles without becoming a runaway physics simulation.
  const MIN_SEP = 38;       // px — minimum comfortable center-to-center spacing
  const PASSES = 40;
  const STEP = 0.5;
  for (let pass = 0; pass < PASSES; pass++) {
    let moved = false;
    for (let i = 0; i < markerData.length; i++) {
      for (let j = i + 1; j < markerData.length; j++) {
        const a = markerData[i], b = markerData[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        let dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 0.01) { dx = (Math.random() - 0.5); dy = (Math.random() - 0.5); dist = 0.01; }
        if (dist < MIN_SEP) {
          moved = true;
          const push = (MIN_SEP - dist) * STEP;
          const ux = dx / dist, uy = dy / dist;
          a.x -= ux * push / 2; a.y -= uy * push / 2;
          b.x += ux * push / 2; b.y += uy * push / 2;
        }
      }
    }
    if (!moved) break;
  }

  markerData.forEach(d => {
    const moved = Math.abs(d.x - d.trueX) > 1 || Math.abs(d.y - d.trueY) > 1;
    d.offsetFromTrue = moved;
  });

  return markerData;
}

function renderMapForSeason(season, tooltip) {
  document.getElementById('map-sb-season').textContent = season;
  const slider = document.getElementById('map-season-slider');
  if (parseInt(slider.value, 10) !== season) slider.value = season;

  const activeRows = teamsActiveInSeason(season);
  const activeFranchises = new Set(activeRows.map(r => r.franchise));
  document.getElementById('map-sb-count-label').textContent =
    `${activeRows.length} team${activeRows.length === 1 ? '' : 's'} in the league`;

  // relocation paths: accumulate as moves happen chronologically up to `season`
  const relocationLines = [];
  geoByFranchise.forEach((rows, franchise) => {
    const path = franchiseCityPath(franchise);
    if (path.length < 2) return;
    const visiblePath = path.filter(p => p.firstSeason <= season);
    if (visiblePath.length < 2) return;
    for (let i = 0; i < visiblePath.length - 1; i++) {
      relocationLines.push({ from: visiblePath[i], to: visiblePath[i + 1], franchise });
    }
  });

  const relocSel = mapSvg.select('.relocation-layer').selectAll('path').data(relocationLines, (d, i) => i);
  relocSel.join('path')
    .attr('class', 'relocation-path')
    .attr('d', d => {
      const p1 = mapProjection([d.from.lng, d.from.lat]);
      const p2 = mapProjection([d.to.lng, d.to.lat]);
      if (!p1 || !p2) return '';
      const mx = (p1[0] + p2[0]) / 2, my = (p1[1] + p2[1]) / 2 - 18;
      return `M${p1[0]},${p1[1]} Q${mx},${my} ${p2[0]},${p2[1]}`;
    });

  // markers: one per franchise, positioned at its CURRENT location as of `season`
  let markerData = [];
  franchiseSpans.forEach((span, franchise) => {
    const rowsUpToSeason = span.rows.filter(r => r.season <= season);
    if (rowsUpToSeason.length === 0) return; // not founded yet
    const isActive = activeFranchises.has(franchise);
    const lastRow = rowsUpToSeason[rowsUpToSeason.length - 1];
    // only show a "ghost" marker for one season after a franchise's last game —
    // long enough to see where a team went dark, not so long it clutters later eras
    const longDefunct = (!isActive) && (season - lastRow.season > 1);
    if (longDefunct && season > span.maxSeason) return;
    markerData.push({ franchise, row: lastRow, isActive });
  });

  markerData = layoutMarkers(markerData);

  // leader lines: thin connector from fanned position back to true geographic point
  const leaderData = markerData.filter(d => d.offsetFromTrue);
  const leaderSel = mapSvg.select('.leader-layer').selectAll('line').data(leaderData, d => d.franchise);
  leaderSel.join('line')
    .attr('class', 'marker-leader')
    .attr('x1', d => d.trueX).attr('y1', d => d.trueY)
    .attr('x2', d => d.x).attr('y2', d => d.y);

  // marker groups: colored badge circle + abbreviation text, sized/dimmed by active status
  const markerSel = mapSvg.select('.markers-layer').selectAll('g.team-marker').data(markerData, d => d.franchise);

  const markerEnter = markerSel.enter().append('g').attr('class', 'team-marker');
  markerEnter.append('circle').attr('class', 'marker-badge-ring');
  markerEnter.append('circle').attr('class', 'marker-badge-fill');
  markerEnter.append('text').attr('class', 'marker-badge-text');

  const markerMerge = markerEnter.merge(markerSel);

  markerMerge
    .attr('transform', d => `translate(${d.x},${d.y})`)
    .style('opacity', d => d.isActive ? 1 : 0.45)
    .style('cursor', 'pointer')
    .each(function (d) {
      const g = d3.select(this);
      const r = d.isActive ? MARKER_R_ACTIVE : MARKER_R_INACTIVE;
      g.select('.marker-badge-ring')
        .attr('r', r + 1.5)
        .attr('fill', 'none')
        .attr('stroke', d.row.secondary_color)
        .attr('stroke-width', d.isActive ? 1.5 : 1);
      g.select('.marker-badge-fill')
        .attr('r', r)
        .attr('fill', d.row.primary_color);
      g.select('.marker-badge-text')
        .attr('font-size', d.isActive ? 9.5 : 7.5)
        .attr('font-weight', 700)
        .attr('font-family', "'JetBrains Mono', monospace")
        .attr('fill', d.row.secondary_color)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'central')
        .attr('dy', '0.32em')
        .text(d.row.abbr || d.row.badge_code);
    })
    .on('mouseenter', function (event, d) {
      const r = d.row;
      tooltip.html(`
        <div class="mt-name">${r.team_name}</div>
        <div class="mt-meta">${r.city} · ${r.season}${r.w != null ? ` · ${r.w}-${r.l}` : ''}</div>
        ${d.isActive ? '' : '<div class="mt-meta" style="margin-top:3px;opacity:0.7;">Not active this season</div>'}
      `).style('opacity', 1);
      d3.select(this).raise();
    })
    .on('mousemove', function (event) {
      const [x, y] = d3.pointer(event, document.getElementById('us-map-container'));
      tooltip.style('left', (x + 14) + 'px').style('top', (y - 10) + 'px');
    })
    .on('mouseleave', function () {
      tooltip.style('opacity', 0);
    })
    .on('click', function (event, d) {
      goToTeam(d.franchise);
    });

  markerSel.exit().remove();

  // keep active markers drawn above inactive/ghost markers
  mapSvg.select('.markers-layer').selectAll('g.team-marker').sort((a, b) => (a.isActive === b.isActive) ? 0 : (a.isActive ? 1 : -1));
}

function goToTeam(franchiseName) {
  $$('.tab-btn').forEach(b => b.classList.remove('active'));
  $$('.view').forEach(v => v.classList.remove('active'));
  $('.tab-btn[data-view="teams"]').classList.add('active');
  $('#view-teams').classList.add('active');
  initTeamsView();
  selectTeam(franchiseName);
}
