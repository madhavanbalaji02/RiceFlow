import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pct,fmt,statusTone,retained,selected,validateBundle,csv,sourceLink} from '../logic.mjs';

test('unavailable genomic measurements never become zero',()=>{assert.equal(pct(null),'—');assert.equal(fmt(undefined),'—');assert.equal(pct(0),'0.0%');assert.equal(retained({tracks:{vcf:{status:'BLOCKED'}}},'vcf'),null);assert.equal(retained({tracks:{vcf:{final_sites:[]}}},'vcf'),0);});
test('incomplete and unverified evidence never gets a successful badge',()=>{for(const s of ['BLOCKED','INCOMPLETE','UNVERIFIED',undefined])assert.notEqual(statusTone(s),'good');assert.equal(statusTone('FAILED'),'bad');assert.equal(statusTone('SUCCESS'),'good');});
test('actual snapshot preserves cohorts, GQ40 decisions and historical failure',()=>{const data=validateBundle(JSON.parse(readFileSync(new URL('../data.json',import.meta.url))));const [real,gq]=data.runs;assert.equal(selected(real,'cohort'),969);assert.equal(retained(real,'cohort'),824);assert.equal(real.variants.length,7);assert.equal(gq.variants.filter(v=>v.retained).length,6);assert.equal(gq.variants.find(v=>v.position===1001391).gq,34);assert.equal(data.runs.find(r=>r.name==='Historical · incomplete').status,'INCOMPLETE');assert.equal(data.runs.find(r=>r.name==='Recovery · injected failure').status,'FAILED');});
test('import rejects unrelated and malformed inputs',()=>{assert.throws(()=>validateBundle({runs:[]}));assert.throws(()=>validateBundle({schema_version:1,runs:[{id:'x',name:'x',tracks:{}}]}));const data=JSON.parse(readFileSync(new URL('../data.json',import.meta.url)));data.runs.push(data.runs[0]);assert.throws(()=>validateBundle(data));});
test('exported CSV neutralizes formula injection and quotes content',()=>{assert.equal(csv([{id:'=1+1',note:'"quoted"'}],['id','note']),'"id","note"\r\n"\'=1+1","""quoted"""');});
test('artifact navigation remains on the source host',()=>{const url=new URL(sourceLink('javascript:alert(1)','main'));assert.equal(url.origin,'https://github.com');assert.ok(url.pathname.includes('javascript%3A'));});

test('local imports reject executable or unrelated artifact URLs',()=>{const data=JSON.parse(readFileSync(new URL('../data.json',import.meta.url)));data.runs[0].files[0].url='javascript:alert(1)';assert.throws(()=>validateBundle(data));});
test('CSV formula protection includes leading whitespace',()=>{assert.match(csv([{id:' \t=1+1'}],['id']),/"' \t=1\+1"/);});
