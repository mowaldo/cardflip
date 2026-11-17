"""Explicit one-time download for optional visual embeddings; no card images sent."""
from backend.embeddings import MODEL_DIR
from transformers import AutoImageProcessor, AutoModel

name='facebook/dinov2-small'
print('Downloading DINOv2 Small model and processor from Hugging Face…')
processor=AutoImageProcessor.from_pretrained(name,trust_remote_code=False)
model=AutoModel.from_pretrained(name,trust_remote_code=False,use_safetensors=True)
MODEL_DIR.mkdir(parents=True,exist_ok=True)
processor.save_pretrained(MODEL_DIR)
model.save_pretrained(MODEL_DIR,safe_serialization=True)
print('Saved local model:',MODEL_DIR)
print('Restart CardFlip. Matching uses local weights only.')
