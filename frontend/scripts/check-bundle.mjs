import { gzipSync } from 'node:zlib';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const assets = join(import.meta.dirname, '..', 'dist', 'assets');
const entry = readdirSync(assets)
  .filter((name) => /^index-.*\.js$/.test(name))
  .map((name) => ({ name, bytes: gzipSync(readFileSync(join(assets, name))).length }))
  .sort((a, b) => b.bytes - a.bytes)[0];

if (!entry) throw new Error('No built entry bundle was found.');
const limit = 200 * 1024;
console.log('Initial shell: ' + (entry.bytes / 1024).toFixed(1) + ' KB gzip');
if (entry.bytes > limit) {
  throw new Error('Initial shell exceeds the 200 KB gzip budget: ' + entry.name);
}
