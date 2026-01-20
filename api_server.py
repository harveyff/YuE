#!/usr/bin/env python3
"""
YuE API Server - FastAPI wrapper for YuE inference
This script provides a REST API interface and Gradio WebUI for YuE music generation.
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
import uvicorn

# Try to import gradio for UI
try:
    import gradio as gr
    from gradio_ui import create_ui
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False
    print("Warning: Gradio not available. Install with: pip install gradio")

app = FastAPI(title="YuE Music Generation API", version="1.0.0")

# Configuration from environment variables
STAGE1_MODEL = os.getenv("STAGE1_MODEL", "m-a-p/YuE-s1-7B-anneal-en-icl")
STAGE2_MODEL = os.getenv("STAGE2_MODEL", "m-a-p/YuE-s2-1B-general")
CUDA_IDX = os.getenv("CUDA_IDX", "0")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/output")
INFERENCE_SCRIPT = "/app/inference/infer.py"

class InferenceRequest(BaseModel):
    genre_txt: Optional[str] = None
    lyrics_txt: Optional[str] = None
    genre_file: Optional[str] = None
    lyrics_file: Optional[str] = None
    run_n_segments: int = 2
    stage2_batch_size: int = 4
    max_new_tokens: int = 3000
    repetition_penalty: float = 1.1
    use_audio_prompt: bool = False
    audio_prompt_path: Optional[str] = None
    prompt_start_time: float = 0
    prompt_end_time: float = 30
    use_dual_tracks_prompt: bool = False
    vocal_track_prompt_path: Optional[str] = None
    instrumental_track_prompt_path: Optional[str] = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "yue-api"}

@app.get("/api")
async def api_info():
    """API info endpoint"""
    return {
        "service": "YuE Music Generation API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "generate": "/api/generate",
            "docs": "/docs"
        },
        "ui": "/" if GRADIO_AVAILABLE else "Not available (install gradio)"
    }

@app.post("/api/generate")
async def generate_music(request: InferenceRequest, background_tasks: BackgroundTasks):
    """
    Generate music using YuE model
    
    This endpoint accepts inference parameters and triggers music generation.
    The generation runs asynchronously and returns a job ID.
    """
    try:
        # Prepare inference command
        cmd = [
            "python", INFERENCE_SCRIPT,
            "--cuda_idx", CUDA_IDX,
            "--stage1_model", STAGE1_MODEL,
            "--stage2_model", STAGE2_MODEL,
            "--run_n_segments", str(request.run_n_segments),
            "--stage2_batch_size", str(request.stage2_batch_size),
            "--output_dir", OUTPUT_DIR,
            "--max_new_tokens", str(request.max_new_tokens),
            "--repetition_penalty", str(request.repetition_penalty),
        ]
        
        # Handle genre and lyrics
        if request.genre_file:
            cmd.extend(["--genre_txt", request.genre_file])
        elif request.genre_txt:
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(request.genre_txt)
                cmd.extend(["--genre_txt", f.name])
        
        if request.lyrics_file:
            cmd.extend(["--lyrics_txt", request.lyrics_file])
        elif request.lyrics_txt:
            # Write to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(request.lyrics_txt)
                cmd.extend(["--lyrics_txt", f.name])
        
        # Handle audio prompts
        if request.use_dual_tracks_prompt:
            cmd.append("--use_dual_tracks_prompt")
            if request.vocal_track_prompt_path:
                cmd.extend(["--vocal_track_prompt_path", request.vocal_track_prompt_path])
            if request.instrumental_track_prompt_path:
                cmd.extend(["--instrumental_track_prompt_path", request.instrumental_track_prompt_path])
            if request.prompt_start_time is not None:
                cmd.extend(["--prompt_start_time", str(request.prompt_start_time)])
            if request.prompt_end_time is not None:
                cmd.extend(["--prompt_end_time", str(request.prompt_end_time)])
        elif request.use_audio_prompt:
            cmd.append("--use_audio_prompt")
            if request.audio_prompt_path:
                cmd.extend(["--audio_prompt_path", request.audio_prompt_path])
            if request.prompt_start_time is not None:
                cmd.extend(["--prompt_start_time", str(request.prompt_start_time)])
            if request.prompt_end_time is not None:
                cmd.extend(["--prompt_end_time", str(request.prompt_end_time)])
        
        # Run inference (this is a simplified version - actual implementation should handle async execution)
        # For now, return a placeholder response
        return {
            "status": "accepted",
            "message": "Music generation started",
            "output_dir": OUTPUT_DIR,
            "note": "This is a placeholder. Actual implementation should run inference asynchronously and return results."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during inference: {str(e)}")

@app.get("/api/output/{filename}")
async def get_output(filename: str):
    """Get generated output file"""
    file_path = Path(OUTPUT_DIR) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

# Mount Gradio UI if available
if GRADIO_AVAILABLE:
    try:
        gradio_ui = create_ui()
        # Mount to root path "/" as default UI
        app = gr.mount_gradio_app(app, gradio_ui, path="/")
        print("✓ Gradio UI mounted at / (root)")
    except Exception as e:
        print(f"Warning: Failed to mount Gradio UI: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    if GRADIO_AVAILABLE:
        print(f"🚀 Starting YuE API Server with Gradio UI")
        print(f"   UI:  http://{host}:{port}/")
        print(f"   API: http://{host}:{port}/api/generate")
        print(f"   Docs: http://{host}:{port}/docs")
    else:
        print(f"🚀 Starting YuE API Server (Gradio UI not available)")
        print(f"   API: http://{host}:{port}")
        print(f"   Docs: http://{host}:{port}/docs")
    
    uvicorn.run(app, host=host, port=port)

