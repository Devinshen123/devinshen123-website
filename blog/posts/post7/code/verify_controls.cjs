"use strict";
const fs=require("fs"),path=require("path"),vm=require("vm"),assert=require("assert");
const root=path.resolve(__dirname,"..");
const html=fs.readFileSync(path.join(root,"results/Blog_Post_7_Review.html"),"utf8");
const data=html.match(/<script id="gas-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const elements=new Map(),downloads=[],blobs=new Map(); const FakeURL={createObjectURL:b=>{const key="blob:test-"+blobs.size;blobs.set(key,b);return key;},revokeObjectURL:()=>{}};
class Element{
 constructor(id){this.id=id;this.value="";this.textContent="";this.children=[];this.events={};this.dataset={};this.clientWidth=900;this.hidden=true;this.disabled=false;}
 addEventListener(name,fn){(this.events[name]||(this.events[name]=[])).push(fn);}
 dispatchEvent(event){event.target=this;(this.events[event.type]||[]).forEach(fn=>fn(event));}
 click(){if(this.id==="a")downloads.push({url:this.href,name:this.download});this.dispatchEvent({type:"click"});}
 replaceChildren(){this.children=[];this.value="";}
 appendChild(child){this.children.push(child);if(!this.value)this.value=child.value;}
 on(name,fn){this.addEventListener(name,fn);}
}
for(const id of ["gas-explorer","gas-data","gas-chart","week-detail","week-values","stat-mean","stat-low","stat-high","date-low","date-high","window-label","date-start","date-end","export-csv","year-select","view-select","apply-dates","reset-window","input-message","chart-error"])elements.set(id,new Element(id));
elements.get("gas-data").textContent=data;
const document={readyState:"complete",getElementById:id=>elements.get(id),createElement:id=>new Element(id)};
const window={document};
const Plotly={react:async(el,traces,layout)=>{el.data=traces;el.layout=layout;},version:"controlled stub (not renderer)"};
class Event{constructor(type){this.type=type;}}
const context=vm.createContext({window,document,Plotly,Intl,Date,Event,console,Blob,URL:FakeURL,setTimeout:fn=>fn(),module:undefined});
vm.runInContext(fs.readFileSync(path.join(root,"assets/chart.js"),"utf8"),context);
const el=id=>elements.get(id),change=(id,value)=>{el(id).value=value;el(id).dispatchEvent(new Event("change"));};
const idle=()=>window.gasRenderComplete;
const checks=[];
const ok=(name,result)=>{assert(result,name);checks.push({name,passed:true});};
(async()=>{
 await idle();ok("initial_313",window.gasApp.summary().count===313);
 const s=JSON.parse(fs.readFileSync(path.join(root,"results/summary.json"),"utf8"));
 for(const y of s.yearly){
  change("year-select",String(y.year));await idle();
  const a=window.gasApp.summary();
  ok("year_"+y.year,a.count===y.weeks&&Math.abs(a.mean-y.mean_extra)<1e-9);
 }
 change("view-select","prices");await idle();ok("price_view_two_series",el("gas-chart").data.length===2);
 el("date-start").value="2022-09-01";el("date-end").value="2022-10-31";el("apply-dates").click();await idle();
 ok("custom_nine_weeks",window.gasApp.summary().count===9);
 el("gas-chart").dispatchEvent({type:"plotly_relayout","xaxis.range":["2022-10-01","2022-10-31"]});
 // Plotly passes its event object directly, unlike a DOM Event.
 el("gas-chart").events.plotly_relayout[0]({"xaxis.range":["2022-10-01","2022-10-31"]});
 ok("native_range_event_five_weeks",window.gasApp.summary().count===5);
 el("date-start").value="2022-09-06";el("date-end").value="2022-09-06";el("apply-dates").click();await idle();
 ok("empty_window_em_dash",window.gasApp.summary()===null&&el("stat-mean").textContent==="—"&&el("export-csv").disabled);
 el("date-start").value="2023-01-01";el("date-end").value="2022-01-01";el("apply-dates").click();
 ok("invalid_dates_do_not_change_state",el("input-message").textContent.length>0&&window.gasApp.summary()===null);
 el("reset-window").click();await idle();ok("reset",window.gasApp.summary().count===313&&el("gas-chart").data.length===1);
 change("week-detail","2022-10-03");ok("weekly_detail_exact_values",el("week-values").textContent.includes("$6.213")&&el("week-values").textContent.includes("$36.47"));
 change("year-select","2025");await idle();el("export-csv").click();
 ok("export_triggered",downloads.length===1&&downloads[0].name.includes("2025-01-01")); const exported=(await blobs.get(downloads[0].url).text()).trim().split(/\r?\n/); ok("exported_csv_has_52_selected_weeks",exported.length===53&&exported[1]==="2025-01-06,4.154,3.047,1.107,16.605");
 // Verify the same CSV content through the browser callback's generated Blob URL.
 // URL remains accessible here because revokeObjectURL is deferred in the real browser.
 const template=el("gas-chart").data[0].hovertemplate;
 ok("hover_template_contains_prices_gap_extra",template.includes("California")&&template.includes("U.S.")&&template.includes("15 gallons"));
 const result={status:"passed",scope:"Actual chart.js event handlers exercised with a controlled DOM and Plotly API stub. No SVG rendering, native pointer hover or visual-layout claim.",checks};
 fs.writeFileSync(path.join(root,"results/control_checks.json"),JSON.stringify(result,null,2)+"\n");
 console.log(JSON.stringify(result));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
