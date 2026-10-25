"""Verify deployed Blog Post 7 against this checkout; use only public URLs."""
import hashlib,json,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT.parents[2]
BASE="https://devinshen123.github.io/devinshen123-website/"
checks=[]
def fetch(relative):
    request=urllib.request.Request(BASE+relative,headers={"User-Agent":"Blog7-public-verification","Cache-Control":"no-cache"})
    with urllib.request.urlopen(request,timeout=20) as response:
        assert response.status==200
        return response.read()
def compare(relative):
    expected=(SITE/"docs"/relative).read_bytes()
    last=None
    for attempt in range(40):
        try:
            actual=fetch(relative)
            assert actual==expected,"Deployed bytes differ from the verified checkout"
            record={"path":relative,"http":200,"sha256":hashlib.sha256(actual).hexdigest(),"matches_checkout":True}
            checks.append(record)
            print(json.dumps(record),flush=True)
            return actual
        except Exception as error:
            last=error
            time.sleep(3)
    raise AssertionError(str(last))
try:
    page=compare("blog/posts/post7/index.html").decode()
    assert "How much extra did 15 gallons cost in California?" in page
    assert page.count("<iframe")==1
    assert "Defang Shen" in page and "October 25, 2026" in page
    compare("blog/posts/post7/results/chart.html")
    compare("blog/posts/post7/results/weekly_comparison.csv")
    compare("blog/posts/post7/README.md")
    listing=fetch("blog/index.html").decode()
    assert all("posts/post"+str(i)+"/index.html" in listing for i in range(1,8))
    result={"status":"passed","checks":checks,"blog_listing_posts":list(range(1,8))}
except Exception as error:
    result={"status":"failed","checks":checks,"error":str(error)}
    raise
finally:
    (ROOT/"results/public_checks.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result),flush=True)
