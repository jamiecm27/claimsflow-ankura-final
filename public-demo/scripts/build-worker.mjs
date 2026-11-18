import { readdir, readFile, mkdir, writeFile, copyFile } from 'node:fs/promises';
import { extname, resolve } from 'node:path';
import { build } from 'esbuild';
import { tmpdir } from 'node:os';
import { mkdtemp, rm } from 'node:fs/promises';

const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.pdf': 'application/pdf' };
const root = resolve('dist');
const entries = await readdir(root, { recursive: true, withFileTypes: true });
const assets = {};
for (const entry of entries) {
  if (!entry.isFile()) continue;
  const file = resolve(entry.parentPath, entry.name);
  const type = mime[extname(file)];
  if (type) assets[file.slice(root.length)] = { mime: type, data: (await readFile(file)).toString('base64') };
}
const temp = await mkdtemp(resolve(tmpdir(), 'claimsflow-worker-'));
try {
  const claims = await readFile('src/claims.json', 'utf8');
  const source = resolve(temp, 'assets.mjs');
  await writeFile(source, `export const assets = ${JSON.stringify(assets)}; export const claims = ${claims};`);
  await build({
    entryPoints: ['worker/index.mjs'], outfile: 'dist/server/index.js', bundle: true,
    platform: 'browser', format: 'esm', target: 'es2022', minify: true,
    plugins: [{ name: 'embedded-claimsflow-assets', setup(builder) {
      builder.onResolve({ filter: /^\.\/assets\.mjs$/ }, () => ({ path: source }));
    } }],
  });
  await mkdir('dist/.openai', { recursive: true });
  await copyFile('.openai/hosting.json', 'dist/.openai/hosting.json');
} finally {
  await rm(temp, { recursive: true, force: true });
}
