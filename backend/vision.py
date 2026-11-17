"""Local Ollama vision; models suggest identities, never prices or bids."""
import base64, hashlib, io, json, re, time
import requests
from PIL import Image, ImageOps
from . import core, recognition

MODELS={'fast':'qwen3.5:4b','detail':'qwen3.5:9b'}
URL='http://127.0.0.1:11434/api'
VERSION='v081-1'
KEYS=('p','s','y','m','t','n','v','g','d','gt','r','a','ps','c')
SCHEMA={'type':'object','properties':{k:{'type':['string','null']} for k in KEYS},'required':list(KEYS),'additionalProperties':False}
for k in ('r','a'): SCHEMA['properties'][k]={'type':['boolean','null']}
PROMPT='''Identify this sports trading card from the whole image. Return only compact JSON using keys: p player, s league (NBA/NFL/MLB or other), y year (first year of season), m manufacturer, t set without manufacturer, n checklist card number (not cert), v exact parallel/insert, g grader (PSA/CGC/BGS/SGC or other; RAW if visibly ungraded), d numeric grade as string, gt grade designation, r rookie, a autograph, ps print serial like 15/99, c slab certificate number. Unknown or uncertain fields null. Do not infer Base from an absent parallel. Card number, print serial, and certificate are distinct. RC is a rookie logo, never a checklist number. For visibly loose cards or cards in sleeves/toploaders, use RAW; a rigid sleeve alone is not a grading slab. If unsure whether graded, return null. Keep parallel words (Refractor, Silver, etc.) separate from product. Never guess a year from the player, and never label a shiny card Base without evidence. For non-PSA 10 distinguish Gem Mint, Pristine, Perfect and Black Label. Do not assume an unseen autograph or condition. No prices or commentary.'''

def session():
    s=requests.Session();s.trust_env=False;return s

def available():
    try:
        with session() as s:
            r=s.get(URL+'/tags',timeout=(.5,1));r.raise_for_status()
            names={x.get('name') for x in r.json().get('models',[]) if isinstance(x,dict)}
        return [m for m in MODELS.values() if m in names]
    except (requests.RequestException,ValueError,AttributeError,TypeError):return []

def image_bytes(data):
    with Image.open(io.BytesIO(data)) as src:
        if src.width*src.height>30_000_000: raise ValueError('Image exceeds 30 megapixels.')
        im=ImageOps.exif_transpose(src).convert('RGB'); im.thumbnail((1280,1280),Image.Resampling.LANCZOS)
        buf=io.BytesIO(); im.save(buf,format='JPEG',quality=92); return buf.getvalue()

def text(v,limit=80):
    if not isinstance(v,(str,int,float)) or isinstance(v,bool): return ''
    s=str(v).strip()
    if core.norm(s) in ('','none','null','unknown','not specified','n a','unspecified','not applicable'):return ''
    if len(s)>limit or any(ord(c)<32 for c in s):return ''
    return s

def normalize(raw):
    if not isinstance(raw,dict):raise ValueError('Expected a JSON object.')
    f={}; warnings=[]
    p=text(raw.get('p')); y=text(raw.get('y')); manufacturer=text(raw.get('m')); product=text(raw.get('t')); n=text(raw.get('n')).lstrip('# '); v=text(raw.get('v')); g=text(raw.get('g')).upper(); d=text(raw.get('d')); gt=core.norm(text(raw.get('gt')))
    if p and len(p)>=2:f['player']=p
    if re.fullmatch(r'(?:18|19|20)\d{2}(?:[-–]\d{2,4})?',y):f['year']=y[:4]
    if product and re.search(r'\s+refractor$',product,re.I):
        product=re.sub(r'\s+refractor$','',product,flags=re.I).strip()
        if not v or core.norm(v)=='base':
            v='';warnings.append('Product/parallel conflict (Refractor); confirm exact variant.')
    if product:
        full=product if not manufacturer or core.phrase(core.norm(product),manufacturer) else manufacturer+' '+product
        if len(full)<=80:f['set']=full
    if re.fullmatch(r'[A-Za-z0-9-]{1,20}',n) and core.norm(n) not in ('rc','rookie','rookie card','n a','na') :f['number']=n
    elif core.norm(n) in ('rc','rookie','rookie card'):warnings.append('RC is a rookie marker, not a checklist number.')
    cert=text(raw.get('c')); serial=text(raw.get('ps'))
    if re.fullmatch(r'\d{1,6}/[1-9]\d{0,5}',n):
        if not serial:serial=n
        f.pop('number',None)
        if serial!=n:warnings.append('Conflicting print serial readings; verify the edition.')
    if re.fullmatch(r'(?:\d{1,6})?/[1-9]\d{0,5}',serial):f['print_run']=serial.split('/')[1]
    if cert and n==cert:f.pop('number',None);warnings.append('Card number equals certificate number; verify.')
    if v and len(v)>=2 and core.norm(v) not in ('rookie','rookie card','rc'):f['variant']=v
    if g in ('PSA','CGC','BGS','SGC'):f['grader']=g
    if re.fullmatch(r'(?:[1-9](?:\.5)?|10(?:\.0)?)',d):f['grade']=d.removesuffix('.0')
    if g in ('CGC','BGS','SGC') and f.get('grade')=='10':
        mapping={'pristine':'Pristine','pristine 10':'Pristine','gem mint':'Gem Mint','gem mt':'Gem Mint','gem mint 10':'Gem Mint','perfect':'Perfect','perfect 10':'Perfect','black label':'Black Label','black label 10':'Black Label'}
        if gt in mapping:f['grade_type']=mapping[gt]
    if g=='RAW':
        f['grader']='RAW';f.pop('grade',None);warnings.append('Raw card: condition is unverified; compare raw sales only.')
    elif g not in ('PSA','CGC','BGS','SGC'):
        f.pop('grade',None);warnings.append('Grader unknown or unsupported; confirm whether raw.')
    if raw.get('a') is True or serial or (v and re.search(core.SPECIAL,core.norm(v))):warnings.append('Autograph, relic or numbered card: check exact edition before pricing.')
    if not f.get('variant'):warnings.append('Parallel not established; confirm exact variant before lookup.')
    keys=['year','player','set','number','variant','grader','grade']
    if g=='RAW':
        keys.remove('grade')
        if f.get('print_run') and f.get('variant'):keys.remove('number')
    missing=[k for k in keys if not f.get(k)]
    required={'CGC':{'Pristine','Gem Mint','Perfect'},'BGS':{'Pristine','Black Label'},'SGC':{'Pristine','Gem Mint'}}
    if g in required and f.get('grade')=='10' and f.get('grade_type') not in required[g]:f.pop('grade_type',None);missing.append('grade_type')
    league=core.norm(text(raw.get('s')))
    sport={'american football':'NFL','football':'Football (verify league)','nfl':'NFL','basketball':'Basketball','nba':'NBA','baseball':'Baseball','mlb':'MLB'}.get(league,text(raw.get('s')))
    return {'fields':f,'missing':missing,'warnings':warnings,'metadata':{'sport':sport,'rookie':raw.get('r') if isinstance(raw.get('r'),bool) else None,'autograph':raw.get('a') if isinstance(raw.get('a'),bool) else None,'print_serial':serial or None,'cert_number':cert or None,'grader':g or None},'auto_eligible':not missing and (g=='RAW' or not (raw.get('a') is True or serial or (v and re.search(core.SPECIAL,core.norm(v)))))}

def scan(data,mode='fast'):
    start=time.perf_counter();model=MODELS[mode];img=image_bytes(data)
    key='vision:'+VERSION+':'+model+':'+hashlib.sha256(img).hexdigest()
    old=core.get_cache(key)
    if old and core.age_hours(old[1])<24*30:
        return dict(old[0],cached=True,elapsed=round(time.perf_counter()-start,2))
    payload={'model':model,'think':False,'stream':False,'format':SCHEMA,'keep_alive':'15m','messages':[{'role':'user','content':PROMPT,'images':[base64.b64encode(img).decode()]}],'options':{'temperature':0,'num_predict':220,'num_ctx':4096}}
    try:
        with session() as s:
            res=s.post(URL+'/chat',json=payload,timeout=(2,15 if mode=='fast' else 90));res.raise_for_status();out=res.json()
    except requests.RequestException as e:raise RuntimeError('Local Ollama unavailable or model failed. Open Ollama, check ollama list, or use OCR.') from e
    if out.get('done_reason')=='length':raise ValueError('Vision output truncated. Retry in detailed mode or use OCR.')
    try:raw=json.loads(out['message']['content']);result=normalize(raw)
    except (KeyError,TypeError,ValueError) as e:raise ValueError('Invalid structured vision result. Retry or use OCR.') from e
    result.update(text=json.dumps(raw,indent=2),method=model+' · local vision',model=model,tokens=out.get('eval_count'),cached=False)
    # Do not store original photos; only structured suggestions.
    core.put_cache(key,result)
    return dict(result,elapsed=round(time.perf_counter()-start,2))

COMPARE_SCHEMA={'type':'object','properties':{'result':{'type':'string','enum':['similar','different','uncertain']},'evidence':{'type':'string'}},'required':['result','evidence'],'additionalProperties':False}
def compare(data,reference,variant=''):
    """User-supplied visual reference; never mutates recognition or valuation."""
    start=time.perf_counter(); images=[base64.b64encode(image_bytes(i)).decode() for i in (data,reference)]
    prompt=('Compare the trading cards in image 1 (target) and image 2 (reference). Compare artwork, border pattern, foil pattern, color, visible parallel text and print numbers; ignore holder, grade, background, glare and angle. A shared player is not sufficient. If finish cannot be determined from photos, choose uncertain. Return only JSON result (similar/different/uncertain) and short evidence. Never authenticate or estimate prices. Reference label supplied by user, not proof: '+json.dumps(variant))
    payload={'model':MODELS['detail'],'think':False,'stream':False,'format':COMPARE_SCHEMA,'keep_alive':'15m','messages':[{'role':'user','content':prompt,'images':images}],'options':{'temperature':0,'num_predict':180,'num_ctx':8192}}
    try:
        with session() as s:
            res=s.post(URL+'/chat',json=payload,timeout=(2,90));res.raise_for_status();out=res.json()
        raw=json.loads(out['message']['content'])
        if out.get('done_reason')=='length' or raw.get('result') not in ('similar','different','uncertain') or not isinstance(raw.get('evidence'),str):raise ValueError('Invalid comparison output.')
    except requests.RequestException as e:raise RuntimeError('Local detailed model unavailable. Check Ollama and qwen3.5:9b.') from e
    except (KeyError,TypeError,AttributeError,ValueError) as e:raise ValueError('Invalid comparison output; no visual match established.') from e
    return {'result':raw['result'],'evidence':raw['evidence'][:500],'elapsed':round(time.perf_counter()-start,2),'model':MODELS['detail'],'verified':False}
