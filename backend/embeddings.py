"""Optional, entirely local DINOv2 embeddings. No model downloads during requests."""
import logging, threading
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
from . import core

MODEL_DIR=core.ROOT/'data'/'models'/'dinov2-small'
_lock=threading.Lock()
_loaded=None
log=logging.getLogger(__name__)


def installed():
    return (MODEL_DIR/'config.json').is_file() and (MODEL_DIR/'model.safetensors').is_file()


def _load():
    global _loaded
    if _loaded is None:
        import torch
        from transformers import AutoImageProcessor, AutoModel
        processor=AutoImageProcessor.from_pretrained(str(MODEL_DIR),local_files_only=True,trust_remote_code=False)
        model=AutoModel.from_pretrained(str(MODEL_DIR),local_files_only=True,trust_remote_code=False,use_safetensors=True).eval()
        device='mps' if torch.backends.mps.is_available() else 'cpu'
        model=model.to(device)
        _loaded=(torch,processor,model,device)
    return _loaded


def vectors(images):
    """Unit-length CLS vectors; batch for efficiency. None means OpenCV fallback."""
    if not installed() or not images:return None
    with _lock:
        try:
            torch,processor,model,device=_load()
            # Resize without dropping corners: foil/border details matter.
            prepared=[Image.fromarray(cv2.cvtColor(cv2.resize(im,(224,224),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2RGB)) for im in images]
            batches=[]
            with torch.inference_mode():
                for start in range(0,len(prepared),8):
                    inputs=processor(images=prepared[start:start+8],return_tensors='pt')
                    out=model(**{k:v.to(device) for k,v in inputs.items()}).last_hidden_state[:,0,:]
                    batches.append(torch.nn.functional.normalize(out.float(),dim=-1).cpu().numpy())
            arr=np.concatenate(batches)
            if arr.ndim!=2 or arr.shape[0]!=len(images) or not np.isfinite(arr).all():return None
            return arr
        except Exception as exc:
            log.warning('Optional DINOv2 unavailable (%s); using OpenCV.',type(exc).__name__)
            return None


def rerank(target, references, matches):
    """DINO is supporting evidence only; no prices, no identity assertion.

    Whole-card embedding can favor shared artwork across parallels. Retain
    OpenCV geometry/color as the majority weight and report both scores.
    """
    if not matches:return 'OpenCV'
    vs=vectors([target,*references])
    if vs is None:return 'OpenCV'
    for row,vec in zip(matches,vs[1:]):
        cosine=float(np.clip(np.dot(vs[0],vec),-1,1))
        row['opencv_score']=row['score']
        row['embedding_similarity']=round(cosine,4)
        row['score']=round(.75*row['score']+.25*max(0.,cosine),4)
    return 'OpenCV + DINOv2'
