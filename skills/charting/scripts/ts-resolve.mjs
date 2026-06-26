/**
 * Module-resolution hook so plain `node` can run the TypeScript sources.
 *
 * The src/ files import each other with `.js` specifiers (the TypeScript ESM
 * convention) but only `.ts` files exist on disk. Node's built-in type stripping
 * (default-on since v22.18) handles the *types*, but it does NOT rewrite import
 * specifiers — so `import '../src/index.js'` throws ERR_MODULE_NOT_FOUND. This hook
 * fills that one gap: when a relative `.js` import doesn't exist but its `.ts`
 * sibling does, resolve to the `.ts`. Pair it with `node --import` / `register()`
 * and the render path needs no bun or tsx — only `node`, which every runtime has.
 */
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export function resolve(specifier, context, nextResolve) {
  if ((specifier.startsWith('./') || specifier.startsWith('../')) && specifier.endsWith('.js')) {
    try {
      const asIs = new URL(specifier, context.parentURL);
      if (!existsSync(fileURLToPath(asIs))) {
        const tsSpecifier = specifier.slice(0, -3) + '.ts';
        if (existsSync(fileURLToPath(new URL(tsSpecifier, context.parentURL)))) {
          return nextResolve(tsSpecifier, context);
        }
      }
    } catch {
      /* fall through to Node's default resolution */
    }
  }
  return nextResolve(specifier, context);
}
