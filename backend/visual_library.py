"""Opt-in local reference photos. Similarity is a heuristic, never an identity assertion."""
import base64, hashlib, io, time
import cv2
import numpy as np
from PIL import Image, ImageOps
from . import core, embeddings

LIMIT=250
PER_FAMILY=24


def read_image(data):
    with Image.open(io.BytesIO(data)) as src:
        if src.width*src.height>24_000_000: raise ValueError('Image too large.')
        im=ImageOps.exif_transpose(src).convert('RGB')
        if min(im.size)<80: raise ValueError('Photo is too small for matching.')
        im.thumbnail((1000,1000),Image.Resampling.LANCZOS)
        return cv2.cvtColor(np.asarray(im),cv2.COLOR_RGB2BGR)


def isolate(im):
    """Try a prominent portrait quadrilateral; keep original if ambiguous."""
    h,w=im.shape[:2]; area=h*w
    gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    edge=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),45,135)
    edge=cv2.morphologyEx(edge,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    contours,_=cv2.findContours(edge,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    options=[]
    for c in sorted(contours,key=cv2.contourArea,reverse=True)[:30]:
        a=cv2.contourArea(c)
        if not .14*area<=a<=.94*area:continue
        q=cv2.approxPolyDP(c,.022*cv2.arcLength(c,True),True)
        if len(q)!=4 or not cv2.isContourConvex(q):continue
        p=q.reshape(4,2).astype('float32'); s=p.sum(1); d=np.diff(p,axis=1).ravel()
        ordered=np.array([p[s.argmin()],p[d.argmin()],p[s.argmax()],p[d.argmax()]],np.float32)
        if len(np.unique(ordered,axis=0))!=4:continue
        tl,tr,br,bl=ordered
        ww=(np.linalg.norm(tr-tl)+np.linalg.norm(br-bl))/2
        hh=(np.linalg.norm(bl-tl)+np.linalg.norm(br-tr))/2
        if hh<100 or not .48<=ww/hh<=.83:continue
        u,v=tr-tl,bl-tl
        if abs(u[0]*v[1]-u[1]*v[0])<.65*ww*hh:continue
        options.append((a,ordered,ww,hh))
    if not options:return im,False
    options.sort(key=lambda x:x[0],reverse=True)
    a,q,ww,hh=options[0]
    # Multiple similarly sized, spatially distinct rectangles are ambiguous.
    if any(b>.65*a and np.linalg.norm(q.mean(0)-r.mean(0))>.12*min(h,w) for b,r,_,_ in options[1:]):return im,False
    W=round(ww);H=round(hh)
    dst=np.array([[0,0],[W-1,0],[W-1,H-1],[0,H-1]],np.float32)
    return cv2.warpPerspective(im,cv2.getPerspectiveTransform(q,dst),(W,H)),True


def jpeg(im):
    ok,buf=cv2.imencode('.jpg',im,[cv2.IMWRITE_JPEG_QUALITY,85]);
    if not ok:raise ValueError('Cannot encode photo.')
    return buf.tobytes()


def features(im):
    im=cv2.resize(im,(320,448),interpolation=cv2.INTER_AREA)
    gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    kp,desc=cv2.ORB_create(nfeatures=600).detectAndCompute(gray,None)
    pts=np.array([k.pt for k in kp],dtype=np.float32)
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    hs=[]
    for y in range(3):
        for x in range(3):
            tile=hsv[y*448//3:(y+1)*448//3,x*320//3:(x+1)*320//3]
            hist=cv2.calcHist([tile],[0,1],None,[12,8],[0,180,0,256]);cv2.normalize(hist,hist,alpha=1,norm_type=cv2.NORM_L1);hs.append(hist)
    return pts,desc,hs


def similarity(a,b):
    ap,ad,ah=a;bp,bd,bh=b
    color=float(np.mean([cv2.compareHist(x,y,cv2.HISTCMP_INTERSECT) for x,y in zip(ah,bh)]))
    inliers=0; geometry=0.
    if ad is not None and bd is not None and len(bd)>=2:
        pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(ad,bd,k=2)
        good=[p[0] for p in pairs if len(p)==2 and p[0].distance<.75*p[1].distance]
        if len(good)>=8:
            _,mask=cv2.findHomography(np.float32([ap[m.queryIdx] for m in good]),np.float32([bp[m.trainIdx] for m in good]),cv2.RANSAC,5)
            if mask is not None:
                inliers=int(mask.sum());geometry=min(1.,inliers/45)*inliers/len(good)
    return round(.65*geometry+.35*color,4),inliers


def family(card):
    if not all(core.norm(card.get(k,'')) for k in ('player','year','set')):raise ValueError('Confirm player, year and product before using references.')
    return core.cache_key({k:card[k] for k in ('player','year','set')})


def table(c):
    c.execute('CREATE TABLE IF NOT EXISTS visual_refs (id TEXT PRIMARY KEY, family TEXT NOT NULL, number TEXT NOT NULL, variant TEXT NOT NULL, photo BLOB NOT NULL, created TEXT NOT NULL)')


def add(card,variant,data):
    key=family(card);number=core.norm(card.get('number',''));variant=variant.strip()
    if not number or not any(ch.isdigit() for ch in number):raise ValueError('Confirm the checklist number before saving a reference.')
    if not variant or core.norm(variant) in ('unknown','unspecified','none','rc','rookie'):raise ValueError('Confirm an exact variant before saving.')
    photo=jpeg(read_image(data));rid=hashlib.sha256(key.encode()+b'\0'+number.encode()+b'\0'+core.norm(variant).encode()+b'\0'+photo).hexdigest()
    with core.connection() as c:
        table(c)
        if c.execute('SELECT 1 FROM visual_refs WHERE id=?',(rid,)).fetchone():return {'id':rid,'duplicate':True}
        if c.execute('SELECT count(*) FROM visual_refs').fetchone()[0]>=LIMIT or c.execute('SELECT count(*) FROM visual_refs WHERE family=?',(key,)).fetchone()[0]>=PER_FAMILY:raise ValueError('Reference library limit reached. Delete an old reference first.')
        c.execute('INSERT INTO visual_refs VALUES (?,?,?,?,?,?)',(rid,key,number,variant,photo,core.stamp()))
    return {'id':rid,'duplicate':False}


def delete(rid):
    with core.connection() as c:
        table(c);return bool(c.execute('DELETE FROM visual_refs WHERE id=?',(rid,)).rowcount)


def rank(card,data):
    start=time.perf_counter();key=family(card);number=core.norm(card.get('number',''))
    with core.connection() as c:
        table(c);rows=c.execute('SELECT * FROM visual_refs WHERE family=? AND (? = \'\' OR number=?)',(key,number,number)).fetchall()
    if not rows:return {'matches':[],'count':0,'elapsed':0,'cropped':False,'verified':False}
    im,cropped=isolate(read_image(data));target=features(im)
    results=[]; references=[]
    for r in rows:
        ref,_=isolate(read_image(r['photo']));score,inliers=similarity(target,features(ref));references.append(ref)
        # Thumbnail only. No external network requests; no change to price board.
        thumb=ref.copy();h,w=thumb.shape[:2];scale=min(1,200/max(h,w));thumb=cv2.resize(thumb,(max(1,round(w*scale)),max(1,round(h*scale))))
        results.append({'id':r['id'],'number':r['number'],'variant':r['variant'],'score':score,'inliers':inliers,'thumbnail':base64.b64encode(jpeg(thumb)).decode()})
    engine=embeddings.rerank(im,references,results)
    results.sort(key=lambda x:x['score'],reverse=True)
    return {'matches':results,'count':len(rows),'elapsed':round(time.perf_counter()-start,2),'cropped':cropped,'verified':False,'engine':engine}
