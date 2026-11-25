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
