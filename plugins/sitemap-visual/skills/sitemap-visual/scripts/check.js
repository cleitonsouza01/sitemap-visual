// Run the rendered artboard's logic outside the canvas: node check.js <Main.dc.html>
// Prints counts per view. "bad" or "offcanvas" above 0 means a layout bug.
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const src = html.split('data-dc-script')[1].split('>').slice(1).join('>').split('</script>')[0];
class DCLogic {
  constructor(p) { this.props = p || {}; }
  setState(s) { this.state = Object.assign({}, this.state, typeof s === 'function' ? s(this.state) : s); }
}
const Component = new Function('DCLogic', src + '\nreturn Component;')(DCLogic);
const c = new Component({});
let failed = false;
const check = (label) => {
  const v = c.renderVals();
  const bad = v.nodes.filter((n) => [n.l, n.t, n.w].some((x) => !isFinite(x)));
  const off = v.nodes.filter((n) => n.l < -10 || n.t < -10 || n.l + n.w > 862 || n.t + n.h > 862);
  if (bad.length || off.length || !v.pv.title) failed = true;
  console.log(label.padEnd(14), 'big', v.bigNum, '| nodes', v.nodes.length, 'labels', v.labels.length,
    '| photos', v.nodes.filter((n) => n.hasImg).length, '| bad', bad.length, 'offcanvas', off.length,
    '| groups', v.groups.map((g) => g.label + ':' + g.count).join(', '));
  // Site text is untrusted: report its shape, never print it into the conversation.
  console.log(''.padEnd(14), 'card:', v.pv.kindLabel, '| title', v.pv.title ? v.pv.title.length + ' chars' : 'MISSING',
    '| description', v.pv.desc ? v.pv.desc.length + ' chars' : 'none', v.pv.price ? '| price set' : '');
  return v;
};
let v = check('start');
v.langs.slice(1).forEach((l) => { l.pick(); check('lang ' + l.label); });
if (v.langs.length) v.langs[0].pick();
const photo = c.renderVals().nodes.find((n) => n.hasImg);
if (photo) { photo.enter(); check('hover photo'); }
console.log(failed ? 'FAILED' : 'OK');
process.exit(failed ? 1 : 0);
