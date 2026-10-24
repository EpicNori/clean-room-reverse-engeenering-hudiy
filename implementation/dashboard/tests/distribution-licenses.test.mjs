import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {packages} from '../scripts/licenses.mjs';

test('production browser assets retain the installed runtime/font license texts and versions',async()=>{
  const source=await readFile(new URL('../public/THIRD_PARTY_NOTICES.txt',import.meta.url),'utf8');
  const built=await readFile(new URL('../dist/client/THIRD_PARTY_NOTICES.txt',import.meta.url),'utf8');
  assert.equal(built,source);
  for(const [name,file] of packages){
    const root=new URL(`../node_modules/${name}/`,import.meta.url);
    const metadata=JSON.parse(await readFile(new URL('package.json',root),'utf8'));
    const license=(await readFile(new URL(file,root),'utf8')).trim();
    assert.ok(built.includes(`${name} ${metadata.version}`),`${name} version missing`);
    assert.ok(built.includes(license),`${name} complete license missing`);
  }
  assert.ok(built.includes('GPL-3.0-or-later'),'Native component must not be described as MIT-only');
});
