"""Local multi-region OCR for graded sports cards."""
import io
import re
import os
import subprocess
import time
import cv2
import numpy as np
from PIL import Image, ImageOps
from .recognition import parse_label


def label_box(image):
    """Find a red, wide PSA-style label. Return None if localization is ambiguous."""
    h,w=image.shape[:2]
    scale=min(1.,1000/max(h,w))
    small=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA) if scale<1 else image
    hsv=cv2.cvtColor(small,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,(0,70,65),(12,255,255)) | cv2.inRange(hsv,(165,70,65),(180,255,255))
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(5,3)))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    H,W=small.shape[:2]; candidates=[]
    for c in contours:
        x,y,bw,bh=cv2.boundingRect(c)
        if bw<50 or bh<12 or not 2.2<=bw/bh<=6.5 or bw<W*.12: continue
        if y+bh>H*.70: continue
        # A label is a rectangular border, not simply a red patch.
        if cv2.contourArea(c)<.12*bw*bh: continue
        candidates.append((bw*bh,(x,y,bw,bh)))
    candidates.sort(reverse=True)
    if not candidates or (len(candidates)>1 and candidates[1][0]>.60*candidates[0][0]): return None
    x,y,bw,bh=candidates[0][1]
    return tuple(round(v/scale) for v in (x,y,bw,bh))


def _read(region,deadline,psm=6,digits=False):
    if region.size==0: return ''
    gray=cv2.cvtColor(region,cv2.COLOR_BGR2GRAY) if region.ndim==3 else region
    factor=min(4.,1600/max(gray.shape)) if digits else min(6., max(1.,1000/max(gray.shape)),2200/max(gray.shape))
    if factor!=1: gray=cv2.resize(gray,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA if factor<1 else (cv2.INTER_NEAREST if digits else cv2.INTER_CUBIC))
    gray=cv2.copyMakeBorder(gray,16,16,16,16,cv2.BORDER_CONSTANT,value=255)
    ok,png=cv2.imencode('.png',gray)
    if not ok: return ''
    remaining=deadline-time.monotonic()
    if remaining<=0: raise subprocess.TimeoutExpired('tesseract',0)
    proc=subprocess.run(['tesseract','stdin','stdout','--psm',str(psm)]+(['-c','tessedit_char_whitelist=0123456789'] if digits else []),input=png.tobytes(),capture_output=True,timeout=remaining,check=True,env={**os.environ,'OMP_THREAD_LIMIT':'2'})
    return proc.stdout.decode('utf-8',errors='replace').strip()


def scan_label(data):
    deadline=time.monotonic()+18
    with Image.open(io.BytesIO(data)) as original:
        if original.width*original.height>24_000_000: raise ValueError('Image too large; choose a smaller photo.')
        image=cv2.cvtColor(np.asarray(ImageOps.exif_transpose(original).convert('RGB')),cv2.COLOR_RGB2BGR)
    box=label_box(image)
    if box is None:
        h,w=image.shape[:2]
        if 2.1<=w/h<=7:
            result=parse_label(_read(image,deadline));result['method']='Cropped label';return result
        return scan_general(image,deadline)
    x,y,w,h=box
    def crop(a,b,c,d):return image[y+int(h*b):y+int(h*d),x+int(w*a):x+int(w*c)]
    # PSA's left column is card identity; right column is card number and grade.
    left=_read(crop(.045,.07,.72,.65),deadline)
    right=_read(crop(.68,.05,.96,.76),deadline)
    result=parse_label(left+'\n'+right)
    # A second pass can recover text spanning the columns. Never override a conflicting read.
    if any(k not in result['fields'] for k in ('year','player','set','number','grader','grade')):
        whole=_read(crop(.035,.07,.965,.80),deadline)
        other=parse_label(whole)
        for k,v in other['fields'].items():
            if k not in result['fields'] and k not in ('player','variant'):result['fields'][k]=v
            elif k in result['fields'] and result['fields'][k]!=v:result['fields'].pop(k)
        result['missing']=[k for k in ('year','player','set','number','variant','grader','grade') if k not in result['fields']]
    result['method']='Red label detected · separate identity and grade columns'
    if result['fields'].get('grader') not in ('PSA',None) or _score(result)<6:
        try:
            fallback=scan_general(image,deadline)
            if _score(fallback)>_score(result):return fallback
        except subprocess.SubprocessError:pass
    return _finish(result)


CORE=('year','player','set','number','grader','grade')

def _score(r):
    return sum(k in r['fields'] for k in CORE)

def _finish(r):
    r['missing']=[k for k in (*CORE,'variant') if k not in r['fields']]
    if r['fields'].get('grade')=='10' and r['fields'].get('grader') in ('CGC','BGS','SGC') and 'grade_type' not in r['fields']:r['missing'].append('grade_type')
    return r

def _gold_box(image):
    # Locate a broad light-gold CGC identity panel; do not use this to infer a grader.
    h,w=image.shape[:2];scale=min(1.,1000/max(h,w));a=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA) if scale<1 else image
    H,W=a.shape[:2];hsv=cv2.cvtColor(a[:int(.40*H)],cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,(12,20,150),(45,255,255));mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);boxes=[]
    for c in contours:
        x,y,bw,bh=cv2.boundingRect(c)
        if bw>=.13*W and bh>=.025*H and 1.5<=bw/bh<=5 and cv2.contourArea(c)>=.45*bw*bh:boxes.append((bw*bh,(x,y,bw,bh)))
    if not boxes:return None
    return tuple(round(v/scale) for v in max(boxes)[1])

def scan_general(image,deadline):
    """Full photo + focused label/grade reads. Prefer coherent label identity, not random art text."""
    h,w=image.shape[:2]
    if np.std(image)<2:return dict(parse_label(''),method='No readable detail')
    def crop(x,y,X,Y):return image[max(0,int(y)):min(h,int(Y)),max(0,int(x)):min(w,int(X))]
    top=_read(crop(0,0,w,.34*h),deadline)
    candidates=[parse_label(top)]
    gold=_gold_box(image)
    if gold:
        x,y,bw,bh=gold
        # Read brand header above the gold rectangle and the identity area inside it.
        header=_read(crop(x-.06*bw,y-.45*bh,x+1.42*bw,y),deadline)
        identity=_read(crop(x+.015*bw,y+.015*bh,x+.97*bw,y+.63*bh),deadline)
        brand_text=header+'\n'+top
        # The full company name is a useful fallback when the small CGC logo OCR is noisy.
        brand=bool(re.search(r'\bCGC\b|CERTIFIED GUARANTY COMPAN[YV]',brand_text,re.I))
        if brand:
            # Gold numerals on dark background: isolate yellow strokes and read only the grade panel.
            badge=crop(x+1.0*bw,y+.23*bh,x+1.33*bw,y+.94*bh)
            hsv=cv2.cvtColor(badge,cv2.COLOR_BGR2HSV) if badge.size else None
            grade_text=''
            if hsv is not None:
                yellow=255-cv2.inRange(hsv,(9,25,90),(45,255,255))
                grade_text=_read(yellow,deadline,7,digits=True)
            # CGC explicitly uses a gold label for Pristine 10. Still present as a suggestion requiring review.
            grade='CGC PRISTINE 10' if re.fullmatch(r'\s*\(?10\)?\s*',grade_text) else 'CGC'
            r=parse_label(identity+'\n'+grade)
            if grade=='CGC PRISTINE 10':r['warnings'].append('Pristine 10 suggested from CGC gold label and grade numeral; verify the designation.')
            r['method']='CGC gold label · identity and grade regions';candidates.append(r)
    # Whole image context (including card face) is kept for review. Only use it as an
    # identity candidate when a coherent identity is present; do not merge conflicting names.
    if max(map(_score,candidates))<6:
        center=_read(crop(.12*w,0,.88*w,.34*h),deadline)
        candidates.append(parse_label(center))
    try:full=_read(image,deadline,11)
    except subprocess.SubprocessError:full=''
    whole=parse_label(full)
    if max(map(_score,candidates))<4 and _score(whole)>=4:candidates.append(whole)
    best=max(candidates,key=_score)
    # Avoid substituting artwork for a trusted grade/variant. A partially read label is safer than a guess.
    best['method']=best.get('method','Multi-region photo OCR · label and card face')
    best['text']=(best['text']+'\n\n--- Whole card text (reference only) ---\n'+full)[:4000]
    if _score(best)<4:best['warnings'].insert(0,'No coherent card identity found. Try a sharper photo or crop the label; raw cards need manual confirmation.')
    return _finish(best)
