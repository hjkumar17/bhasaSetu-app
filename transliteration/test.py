from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from ai4bharat.transliteration import XlitEngine

import torch
import argparse
from torch.serialization import safe_globals  # ✅ Needed for PyTorch 2.6+

app = FastAPI(title="Transliteration Prototype", version="1.0")

# Supported languages
SUPPORTED_LANGS = ["ta", "hi", "te"]  # Tamil, Hindi, Telugu; add more as needed

class TransliterationRequest(BaseModel):
    sentences: List[str]
    lang: str = "ta"  # Default to Tamil
    beam_width: int = 10

class TransliterationResponse(BaseModel):
    original: str
    transliterated: str

@app.get("/health")
def health_check():
    print("[INFO] Health check requested")
    return {"status": "Transliteration service is running."}

@app.post("/transliterate", response_model=List[TransliterationResponse])
def transliterate_text(req: TransliterationRequest):
    print("[INFO] Received transliteration request")
    print(f"[DEBUG] Input: sentences={req.sentences}, lang={req.lang}, beam_width={req.beam_width}")

    # Input validation
    if not req.sentences:
        print("[ERROR] No sentences provided")
        raise HTTPException(status_code=400, detail="No sentences provided")
    if req.lang not in SUPPORTED_LANGS:
        print(f"[ERROR] Unsupported language: {req.lang}")
        raise HTTPException(status_code=400, detail=f"Unsupported language: {req.lang}")
    if req.beam_width < 1 or req.beam_width > 20:
        print(f"[ERROR] Invalid beam_width: {req.beam_width}")
        raise HTTPException(status_code=400, detail="beam_width must be between 1 and 20")

    # Initialize engine using secure context for PyTorch 2.6+
    print(f"[INFO] Initializing XlitEngine for language: {req.lang}")
    try:
        with safe_globals([argparse.Namespace]):
            engine = XlitEngine(req.lang, beam_width=req.beam_width)
    except Exception as e:
        print(f"[ERROR] Failed to initialize transliteration engine: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize transliteration engine: {str(e)}")

    # Transliteration
    result = []
    for sentence in req.sentences:
        print(f"[INFO] Transliterating sentence: '{sentence}'")
        try:
            translit = engine.translit_sentence(sentence)[req.lang]
            print(f"[DEBUG] Transliterated output: '{translit}'")
            result.append(TransliterationResponse(original=sentence, transliterated=translit))
        except Exception as e:
            print(f"[ERROR] Transliteration failed for '{sentence}': {str(e)}")
            raise HTTPException(status_code=500, detail=f"Transliteration failed: {str(e)}")

    print("[INFO] Transliteration complete")
    return result
