// ===================================================================
// SHOT PROFILE: half-court SVG with 6 shooting zones
// ===================================================================
// Court geometry uses standard NBA regulation dimensions (in feet),
// scaled to SVG units. Origin: basket center.
const COURT_SCALE = 10;
const COURT_W = 50 * COURT_SCALE;
const COURT_H = 42 * COURT_SCALE;
const BASKET_X = COURT_W / 2;
const BASKET_Y = 5.25 * COURT_SCALE;

function courtPt(xFt, yFt) {
  return [BASKET_X + xFt * COURT_SCALE, BASKET_Y + yFt * COURT_SCALE];
}

// Heat color scale (cool blue -> green -> amber -> red) for FG%, independent
// of team brand colors so it reads as a neutral analytic scale.
function fgPctColor(pct) {
  if (pct == null) return '#3a3530';
  const t = Math.max(0, Math.min(1, (pct - 0.25) / (0.65 - 0.25)));
  const stops = [
    { t: 0, c: [58, 111, 158] },
    { t: 0.4, c: [106, 138, 90] },
    { t: 0.7, c: [217, 154, 62] },
    { t: 1, c: [224, 82, 74] },
  ];
  let lo = stops[0], hi = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (t >= stops[i].t && t <= stops[i + 1].t) { lo = stops[i]; hi = stops[i + 1]; break; }
  }
  const span = (hi.t - lo.t) || 1;
  const localT = (t - lo.t) / span;
  const c = lo.c.map((v, i) => Math.round(v + (hi.c[i] - v) * localT));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

// Build a closed polygon (as an SVG path) for a ring-wedge: the area between
// r_inner and r_outer, swept from angle a0 to a1 (degrees, 0=along the right
// baseline, 90=straight up the court, 180=along the left baseline).
function ringWedgePath(rInner, rOuter, a0Deg, a1Deg, n = 20) {
  const outer = [];
  const inner = [];
  for (let i = 0; i <= n; i++) {
    const a = ((a0Deg + (a1Deg - a0Deg) * i / n) * Math.PI) / 180;
    outer.push(courtPt(rOuter * Math.cos(a), rOuter * Math.sin(a)));
  }
  for (let i = 0; i <= n; i++) {
    const a = ((a1Deg - (a1Deg - a0Deg) * i / n) * Math.PI) / 180;
    inner.push(courtPt(rInner * Math.cos(a), rInner * Math.sin(a)));
  }
  const all = rInner > 0 ? [...outer, ...inner] : [...outer, courtPt(0, 0)];
  return 'M' + all.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' L') + ' Z';
}

// Build a closed polygon for a rectangular corner-3 wedge: from the baseline
// up to where the corner line meets the arc, on one side (left=-1, right=1).
function cornerWedgePath(side) {
  const r3 = 23.75, cornerDist = 22;
  const dy = Math.sqrt(r3 * r3 - cornerDist * cornerDist);
  const xNear = side * 18; // inner boundary of the corner wedge (just outside the long-mid zone)
  const xFar = side * 25;  // sideline-ish outer boundary for visual purposes
  const p1 = courtPt(xNear, 0);
  const p2 = courtPt(xFar, 0);
  const p3 = courtPt(xFar, dy);
  const p4 = courtPt(xNear, dy);
  return `M${p1[0]},${p1[1]} L${p2[0]},${p2[1]} L${p3[0]},${p3[1]} L${p4[0]},${p4[1]} Z`;
}

const ZONE_DEFS = [
  { key: 'pct_fga_0_3', pctKey: 'fg_pct_0_3', label: 'Restricted Area', sub: '0-3 ft', rInner: 0, rOuter: 4 },
  { key: 'pct_fga_3_10', pctKey: 'fg_pct_3_10', label: 'Short Range', sub: '3-10 ft', rInner: 4, rOuter: 10 },
  { key: 'pct_fga_10_16', pctKey: 'fg_pct_10_16', label: 'Mid-Range', sub: '10-16 ft', rInner: 10, rOuter: 16 },
  { key: 'pct_fga_16_3p', pctKey: 'fg_pct_16_3p', label: 'Long Mid-Range', sub: '16 ft-3PT', rInner: 16, rOuter: 23 },
  { key: 'pct_fga_3p', pctKey: 'fg_pct_3p', label: 'Three-Point', sub: 'Beyond the arc', rInner: 23, rOuter: 31 },
];

function buildCourtSVG(zoneData) {
  if (!zoneData) return '';

  const lineEls = [];
  // baseline
  lineEls.push(`<line class="court-line" x1="0" y1="${BASKET_Y - 5.25 * COURT_SCALE}" x2="${COURT_W}" y2="${BASKET_Y - 5.25 * COURT_SCALE}"/>`);
  // paint
  // paint corners in court-feet; courtPt's y grows downward in SVG screen-space
  // as yFt decreases (since yFt=19 is further up-court / smaller screen-y), so
  // the corner with the larger yFt is the visually-higher (smaller screen-y) one.
  const paintNear = courtPt(-8, 0), paintFar = courtPt(8, 19);
  const paintX = Math.min(paintNear[0], paintFar[0]);
  const paintY = Math.min(paintNear[1], paintFar[1]);
  const paintW = Math.abs(paintFar[0] - paintNear[0]);
  const paintH = Math.abs(paintFar[1] - paintNear[1]);
  lineEls.push(`<rect class="court-line" x="${paintX}" y="${paintY}" width="${paintW}" height="${paintH}"/>`);
  // free throw circle
  const ftCenter = courtPt(0, 19);
  lineEls.push(`<circle class="court-line" cx="${ftCenter[0]}" cy="${ftCenter[1]}" r="${6 * COURT_SCALE}"/>`);
  // restricted arc
  const raL = courtPt(-4, 0), raR = courtPt(4, 0), raTop = courtPt(0, 4);
  lineEls.push(`<path class="court-line" d="M${raL[0]},${raL[1]} A${4*COURT_SCALE},${4*COURT_SCALE} 0 0 1 ${raR[0]},${raR[1]}"/>`);
  // 3pt line + corners
  const r3 = 23.75, cornerDist = 22;
  const dy3 = Math.sqrt(r3 * r3 - cornerDist * cornerDist);
  const cL0 = courtPt(-cornerDist, 0), cL1 = courtPt(-cornerDist, dy3);
  const cR0 = courtPt(cornerDist, 0), cR1 = courtPt(cornerDist, dy3);
  lineEls.push(`<line class="court-line" x1="${cL0[0]}" y1="${cL0[1]}" x2="${cL1[0]}" y2="${cL1[1]}"/>`);
  lineEls.push(`<line class="court-line" x1="${cR0[0]}" y1="${cR0[1]}" x2="${cR1[0]}" y2="${cR1[1]}"/>`);
  lineEls.push(`<path class="court-line" d="M${cL1[0]},${cL1[1]} A${r3*COURT_SCALE},${r3*COURT_SCALE} 0 0 1 ${cR1[0]},${cR1[1]}"/>`);
  // backboard + rim
  const bbL = courtPt(-3, -0.75), bbR = courtPt(3, -0.75);
  lineEls.push(`<line class="court-line" x1="${bbL[0]}" y1="${bbL[1]}" x2="${bbR[0]}" y2="${bbR[1]}"/>`);
  lineEls.push(`<circle class="court-line" cx="${BASKET_X}" cy="${BASKET_Y}" r="${0.75 * COURT_SCALE}"/>`);

  // interactive zone wedges (full semicircle bands, baseline to baseline)
  const zoneEls = ZONE_DEFS.map(z => {
    const pctFga = zoneData[z.key];
    const fgPct = zoneData[z.pctKey];
    const path = ringWedgePath(z.rInner, z.rOuter, 0, 180);
    const fill = fgPctColor(fgPct);
    const opacity = pctFga != null ? Math.max(0.35, Math.min(0.95, 0.35 + pctFga * 1.3)) : 0.15;
    return `<path class="court-zone" data-zone="${z.label}" data-sub="${z.sub}" data-pct-fga="${pctFga != null ? pctFga : ''}" data-fg-pct="${fgPct != null ? fgPct : ''}" d="${path}" fill="${fill}" fill-opacity="${opacity.toFixed(2)}"/>`;
  });

  // corner-3 overlay wedges (drawn on top, distinguishable via the data's
  // separate corner-3 stats rather than the general 3pt zone underneath)
  const cornerPct = zoneData.corner_3_pct;
  const cornerShare = zoneData.pct_corner_3;
  const cornerFill = fgPctColor(cornerPct);
  const cornerOpacity = cornerShare != null ? Math.max(0.4, Math.min(0.95, 0.4 + cornerShare * 2.2)) : 0.15;
  const cornerEls = [-1, 1].map(side =>
    `<path class="court-zone" data-zone="Corner Three" data-sub="${side < 0 ? 'Left corner' : 'Right corner'}" data-pct-fga="${cornerShare != null ? cornerShare : ''}" data-fg-pct="${cornerPct != null ? cornerPct : ''}" d="${cornerWedgePath(side)}" fill="${cornerFill}" fill-opacity="${cornerOpacity.toFixed(2)}"/>`
  );

  const labelEls = ZONE_DEFS.map((z, i) => {
    const midR = (z.rInner + z.rOuter) / 2;
    const pt = courtPt(0, midR);
    const fgPct = zoneData[z.pctKey];
    return `<text class="court-zone-label" x="${pt[0]}" y="${pt[1] - 3}">${fgPct != null ? (fgPct * 100).toFixed(2) + '%' : '—'}</text>
            <text class="court-zone-sublabel" x="${pt[0]}" y="${pt[1] + 10}">${z.sub}</text>`;
  });

  return `<svg viewBox="0 0 ${COURT_W} ${COURT_H}" xmlns="http://www.w3.org/2000/svg">
    <g class="zones-layer">${zoneEls.join('')}${cornerEls.join('')}</g>
    <g class="lines-layer">${lineEls.join('')}</g>
    <g class="labels-layer">${labelEls.join('')}</g>
  </svg>`;
}
