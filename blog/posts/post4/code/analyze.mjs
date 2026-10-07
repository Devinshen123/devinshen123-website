// Node 18+; no packages. Run from blog/posts/post4: node code/analyze.mjs
// Add --refresh to download current FRED CSVs before analysis.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const postRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const resultFile=name=>path.join(postRoot,'results',name);
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
export async function runAnalysis({refresh=false, runtime='Node.js'}={}) {
const ids=['MSPUS','MORTGAGE30US','CPIAUCSL'];
const raw=path.join(postRoot,'data/raw');
fs.mkdirSync(path.join(postRoot,'results'),{recursive:true});
if(refresh) {
  const retrieved=new Date().toISOString();
  const downloads=[];
  for(const id of ids) {
    const url=`https://fred.stlouisfed.org/graph/fredgraph.csv?id=${id}&cosd=2021-01-01&coed=2024-12-31`;
    const response=await fetch(url);
    if(!response.ok) throw new Error(`${id}: HTTP ${response.status}`);
    const bytes=await response.text();
    assert(bytes.includes(id),`${id}: expected CSV header`);
    downloads.push({id,url,bytes});
  }
  // Download all successfully before replacing any snapshots.
  for(const {id,bytes} of downloads) fs.writeFileSync(`${raw}/${id}.csv`,bytes);
  fs.writeFileSync(`${raw}/provenance.json`,JSON.stringify({retrieved,acquisition:'Direct FRED CSV URL',urls:downloads.map(({id,url})=>({id,url}))},null,2));
}
function read(id) {
  const lines=fs.readFileSync(`${raw}/${id}.csv`,'utf8').trim().split(/\r?\n/);
  const header=lines.shift().replace(/^\uFEFF/,'').split(',');
  assert(header.length===2&&header[1]===id,`Unexpected ${id} header`);
  const rows=lines.map(l=>l.split(',')).filter(([d])=>d>='2021-01-01'&&d<='2024-12-31').map(([date,v])=>({date,value:v===''||v==='.'?NaN:Number(v)}));
  assert(rows.every(r=>Number.isFinite(r.value)&&r.value>0),`Missing or invalid ${id} values`);
  assert(new Set(rows.map(r=>r.date)).size===rows.length,`Duplicate ${id} dates`);
  return rows.sort((a,b)=>a.date.localeCompare(b.date));
}
const [prices,rates,cpi]=ids.map(read);
assert(prices.length===16&&rates.length===208&&cpi.length===48,'Incomplete input period');
const quarter=d=>d.slice(0,4)+'Q'+(Math.floor((Number(d.slice(5,7))-1)/3)+1);
const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
function aggregate(rows,expected) {
  const out=new Map();
  for(const r of rows){const q=quarter(r.date);if(!out.has(q))out.set(q,[]);out.get(q).push(r.value);}
  assert(out.size===16);
  for(const [q,a] of out) assert(expected(a.length),`Bad count in ${q}`);
  return new Map([...out].map(([q,a])=>[q,{mean:mean(a),n:a.length}]));
}
const r=aggregate(rates,n=>n>=12&&n<=14),c=aggregate(cpi,n=>n===3);
const payment=(price,annualRate)=>{const loan=.8*price,m=annualRate/1200;return loan*m/(1-Math.pow(1+m,-360));};
const baseCPI=c.get('2021Q1').mean,baseRate=r.get('2021Q1').mean,basePrice=prices[0].value;
const data=prices.map(p=>{
 const q=quarter(p.date),rate=r.get(q),index=c.get(q).mean,deflator=baseCPI/index;
 return {quarter:q,date:p.date,price:p.value,cpi:index,rate:rate.mean,rate_n:rate.n,cpi_n:3,price_real:p.value*deflator,price_index:100*p.value/basePrice,price_real_index:100*p.value*deflator/basePrice,payment:payment(p.value,rate.mean),payment_real:payment(p.value,rate.mean)*deflator,payment_constant_rate_real:payment(p.value,baseRate)*deflator};
});
assert(data.every(d=>Object.values(d).filter(v=>typeof v==='number').every(Number.isFinite)));
assert(Math.abs(data[0].payment_real-data[0].payment_constant_rate_real)<1e-8);
for(const d of data) assert(Math.abs(d.payment_real/d.payment_constant_rate_real-payment(1,d.rate)/payment(1,baseRate))<1e-10);
const fields=Object.keys(data[0]);
fs.writeFileSync(resultFile('quarterly.csv'),fields.join(',')+'\n'+data.map(d=>fields.map(k=>d[k]).join(',')).join('\n')+'\n');
const hashes=Object.fromEntries(ids.map(id=>[id,crypto.createHash('sha256').update(fs.readFileSync(`${raw}/${id}.csv`)).digest('hex')]));
fs.writeFileSync(resultFile('audit.json'),JSON.stringify({node:runtime,period:'2021Q1-2024Q4',observations:{MSPUS:16,MORTGAGE30US:208,CPIAUCSL:48},hashes,checks:['positive finite values','unique dates','16 complete quarters','3 CPI months per quarter','12-14 mortgage observations per quarter','baseline payment identity','constant-rate comparison identity'],baseRate,baseCPI},null,2));
const esc=t=>String(t).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const colors=['#216B6B','#B15D2A'];
function chart({title,subtitle,series,ymin,ymax,step,label,unit,source}) {
 const W=960,H=560,L=95,R=140,T=100,B=90,pw=W-L-R,ph=H-T-B;
 const x=i=>L+pw*i/15,y=v=>T+ph*(ymax-v)/(ymax-ymin);
 let svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}"><rect width="960" height="560" fill="white"/><style>text{font-family:Arial,sans-serif;fill:#23333e}.tick{font-size:15px;fill:#596873}.title{font-size:26px;font-weight:700}.sub{font-size:17px}.source{font-size:13px;fill:#596873}</style><text x="30" y="37" class="title">${esc(title)}</text><text x="30" y="66" class="sub">${esc(subtitle)}</text><text x="${L}" y="${T-12}" class="tick">${esc(unit)}</text>`;
 for(let v=ymin;v<=ymax;v+=step){svg+=`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" stroke="#e3e8eb"/><text x="${L-12}" y="${y(v)+5}" text-anchor="end" class="tick">${label(v)}</text>`;}
 for(const i of [0,4,8,12,15])svg+=`<text x="${x(i)}" y="${H-B+27}" text-anchor="middle" class="tick">${data[i].quarter.replace('Q',' Q')}</text>`;
 for(let j=0;j<series.length;j++){const s=series[j],values=data.map(d=>d[s.key]);const color=colors[j];svg+=`<polyline points="${values.map((v,i)=>`${x(i)},${y(v)}`).join(' ')}" fill="none" stroke="${color}" stroke-width="3.5" ${j?'stroke-dasharray="8 5"':''}/>`;for(let i=0;i<16;i++)svg+=`<circle cx="${x(i)}" cy="${y(values[i])}" r="3.5" fill="${color}"><title>${data[i].quarter}: ${label(values[i])}</title></circle>`;const yy=y(values[15]);svg+=`<text x="${W-R+12}" y="${yy-7}" style="font-size:15px;fill:${color}">${esc(s.end)}</text><text x="${W-R+12}" y="${yy+14}" style="font-size:18px;font-weight:700;fill:${color}">${label(values[15])}</text>`;}
 svg+=`<text x="30" y="${H-25}" class="source">${esc(source)}</text></svg>`;return svg;
}
const charts=[
 {file:'prices.svg',title:'Prices cooled after 2022',subtitle:'U.S. median new-home sale price, nominal and adjusted for CPI',unit:'Index: 2021 Q1 = 100',ymin:80,ymax:140,step:10,label:v=>v.toFixed(0),series:[{key:'price_index',end:'Nominal'},{key:'price_real_index',end:'CPI-adjusted'}],source:'Source: Census/HUD MSPUS and BLS CPIAUCSL via FRED. Quarterly; real values use 2021 Q1 CPI.'},
 {file:'rates.svg',title:'Borrowing costs moved in the opposite direction',subtitle:'Quarterly mean of weekly 30-year fixed mortgage rates',unit:'Percent',ymin:0,ymax:8,step:2,label:v=>v.toFixed(2)+'%',series:[{key:'rate',end:'Mortgage rate'}],source:'Source: Freddie Mac PMMS (MORTGAGE30US). Methodology changed November 17, 2022.'},
 {file:'payments.svg',title:'Lower prices did not restore the earlier monthly payment',subtitle:'Illustrative new-home loan: 20% down, 30 years, principal and interest only',unit:'Dollars per month (2021 Q1 purchasing power)',ymin:0,ymax:2600,step:500,label:v=>'$'+Math.round(v).toLocaleString('en-US'),series:[{key:'payment_real',end:'Observed rates'},{key:'payment_constant_rate_real',end:'2021 Q1 rate'}],source:'Sources: MSPUS, CPIAUCSL and Freddie Mac PMMS. Calculations use quarterly mean rates and CPI.'}
];
for(const ch of charts)fs.writeFileSync(resultFile(ch.file),chart(ch));
const last=data.at(-1),peak=data.reduce((a,b)=>a.price>b.price?a:b),at=q=>data.find(d=>d.quarter===q),base=data[0];
const changes={nominalFromPeak:100*(last.price/peak.price-1),realFromPeak:100*(last.price_real/peak.price_real-1),paymentFromBase:100*(last.payment_real/base.payment_real-1),ratePremium:100*(last.payment_real/last.payment_constant_rate_real-1)};
fs.writeFileSync(resultFile('summary.json'),JSON.stringify({base,peak,last,changes},null,2));
return {base,peak,last,changes};
}

if (typeof process !== 'undefined' && process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  runAnalysis({refresh:process.argv.includes('--refresh'),runtime:process.version})
    .then(result=>console.log(JSON.stringify(result,null,2)))
    .catch(error=>{console.error(error);process.exitCode=1;});
}
