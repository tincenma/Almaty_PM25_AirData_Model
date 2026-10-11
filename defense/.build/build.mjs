import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const ROOT = 'C:/Users/user/Рабочий стол/AI Essentials Theory and Applications/Research';
const RUNTIME = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const SKILL = 'C:/Users/user/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
process.env.RUNTIME_NODE_MODULES = `${RUNTIME}/node/node_modules`;
const {Presentation, PresentationFile} = await import(pathToFileURL(`${RUNTIME}/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs`).href);
const {finalizePresentation, applyPresentationChartFont} = await import(pathToFileURL(`${SKILL}/container_tools/artifact_tool_utils.mjs`).href);
const {requireRuntimeModule} = await import(pathToFileURL(`${SKILL}/container_tools/runtime_helpers.mjs`).href);
const {createCanvas, loadImage} = await requireRuntimeModule('@napi-rs/canvas');
const BUILD = `${ROOT}/defense/.build`;
const OUT = `${ROOT}/defense/output`;
await fs.mkdir(BUILD, {recursive:true});
await fs.mkdir(OUT, {recursive:true});
const deck = Presentation.create({slideSize:{width:1280,height:720}});
const C = {ink:'#152B29', muted:'#546663', green:'#216657', gold:'#AF6B39', paper:'#FAFBF8', gray:'#BBC6C1'};
const font = 'Arial';
function text(s,value,x,y,w,h,size=28,bold=false,color=C.ink) {
 const box=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 box.text=value;
 box.text.style={fontSize:size,typeface:font,color,bold,autoFit:'none',insets:0,wrap:'square',verticalAlignment:'top'};
 return box;
}
function slide(title,note,source='',backup=false) {
 const s=deck.slides.add(); s.background.fill=C.paper;
 text(s,title,64,44,1140,105,44,true);
 text(s,String(deck.slides.items.length).padStart(2,'0'),1170,667,48,24,18,false,C.muted);
 if(backup) text(s,'BACKUP',64,668,200,25,18,true,C.muted);
 s.speakerNotes.text=note+(source?'\n\nSources: '+source:'');
 return s;
}
function line(s,label,body,y,accent=C.green) {
 text(s,label,66,y,265,65,28,true,accent);
 text(s,body,355,y,850,88,28);
}
function table(s,values,y=190,widths=null,height=300) {
 const cols=values[0].length;
 const t=s.tables.add({rows:values.length,columns:cols,left:64,top:y,width:1150,height,values,columnWidths:widths||Array(cols).fill(1150/cols)});
 t.borders.assign({fill:'#DAE2DC',width:0.6,style:'solid'});
 t.cells.block({row:0,column:0,rowCount:values.length,columnCount:cols}).assign({textStyle:{fontSize:27,typeface:font,color:C.ink},margins:{left:14,right:14,top:10,bottom:10}});
 for(let r=0;r<values.length;r++) for(let c=0;c<cols;c++) {
  const cell=t.getCell(r,c); cell.fill=r===0?C.green:(r%2?'#FFFFFF':'#F0F4EF');
  cell.text.style={fontSize:27,typeface:font,color:r===0?'#FFFFFF':C.ink,bold:r===0};
 }
 return t;
}
function bar(s,categories,series,pos={left:64,top:176,width:830,height:400},max=12) {
 const chart=s.charts.add('bar',{position:pos,categories,series,hasLegend:true,
  barOptions:{direction:'column',grouping:'clustered',gapWidth:130},
  legend:{position:'bottom',textStyle:{fontSize:24,fill:C.ink}},
  dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.00',textStyle:{fontSize:23,fill:C.ink}},
  xAxis:{textStyle:{fontSize:25,fill:C.ink},line:{fill:C.gray,width:1}},
  yAxis:{min:0,max,majorUnit:max>15?5:2,numberFormatCode:'0',textStyle:{fontSize:22,fill:C.muted},majorGridlines:{fill:'#DFE6E0',width:0.8}},
  chartFill:C.paper,plotAreaFill:C.paper});
 applyPresentationChartFont(chart,{fontFamily:font}); return chart;
}
let s;
s=deck.slides.add(); s.background.fill=C.ink;
text(s,'PM2.5 forecasting\nin Almaty',70,150,1100,180,62,true,'#FFFFFF');
text(s,'Open station data and a reproducible forecasting application',73,355,1090,75,30,false,'#D9E5DF');
text(s,'Temirlan Ilyassov\nAAI-2605M, Astana IT University\nAI Essentials: Theory and Application',73,494,1060,130,26,false,'#FFFFFF');
s.speakerNotes.text='20 seconds. Our project predicts hourly PM2.5 concentration for individual Almaty stations one, six and 24 hours ahead. We built both an evaluation workflow and an application. The central finding is a useful six-hour improvement, alongside important failures that constrain next-day use. Explain personal contributions truthfully if asked; this deck does not assign unverified team roles.';
s=slide('Forecasting task and research question','25 seconds. PM2.5 is fine particulate matter. Our output is concentration in micrograms per cubic metre at a future station hour. We ask whether learned patterns improve on simply repeating the latest reading. The project also addresses a practical problem: public data can arrive late and contain gaps. Its scope is individual stations, so it cannot establish a citywide exposure or health alert.');
line(s,'Target','Station-level hourly PM2.5 concentration in µg/m³',185);
line(s,'Horizons','1, 6 and 24 hours after an observed origin',305);
line(s,'Question','Do history and calendar features improve on persistence?',425);
text(s,'Publication delays and missing history affect how a forecast should be used',66,575,1130,60,25,false,C.muted);
s=slide('Two separate station experiments','30 seconds. The historical US Embassy experiment uses 2020 through 2022 for training, 2023 for validation and 2024 for testing. The reporting-station experiment uses PCP 31 and a separate snapshot. Its test starts in September 2025. The stations and periods differ, so smaller errors at PCP 31 are not a direct model superiority comparison.','artifacts/experiment.json; artifacts/current/experiment.json; https://github.com/qazybekb/AirDatakz-OpenData');
table(s,[['Experiment','Station','Held-out period'],['Historical replay','US Embassy\noaq_25903','2024'],['Latest forecast','KazHydroMet PCP #31\nkgmt_27','From 26 Sep 2025\nSnapshot ends 10 Oct 2026']],182,[290,430,430],292);
text(s,'PCP #31: 17,246 observed hours out of 26,281 grid hours',66,515,1140,60,31,true,C.green);
text(s,'65.6% coverage across the training grid',66,589,1100,50,26,false,C.muted);
s=slide('Causal features and missing data','30 seconds. We preserve missing hours on an hourly grid so lag 24 means 24 elapsed hours, rather than 24 available readings. Features include the current value, nine lags, rolling means, standard deviations and observed counts. Calendar features use Almaty local time. Training fits imputation on training rows only. We never fill missing targets. Daily eligibility requires at least 18 observed hours out of 24. No weather or neighbouring-station inputs are included.','backend/app/features.py; backend/train_current.py');
line(s,'History','Current value and lags from 1 to 168 hours',182);
line(s,'Rolling context','Means, variability and counts over 6 to 168 hours',292);
line(s,'Calendar','Cyclic hour, weekday and day-of-year features',402);
text(s,'28 inputs; median imputation with missingness indicators',66,518,1120,60,30,true,C.green);
text(s,'Observed targets only; at least 18 of the latest 24 hours required',66,601,1130,50,26,false,C.muted);
s=slide('Chronological validation and independent testing','30 seconds. We use chronological partitions and purge origins when their future targets cross the boundary. At PCP 31 the validation and test boundaries are based on eligible-origin quantiles, which accommodates long gaps but changes seasonal representation. Validation chooses settings. Evaluation refits only on pre-test labels. A separate deployment refit uses all available labelled data after testing. We preserve both types of pipeline.','backend/train_current.py; artifacts/current/experiment.json');
table(s,[['Stage','PCP #31 rule'],['Training','Targets before 6 Jun 2025, 05:00 UTC'],['Validation','Origins from 6 Jun; targets before 26 Sep 2025'],['Testing','Origins from 26 Sep 2025, 06:00 UTC']],177,[275,875],310);
text(s,'Validation chooses settings; the test set measures performance',66,533,1130,55,30,true,C.green);
text(s,'Evaluation and deployment refits remain separate',66,603,1100,45,26,false,C.muted);
s=slide('Models and comparison baselines','30 seconds. Ridge gives a fast linear comparison after scaling. XGBoost can learn nonlinear feature combinations. We compare a small fixed search and minimize validation MAE. PCP 31 selects 350 trees with depth five at each horizon. Persistence repeats the origin value. Same hour yesterday refers to the target hour on the previous day. At a 24-hour horizon it is identical to persistence, so it is not a second independent next-day baseline.','backend/train_current.py; https://arxiv.org/abs/1603.02754; https://otexts.com/fpp3/simple-methods.html');
line(s,'Ridge','Linear regression with regularization and scaling',180);
line(s,'XGBoost','Two configurations; selection by validation MAE',282);
line(s,'Persistence','Repeat the latest observed concentration',384);
line(s,'Daily seasonal','Use the same target hour from the previous day',486);
text(s,'At 24 hours, persistence and the daily seasonal baseline coincide',66,602,1120,45,25,false,C.muted);
s=slide('Six-hour forecasts improve most over persistence','35 seconds. These are PCP 31 test results. At six hours XGBoost MAE is 6.33 against 9.18 for persistence, an approximately 31 percent reduction. One-hour MAE is 2.94 and next-day MAE is 7.12. We compare on identical eligible rows within each horizon. The table of uncertainty on a later slide explains why the six-hour improvement has stronger evidence than the other two.','artifacts/current/test_metrics.csv');
bar(s,['1 hour','6 hours','24 hours'],[{name:'XGBoost',values:[2.9382069587,6.3341650892,7.1210334171],fill:C.green},{name:'Persistence',values:[3.0326214372,9.1814084507,7.9825114536],fill:C.gray}]);
text(s,'31.0%',943,228,270,85,56,true,C.green);
text(s,'lower MAE\nat six hours',944,331,260,108,30);
text(s,'MAE in µg/m³. Lower is better. Test rows: 2,491 / 2,485 / 2,401',66,611,1130,44,23,false,C.muted);
s=slide('Historical results support the six-hour finding','25 seconds. The independent historical station also shows the largest relative MAE improvement at six hours, approximately 22 percent. Ridge remains competitive and has better RMSE at some horizons. A history-versus-calendar validation ablation decreases six-hour MAE from 13.97 to 11.66, but calendar features slightly worsen next-day MAE. This ablation belongs to the historical experiment.','artifacts/test_metrics.csv; artifacts/validation_feature_ablation.csv');
bar(s,['1 hour','6 hours','24 hours'],[{name:'XGBoost',values:[5.3952759973,11.0107139152,12.160606382],fill:C.green},{name:'Persistence',values:[5.4995667244,14.1460119134,13.4497979949],fill:C.gray}],{left:64,top:180,width:820,height:393},20);
text(s,'22.2%',927,231,292,75,53,true,C.green);
text(s,'lower six-hour MAE\non the 2024 test set',927,324,280,115,28);
text(s,'Calendar ablation: six-hour validation MAE 13.97 to 11.66 µg/m³',66,611,1150,45,24,false,C.muted);
s=slide('Average gains conceal important model failures','40 seconds. These rows compare the same model with persistence on specific next-day groups. On historical peaks, XGBoost loses despite its overall gain. At PCP 31, sparse weekly history gives MAE 5.17 versus 2.44, and spring gives 4.30 versus 3.05. Different rows are different subgroups and stations, not directly comparable exposure regimes. PCP 31 also underpredicts its high-concentration group with mean bias minus 20.56. We cannot attribute these errors to weather because weather is absent.','artifacts/peak_errors.csv; artifacts/current/analysis/sparse_history_errors.csv; artifacts/current/analysis/season_errors.csv; artifacts/current/analysis/peak_errors.csv');
table(s,[['24-hour subgroup','XGBoost MAE','Persistence MAE'],['US Embassy peaks, n = 360','54.62','47.98'],['PCP #31 sparse week, n = 138','5.17','2.44'],['PCP #31 spring, n = 334','4.30','3.05']],178,[580,285,285],310);
text(s,'PCP #31 peak bias: −20.56 µg/m³',66,541,1150,58,33,true,C.gold);
text(s,'Peak cutoffs use pre-test percentiles. They are statistical thresholds.',66,608,1125,42,24,false,C.muted);
s=slide('Uncertainty and limits of the test evidence','35 seconds. We pair model and baseline errors and resample seven-day blocks 2000 times. Nineteen blocks contain eligible observations. Only the six-hour interval excludes zero. These are approximate intervals for aggregate MAE improvement, not bounds around tomorrow’s concentration. There are no eligible summer examples and only three October next-day examples. We therefore cannot claim year-round or current-condition reliability.','artifacts/current/analysis/paired_block_bootstrap.csv; artifacts/current/analysis/recent_period_errors.csv; artifacts/current/analysis/season_errors.csv');
table(s,[['Horizon','MAE gain over persistence','Approximate 95% interval'],['1 hour','0.09','−0.04 to 0.24'],['6 hours','2.85','1.41 to 4.30'],['24 hours','0.86','−0.04 to 1.64']],172,[240,450,460],290);
text(s,'Summer has no eligible test examples',66,509,1120,50,30,true,C.gold);
text(s,'Recent next-day evidence contains only 3 examples',66,574,1120,48,29);
s=slide('Forecast application and timestamp transparency','30 seconds. This screenshot shows the recorded 10 October demonstration. The app uses React and TypeScript with a FastAPI backend. Refresh retrieves measurements and reruns the saved pipelines. The target date starts from the measured hour. A next-day point can therefore appear, but it is not an arbitrary future-date forecast. Daily and weekly counts show the input context. If publication delays make the input stale, the app warns users and labels expired target hours.','latest-forecast-preview.jpg; backend/app/current.py; frontend/src/App.tsx');
const canvas=createCanvas(975,510);
canvas.getContext('2d').drawImage(await loadImage(`${ROOT}/latest-forecast-preview.jpg`),260,221,975,510,0,0,975,510);
const cropped=canvas.toBuffer('image/png');
s.images.add({blob:cropped.buffer.slice(cropped.byteOffset,cropped.byteOffset+cropped.byteLength),contentType:'image/png',alt:'Recorded dashboard excerpt showing PCP 31 origin timestamp, coverage and three target hours',fit:'contain',position:{left:64,top:181,width:835,height:437}});
text(s,'React + TypeScript\nFastAPI + Python',934,197,270,115,28,true,C.green);
text(s,'Latest measured hour\nExplicit target dates\nCoverage warnings',934,341,279,170,27);
text(s,'Recorded example: 10 Oct 2026. Refresh runs inference without retraining.',66,639,1140,30,22,false,C.muted);
s=slide('Reproducibility and conclusion','30 seconds. Reproduce mode verifies the immutable dataset hash and uses the recorded station, settings and chronological boundaries. It works independently of today’s date. Update mode downloads fresh data and applies station freshness checks, saving a new experiment without automatically replacing deployed models. Our repeated run matches the saved predictions and metrics. We conclude that six-hour forecasts are useful in the held-out evidence, while peaks and sparse history require further work. Weather features, calibrated prediction intervals and fallback rules need a new evaluation period.','backend/train_current.py; backend/tests/test_training_modes.py; artifacts/reproduce/verified-run/test_metrics.csv; README.md');
line(s,'Reproduce','Frozen snapshot, checksum and recorded experiment',181);
line(s,'Update','Fresh data, coverage checks and a separate new run',290);
text(s,'Six-hour forecasts provide the strongest evidence of value',66,430,1120,91,39,true,C.green);
text(s,'Next step: evaluate weather inputs and a coverage fallback on new data',66,553,1120,80,29);
s=slide('Five-minute demonstration route','Use this slide after the six-minute talk, then switch to the app at http://127.0.0.1:8000/. Minute 0 to 1: latest station identity, origin time and 24/168-hour coverage. Minute 1 to 2: target cards, the next-day target and a past target if applicable. Minute 2 to 3: refresh, explain inference versus retraining, and export CSV. If refresh fails, explain the saved-data warning rather than claiming fresh data. Minute 3 to 4: historical replay, choose a valid 2024 origin and reveal observed outcomes. Minute 4 to 5: station directory, distinguish reporting stations from the trained station and explain reproducibility. Keep the recorded screenshot as fallback for a network outage.','README.md; frontend/src/App.tsx; backend/app/current.py',true);
table(s,[['Time','Demonstration'],['0–1 min','Station identity, origin timestamp and coverage'],['1–2 min','Forecast target dates and the next-day point'],['2–3 min','Refresh observations and export predictions'],['3–4 min','Historical replay with observed outcomes'],['4–5 min','Station directory and reproducibility explanation']],173,[250,900],406);
text(s,'Local application: http://127.0.0.1:8000/',66,612,1120,40,27,true,C.green);
s=slide('Questions to prepare for','Use during the three-minute question period. Why XGBoost? It won the fixed validation comparison; no claim against untested model families. Why no future date picker? The estimator predicts only the trained horizons after the latest observed origin, and requires real historical inputs. Why not trust the average MAE? Peaks, spring and sparse-history groups can lose to persistence. Does the model use live measurements? It uses the latest published public snapshot, with delays and missingness displayed. Contribution question: explain your actual implementation and analysis work, and disclose AI assistance according to your course policy.','MODEL_FAILURES.md; README.md',true);
line(s,'Why XGBoost?','It achieved the lowest validation MAE in the fixed search',177);
line(s,'Tomorrow’s date?','24 hours after the latest measured origin',282);
line(s,'Where does it fail?','Pollution peaks, spring and sparse weekly history',387);
line(s,'Is it continuous live data?','Public snapshots update daily and can arrive late',492);
s=slide('Sources and supporting materials','Use as a reference slide and do not read every citation aloud. Measurement attribution: AirData.kz and original providers. Methods: Chen and Guestrin 2016 and Hyndman and Athanasopoulos 2021. Empirical results come from the saved project manifests, test metrics and failure analysis, not these external papers. Supporting materials include the research paper, notebook, reproducible trainer, backend tests and application.','https://github.com/qazybekb/AirDatakz-OpenData; https://arxiv.org/abs/1603.02754; https://otexts.com/fpp3/; paper/Almaty_PM25_Research_Paper.docx',true);
text(s,'AirData.kz and original measurement providers\nOpen observations for Kazakhstan\nhttps://github.com/qazybekb/AirDatakz-OpenData',66,177,1150,125,27);
text(s,'Chen and Guestrin (2016)\nXGBoost: A Scalable Tree Boosting System',66,323,1150,92,28);
text(s,'Hyndman and Athanasopoulos (2021)\nForecasting: Principles and Practice, third edition',66,438,1150,92,28);
text(s,'Research paper, notebook, saved experiments and model failure discussion',66,575,1140,60,26,true,C.green);

await (await PresentationFile.exportPptx(deck)).save(`${BUILD}/candidate.pptx`);
for(const [i,item] of deck.slides.items.entries()) {
 const png=await deck.export({slide:item,format:'png',scale:1});
 await fs.writeFile(`${BUILD}/slide-${String(i+1).padStart(2,'0')}.png`,new Uint8Array(await png.arrayBuffer()));
}
const result=await finalizePresentation({workspaceDir:ROOT,candidatePath:`${BUILD}/candidate.pptx`,finalPath:`${OUT}/Almaty_PM25_Defense.pptx`,pythonExecutable:`${RUNTIME}/python/python.exe`,integrityValidatorPath:`${SKILL}/container_tools/inspect_presentation_package_integrity.py`,layoutValidatorPath:`${SKILL}/container_tools/inspect_presentation_layout_geometry.py`,layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...[3,5,9,10,13].flatMap(n=>['--require-native-table-slide',String(n)])],explicitTotalSlideCount:15,requiredNativeTableOwnerSlides:[3,5,9,10,13],requiredNativeChartOwnerSlides:[7,8],fontPolicy:{basis:'design',families:[font]},materializeLiteralChartWorkbooks:true,verifyArtifactToolImport:true,receiptPath:`${BUILD}/validation.json`});
console.log(JSON.stringify(result));

