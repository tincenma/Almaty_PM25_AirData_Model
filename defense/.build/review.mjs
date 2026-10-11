import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const {FileBlob,PresentationFile}=await import(pathToFileURL('C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs').href);
const root='C:/Users/user/Рабочий стол/AI Essentials Theory and Applications/Research/defense';
const presentation=await PresentationFile.importPptx(await FileBlob.load(`${root}/output/Almaty_PM25_Defense.pptx`));
for(const [i,slide] of presentation.slides.items.entries()) {
 const png=await presentation.export({slide,format:'png',scale:1});
 await fs.writeFile(`${root}/.build/final-${String(i+1).padStart(2,'0')}.png`,new Uint8Array(await png.arrayBuffer()));
}
console.log('Rendered final presentation: '+presentation.slides.items.length+' slides');
