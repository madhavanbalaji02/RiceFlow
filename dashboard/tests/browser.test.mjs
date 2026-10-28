import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {chromium} from 'playwright';

const base=process.env.DASHBOARD_URL||'http://127.0.0.1:8765/';
const output=resolve(process.env.DASHBOARD_QA_DIR||'.tools/dashboard-qa');
await mkdir(output,{recursive:true});
const snapshot=JSON.parse(await readFile(new URL('../data.json',import.meta.url),'utf8'));
const browser=await chromium.launch({headless:true,...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}:{})});
const checks=[];
try {
 for(const [device,width,height] of [['desktop',1440,1000],['mobile',390,844]]) {
  const context=await browser.newContext({viewport:{width,height},acceptDownloads:true});
  const page=await context.newPage(),errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.method());});
  async function screenshot(name){if(device==='mobile')await page.waitForFunction(()=>document.getElementById('sidebar').getBoundingClientRect().right<=1);await page.screenshot({path:resolve(output,`${device}-${name}.png`),fullPage:true,animations:'disabled'});}
  async function nav(label){const menu=page.getByRole('button',{name:'Toggle navigation'});if(await menu.isVisible()&&!await page.locator('#sidebar').evaluate(e=>e.classList.contains('open')))await menu.click();await page.locator('#navigation').getByRole('link',{name:label}).click();await page.waitForFunction(value=>document.getElementById('breadcrumb').textContent===value,label);assert.equal(await page.locator('#breadcrumb').textContent(),label);await page.locator('#main h1').waitFor();const size=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert.ok(size.scroll<=size.width+1,`${device}/${label} overflows viewport: ${JSON.stringify(size)}`);}
  async function download(selector,name){const promised=page.waitForEvent('download');await page.locator(selector).click();const file=await promised;const path=resolve(output,`${device}-${name}`);await file.saveAs(path);return readFile(path,'utf8');}
  await page.goto(base);await page.locator('.metrics-grid').waitFor();
  assert.match(await page.locator('#main').innerText(),/824/);await screenshot('overview');
  await page.getByLabel('Selected recorded run').selectOption(snapshot.runs[1].id);
  assert.equal((await page.locator('.metric').filter({has:page.getByText('VCF SNPs retained',{exact:true})}).locator('.metric-value').innerText()).trim(),'6');
  checks.push(`${device}: run selection`);
  await nav('Cohort samples');await page.getByLabel('Search cohort samples').fill('B007');
  assert.equal(await page.locator('#main tbody tr').count(),1);assert.match(await page.locator('#main tbody').innerText(),/B007/);
  const samples=await download('[data-action="export-samples"]','samples.csv');assert.match(samples,/B007/);assert.equal(samples.trim().split('\n').length,2);
  await page.locator('tr[data-sample]').first().click();assert.match(await page.locator('#detail-dialog').innerText(),/969/);assert.match(await page.locator('#detail-dialog').innerText(),/824/);await page.locator('#close-dialog').click();await screenshot('samples');
  checks.push(`${device}: sample search, denominators and CSV`);
  await nav('Variant QC');await page.getByLabel('Filter variant decisions').selectOption('excluded');
  assert.equal(await page.locator('#main tbody tr').count(),1);assert.match(await page.locator('#main tbody').innerText(),/1001391/);assert.match(await page.locator('#main tbody').innerText(),/34/);
  const variants=await download('[data-action="export-variants"]','variants.csv');assert.match(variants,/1001391/);assert.match(variants,/LowQual/);
  await page.locator('[data-variant]').first().click();assert.match(await page.locator('#detail-dialog').innerText(),/"retained": false/);await page.locator('#close-dialog').click();
  await page.getByLabel('Filter variant decisions').selectOption('retained');assert.equal(await page.locator('#main tbody tr').count(),6);await screenshot('variants');
  checks.push(`${device}: variant filters, original quality and CSV`);
  await nav('Compare policies');await page.getByLabel('First run to compare').selectOption(snapshot.runs[0].id);await page.getByLabel('Second run to compare').selectOption(snapshot.runs[1].id);
  assert.match(await page.locator('#main').innerText(),/VCF SNPs retained/);assert.match(await page.locator('#main').innerText(),/40/);await screenshot('comparison');checks.push(`${device}: recorded policy comparison`);
  await nav('Provenance');const links=await page.locator('.file-item').evaluateAll(es=>es.map(e=>e.href));assert.ok(links.length>=5);for(const value of links){const url=new URL(value);assert.equal(url.origin,'https://github.com');assert.ok(url.pathname.startsWith('/madhavanbalaji02/RiceFlow/blob/'));}
  const run=JSON.parse(await download('[data-action="export-run"]','run.json'));assert.equal(run.status,'SUCCESS');assert.equal(run.tracks.vcf.final_sites.length,6);await screenshot('provenance');checks.push(`${device}: provenance and run JSON export`);
  await nav('Run explorer');await page.getByLabel('Filter run status').selectOption('INCOMPLETE');assert.equal(await page.locator('#main tbody tr').count(),1);assert.match(await page.locator('#main tbody').innerText(),/Historical/);
  await page.getByLabel('Filter run status').selectOption('FAILED');assert.equal(await page.locator('#main tbody tr').count(),1);assert.match(await page.locator('#main tbody').innerText(),/injected failure/);
  await page.getByLabel('Filter run status').selectOption('all');await page.getByLabel('Search recorded runs').fill('resumed');assert.equal(await page.locator('#main tbody tr').count(),1);await page.getByLabel('Search recorded runs').fill('');await screenshot('runs');
  const bundle=JSON.parse(await download('[data-action="export-bundle"]','snapshot.json'));assert.equal(bundle.runs.length,7);assert.ok(bundle.runs.some(r=>r.status==='FAILED'));assert.ok(bundle.runs.some(r=>r.status==='INCOMPLETE'));
  const [chooser]=await Promise.all([page.waitForEvent('filechooser'),page.locator('[data-action="import"]').first().click()]);await chooser.setFiles({name:'snapshot.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(bundle))});
  await page.waitForFunction(()=>document.getElementById('toast').textContent.includes('Snapshot opened locally'));await nav('Provenance');assert.match(await page.locator('#main').innerText(),/claims are not re-certified/);await screenshot('imported');checks.push(`${device}: historical status filters, snapshot export and local import`);
  await nav('Cloud execution');assert.match(await page.locator('#main').innerText(),/AWS Batch/);assert.match(await page.locator('#main').innerText(),/Not live monitoring/);assert.match(await page.locator('#main').innerText(),/historical/);await screenshot('cloud');checks.push(`${device}: historical AWS labels`);
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);checks.push(`${device}: no browser errors, no write requests, responsive navigation`);
  await context.close();
 }
 await writeFile(resolve(output,'results.json'),JSON.stringify({status:'PASS',url:base,checks},null,2)+'\n');console.log(JSON.stringify({status:'PASS',checks:checks.length,url:base}));
}finally{await browser.close();}
