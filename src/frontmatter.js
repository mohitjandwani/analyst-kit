// Minimal YAML-frontmatter parser for the constrained skill schema
// (name, type, description scalar/block, requires/env lists). Not a general
// YAML parser — it handles exactly the shapes the skill contract allows.

function stripQuotes(s) {
  const t = s.trim();
  if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) {
    return t.slice(1, -1);
  }
  return t;
}

function parseScalarOrList(value, lines, iRef) {
  // value is the text after `key:` on the same line
  if (value === '>' || value === '|') {
    const buf = [];
    let i = iRef.i + 1;
    while (i < lines.length && (/^\s{2,}\S/.test(lines[i]) || lines[i].trim() === '')) {
      buf.push(lines[i].replace(/^\s{2}/, ''));
      i++;
    }
    iRef.i = i;
    const joined = value === '>'
      ? buf.join(' ').replace(/\s+/g, ' ').trim()
      : buf.join('\n').trim();
    return joined;
  }
  if (value === '') {
    // block list:  - item
    const list = [];
    let i = iRef.i + 1;
    while (i < lines.length && /^\s*-\s+/.test(lines[i])) {
      list.push(stripQuotes(lines[i].replace(/^\s*-\s+/, '')));
      i++;
    }
    iRef.i = i;
    return list;
  }
  iRef.i += 1;
  if (value === '[]') return [];
  const inline = value.match(/^\[(.*)\]$/);
  if (inline) {
    return inline[1].split(',').map((s) => stripQuotes(s)).filter((s) => s.length);
  }
  return stripQuotes(value);
}

export function parseFrontmatter(md) {
  if (!md.startsWith('---')) return { data: null, body: md };
  const rest = md.slice(3).replace(/^\r?\n/, '');
  const closeMatch = rest.match(/\r?\n---\s*(\r?\n|$)/);
  if (!closeMatch) return { data: null, body: md };
  const fmRaw = rest.slice(0, closeMatch.index);
  const body = rest.slice(closeMatch.index + closeMatch[0].length);

  const lines = fmRaw.split('\n');
  const data = {};
  const iRef = { i: 0 };
  while (iRef.i < lines.length) {
    const line = lines[iRef.i];
    if (!line.trim()) { iRef.i += 1; continue; }
    const m = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/);
    if (!m) { iRef.i += 1; continue; }
    const key = m[1];
    data[key] = parseScalarOrList(m[2], lines, iRef);
  }
  return { data, body };
}
