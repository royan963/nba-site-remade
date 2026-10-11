// Builds the two map topology files from npm packages.
//   npm install us-atlas world-atlas topojson-client topojson-server topojson-simplify d3
//   node scripts/build_map_data.js
// Outputs: data/states-10m.json (US states) and data/canada_topo.json (simplified Canada, Arctic islands dropped).
const fs = require('fs');
const path = require('path');
const d3 = require('d3');
const topojson = require('topojson-client');
const topojsonServer = require('topojson-server');
const topojsonSimplify = require('topojson-simplify');

const outDir = path.join(__dirname, '..', 'data');

// US states: used as-is
fs.copyFileSync(require.resolve('us-atlas/states-10m.json'), path.join(outDir, 'states-10m.json'));

// Canada: extract, simplify, then keep only polygons that reach south of 58N
const world = JSON.parse(fs.readFileSync(require.resolve('world-atlas/countries-50m.json'), 'utf8'));
const countries = topojson.feature(world, world.objects.countries);
const canada = countries.features.find(f => f.properties.name === 'Canada');

let topo = topojsonServer.topology({ canada });
topo = topojsonSimplify.presimplify(topo);
const simplified = topojsonSimplify.simplify(topo, 0.05);

const geo = topojson.feature(simplified, simplified.objects.canada);
const kept = geo.geometry.coordinates.filter(poly =>
  d3.geoBounds({ type: 'Feature', geometry: { type: 'Polygon', coordinates: poly } })[0][1] < 58);
const trimmed = { type: 'Feature', properties: { name: 'Canada' }, geometry: { type: 'MultiPolygon', coordinates: kept } };

fs.writeFileSync(path.join(outDir, 'canada_topo.json'), JSON.stringify(topojsonServer.topology({ canada: trimmed })));
console.log('wrote states-10m.json and canada_topo.json');
