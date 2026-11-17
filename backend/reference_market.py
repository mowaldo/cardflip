"""Opt-in active listing reference photos; never used as sold comps or saved as verified references."""
import base64, re, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
import requests
import cv2
from . import core, board, variants, visual_library as visual, embeddings

MAX_PHOTOS=10
MAX_BYTES=2_000_000

def image_url(value):
    if not isinstance(value,str) or len(value)>1000:return None
    try:
        u=urlsplit(value)
        if u.scheme!='https' or u.hostname!='i.ebayimg.com' or u.port not in (None,443) or u.username or u.password or not u.path.startswith('/images/'):return None
    except ValueError:return None
    return value

def candidates(items,card):
    groups=defaultdict(list);seen=set()
    for item in items:
        if not isinstance(item,dict):continue
        title=str(item.get('title',''));t=core.norm(title);id=str(item.get('item_id',''))
        if not id.isdigit() or id in seen or re.search(core.JUNK,t):continue
        if any(not core.phrase(t,card[k]) for k in ('player','year','set')):continue
        if core.norm(board.number_for(item))!=core.norm(card['number']):continue
        variant=variants.group_name(dict(item,title=board.clean_season(title)),card)
        if not variant:continue
        url=image_url(item.get('image'))
        if not url:continue
        seen.add(id);groups[variant].append({'id':id,'number':card['number'],'variant':variant,'title':title[:300],'image':url,'url':'https://www.ebay.com/itm/'+id})
    # One per variant first, then a second example if space remains.
    result=[]
    for i in range(2):
        for rows in groups.values():
            if i<len(rows):result.append(rows[i])
    return result[:MAX_PHOTOS]

def download(url):
    if not image_url(url):return None
    try:
        with requests.get(url,headers={'User-Agent':'CardFlipLocal/1.0.2'},stream=True,allow_redirects=False,timeout=(2,3)) as r:
            if r.status_code!=200 or r.headers.get('Content-Type','').split(';')[0].lower() not in ('image/jpeg','image/png'):return None
            data=bytearray();start=time.monotonic()
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data)>MAX_BYTES or time.monotonic()-start>5:return None
            return bytes(data)
    except requests.RequestException:return None

def rank(card,data,items):
    start=time.perf_counter();target,cropped=visual.isolate(visual.read_image(data));features=visual.features(target)
    rows=candidates(items,card)
    def match(row):
        try:
            raw=download(row['image'])
            if not raw:return None
            im,_=visual.isolate(visual.read_image(raw));score,inliers=visual.similarity(features,visual.features(im))
            ref=im;h,w=im.shape[:2];scale=min(1,220/max(h,w));im=cv2.resize(im,(max(1,round(w*scale)),max(1,round(h*scale))))
            return (dict({k:v for k,v in row.items() if k!='image'},score=score,inliers=inliers,thumbnail=base64.b64encode(visual.jpeg(im)).decode()),ref)
        except (ValueError,OSError,cv2.error):return None
    with ThreadPoolExecutor(max_workers=5) as pool:pairs=[r for r in pool.map(match,rows) if r]
    matches=[r[0] for r in pairs];engine=embeddings.rerank(target,[r[1] for r in pairs],matches)
    matches.sort(key=lambda x:x['score'],reverse=True)
    return {'matches':matches,'count':len(matches),'attempted':len(rows),'elapsed':round(time.perf_counter()-start,2),'cropped':cropped,'verified':False,'engine':engine}
