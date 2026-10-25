"""Generate article source and offline review from saved EIA calculations."""
import base64,csv,hashlib,html,json,re
from datetime import datetime
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/"results"
CA="https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=W&n=PET&s=EMM_EPMR_PTE_SCA_DPG"
US="https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=W&n=PET&s=EMM_EPMR_PTE_NUS_DPG"
NOTES="https://www.eia.gov/dnav/pet/tbldefs/pet_pri_gnd_tbldef2.asp"
EXPLAINER="https://www.eia.gov/energyexplained/gasoline/regional-price-differences.php"
TITLE="How much extra did 15 gallons cost in California?"
SUBTITLE="A weekly comparison with the U.S. average, 2020–2025"
def cash(value):
    return "$"+format(Decimal(str(value)).quantize(Decimal(".01"),rounding=ROUND_HALF_UP),",.2f")
def gallon(value):return "$"+format(value,".3f")
def day(iso):
    stamp=datetime.fromisoformat(iso)
    return f"{stamp:%B} {stamp.day}, {stamp.year}"
def inline(text,embedded=False):
    text=html.escape(text)
    def link(match):
        label,url=match.group(1),html.unescape(match.group(2))
        download=""
        if embedded and not url.startswith("http"):
            path=(ROOT/url).resolve()
            if path.suffix==".zip":
                return '<a href="#source-package">'+label+'</a>'
            assert path.is_relative_to(ROOT) and path.exists()
            mime="text/csv" if path.suffix==".csv" else "text/plain"
            url="data:"+mime+";base64,"+base64.b64encode(path.read_bytes()).decode()
            download=' download="'+html.escape(path.name)+'"'
        return '<a href="'+html.escape(url,quote=True)+'"'+download+'>'+label+'</a>'
    text=re.sub(r"\[([^\]]+)\]\(([^)]+)\)",link,text)
    return re.sub(r"\*\*(.*?)\*\*",r"<strong>\1</strong>",text)
def widget(rows):
    compact=[{"date":r["date"],"ca_mills":int(Decimal(r["ca_price"])*1000),"us_mills":int(Decimal(r["us_price"])*1000)} for r in rows]
    return '''<section id="gas-explorer" class="gas-explorer" aria-label="Interactive gasoline price comparison">
<h3>Extra cost of a 15-gallon fill</h3>
<p class="explorer-help">Select a year, choose dates, or drag the window below the chart. The summaries follow the visible dates.</p>
<div class="controls">
<label>Year<select id="year-select"><option value="all">All years: 2020–2025</option>'''+''.join(f'<option value="{y}">{y}</option>' for y in range(2020,2026))+'''<option value="custom">Custom window</option></select></label>
<label class="view-label">Chart view<select id="view-select"><option value="extra">Extra cost for 15 gallons</option><option value="prices">Pump prices per gallon</option></select></label>
<button id="export-csv" type="button">Download selected data</button></div>
<div class="controls dates">
<label>From<input id="date-start" type="date" min="2020-01-01" max="2025-12-31" value="2020-01-01"></label>
<label>To<input id="date-end" type="date" min="2020-01-01" max="2025-12-31" value="2025-12-31"></label>
<button id="apply-dates" class="primary" type="button">Apply dates</button><button id="reset-window" type="button">Reset all</button></div>
<p id="input-message" class="input-message" role="alert"></p>
<p id="window-label" class="window-label" aria-live="polite">2020–2025 · 313 weekly observations</p>
<p class="summary-title">Extra per 15-gallon fill in this window</p>
<div class="summary" aria-live="polite">
<div><span>Weekly mean</span><strong id="stat-mean">$17.59</strong><small>Equal weight per observed week</small></div>
<div><span>Lowest week</span><strong id="stat-low">$11.84</strong><small id="date-low">June 29, 2020</small></div>
<div><span>Highest week</span><strong id="stat-high">$36.47</strong><small id="date-high">October 3, 2022</small></div></div>
<div id="chart-error" class="chart-error" role="alert" hidden></div>
<div id="gas-chart" class="chart" role="img" aria-label="Weekly additional cost in California for 15 gallons relative to the U.S. average. The observation selector provides the same values without hovering."></div>
<div class="detail-row"><label>Inspect a weekly observation<select id="week-detail"></select></label><div id="week-values" class="detail-values" aria-live="polite"></div></div>
<p class="figure-note">Source: EIA. Regular gasoline, all formulations, including taxes. Nominal U.S. dollars; the U.S. average includes California. Fifteen gallons is a fixed comparison quantity, not an assumed tank size.</p>
<noscript>The full-period average is $17.59 extra per 15 gallons; the observed range is $11.84–$36.47. JavaScript is required for interaction.</noscript>
<script id="gas-data" type="application/json">'''+json.dumps(compact,separators=(",",":"))+"</script></section>"
def main():
    s=json.loads((RESULTS/"summary.json").read_text(encoding="utf-8"))
    o=s["overall"]; years={r["year"]:r for r in s["yearly"]}
    peak,june=s["largest_gap"],s["highest_ca_price"]
    sections=[
("p","A difference of a dollar per gallon can look small on a gas-station sign. For a 15-gallon purchase, it adds $15 to the bill. I wanted to put California's price difference in these everyday terms: **from 2020 through 2025, how much more did the same 15 gallons cost in California than at the U.S. average price?**"),
("p",f"Across {o['weeks']} weekly observations, the extra cost averaged **{cash(o['mean_extra'])}**. California's price was higher in every observed week. But that average hides a wide range: the extra cost ran from {cash(o['min_extra'])} to {cash(o['max_extra'])}, depending on the date."),
("h2","Making the comparison fair"),
("p",f"I use the Energy Information Administration's weekly [California]({CA}) and [U.S.]({US}) prices for regular gasoline, all formulations, including taxes. Matching the same date and grade avoids comparing different products or different weeks. There are no missing dates in the matched series."),
("p","Fifteen gallons is a fixed comparison quantity, not an estimate of anyone's tank size or fuel use. For each week, I calculate:"),
("formula","Extra for 15 gallons = 15 × (California price − U.S. price)."),
("p","The national average includes California. It therefore provides a familiar benchmark, rather than the average for the other 49 states. The overall result gives each observed week equal weight; it does not estimate the average driver's spending."),
("p","Start with the full period below, then choose a year. The average and the lowest and highest weeks update together. Hover over the line, or use the observation selector, to inspect the prices behind any point."),
("figure",""),
("h2","Was the extra cost similar every year?"),
("p",f"Choosing 2020 gives an average extra cost of {cash(years[2020]['mean_extra'])}. Choosing 2025 raises it to {cash(years[2025]['mean_extra'])}. For the same quantity of gasoline, the average difference was {cash(Decimal(str(years[2025]['mean_extra']))-Decimal(str(years[2020]['mean_extra'])))} larger in 2025. The annual average was highest in 2022, at {cash(years[2022]['mean_extra'])}."),
("p","All amounts are nominal dollars: they describe the dollar gap at the time, without adjusting for inflation. They do not show whether the extra cost took a larger share of someone's income. That would require income and fuel-use data."),
("h2","The highest pump price was not the largest gap"),
("p",f"The most revealing comparison is within 2022. On {day(june['date'])}, California's price reached its highest level in this dataset, {gallon(june['ca_price'])} per gallon. The U.S. average was {gallon(june['us_price'])}, so the extra cost for 15 gallons was {cash(june['extra_15_gallons'])}."),
("p",f"By {day(peak['date'])}, California's price had edged down to {gallon(peak['ca_price'])}. Meanwhile, the U.S. average had fallen to {gallon(peak['us_price'])}. The extra cost reached **{cash(peak['extra_15_gallons'])}**, the largest weekly gap in the six-year period. California gasoline was slightly cheaper than in June, yet its premium over the national price was much larger."),
("p","Select 2022 and switch the chart view to pump prices to see why. The two lines show the comparison that the extra-cost line summarizes. Zooming into June through October makes this change easier to inspect. The interaction lets me check how a period average changes when I include or exclude the spike."),
("h2","What I take from the chart"),
("p",f"The evidence answers how large the difference was and when it widened. It does not identify its causes. EIA [discusses]({EXPLAINER}) taxes, fuel specifications, transport and supply conditions as contributors to regional prices, but these two series cannot separate their effects."),
("p",f"EIA's [survey notes]({NOTES}) describe Monday morning cash prices, generally self-service, with volume weights within each area. These are estimates, not prices at every station. The minimum and maximum show variation over dates, not a confidence interval."),
("p",f"My takeaway is straightforward: over 2020–2025, buying the same 15 gallons at California's average price cost about {cash(o['mean_extra'])} more than at the U.S. average. To understand that difference, I need both prices. A falling California price alone does not tell me whether the extra cost is shrinking."),
("p","[Download the weekly calculations](results/weekly_comparison.csv), [code and data](https://github.com/Devinshen123/devinshen123-website/tree/main/blog/posts/post7), or see the [replication instructions](README.md).")]
    caption="Figure 1. Extra cost at California's average price relative to the U.S. average, January 6, 2020–December 29, 2025. Both views use the same 313 weekly observations."
    qmd=["---",f'title: "{TITLE}"',f'description: "{SUBTITLE}"','author: "Defang Shen"',"date: 2026-10-25","categories: [Interactive visualization, Energy]","draft: false","format:","  html:","    toc: false","---",""]
    body,prose=[],[]
    with (ROOT/"data/processed/weekly_prices.csv").open(encoding="utf-8") as handle:rows=list(csv.DictReader(handle))
    chart_body=widget(rows);ticks=chr(96)*3
    for kind,text in sections:
        if kind=="figure":
            frame_markup = '''<iframe id="gasoline-comparison-frame" src="results/chart.html" title="Interactive EIA gasoline price comparison" style="width:100%;height:1000px;border:0;" loading="lazy"></iframe>
<script>
(() => {
  const frame = document.getElementById("gasoline-comparison-frame");
  frame.addEventListener("load", () => {
    const body = frame.contentDocument.body;
    const fit = () => { frame.style.height = (body.scrollHeight + 32) + "px"; };
    new ResizeObserver(fit).observe(body);
    fit();
  });
})();
</script>'''
            qmd += [ticks+"{=html}",frame_markup,ticks,"",caption,""]
            body += ["<figure>",chart_body,"<figcaption>"+html.escape(caption)+"</figcaption></figure>"]
            prose.append(caption)
        elif kind=="h2":
            qmd += ["## "+text,""];body.append('<div class="prose"><h2>'+inline(text)+"</h2></div>");prose.append(text)
        else:
            qmd += ["**"+text+"**" if kind=="formula" else text,""]
            body.append('<div class="prose"><p'+(' class="calculation"' if kind=="formula" else "")+">"+inline(text,True)+"</p></div>");prose.append(text)
    (ROOT/"index.qmd").write_text("\n".join(qmd),encoding="utf-8")
    css=(ROOT/"assets/style.css").read_text(encoding="utf-8")
    runtime=(ROOT/"assets/plotly-basic-3.0.1.min.js").read_text(encoding="utf-8").replace("</script",r"<\/script")
    scripts="<script>"+runtime+"</script><script>"+(ROOT/"assets/chart.js").read_text(encoding="utf-8")+"</script>"
    head='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="author" content="Defang Shen"><title>'+html.escape(TITLE)+"</title><style>"+css+"</style></head>"
    chart_html=head+'<body class="chart-only">'+chart_body+scripts+"</body></html>"
    review=head+'<body><header class="site">AEDS 6400 · Computational Methods for Economists</header><main class="article"><div class="eyebrow">Blog Post 7</div><h1>'+html.escape(TITLE)+'</h1><p class="subtitle">'+html.escape(SUBTITLE)+'</p><p class="byline">Defang Shen · October 25, 2026</p>'+"".join(body)+'<footer>© 2026 Defang Shen</footer></main>'+scripts+"</body></html>"

    import zipfile
    package=RESULTS/"Blog_Post_7_Source.zip"
    package_paths=[]
    for folder in ("code","assets","data"):
        package_paths.extend(p for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    package_paths.extend([ROOT/"README.md",ROOT/"index.qmd",ROOT/".gitignore"])
    for name in ("weekly_comparison.csv","yearly_summary.csv","summary.json","data_checks.json",
                 "independent_checks.json","control_checks.json","interaction_checks.json","quarto_checks.json"):
        if (RESULTS/name).exists():package_paths.append(RESULTS/name)
    with zipfile.ZipFile(package,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(package_paths):
            item=zipfile.ZipInfo("post7/"+path.relative_to(ROOT).as_posix(),(2026,10,25,0,0,0))
            item.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(item,path.read_bytes())
    source_url="data:application/zip;base64,"+base64.b64encode(package.read_bytes()).decode()
    review=review.replace("<footer>",'<footer id="source-package"><a href="'+source_url+'" download="Blog_Post_7_Source.zip">Download source package</a><br>')

    (RESULTS/"chart.html").write_text(chart_html,encoding="utf-8")
    (RESULTS/"Blog_Post_7_Review.html").write_text(review,encoding="utf-8")
    words=re.sub(r"\[([^\]]+)\]\([^)]+\)",r"\1","\n".join(prose))
    count=len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b",words))
    build={"article_words_including_headings_and_caption":count,"figures":1,"offline_runtime":"Plotly.js basic 3.0.1","third_party_python_packages":[],"publication_status":"prepared for GitHub Pages","review_sha256":hashlib.sha256(review.encode()).hexdigest()}
    (RESULTS/"build.json").write_text(json.dumps(build,indent=2)+"\n",encoding="utf-8");print(json.dumps(build));return build
if __name__=="__main__":main()
