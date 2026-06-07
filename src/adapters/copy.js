import { readdirSync, mkdirSync, copyFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const SKIP_DIRS = new Set(['node_modules', '.venv', '__pycache__', '.git', 'tests']);

// Recursively copy a skill's source folder, skipping regenerable/dev dirs.
export function copyTree(src, dest) {
  mkdirSync(dest, { recursive: true });
  for (const entry of readdirSync(src, { withFileTypes: true })) {
    if (entry.isDirectory() && SKIP_DIRS.has(entry.name)) continue;
    if (entry.name === '.DS_Store') continue;
    const s = join(src, entry.name);
    const d = join(dest, entry.name);
    if (entry.isDirectory()) copyTree(s, d);
    else if (entry.isFile()) copyFileSync(s, d);
  }
}

export function fileCount(dir) {
  let n = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory() && SKIP_DIRS.has(entry.name)) continue;
    const p = join(dir, entry.name);
    if (entry.isDirectory()) n += fileCount(p);
    else if (statSync(p).isFile()) n += 1;
  }
  return n;
}
