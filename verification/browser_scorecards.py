"""Real templates/scripts + Python scoring/aggregation; mocked HTTP/provider transport."""
from pathlib import Path
import sys,json,copy,re,time
from urllib.parse import urlparse,parse_qs
from jinja2 import Environment,FileSystemLoader,select_autoescape
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evaluation.dashboard import build_dashboard
from evaluation.profiles import profile_catalog
from evaluation.overview import compact_case
from tests.test_dashboard_v16 import fixture
from ui_integrity import UI_BUILD
EVID=ROOT/'verification/browser_local';EVID.mkdir(exist_ok=True)
REPORT=Path(sys.argv[1]) if len(sys.argv)>1 else None
if not REPORT or not REPORT.is_file():raise SystemExit('Usage: python verification/browser_scorecards.py PATH_TO_EXPORTED_HTML')
original=json.loads(re.search(r'id="bootstrap">(.*?)</script>',REPORT.read_text('utf-8'),re.S).group(1))
sample=json.loads((ROOT/'examples/sample.json').read_text())
env=Environment(loader=FileSystemLoader(ROOT/'templates'),autoescape=select_autoescape(['html']))
env.globals['url_for']=lambda _,filename,**kw:'/static/'+filename
boot={'offline':False,'ui_version':UI_BUILD,'version':'1.6.2','sample':sample,'normalization':profile_catalog(),'csrf':'test-token'}
html=env.get_template('index.html').render(boot=boot,asset_version=UI_BUILD)
# Browser policy blocks URL navigation. Inline exactly the distributed assets;
# only HTTP/storage are supplied by this test harness.
html=re.sub(r'<link rel="stylesheet"[^>]*>', lambda _: '<style>'+ (ROOT/'static/css/app.css').read_text()+'</style>',html)
for asset in ['charts','app']:
    html=re.sub(r'<script defer src="[^"]*'+asset+r'\.js[^"]*"></script>', lambda _,a=asset: '<script>'+ (ROOT/('static/js/'+a+'.js')).read_text()+'</script>',html)
bridge='''<script>
window.fetch=async (url,options={})=>{const r=await window.__asrRequest(String(url),{method:options.method||'GET',body:options.body||null});return new Response(r.body,{status:r.status,headers:{'Content-Type':r.content_type}})};
window.__fakeSession={};
try {sessionStorage.getItem('probe');}catch(e){Object.defineProperty(window,'sessionStorage',{configurable:true,value:{getItem:k=>window.__fakeSession[k]??null,setItem:(k,v)=>{window.__fakeSession[k]=String(v)},removeItem:k=>{delete window.__fakeSession[k]}}});}
</script>'''
html=html.replace('<head>','<head>'+bridge)
checks=[]; errors=[]
def check(name,value):
    checks.append({'name':name,'passed':bool(value)})
    print(('PASS ' if value else 'FAIL ')+name,flush=True)
    if not value:raise AssertionError(name)
class FakeHTTP:
    def __init__(self):
        self.cases=copy.deepcopy(original['cases']);self.jobs=copy.deepcopy(original['jobs']);self.sequence=0
        self.pending=None;self.next_status='complete';self.hold=False;self.batch=False;self.fail_once=False;self.summary=None;self.events=[]
    def transport(self,url,options):
        class Request:
            method=options['method']
            post_data_json=json.loads(options['body']) if options.get('body') else {}
        Request.url='http://asr.local'+url if url.startswith('/') else url
        class Route:
            request=Request()
            response=None
            def fulfill(self,status=200,content_type='application/json',body=''):
                self.response={'status':status,'content_type':content_type,'body':body.decode('utf-8') if isinstance(body,bytes) else body}
        route=Route();self.route(route);return route.response
    def start(self,body,kind):
        self.sequence+=1; rid='run_navigation'+str(self.sequence)
        cs=[fixture(rid,cid='case_'+str(i+1).zfill(3),ref='HELLO WORLD',a='hello world',b='hello',audio=rid+str(i),language='en',when='2026-09-17T13:'+str(self.sequence).zfill(2)+':00+00:00') for i in range(2 if self.batch else 1)]
        for c in cs:
            c['title']='[Fixture] Navigation '+str(self.sequence)
            if self.next_status=='failed':c.update(models=[],status='failed',error={'stage':'audio','message':'[Fixture] Audio failed'})
            elif self.next_status=='partial':c['models'][1].update(status='failed',error={'stage':'elevenlabs','message':'[Fixture] No permission'});c['status']='partial'
        j={'run_id':rid,'job_id':rid,'name':cs[0]['title'],'created_at':cs[0]['created_at'],'status':'queued','completed':0,'total':len(cs),'mode':kind,'stage':'Queued', 'profile':cs[0]['profile'], 'score_view':body.get('score_view','normalized'),'case_headers':[{'case_id':c['case_id'],'title':c['title']} for c in cs]}
        self.jobs.insert(0,j);self.pending={'job':j,'cases':cs,'ticks':0,'final':self.next_status};self.next_status='complete';self.batch=False
        return copy.deepcopy(j)
    def progress(self):
        if not self.pending:return
        p=self.pending;p['ticks']+=1
        if self.hold or p['ticks']<2:p['job'].update(status='running',stage='Preparing audio');return
        p['job'].update(status=p['final'],stage='Finished',completed=len(p['cases']));self.cases+=p['cases'];self.pending=None
    def route(self,route):
        req=route.request;u=urlparse(req.url);path=u.path;q={k:v[0] for k,v in parse_qs(u.query).items()};self.events.append((req.method,path))
        def answer(data,status=200):route.fulfill(status=status,content_type='application/json',body=json.dumps(data))
        if path=='/':return route.fulfill(status=200,content_type='text/html',body=html)
        if path.startswith('/static/'):
            p=ROOT/path.lstrip('/');return route.fulfill(status=200,content_type='text/javascript' if p.suffix=='.js' else 'text/css',body=p.read_bytes())
        if path=='/api/sample':return answer(sample)
        if path=='/api/health':return answer({'version':'1.6.2','tools':{'ffmpeg':True,'ffprobe':True},'providers':{'humain':True,'elevenlabs':True}})
        if path=='/api/sample/audio' or path.startswith('/api/audio/'):
            return route.fulfill(status=200,content_type='audio/mpeg',body=(ROOT/'examples/doctor_clip.mp3').read_bytes())
        if path=='/api/jobs':return answer({'jobs':self.jobs})
        if path=='/api/overview':
            if self.fail_once:self.fail_once=False;return answer({'error':'[Fixture] Temporary read failure'},503)
            self.progress();self.summary=build_dashboard(self.cases,self.jobs,q.get('view','normalized'),{'q':q.get('q',''),'run':'all'},pair_keys=(q.get('pair_a',''),q.get('pair_b','')))
            return answer({'summary':self.summary,'jobs':self.jobs})
        if path.startswith('/api/results/'):
            parts=path.split('/')[3:];rid=parts[0]
            cs=[c for c in self.cases if c['run_id']==rid]
            if len(parts)==1:
                j=next(j for j in self.jobs if j['run_id']==rid)
                return answer({'job':j,'summary':build_dashboard(cs,[j],q.get('view','normalized'))})
            c=copy.deepcopy(next(c for c in cs if c['case_id']==parts[1]));c['quality_flags']=compact_case(c).get('quality_flags',[]);return answer(c)
        if req.method=='POST' and (path in ['/api/evaluate','/api/imported/evaluate'] or path.startswith('/api/rescore/')):
            return answer(self.start(req.post_data_json,'rescore' if 'rescore' in path else 'live'),202)
        return answer({'error':'Unexpected test route '+path},404)
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1100},reduced_motion='reduce')
    db=FakeHTTP();context.expose_function('__asrRequest',db.transport)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.set_content(html,wait_until='load')
        page.wait_for_function("document.querySelector('#kCases').textContent==='12'")
        check('all twelve prior cases visible',page.locator('#resultsBody .audio-case').count()==12)
        check('two top model scorecards',page.locator('#modelScorecards .model-scorecard').count()==2)
        for i,m in enumerate(db.summary['comparison']['models']):
            card=page.locator('.model-scorecard').nth(i)
            for key,field in [('mean-wer','mean_case_wer'),('mean-cer','mean_case_cer')]:
                check(f'{m["provider"]} {key} matches Python',card.locator('[data-stat="'+key+'"]').inner_text()==f'{100*m[field]:.2f}%')
            for k in 'SDI':check(f'{m["provider"]} total {k} matches Python',card.locator('[data-stat="'+k+'"]').inner_text()==f'{m["counts"][k]:,}')
        check('no pinned sample in overview',page.locator('#page-overview').get_by_text('PINNED SAMPLE',exact=True).count()==0)
        check('no separate quality or configurations section',page.locator('#qualitySection,#coverageBody').count()==0)
        check('charts collapsed initially',not page.locator('#chartsSection').evaluate('(e)=>e.open'))
        page.screenshot(path=str(EVID/'overview.png'),full_page=False)
        page.locator('[data-jump="chartsSection"]').click();page.wait_for_timeout(150)
        check('charts jump opens section',page.locator('#chartsSection').evaluate('(e)=>e.open'))
        check('both charts render',page.locator('#chartsSection svg').count()==2)
        page.screenshot(path=str(EVID/'charts.png'),full_page=False)
        page.locator('[data-view="raw"]').click();page.wait_for_timeout(250)
        check('no-cleaning updates average metric',page.locator('.model-scorecard').first.locator('[data-stat="mean-wer"]').inner_text()==f'{100*db.summary["comparison"]["models"][0]["mean_case_wer"]:.2f}%')
        page.locator('[data-view="normalized"]').click();page.wait_for_timeout(150)
        page.locator('[data-jump="audioCasesSection"]').click();page.wait_for_timeout(80)
        check('audio list jump is in viewport',page.locator('#audioCasesSection').bounding_box()['y']<100)
        page.locator('#resultsBody .case-issues summary').first.click()
        check('case problem disclosure does not open inspector',not page.locator('#detailDialog').evaluate('(e)=>e.open'))
        page.locator('[data-page="runs"]').first.click();page.wait_for_timeout(100)
        for rid in [j['run_id'] for j in original['jobs']]:
            page.locator('#runsList [data-open-run="'+rid+'"]').click()
            page.wait_for_function("document.querySelector('#savedRunMeta').textContent.includes('"+rid+"') && !document.querySelector('#savedRunTitle').textContent.includes('Loading')")
            check('saved run opens '+rid[-6:],'Could not' not in page.locator('#savedRunTitle').inner_text())
            page.locator('[data-page="runs"]').first.click();page.wait_for_timeout(50)
        def submit(raw=False):
            page.locator('[data-page="new"]').first.click();page.wait_for_timeout(60)
            page.locator('#referenceConfirmed').check();page.locator('#consent').check()
            if raw:page.locator('input[name="cleaningMode"][value="raw"]').check()
            page.locator('#runButton').click()
        submit(raw=True)
        page.wait_for_function("document.querySelector('#detailDialog').open",timeout=10000)
        check('single job auto-opens its own inspector','run_navigation1' in page.locator('#detailMeta').inner_text())
        check('completion preserves no-cleaning selection',page.locator('#detailScoreView').input_value()=='raw')
        n=len([r for r in db.events if r[1]=='/api/results/run_navigation1/case_001'])
        page.wait_for_timeout(2100)
        check('completion is handled only once',len([r for r in db.events if r[1]=='/api/results/run_navigation1/case_001'])==n)
        page.locator('#closeDetail').click()
        db.next_status='partial';submit();page.wait_for_function("document.querySelector('#detailDialog').open",timeout=10000)
        check('partial job opens saved success and failure',page.locator('#detailModel option').count()==2 and 'partial' in page.locator('#detailMeta').inner_text())
        page.locator('#closeDetail').click()
        db.next_status='failed';submit();page.wait_for_function("document.querySelector('#detailDialog').open",timeout=10000)
        check('failed job opens its actual error','Audio failed' in page.locator('#detailContent').inner_text())
        page.locator('#closeDetail').click()
        db.batch=True;submit();page.wait_for_function("!document.querySelector('#page-run').classList.contains('hidden') && document.querySelector('#runCaseCount').textContent==='2'",timeout=10000)
        check('batch opens run list without wrong single inspector',not page.locator('#detailDialog').evaluate('(e)=>e.open'))
        page.wait_for_timeout(100)
        box=page.locator('#runCasesBody .audio-case').first.bounding_box()
        check('batch result is visible without manual scrolling',0 <= box['y'] and box['y']+box['height'] <= 1100)
        db.hold=True;submit()
        page.wait_for_function("!document.querySelector('#jobProgress').classList.contains('hidden')")
        page.locator('[data-page="new"]').first.click();page.locator('#caseTitle').fill('Do not interrupt my form')
        db.hold=False
        page.wait_for_function("!document.querySelector('#completionNotice').classList.contains('hidden')",timeout=10000)
        check('completion does not interrupt a new form',page.locator('#caseTitle').input_value()=='Do not interrupt my form' and page.locator('#page-new').is_visible())
        page.locator('#openCompletedRun').click();page.wait_for_function("document.querySelector('#detailDialog').open")
        check('completion notice opens the finished run','run_navigation5' in page.locator('#detailMeta').inner_text())
        page.locator('#closeDetail').click()
        # Verify that the completion was consumed; browser navigation is blocked.
        check('pending follow consumed from session storage',page.evaluate("sessionStorage.getItem('asr-follow-run')===null"))
        page.locator('[data-page="overview"]').first.click();page.wait_for_timeout(150)
        check('old terminal history never auto-opens',not page.locator('#detailDialog').evaluate('(e)=>e.open'))
        # Narrow screen: screenshot actual report data, not the synthetic jobs.
        page.set_viewport_size({'width':390,'height':844})
        page.locator('[data-jump="modelSummarySection"]').click();page.wait_for_timeout(100)
        check('mobile has no page-wide horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
        check('mobile scorecard is readable width',page.locator('.model-scorecard').first.bounding_box()['width']>270)
        page.screenshot(path=str(EVID/'mobile.png'))
        page.locator('#themeToggle').evaluate('(e)=>e.click()');page.wait_for_timeout(50);page.screenshot(path=str(EVID/'dark_mobile.png'))
        check('no uncaught JavaScript errors',not errors)
    finally:
        (EVID/'checks.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'http':'set_content with injected fetch/storage bridge, because browser navigation was blocked. Actual Jinja, CSS, JS and Python aggregation. No live Flask or ASR.'},indent=2),'utf-8')
        browser.close()
