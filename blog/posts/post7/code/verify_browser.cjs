"use strict";
const fs=require("fs"),path=require("path"),http=require("http"),{spawn}=require("child_process"),assert=require("assert");
const root=path.resolve(__dirname,".."),qa=path.join(root,"qa");
fs.mkdirSync(qa,{recursive:true});
const expected=JSON.parse(fs.readFileSync(path.join(root,"results/summary.json"),"utf8"));
const checks=[],exceptions=[],requests=[];
const delay=ms=>new Promise(r=>setTimeout(r,ms));
let chrome,server,ws;
const record={status:"running",checks,exceptions};
const targetUrl=process.env.POST7_PAGE_URL;
function check(name,value,details){assert(value,name+": "+JSON.stringify(details));checks.push({name,passed:true,details});}
class CDP{
 constructor(socket){this.socket=socket;this.id=0;this.pending=new Map();this.listeners=[];
  socket.addEventListener("message",event=>{const message=JSON.parse(event.data);
   if(message.id){const p=this.pending.get(message.id);if(!p)return;clearTimeout(p.timer);this.pending.delete(message.id);message.error?p.reject(Error(JSON.stringify(message.error))):p.resolve(message.result);}
   else this.listeners.forEach(f=>f(message));
  });
 }
 send(method,params={},sessionId){
  const id=++this.id;return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{this.pending.delete(id);reject(Error("CDP timeout "+method));},25000);
   this.pending.set(id,{resolve,reject,timer});this.socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
  });
 }
}
(async()=>{
 try{
  server=http.createServer((req,res)=>{
   const name=decodeURIComponent(new URL(req.url,"http://localhost").pathname);
   const isSiteAsset=/^\/(blog\/|site_libs\/|images\/|styles\.css)/.test(name);
   const servedRoot=path.resolve(isSiteAsset&&process.env.POST7_WEB_ROOT?process.env.POST7_WEB_ROOT:root);
   const file=path.resolve(servedRoot,"."+name);
   (record.local_requests||(record.local_requests=[])).push({name,file,exists:fs.existsSync(file)});
   if(!file.startsWith(servedRoot+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);return res.end("Not found");}
   const mime={".html":"text/html; charset=utf-8",".csv":"text/csv",".css":"text/css",".js":"text/javascript",".json":"application/json",".png":"image/png",".svg":"image/svg+xml",".woff":"font/woff",".woff2":"font/woff2"};
   const type=mime[path.extname(file)]||"application/octet-stream";
   res.writeHead(200,{"Content-Type":type});fs.createReadStream(file).pipe(res);
  });
  await new Promise(r=>server.listen(0,"127.0.0.1",r));
  const origin="http://127.0.0.1:"+server.address().port;
  const response=await fetch(origin+"/results/Blog_Post_7_Review.html");
  const served=await response.text();
  check("offline_review_served",response.ok&&served.includes('id="gas-explorer"'),{http:response.status,length:served.length});
  const executable=process.env.CHROME_PATH||(process.platform==="win32"?"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe":"/usr/bin/google-chrome");
  assert(fs.existsSync(executable),"An existing Chrome installation is required");
  chrome=spawn(executable,["--headless=new","--disable-gpu","--disable-crashpad-for-testing","--disable-crash-reporter","--disable-breakpad","--noerrdialogs","--no-first-run","--no-default-browser-check",
   "--disable-background-networking","--disable-component-update","--disable-sync","--disable-default-apps",
   "--remote-debugging-port=0","--user-data-dir="+path.join(qa,"chrome-profile"),"about:blank"],
   {windowsHide:true,stdio:["ignore","ignore","pipe"]});
  let stderr="";
  const endpoint=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error("Chrome did not expose its testing endpoint: "+stderr.slice(-1500))),20000);
   chrome.on("error",e=>{clearTimeout(timer);reject(e);});
   chrome.stderr.on("data",chunk=>{stderr+=chunk.toString();const match=stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(match){clearTimeout(timer);resolve(match[1]);}});
   chrome.on("exit",code=>{if(!stderr.includes("DevTools listening")){clearTimeout(timer);reject(Error("Chrome exited "+code+": "+stderr));}});
  });
  ws=new WebSocket(endpoint);await new Promise((resolve,reject)=>{ws.addEventListener("open",resolve,{once:true});ws.addEventListener("error",reject,{once:true});});
  const cdp=new CDP(ws);
  record.browser_version=await cdp.send("Browser.getVersion");
  const target=await cdp.send("Target.createTarget",{url:"about:blank"});
  const attached=await cdp.send("Target.attachToTarget",{targetId:target.targetId,flatten:true});
  const sid=attached.sessionId;
  cdp.listeners.push(m=>{if(m.sessionId!==sid)return;if(m.method==="Runtime.exceptionThrown")exceptions.push(m.params.exceptionDetails.text+" "+JSON.stringify(m.params.exceptionDetails.exception));
    if(m.method==="Network.requestWillBeSent")requests.push(m.params.request.url);});
  const send=(m,p={})=>cdp.send(m,p,sid);
  const evaluate=async code=>{const r=await send("Runtime.evaluate",{expression:"(async()=>{"+code+"})()",awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  await send("Page.enable");await send("Runtime.enable");await send("Network.enable");
  await send("Emulation.setDeviceMetricsOverride",{width:1280,height:1100,deviceScaleFactor:1,mobile:false});
  record.navigation=await send("Page.navigate",{url:targetUrl||origin+"/results/Blog_Post_7_Review.html"});
  let ready=false;for(let i=0;i<100;i++){await delay(100);ready=await evaluate("return window.gasReady===true;");if(ready)break;}
  check("actual_plotly_loaded",ready,await evaluate("return {version:window.Plotly&&Plotly.version,url:location.href,body:document.body?.innerText.slice(0,300),error:document.getElementById('chart-error')?.textContent};"));
  const snapshot=()=>evaluate("await window.gasRenderComplete;return {summary:gasApp.summary(),mean:document.getElementById('stat-mean').textContent,low:document.getElementById('stat-low').textContent,high:document.getElementById('stat-high').textContent,traces:document.getElementById('gas-chart').data.length};");
  let view=await snapshot();
  check("full_window_313_and_mean",view.summary.count===313&&Math.abs(view.summary.mean-expected.overall.mean_extra)<1e-9,view);
  for(const year of expected.yearly){
   await evaluate("const el=document.getElementById('year-select');el.value='"+year.year+"';el.dispatchEvent(new Event('change',{bubbles:true}));await window.gasRenderComplete;");
   view=await snapshot();
   check("year_"+year.year,view.summary.count===year.weeks&&Math.abs(view.summary.mean-year.mean_extra)<1e-9,view.summary);
  }
  await evaluate("document.getElementById('year-select').value='2022';document.getElementById('year-select').dispatchEvent(new Event('change',{bubbles:true}));await gasRenderComplete;document.getElementById('view-select').value='prices';document.getElementById('view-select').dispatchEvent(new Event('change',{bubbles:true}));await gasRenderComplete;");
  check("pump_price_view_two_real_series",(await snapshot()).traces===2,await evaluate("return document.getElementById('gas-chart').data.map(t=>({name:t.name,points:t.x.length}));"));
  await evaluate("document.getElementById('date-start').value='2022-09-01';document.getElementById('date-end').value='2022-10-31';document.getElementById('apply-dates').click();await gasRenderComplete;");
  view=await snapshot();check("custom_window_and_peak",view.summary.count===9&&view.summary.maxDate==="2022-10-03",view.summary);
  await evaluate("await Plotly.relayout(document.getElementById('gas-chart'),{'xaxis.range':['2022-10-01','2022-10-31']});");
  view=await snapshot();check("native_plotly_zoom_updates_summary",view.summary.count===5&&view.summary.minDate.startsWith("2022-10"),view.summary);
  await evaluate("document.getElementById('date-start').value='2022-09-06';document.getElementById('date-end').value='2022-09-06';document.getElementById('apply-dates').click();await gasRenderComplete;");
  view=await snapshot();check("empty_window_is_not_zero",view.summary===null&&view.mean==="—",view);
  await evaluate("document.getElementById('date-start').value='2023-01-01';document.getElementById('date-end').value='2022-01-01';document.getElementById('apply-dates').click();");
  check("reversed_dates_rejected",await evaluate("return document.getElementById('input-message').textContent.length>0;"));
  await evaluate("document.getElementById('reset-window').click();await gasRenderComplete;document.getElementById('gas-chart').scrollIntoView({block:'center'});");
  view=await snapshot();check("reset_restores_full_data",view.summary.count===313&&view.traces===1,view);
  const hover=await evaluate("const g=document.getElementById('gas-chart'),b=g.getBoundingClientRect(),x=g._fullLayout.xaxis,y=g._fullLayout.yaxis;return {x:b.left+x._offset+x.d2p('2022-10-03'),y:b.top+y._offset+y.d2p(36.465)};");
  await send("Input.dispatchMouseEvent",{type:"mouseMoved",x:hover.x,y:hover.y});await delay(250);
  const hoverText=await evaluate("return document.querySelector('#gas-chart .hoverlayer').textContent;");
  check("pointer_hover_shows_prices_and_extra",hoverText.includes("$6.213")&&hoverText.includes("$3.782")&&hoverText.includes("$36.47"),hoverText);
  await evaluate("document.getElementById('week-detail').value='2022-10-03';document.getElementById('week-detail').dispatchEvent(new Event('change',{bubbles:true}));");
  const detail=await evaluate("return document.getElementById('week-values').textContent;");
  check("weekly_selector_matches_hover",detail.includes("$6.213")&&detail.includes("$36.47"),detail);
  await evaluate("document.getElementById('week-detail').focus();");
  await send("Input.dispatchKeyEvent",{type:"keyDown",key:"ArrowDown",code:"ArrowDown",windowsVirtualKeyCode:40});
  await send("Input.dispatchKeyEvent",{type:"keyUp",key:"ArrowDown",code:"ArrowDown",windowsVirtualKeyCode:40});
  check("weekly_selector_keyboard_operable",await evaluate("return document.getElementById('week-detail').value==='2022-10-10';"),await evaluate("return document.getElementById('week-detail').value;"));
  const downloads=path.join(qa,"downloads");fs.mkdirSync(downloads,{recursive:true});
  await cdp.send("Browser.setDownloadBehavior",{behavior:"allow",downloadPath:downloads,eventsEnabled:true});
  await evaluate("document.getElementById('year-select').value='2025';document.getElementById('year-select').dispatchEvent(new Event('change',{bubbles:true}));await gasRenderComplete;document.getElementById('export-csv').click();");
  let downloaded;for(let i=0;i<40;i++){await delay(100);downloaded=fs.readdirSync(downloads).find(f=>f.endsWith(".csv"));if(downloaded)break;}
  assert(downloaded,"CSV was not downloaded");
  const download=fs.readFileSync(path.join(downloads,downloaded),"utf8").trim().split(/\r?\n/);
  check("selected_csv_export_has_52_weeks",download.length===53&&download[1].startsWith("2025-01-06,4.154,3.047,1.107,16.605"),{file:downloaded,rows:download.length-1,first:download[1]});
  await evaluate("document.getElementById('reset-window').click();await gasRenderComplete;document.getElementById('gas-explorer').scrollIntoView({block:'start'});");
  let png=await send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});fs.writeFileSync(path.join(qa,"desktop.png"),Buffer.from(png.data,"base64"));
  await send("Emulation.setDeviceMetricsOverride",{width:390,height:1100,deviceScaleFactor:1,mobile:true});
  await evaluate("await Plotly.Plots.resize(document.getElementById('gas-chart'));document.getElementById('gas-explorer').scrollIntoView({block:'start'});");
  await delay(200);
  const layout=await evaluate("return {viewport:innerWidth,pageWidth:document.documentElement.scrollWidth,plotWidth:document.getElementById('gas-chart').getBoundingClientRect().width};");
  check("mobile_no_horizontal_overflow",layout.pageWidth<=layout.viewport+1,layout);
  png=await send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});fs.writeFileSync(path.join(qa,"mobile.png"),Buffer.from(png.data,"base64"));
  check("no_javascript_exceptions",exceptions.length===0,exceptions);
  check("offline_no_external_requests",requests.every(u=>u.startsWith(origin)||u.startsWith("data:")),requests);
  if(process.env.POST7_SITE_URL || process.env.POST7_WEB_ROOT){
   const pageUrl=process.env.POST7_SITE_URL||origin+"/blog/posts/post7/index.html";
   await send("Emulation.setDeviceMetricsOverride",{width:1280,height:1100,deviceScaleFactor:1,mobile:false});
   await send("Page.navigate",{url:pageUrl});
   let pageReady=false;
   for(let i=0;i<100;i++){
    await delay(100);
    pageReady=await evaluate("const f=document.getElementById('gasoline-comparison-frame');return !!(f&&f.contentWindow&&f.contentWindow.gasReady);");
    if(pageReady)break;
   }
   check("quarto_page_actual_iframe_loaded",pageReady);
   const page=await evaluate("return {title:document.querySelector('h1').textContent,author:document.querySelector('.quarto-title-meta-contents').textContent,footer:document.querySelector('footer').textContent,date:document.querySelector('.publishedDate')?.textContent||document.querySelector('.date')?.textContent||document.querySelectorAll('.quarto-title-meta-contents')[1]?.textContent};");
   check("page_title_author_footer",page.title.includes('15 gallons')&&page.author.includes('Defang Shen')&&page.footer.includes('Defang Shen'),page);
   for(const width of [1280,390]){
    await send("Emulation.setDeviceMetricsOverride",{width,height:1100,deviceScaleFactor:1,mobile:width===390});
    await evaluate("const f=document.getElementById('gasoline-comparison-frame');await f.contentWindow.Plotly.Plots.resize(f.contentDocument.getElementById('gas-chart'));f.scrollIntoView({block:'start'});");
    await delay(300);
    const box=await evaluate("const f=document.getElementById('gasoline-comparison-frame');return {viewport:innerWidth,pageWidth:document.documentElement.scrollWidth,frameHeight:f.clientHeight,contentHeight:f.contentDocument.body.scrollHeight,observations:f.contentWindow.gasApp.summary().count};");
    check("published_layout_"+width,box.pageWidth<=box.viewport+1&&box.frameHeight>=box.contentHeight&&box.observations===313,box);
    const shot=await send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});
    fs.writeFileSync(path.join(qa,"page-"+width+".png"),Buffer.from(shot.data,"base64"));
   }
   await evaluate("const w=document.getElementById('gasoline-comparison-frame').contentWindow;const el=w.document.getElementById('year-select');el.value='2022';el.dispatchEvent(new w.Event('change',{bubbles:true}));await w.gasRenderComplete;w.document.getElementById('view-select').value='prices';w.document.getElementById('view-select').dispatchEvent(new w.Event('change',{bubbles:true}));await w.gasRenderComplete;");
   const live=await evaluate("const w=document.getElementById('gasoline-comparison-frame').contentWindow;return {summary:w.gasApp.summary(),traces:w.document.getElementById('gas-chart').data.length};");
   check("published_iframe_year_and_view_controls",live.summary.count===52&&live.traces===2&&Math.abs(live.summary.mean-expected.yearly.find(y=>y.year===2022).mean_extra)<1e-9,live);
   check("published_no_javascript_exceptions",exceptions.length===0,exceptions);
  }
  record.status="passed";record.engine="Headless Google Chrome, actual vendored Plotly.js 3.0.1";
  record.external_requests=0;record.completed_at=new Date().toISOString();
  await cdp.send("Browser.close").catch(()=>{});
 }catch(error){record.status="failed";record.error=error.stack||String(error);process.exitCode=1;}
 finally{
  fs.writeFileSync(path.join(root,"results/interaction_checks.json"),JSON.stringify(record,null,2)+"\n");
  if(ws)ws.close();if(chrome&&!chrome.killed)chrome.kill();
  if(server)await new Promise(resolve=>server.close(resolve));
  console.log(JSON.stringify(record));
 }
})();
