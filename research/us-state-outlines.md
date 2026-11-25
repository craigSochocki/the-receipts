# US state outlines for the Senate map

`data/source/us_states_albers.json` holds one SVG path and centroid per state (plus DC), keyed by postal code.
It is derived from [us-atlas](https://github.com/topojson/us-atlas) 3.0.1 `states-albers-10m.json` (ISC
license; built from the Census Bureau cartographic boundary files, pre-projected to Albers USA in a
975×610 frame), converted on Nov 25, 2026 with topojson-client 3.1.0 and d3-geo 3.1.1:

```js
import fs from 'fs';
import {feature} from 'topojson-client';
import {geoPath} from 'd3-geo';
const topo = JSON.parse(fs.readFileSync('node_modules/us-atlas/states-albers-10m.json'));
const path = geoPath();
const FIPS = {'01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE','11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA','20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI','45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV','55':'WI','56':'WY','60':'AS','66':'GU','69':'MP','72':'PR','78':'VI'};
const round = s => s.replace(/-?\d+\.\d+/g, n => (+n).toFixed(1));
const out = {};
for (const f of feature(topo, topo.objects.states).features) {
  const code = FIPS[f.id]; if (!code) continue;
  const [x, y] = path.centroid(f);
  out[code] = {d: round(path(f)), cx: +x.toFixed(1), cy: +y.toFixed(1)};
}
fs.writeFileSync('us_states_albers.json', JSON.stringify(out));
console.log(Object.keys(out).length, 'states', fs.statSync('us_states_albers.json').size, 'bytes');
```

Coordinates are rounded to 0.1 units. The geometry is a drawing aid only; no figure depends on it.

# House districts for the district map

`data/source/us_districts_albers.json` holds one SVG path and centroid per House district of the
120th Congress (435 seats plus DC's, keyed `<state>-<CD120FP>`; at-large seats are `00`, DC is `98`),
in the same Albers USA frame as the state outlines (`d3.geoAlbersUsa().scale(1300).translate([487.5, 305])`).
The five territorial delegates' seats fall outside that frame and are not drawn.

**Source:** Census Bureau TIGER/Line 2026, 120th Congressional District, one file per state
(`https://www2.census.gov/geo/tiger/TIGER2026/CD/tl_2026_<fips>_cd120.zip`, directory dated
2026-11-09), downloaded Nov 25, 2026.

**Check that it carries the 2026 maps (Nov 25, 2026).** Each 120th district was compared with the
119th file (`TIGER2025/CD/tl_2025_<fips>_cd119.zip`) by its largest overlap with any 119th district.
Exactly nine states have a district overlapping its best 119th match by less than 98%: AL, CA, FL,
LA, NC, OH, TN, TX, UT — the nine states `data/source/house_maps.yaml` lists with new maps for
2026, including the plans enacted after January (LA May 29, TN May 7, FL May 4, AL reinstated
June 2). Every other state matches its 119th file. So the Census file already contains the nine
states' 2026 plans; no state-by-state source was needed.

**Conversion** (mapshaper 0.6.102, topojson-client 3.1.0, d3-geo 3.1.1):

```sh
mapshaper -i tl_2026_*_cd120.shp combine-files -merge-layers -filter 'CD120FP !== "ZZ"' \
  -filter-fields STATEFP,CD120FP -simplify 0.6% weighted keep-shapes -clean \
  -o cd120_simple.json format=geojson precision=0.0001
node districts.mjs cd120_simple.json us_districts_albers.json
```

```js
import fs from 'fs';
import {geoAlbersUsa, geoPath} from 'd3-geo';
const fc = JSON.parse(fs.readFileSync(process.argv[2]));
// The us-atlas Albers frame (975 x 610), so districts align with the state outlines.
const path = geoPath(geoAlbersUsa().scale(1300).translate([487.5, 305]));
const FIPS = {'01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE','11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA','20':'KS','21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI','45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV','55':'WI','56':'WY'};
// mapshaper writes RFC 7946 rings (counterclockwise); d3's spherical geometry wants clockwise.
const rewind = g => g.type === 'Polygon' ? {...g, coordinates: g.coordinates.map(r => r.slice().reverse())}
  : {...g, coordinates: g.coordinates.map(p => p.map(r => r.slice().reverse()))};
const round = s => s.replace(/-?\d+\.\d+/g, n => (+n).toFixed(1));
const out = {};
for (const f of fc.features) {
  const st = FIPS[f.properties.STATEFP]; if (!st) continue;
  f.geometry = rewind(f.geometry);
  if (path.area(f) > 975 * 610 / 4) throw new Error(`inverted ring: ${f.properties.STATEFP}-${f.properties.CD120FP}`);
  const d = path(f); if (!d) continue;
  const [x, y] = path.centroid(f);
  out[`${st}-${f.properties.CD120FP}`] = {d: round(d), cx: +x.toFixed(1), cy: +y.toFixed(1)};
}
fs.writeFileSync(process.argv[3], JSON.stringify(out));
console.log(Object.keys(out).length, 'districts', fs.statSync(process.argv[3]).size, 'bytes');
```
