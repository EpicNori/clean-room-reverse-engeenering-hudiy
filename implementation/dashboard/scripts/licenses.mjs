// Preserve the actual installed packages' complete notices in every browser build.
import {readFileSync,existsSync,mkdirSync,writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const packages=[
  ['react','LICENSE'],['react-dom','LICENSE'],['scheduler','LICENSE'],
  ['chart.js','LICENSE.md'],['@kurkle/color','LICENSE.md'],
  ['@fontsource/roboto','LICENSE'],['@material-symbols/font-600','LICENSE'],
  ['vite','LICENSE.md'],
];
const sections=['Browser bundle license notices\n\nThese notices accompany the dashboard JavaScript, Roboto font files and Material Symbols icon font. Native executable licensing is separate: implementation/native/THIRD_PARTY.md (GPL-3.0-or-later).',
  'PROJECT DASHBOARD/BACKEND\n\n'+readFileSync(path.resolve(root,'../../LICENSE'),'utf8').trim()];
for(const [name,file] of packages){
  const folder=path.join(root,'node_modules',name);
  const metadata=JSON.parse(readFileSync(path.join(folder,'package.json'),'utf8'));
  let text=readFileSync(path.join(folder,file),'utf8').trim(); // Missing notices fail the build.
  for(const notice of ['NOTICE','NOTICE.txt','NOTICE.md']){
    if(existsSync(path.join(folder,notice)))text+='\n\n'+readFileSync(path.join(folder,notice),'utf8').trim();
  }
  sections.push(`${name} ${metadata.version} (${metadata.license || 'see license below'})\n\n${text}`);
}
mkdirSync(path.join(root,'public'),{recursive:true});
writeFileSync(path.join(root,'public/THIRD_PARTY_NOTICES.txt'),sections.join('\n\n============================================================\n\n')+'\n');
console.log(`Preserved complete browser notices for ${packages.length} runtime/font/helper packages.`);
