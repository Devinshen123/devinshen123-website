"use strict";
const fs=require("fs"),path=require("path"),crypto=require("crypto"),assert=require("assert");
const root=path.resolve(__dirname,"..");
function source(name){
 const out=new Map(),month={Jan:1,Feb:2,Mar:3,Apr:4,May:5,Jun:6,Jul:7,Aug:8,Sep:9,Oct:10,Nov:11,Dec:12};
 for(const line of fs.readFileSync(path.join(root,"data/raw",name),"utf8").trim().split(/\r?\n/)){
  const cells=line.split("|").map(x=>x.trim()),year=Number(cells[0].slice(0,4));
  assert(month[cells[0].slice(5,8)]);
  for(let i=1;i+1<cells.length;i+=2){
   if(!cells[i])continue;
   assert(/^\d{2}\/\d{2}$/.test(cells[i]));
   assert(/^\d+\.\d{3}$/.test(cells[i+1]));
   const date=year+"-"+cells[i].replace("/","-");
   const bits=cells[i+1].split(".");
   const mills=Number(bits[0])*1000+Number(bits[1]);
   assert(!out.has(date));out.set(date,mills);
  }
 }
 return out;
}
const ca=source("california_history_extracted.txt"),us=source("us_history_extracted.txt");
const lines=fs.readFileSync(path.join(root,"data/processed/weekly_prices.csv"),"utf8").trim().split(/\r?\n/);
const rows=lines.slice(1).map(line=>{const [date,c,u]=line.split(",");return{date,ca_mills:Math.round(Number(c)*1000),us_mills:Math.round(Number(u)*1000)};});
assert.equal(rows.length,313);assert.equal(ca.size,313);assert.equal(us.size,313);
rows.forEach(r=>{assert.equal(ca.get(r.date),r.ca_mills);assert.equal(us.get(r.date),r.us_mills);});
const model=require("../assets/chart.js");
const summary=JSON.parse(fs.readFileSync(path.join(root,"results/summary.json")));
function compare(active,reference){
 const s=model.summarize(active);
 assert.equal(s.count,reference.weeks);
 assert(Math.abs(s.mean-reference.mean_extra)<1e-10);
 assert(Math.abs(s.minimum-reference.min_extra)<1e-10);
 assert(Math.abs(s.maximum-reference.max_extra)<1e-10);
 assert.equal(s.minDate,reference.min_date);assert.equal(s.maxDate,reference.max_date);
}
compare(rows,summary.overall);
summary.yearly.forEach(y=>compare(model.rowsInRange(rows,y.year+"-01-01",y.year+"-12-31"),y));
assert.equal(model.summarize(model.rowsInRange(rows,"2022-09-06","2022-09-06")),null);
const js=fs.readFileSync(path.join(root,"assets/plotly-basic-3.0.1.min.js"));
const gitSha=crypto.createHash("sha1").update(Buffer.from("blob "+js.length+"\0")).update(js).digest("hex");
const provenance=JSON.parse(fs.readFileSync(path.join(root,"assets/plotly-source.json")));
assert.equal(gitSha,provenance.git_blob_sha,"Vendored Plotly differs from its retrieved Git blob");
const article=fs.readFileSync(path.join(root,"index.qmd"),"utf8");
assert(!/\brubric\b|\bChatGPT\b|\bassistant\b|\bAI\b/i.test(article));
assert(article.includes('author: "Defang Shen"'));
assert(article.includes("draft: false"));
assert.equal((article.match(/<iframe/g)||[]).length,1);
const build=JSON.parse(fs.readFileSync(path.join(root,"results/build.json")));
assert(build.article_words_including_headings_and_caption>=600&&build.article_words_including_headings_and_caption<=800);
const record={status:"passed",source_rows_per_series:313,comparison_windows_checked:7,
 direct_source_cell_reconciliation:true,integer_browser_vs_decimal_python:true,
 empty_window_not_zero:true,plotly_git_blob_verified:gitSha,article_words:build.article_words_including_headings_and_caption};
fs.writeFileSync(path.join(root,"results/independent_checks.json"),JSON.stringify(record,null,2)+"\n");
console.log(JSON.stringify(record));
