import os, hmac, base64, binascii, subprocess, shutil, threading, re
from datetime import timedelta
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from . import core, provider, recognition, label_image, vision, variants, board

load_dotenv(core.ROOT/'.env')
app=FastAPI(title='CardFlip Local',docs_url=None,redoc_url=None,openapi_url=None)
lookup_lock=threading.Lock()

def auth(x_local_token: str=Header(default='')):
    secret=os.getenv('LOCAL_TOKEN','')
    if len(secret)<24 or not hmac.compare_digest(x_local_token,secret): raise HTTPException(401,'Invalid local token. Set it in the sidebar using the value in .env.')

class Card(BaseModel):
    year:str=Field(pattern=r'^\d{4}$')
    player:str=Field(min_length=2,max_length=80)
    set:str=Field(min_length=2,max_length=80)
    number:str=Field(default='',pattern=r'^[A-Za-z0-9-]{0,20}$')
    print_run:str=Field(default='',pattern=r'^$|^[1-9][0-9]{0,5}$')
    variant:str=Field(min_length=2,max_length=80)
    grader:Literal['PSA','BGS','SGC','CGC','RAW']
    grade:Literal['','1','1.5','2','2.5','3','3.5','4','4.5','5','5.5','6','6.5','7','7.5','8','8.5','9','9.5','10']=''
    grade_type:Literal['','Pristine','Gem Mint','Perfect','Black Label']=''
    @model_validator(mode='after')
    def grade_designation(self):
        if self.number.lower() in ('rc','rookie','na'): raise ValueError('RC is not a checklist number. Leave unknown numbers blank.')
        if self.grader=='RAW':
            if self.grade or self.grade_type: raise ValueError('Raw cards must not have a grade.')
            if not self.number and not self.print_run and self.variant!='Unknown': raise ValueError('Provide checklist number, or exact edition and print run for a conditional raw lookup.')
        elif not self.grade or not self.number: raise ValueError('Graded cards require checklist number and grade.')
        required={'CGC':{'Pristine','Gem Mint','Perfect'},'BGS':{'Pristine','Black Label'},'SGC':{'Pristine','Gem Mint'}}
        if self.grader in required and self.grade=='10':
            if self.grade_type not in required[self.grader]: raise ValueError('Confirm the exact grade designation before looking up a non-PSA 10.')
        elif self.grade_type: raise ValueError('Grade designation applies only to supported non-PSA 10 grades.')
        return self
    @field_validator('player','set','variant',mode='before')
    @classmethod
    def trim(cls,v): return v.strip() if isinstance(v,str) else v
class Lookup(BaseModel):
    card:Card
    refresh:bool=False
    demo:bool=False
class Settings(BaseModel):
    bid:float=Field(default=0,ge=0,le=1000000,allow_inf_nan=False)
    inbound:float=Field(default=2,ge=0,le=1000,allow_inf_nan=False)
    outbound:float=Field(default=5,ge=0,le=1000,allow_inf_nan=False)
    purchase_tax:float=Field(default=7,ge=0,le=100,allow_inf_nan=False)
    buyer_tax:float=Field(default=7,ge=0,le=100,allow_inf_nan=False)
    fee:float=Field(default=13.25,ge=0,le=100,allow_inf_nan=False)
    order_fee:float=Field(default=.4,ge=0,le=100,allow_inf_nan=False)
    min_profit:float=Field(default=5,ge=0,le=1000000,allow_inf_nan=False)
    min_roi:float=Field(default=25,ge=0,le=10000,allow_inf_nan=False)
    haircut:float=Field(default=5,ge=0,le=100,allow_inf_nan=False)
class FamilyLookup(BaseModel):
    card:Card
    settings:Settings=Field(default_factory=Settings)
    refresh:bool=False
class BoardCard(BaseModel):
    player:str=Field(min_length=2,max_length=80)
    year:str=Field(default='',pattern=r'^$|^\d{4}$')
    set:str=Field(default='',max_length=80)
    number:str=Field(default='',pattern=r'^[A-Za-z0-9-]{0,20}$')
    @model_validator(mode='after')
    def validate_number(self):
        if self.number and not any(c.isdigit() for c in self.number): self.number=''
        return self
class BoardLookup(BaseModel):
    card:BoardCard
    settings:Settings=Field(default_factory=Settings)
    refresh:bool=False

class Remember(BaseModel):
    card:Card
    cert:str=Field(pattern=r'^[A-Za-z0-9-]{5,32}$')
    confirmed:Literal[True]
class Evaluate(BaseModel):
    key:str=Field(max_length=1500)
    selected:list[str]=Field(max_length=240)
    settings:Settings
    preview:bool=False
class LabelText(BaseModel):
    text:str=Field(max_length=4000)
class OCR(BaseModel):
    image:str=Field(max_length=7_000_000)
class Vision(OCR):
    mode:Literal['fast','detail']='fast'

class VisualCompare(OCR):
    reference:str=Field(max_length=7_000_000)
    variant:str=Field(default='',max_length=80)

def result(key,payload,fetched,origin,notice=''):
    return {'key':key,'rows':payload['rows'],'source':payload['source'],'origin':origin,'fetched':fetched,'age_hours':round(core.age_hours(fetched),2),'stale':core.age_hours(fetched)>24,'notice':notice,'used':core.used(),'limit':core.budget()}

@app.get('/api/status',dependencies=[Depends(auth)])
def status(): return {'version':'0.9.4','key_configured':bool(os.getenv('COMPSAPI_KEY','').strip()),'used':core.used(),'limit':core.budget(),'ocr_available':bool(shutil.which('tesseract'))}

@app.post('/api/lookup',dependencies=[Depends(auth)])
def lookup(req:Lookup):
    card=req.card.model_dump();
    if card['variant']=='Unknown': raise HTTPException(422,'Use variant discovery for unresolved identities.')
    if not card['grade_type']: card.pop('grade_type')
    if not card['print_run']: card.pop('print_run')
    key=('demo:' if req.demo else 'live:')+core.cache_key(card)
    with lookup_lock:
        old=core.get_cache(key)
        if req.demo:
            rows=[{'id':f'demo-{i}','title':f"DEMO • {card['year']} {card['player']} {card['set']} #{card['number']} {card['variant']} {card['grader']} {card['grade']}",'price':price,'shipping':0,'date':(core.now()-timedelta(days=i*2)).isoformat(),'url':'','flags':['Synthetic example']} for i,price in enumerate([55,61,60,58,62,57,65,59,60,64],1)]
            payload={'source':'demo','rows':rows}; fetched=core.put_cache(key,payload)
            return result(key,payload,fetched,'demo')
        if old and not req.refresh and core.age_hours(old[1])<=24: return result(key,*old,'cache')
        family=None if card.get('print_run') or re.search(core.SPECIAL,core.norm(card['variant'])) else core.get_cache(variants.family_key(card))
        if family and not req.refresh and core.age_hours(family[1])<=24:
            rows=variants.exact_rows(family[0]['items'],card)
            if rows:
                payload={'source':'compsapi','rows':rows}; core.put_cache(key,payload,family[1])
                return result(key,payload,family[1],'family cache','Derived from broad search; review exact matches.')
            return result(key,{'source':'compsapi','rows':[]},core.put_cache(key,{'source':'compsapi','rows':[]},family[1]),'family cache','No classified matches. Force refresh for a targeted search if needed.')
        if not req.refresh:
            mixed=core.get_cache(board.key(card)) or core.get_cache(board.key(dict(card,number='')))
            if mixed and core.age_hours(mixed[1])<=24:
                rows=core.matches(mixed[0]['items'],card)
                if rows:
                    payload={'source':'compsapi','rows':rows};core.put_cache(key,payload,mixed[1])
                    return result(key,payload,mixed[1],'price board cache','Review exact matches from the mixed-grade search.')
        try:
            if not os.getenv('COMPSAPI_KEY','').strip(): raise RuntimeError('No API key configured. Add COMPSAPI_KEY to .env and restart.')
            core.reserve(); items=provider.fetch(card)
            payload={'source':'compsapi','rows':core.matches(items,card)}; fetched=core.put_cache(key,payload)
            return result(key,payload,fetched,'provider')
        except RuntimeError as e:
            if old: return result(key,*old,'cache',str(e))
            raise HTTPException(503,str(e))

@app.post('/api/family',dependencies=[Depends(auth)])
def family_lookup(req:FamilyLookup):
    card=req.card.model_dump(); card.pop('print_run',None) if not card['print_run'] else None; key=variants.family_key(card)
    if card['variant']!='Unknown':raise HTTPException(422,'Family lookup expects an unresolved variant.')
    notice=''; origin='cache'
    with lookup_lock:
        old=core.get_cache(key)
        if old and not req.refresh and core.age_hours(old[1])<=24:payload,fetched=old
        else:
            try:
                if not os.getenv('COMPSAPI_KEY','').strip():raise RuntimeError('No API key configured.')
                core.reserve(); items=provider.fetch(card,broad=True)
                payload={'items':items};fetched=core.put_cache(key,payload);origin='provider'
            except RuntimeError as e:
                if not old:raise HTTPException(503,str(e))
                payload,fetched=old;notice=str(e)
    result_groups=[]
    for name,rows in variants.groups(payload['items'],card).items():
        r=core.calculate(rows,req.settings.model_dump(),fetched,'compsapi')
        usable=bool(card['number']) and r['recommendation'] in ('BUY CANDIDATE','PASS') and r['max_bid'] is not None
        result_groups.append({'variant':name,'count':r['count'],'last30_sample':r['last30_sample'],'median':r['median'] if card['number'] else None,'max_bid':r['max_bid'] if usable else None,'sample_titles':[row['title'] for row in rows[:3]]})
    result_groups.sort(key=lambda g:(g['variant'] not in ('Base','Unspecified'),-g['count'],g['variant']))
    return {'groups':result_groups,'origin':origin,'fetched':fetched,'stale':core.age_hours(fetched)>24,'used':core.used(),'limit':core.budget(),'notice':notice,'recommendation':'VERIFY VARIANT — PASS','reason':('Checklist number unknown: possible sold titles only. Different cards may be mixed; confirm the number before pricing.' if not card['number'] else 'Groups are title-derived possibilities, not exhaustive. No safe maximum bid until identity is confirmed.')}

@app.post('/api/board',dependencies=[Depends(auth)])
def price_board(req:BoardLookup):
    card=req.card.model_dump(); key=board.key(card); origin='cache'; notice=''
    with lookup_lock:
        old=core.get_cache(key)
        if old and not req.refresh and core.age_hours(old[1])<=24: payload,fetched=old
        else:
            try:
                if not os.getenv('COMPSAPI_KEY','').strip():raise RuntimeError('No API key configured.')
                core.reserve();items=provider.fetch_board(card);payload={'items':items};fetched=core.put_cache(key,payload);origin='provider'
            except RuntimeError as e:
                if not old:raise HTTPException(503,str(e))
                payload,fetched=old;notice=str(e)
    output=board.build(payload['items'],card,req.settings.model_dump(),fetched)
    return dict(output,origin=origin,fetched=fetched,stale=core.age_hours(fetched)>24,used=core.used(),limit=core.budget(),notice=notice,retrieved=len(payload['items']))

@app.post('/api/remember',dependencies=[Depends(auth)])
def remember(req:Remember):
    card=req.card.model_dump(); card.pop('print_run',None) if not card['print_run'] else None
    if card['grader']=='RAW' or card.get('print_run'):raise HTTPException(422,'Only standard graded slabs can be remembered.')
    if core.norm(card['variant']) in ('unknown','unspecified','none') or re.search(core.SPECIAL,core.norm(card['variant'])):raise HTTPException(422,'Confirm an exact supported variant first.')
    key=variants.memory_key(card['grader'],req.cert)
    core.put_cache(key,{'card':card,'source':'user-confirmed'})
    return {'saved':True}

def json_from_key(key):
    import json
    try:return json.loads(key.split(':',1)[1])
    except (ValueError,TypeError):return {}

@app.post('/api/evaluate',dependencies=[Depends(auth)])
def evaluate(req:Evaluate):
    if not req.key.startswith(('live:','demo:')): raise HTTPException(404,'Lookup first.')
    saved=core.get_cache(req.key)
    if not saved: raise HTTPException(404,'Lookup first.')
    payload,fetched=saved; ids=set(req.selected)
    rows=payload['rows'] if req.preview else [r for r in payload['rows'] if r['id'] in ids]
    output=core.calculate(rows,req.settings.model_dump(),fetched,payload['source'])
    card=json_from_key(req.key)
    if card.get('grader')=='raw' and not card.get('number') and output['recommendation'] in ('BUY CANDIDATE','PASS'):
        output.update(recommendation='REVIEW — PASS',reason='Checklist number unknown. Conditional raw edition estimate; verify exact card before bidding.')
    if req.preview and output['recommendation'] in ('BUY CANDIDATE','PASS'):
        output.update(recommendation='PREVIEW — UNVERIFIED',reason='Title-filtered candidates only. Confirm exact listings before using this estimate to bid.')
    return output

@app.post('/api/parse-label',dependencies=[Depends(auth)])
def parse_label(req:LabelText): return recognition.parse_label(req.text)

@app.get('/api/vision-status',dependencies=[Depends(auth)])
def vision_status(): return {'models':vision.available()}

@app.post('/api/vision',dependencies=[Depends(auth)])
def vision_scan(req:Vision):
    try: data=base64.b64decode(req.image,validate=True)
    except (ValueError,binascii.Error): raise HTTPException(400,'Invalid image encoding.')
    if len(data)>5_000_000 or not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')): raise HTTPException(400,'Choose PNG or JPEG under 5 MB.')
    try: return variants.recall(vision.scan(data,req.mode))
    except RuntimeError as e: raise HTTPException(503,str(e))
    except (ValueError,OSError) as e: raise HTTPException(422,str(e))

@app.post('/api/visual-compare',dependencies=[Depends(auth)])
def visual_compare(req:VisualCompare):
    images=[]
    for encoded in (req.image,req.reference):
        try: data=base64.b64decode(encoded,validate=True)
        except (ValueError,binascii.Error): raise HTTPException(400,'Invalid image encoding.')
        if len(data)>5_000_000 or not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')): raise HTTPException(400,'Choose PNG or JPEG under 5 MB.')
        images.append(data)
    try:return vision.compare(*images,req.variant)
    except RuntimeError as e:raise HTTPException(503,str(e))
    except (ValueError,OSError) as e:raise HTTPException(422,str(e))

@app.post('/api/ocr',dependencies=[Depends(auth)])
def ocr(req:OCR):
    if not shutil.which('tesseract'): raise HTTPException(503,'Install Tesseract locally first (brew install tesseract).')
    try: data=base64.b64decode(req.image,validate=True)
    except (ValueError,binascii.Error): raise HTTPException(400,'Invalid image encoding.')
    if len(data)>5_000_000 or not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')): raise HTTPException(400,'Choose a PNG or JPEG under 5 MB.')
    try:
        return label_image.scan_label(data)
    except (ValueError, OSError, subprocess.SubprocessError): raise HTTPException(422,'OCR failed or timed out. Try a sharper, cropped image.')

app.mount('/',StaticFiles(directory=core.ROOT/'extension',html=True),name='ui')
