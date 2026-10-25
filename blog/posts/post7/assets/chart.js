/* Plotly figure and pure date-window calculations; no network requests. */
(function (scope) {
  "use strict";
  const model = {
    rowsInRange: (rows, start, end) => rows.filter(r => r.date >= start && r.date <= end),
    extraMills: r => (r.ca_mills - r.us_mills) * 15,
    summarize(rows) {
      if (!rows.length) return null;
      let total = 0, low = rows[0], high = rows[0];
      rows.forEach(r => {
        const value = model.extraMills(r);
        total += value;
        if (value < model.extraMills(low)) low = r;
        if (value > model.extraMills(high)) high = r;
      });
      return {count: rows.length, mean: total / rows.length / 1000,
              minimum: model.extraMills(low) / 1000, maximum: model.extraMills(high) / 1000,
              minDate: low.date, maxDate: high.date};
    }
  };
  if (typeof module !== "undefined" && module.exports) module.exports = model;
  if (!scope || !scope.document) return;
  scope.GasComparison = model;
  const money = new Intl.NumberFormat("en-US", {style:"currency", currency:"USD", minimumFractionDigits:2});
  const price = value => "$" + (value / 1000).toFixed(3);
  const niceDate = iso => new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", {
    month:"short", day:"numeric", year:"numeric", timeZone:"UTC"});
  function init() {
    const root = document.getElementById("gas-explorer");
    if (!root || root.dataset.started) return;
    root.dataset.started = "true";
    const rows = JSON.parse(document.getElementById("gas-data").textContent);
    const chart = document.getElementById("gas-chart");
    const el = id => document.getElementById(id);
    const state = {start:"2020-01-01", end:"2025-12-31", view:"extra",
      baseStart:"2020-01-01", baseEnd:"2025-12-31", drawing:false, week:null};
    let queue = Promise.resolve(), subscribed = false;
    const getRows = () => model.rowsInRange(rows, state.start, state.end);
    function updateDetails(active) {
      const select = el("week-detail"), chosen = select.value;
      select.replaceChildren();
      active.forEach(r => {
        const option = document.createElement("option");
        option.value = r.date; option.textContent = niceDate(r.date);
        select.appendChild(option);
      });
      select.disabled = active.length === 0;
      const selected = active.find(r => r.date === chosen) || active[0];
      if (!selected) {
        el("week-values").textContent = "No weekly observation in this window.";
        return;
      }
      select.value = selected.date;
      state.week = selected.date;
      el("week-values").textContent = "California " + price(selected.ca_mills) +
        "/gal · U.S. " + price(selected.us_mills) + "/gal · " +
        money.format(model.extraMills(selected) / 1000) + " extra for 15 gallons";
    }
    function updateSummary() {
      const active = getRows(), summary = model.summarize(active);
      el("date-start").value = state.start; el("date-end").value = state.end;
      el("window-label").textContent = niceDate(state.start) + " – " + niceDate(state.end) +
        " · " + active.length + " weekly observations";
      for (const id of ["stat-mean","stat-low","stat-high"]) el(id).textContent = "—";
      el("date-low").textContent = ""; el("date-high").textContent = "";
      if (summary) {
        el("stat-mean").textContent = money.format(summary.mean);
        el("stat-low").textContent = money.format(summary.minimum);
        el("stat-high").textContent = money.format(summary.maximum);
        el("date-low").textContent = niceDate(summary.minDate);
        el("date-high").textContent = niceDate(summary.maxDate);
      }
      el("export-csv").disabled = !active.length;
      updateDetails(active);
      return active;
    }
    function customData(active) {
      return active.map(r => [r.date, price(r.ca_mills), price(r.us_mills),
        money.format(model.extraMills(r)/1000), ((r.ca_mills-r.us_mills)/1000).toFixed(3)]);
    }
    async function draw() {
      state.drawing = true;
      const active = updateSummary(), extraView = state.view === "extra";
      const details = customData(active);
      const common = {type:"scatter", mode:"lines+markers",
        x:active.map(r=>r.date), customdata:details,
        hovertemplate:"<b>%{customdata[0]}</b><br>California: %{customdata[1]}/gal" +
          "<br>U.S.: %{customdata[2]}/gal<br>Gap: $%{customdata[4]}/gal" +
          "<br><b>%{customdata[3]} extra for 15 gallons</b><extra></extra>"};
      const traces = extraView ? [Object.assign({}, common, {
        y:active.map(r=>model.extraMills(r)/1000), name:"Extra for 15 gallons",
        line:{color:"#216080",width:2.4}, marker:{size:3,color:"#216080"}
      })] : [
        Object.assign({},common,{y:active.map(r=>r.ca_mills/1000),name:"California",
          line:{color:"#216080",width:2.4},marker:{size:3,color:"#216080"}}),
        Object.assign({},common,{y:active.map(r=>r.us_mills/1000),name:"U.S. average",
          line:{color:"#a86616",width:2.2,dash:"dash"},marker:{size:3,color:"#a86616",symbol:"circle-open"}})
      ];
      const narrow = root.clientWidth < 500;
      const end = state.start === state.end ? state.end + " 23:59:59" : state.end;
      const layout = {
        autosize:true, height:narrow?390:450,
        margin:{l:narrow?57:68,r:18,t:extraView?28:48,b:65},
        paper_bgcolor:"#ffffff", plot_bgcolor:"#ffffff",
        font:{family:"Arial, sans-serif",size:narrow?12:14,color:"#283b48"},
        hovermode:"closest", hoverlabel:{bgcolor:"#ffffff",font:{size:13,color:"#172d3b"}},
        showlegend:!extraView, legend:{orientation:"h",x:0,y:1.12},
        xaxis:{type:"date",range:[state.start,end],title:{text:"Week (Monday)",standoff:10},
          gridcolor:"#eef1f3",showline:true,linecolor:"#a8b1b7",tickformat:"%b\n%Y",
          nticks:narrow?4:8,rangeslider:{visible:true,thickness:.12,bgcolor:"#f7f8f9"}},
        yaxis:{title:{text:extraView?"Extra cost for 15 gallons (US$)":"Price per gallon (US$)",standoff:9},
          range:extraView?[0,40]:[0,7],fixedrange:false,tickprefix:"$",gridcolor:"#e3e8ec",
          zeroline:true,zerolinecolor:"#9aa6ad",showline:true,linecolor:"#a8b1b7"},
        annotations:active.length?[]:[{xref:"paper",yref:"paper",x:.5,y:.55,
          text:"No weekly observations in this date window",showarrow:false,font:{size:15}}],
        uirevision:state.start+"|"+state.end+"|"+state.view
      };
      await Plotly.react(chart,traces,layout,{
        responsive:true,displaylogo:false,scrollZoom:false,
        modeBarButtonsToRemove:["select2d","lasso2d","toImage"],
        doubleClick:"reset"
      });
      if (!subscribed) {
        chart.on("plotly_relayout", event => {
          if (state.drawing) return;
          let start, end;
          if (event["xaxis.autorange"]) {
            start=state.baseStart; end=state.baseEnd;
          } else if (event["xaxis.range"]) {
            [start,end]=event["xaxis.range"];
          } else if (event["xaxis.range[0]"] && event["xaxis.range[1]"]) {
            start=event["xaxis.range[0]"]; end=event["xaxis.range[1]"];
          } else return;
          const iso = value => typeof value === "number" ?
            new Date(value).toISOString().slice(0,10) : String(value).slice(0,10);
          start=iso(start); end=iso(end);
          if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end)) return;
          state.start=start; state.end=end; el("year-select").value="custom";
          updateSummary();
        });
        subscribed=true;
      }
      state.drawing=false;
      root.dataset.ready="true";
      scope.gasReady=true;
    }
    function requestDraw() {
      root.dataset.ready="false";
      scope.gasReady=false;
      queue=queue.catch(()=>{}).then(draw).catch(error => {
        state.drawing=false;
        el("chart-error").hidden=false;
        el("chart-error").textContent="The figure could not be drawn: "+error.message;
        throw error;
      });
      scope.gasRenderComplete=queue;
      return queue;
    }
    function applyRange(start,end) {
      if (!start || !end || start>end) {
        el("input-message").textContent="Choose a start date on or before the end date.";
        return false;
      }
      el("input-message").textContent="";
      state.start=start; state.end=end; state.baseStart=start; state.baseEnd=end;
      requestDraw(); return true;
    }
    el("year-select").addEventListener("change",event=>{
      const year=event.target.value;
      if(year==="custom")return;
      applyRange(year==="all"?"2020-01-01":year+"-01-01",year==="all"?"2025-12-31":year+"-12-31");
    });
    el("view-select").addEventListener("change",event=>{
      state.view=event.target.value; requestDraw();
    });
    el("apply-dates").addEventListener("click",()=>{
      if(applyRange(el("date-start").value,el("date-end").value))el("year-select").value="custom";
    });
    el("reset-window").addEventListener("click",()=>{
      state.view="extra"; el("view-select").value="extra"; el("year-select").value="all";
      applyRange("2020-01-01","2025-12-31");
    });
    el("week-detail").addEventListener("change",()=>updateDetails(getRows()));
    el("export-csv").addEventListener("click",()=>{
      const active=getRows(), lines=["date,ca_price,us_price,gap_per_gallon,extra_15_gallons"];
      active.forEach(r=>lines.push([r.date,(r.ca_mills/1000).toFixed(3),
        (r.us_mills/1000).toFixed(3),((r.ca_mills-r.us_mills)/1000).toFixed(3),
        (model.extraMills(r)/1000).toFixed(3)].join(",")));
      const url=URL.createObjectURL(new Blob([lines.join("\n")+"\n"],{type:"text/csv;charset=utf-8"}));
      const link=document.createElement("a");
      link.href=url; link.download="gasoline-comparison-"+state.start+"-to-"+state.end+".csv";
      link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    scope.gasApp={state,rows,summary:()=>model.summarize(getRows()),getRows,requestDraw};
    if (typeof Plotly === "undefined") {
      el("chart-error").hidden=false;
      el("chart-error").textContent="Plotly did not load. Open the complete offline review file or keep its assets folder alongside the chart.";
      return;
    }
    requestDraw();
  }
  if (document.readyState==="loading") document.addEventListener("DOMContentLoaded",init);
  else init();
})(typeof window!=="undefined"?window:null);
