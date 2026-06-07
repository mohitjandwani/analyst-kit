import { readFileSync, writeFileSync, existsSync, chmodSync } from 'node:fs';
import { createInterface } from 'node:readline';

export function parseEnvFile(file) {
  const out = {};
  if (!file || !existsSync(file)) return out;
  for (const line of readFileSync(file, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)\s*$/);
    if (m) out[m[1]] = m[2];
  }
  return out;
}

// Union of env vars required across a set of skills.
export function requiredEnv(skills) {
  const set = new Set();
  for (const s of skills) for (const v of s.env || []) set.add(v);
  return [...set];
}

function ask(question) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(question, (a) => { rl.close(); resolve(a); }));
}

// Resolve required vars against the environment + an .env file. When interactive
// and a var is missing, prompt for it; persist answers back to `envFile`.
// Returns { resolved: {VAR: value}, missing: [VAR], wrote: bool }.
export async function resolveEnv(vars, { envFile, interactive, persist = true } = {}) {
  const fileVals = parseEnvFile(envFile);
  const resolved = {};
  const missing = [];
  const collected = {};

  for (const v of vars) {
    const val = process.env[v] || fileVals[v];
    if (val) { resolved[v] = val; continue; }
    if (interactive) {
      const answer = (await ask(`  set ${v} (leave blank to skip): `)).trim();
      if (answer) { resolved[v] = answer; collected[v] = answer; continue; }
    }
    missing.push(v);
  }

  let wrote = false;
  if (persist && envFile && Object.keys(collected).length) {
    const merged = { ...fileVals, ...collected };
    const body = Object.entries(merged).map(([k, val]) => `${k}=${val}`).join('\n') + '\n';
    writeFileSync(envFile, body);
    try { chmodSync(envFile, 0o600); } catch { /* best effort */ }
    wrote = true;
  }
  return { resolved, missing, wrote };
}
