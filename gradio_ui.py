#!/usr/bin/env python3
"""
YuE Gradio WebUI - Reference to YuE-UI by joeljuvel
A comprehensive Gradio interface for YuE music generation
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List
import gradio as gr

# Configuration from environment variables
STAGE1_MODEL = os.getenv("STAGE1_MODEL", "m-a-p/YuE-s1-7B-anneal-en-icl")
STAGE2_MODEL = os.getenv("STAGE2_MODEL", "m-a-p/YuE-s2-1B-general")
CUDA_IDX = os.getenv("CUDA_IDX", "0")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/output")
INFERENCE_SCRIPT = "/app/inference/infer.py"

# Load top 200 tags if available
TOP_TAGS = []
try:
    tags_file = Path(__file__).parent / "top_200_tags.json"
    if tags_file.exists():
        with open(tags_file, 'r', encoding='utf-8') as f:
            TOP_TAGS = json.load(f)
except:
    pass

def run_inference(
    genre_txt: str,
    lyrics_txt: str,
    run_n_segments: int,
    stage2_batch_size: int,
    max_new_tokens: int,
    repetition_penalty: float,
    use_audio_prompt: bool,
    audio_prompt_path: Optional[str],
    prompt_start_time: float,
    prompt_end_time: float,
    use_dual_tracks_prompt: bool,
    vocal_track_prompt_path: Optional[str],
    instrumental_track_prompt_path: Optional[str],
    stage1_model: str,
    stage2_model: str,
    progress=None,
) -> Tuple[str, str]:
    """
    Run YuE inference and return output audio path and status message
    """
    try:
        # Prepare inference command
        cmd = [
            "python", INFERENCE_SCRIPT,
            "--cuda_idx", CUDA_IDX,
            "--stage1_model", stage1_model,
            "--stage2_model", stage2_model,
            "--run_n_segments", str(run_n_segments),
            "--stage2_batch_size", str(stage2_batch_size),
            "--output_dir", OUTPUT_DIR,
            "--max_new_tokens", str(max_new_tokens),
            "--repetition_penalty", str(repetition_penalty),
        ]
        
        # Handle genre and lyrics
        if genre_txt:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(genre_txt)
                cmd.extend(["--genre_txt", f.name])
        
        if lyrics_txt:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(lyrics_txt)
                cmd.extend(["--lyrics_txt", f.name])
        
        # Handle audio prompts
        if use_dual_tracks_prompt:
            cmd.append("--use_dual_tracks_prompt")
            if vocal_track_prompt_path:
                cmd.extend(["--vocal_track_prompt_path", vocal_track_prompt_path])
            if instrumental_track_prompt_path:
                cmd.extend(["--instrumental_track_prompt_path", instrumental_track_prompt_path])
            if prompt_start_time is not None:
                cmd.extend(["--prompt_start_time", str(prompt_start_time)])
            if prompt_end_time is not None:
                cmd.extend(["--prompt_end_time", str(prompt_end_time)])
        elif use_audio_prompt:
            cmd.append("--use_audio_prompt")
            if audio_prompt_path:
                cmd.extend(["--audio_prompt_path", audio_prompt_path])
            if prompt_start_time is not None:
                cmd.extend(["--prompt_start_time", str(prompt_start_time)])
            if prompt_end_time is not None:
                cmd.extend(["--prompt_end_time", str(prompt_end_time)])
        
        # Run inference with progress tracking
        if progress:
            progress(0, desc="Starting inference...")
            progress(0.3, desc="Running Stage 1...")
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/app")
        
        if progress:
            progress(0.7, desc="Running Stage 2...")
        
        if result.returncode != 0:
            return None, f"Error: {result.stderr}\n\nCommand: {' '.join(cmd)}"
        
        if progress:
            progress(0.9, desc="Finding output files...")
        
        # Find generated audio files
        output_path = Path(OUTPUT_DIR)
        if not output_path.exists():
            return None, f"Output directory {OUTPUT_DIR} does not exist."
        
        audio_files = list(output_path.glob("*.mp3")) + list(output_path.glob("*.wav"))
        
        if progress:
            progress(1.0, desc="Complete!")
        
        if audio_files:
            latest_file = max(audio_files, key=lambda p: p.stat().st_mtime)
            return str(latest_file), f"✅ Success! Generated {len(audio_files)} file(s).\nLatest: {latest_file.name}\n\nOutput directory: {OUTPUT_DIR}"
        else:
            return None, f"Generation completed but no audio files found in {OUTPUT_DIR}.\n\nCommand output: {result.stdout}"
            
    except Exception as e:
        return None, f"Exception: {str(e)}"

def create_ui():
    """Create the Gradio UI interface"""
    
    # Note: theme parameter moved to launch() in Gradio 6.0+
    with gr.Blocks(title="YuE Music Generation") as demo:
        gr.Markdown("""
        # 🎵 YuE Music Generation UI
        **Open Music Foundation Models for Full-Song Generation**
        
        Generate complete songs with vocals and accompaniment from lyrics. Support for multiple languages and music styles.
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📝 Input Settings")
                
                genre_input = gr.Textbox(
                    label="风格标签 (Genre Tags)",
                    placeholder="例如: inspiring female uplifting pop airy vocal electronic bright",
                    value="inspiring female uplifting pop airy vocal electronic bright vocal vocal",
                    lines=2,
                    info="推荐包含：风格、乐器、情绪、性别、音色，用空格分隔"
                )
                
                # Tag suggestions dropdown
                if TOP_TAGS:
                    with gr.Accordion("常用标签 (Common Tags)", open=False):
                        # Convert to list for Gradio 6.0+ compatibility
                        tag_choices = list(TOP_TAGS[:50]) if isinstance(TOP_TAGS, (list, tuple)) else list(TOP_TAGS)[:50]
                        tag_dropdown = gr.Dropdown(
                            choices=tag_choices,  # Show first 50 tags
                            label="选择标签添加到输入框",
                            multiselect=True
                        )
                        def add_tags(selected_tags, current_text):
                            if selected_tags:
                                new_tags = " ".join(selected_tags)
                                return current_text + " " + new_tags if current_text else new_tags
                            return current_text
                        tag_dropdown.change(
                            fn=add_tags,
                            inputs=[tag_dropdown, genre_input],
                            outputs=genre_input
                        )
                
                lyrics_input = gr.Textbox(
                    label="歌词 (Lyrics)",
                    placeholder="[verse]\n第一段歌词...\n\n[chorus]\n副歌歌词...",
                    value="""[verse]
Staring at the sunset, colors paint the sky
Thoughts of you keep swirling, can't deny
I know I let you down, I made mistakes
But I'm here to mend the heart I didn't break

[chorus]
Every road you take, I'll be one step behind
Every dream you chase, I'm reaching for the light
You can't fight this feeling now
I won't back down""",
                    lines=15,
                    info="使用 [verse], [chorus], [bridge], [outro] 标签分隔段落，段落间用两个换行符分隔"
                )
                
                with gr.Accordion("🎚️ Generation Parameters", open=True):
                    run_n_segments = gr.Slider(
                        minimum=1,
                        maximum=10,
                        value=2,
                        step=1,
                        label="段落数量 (Segments)",
                        info="要生成的歌词段落数。24GB显存建议≤2，80GB显存可生成完整歌曲"
                    )
                    
                    stage2_batch_size = gr.Slider(
                        minimum=1,
                        maximum=16,
                        value=4,
                        step=1,
                        label="Stage2 批次大小",
                        info="根据GPU内存调整，越大越快但占用更多显存"
                    )
                    
                    max_new_tokens = gr.Slider(
                        minimum=1000,
                        maximum=5000,
                        value=3000,
                        step=100,
                        label="最大Token数",
                        info="每段约30秒音频，默认3000"
                    )
                    
                    repetition_penalty = gr.Slider(
                        minimum=1.0,
                        maximum=2.0,
                        value=1.1,
                        step=0.1,
                        label="重复惩罚 (Repetition Penalty)",
                        info="控制重复度，1.1为默认值"
                    )
                
                with gr.Accordion("🎧 Audio Prompt / ICL (Optional)", open=False):
                    use_audio_prompt = gr.Checkbox(
                        label="使用单轨音频提示 (Single-track ICL)",
                        value=False
                    )
                    
                    audio_prompt = gr.Audio(
                        label="参考音频 (Reference Audio)",
                        type="filepath",
                        visible=False
                    )
                    
                    use_dual_tracks_prompt = gr.Checkbox(
                        label="使用双轨音频提示 (Dual-track ICL) - 推荐",
                        value=False
                    )
                    
                    with gr.Row():
                        vocal_track = gr.Audio(
                            label="人声轨道 (Vocal Track)",
                            type="filepath",
                            visible=False
                        )
                        instrumental_track = gr.Audio(
                            label="伴奏轨道 (Instrumental Track)",
                            type="filepath",
                            visible=False
                        )
                    
                    with gr.Row():
                        prompt_start_time = gr.Number(
                            label="开始时间 (秒)",
                            value=0.0,
                            precision=1,
                            visible=False
                        )
                        prompt_end_time = gr.Number(
                            label="结束时间 (秒)",
                            value=30.0,
                            precision=1,
                            visible=False
                        )
                    
                    # Toggle visibility based on checkbox
                    def toggle_audio_prompt(use_single, use_dual):
                        return (
                            gr.update(visible=use_single),
                            gr.update(visible=use_dual),
                            gr.update(visible=use_dual),
                            gr.update(visible=use_single or use_dual),
                            gr.update(visible=use_single or use_dual)
                        )
                    
                    use_audio_prompt.change(
                        fn=lambda x: toggle_audio_prompt(x, False),
                        inputs=[use_audio_prompt],
                        outputs=[audio_prompt, vocal_track, instrumental_track, prompt_start_time, prompt_end_time]
                    )
                    
                    use_dual_tracks_prompt.change(
                        fn=lambda x: toggle_audio_prompt(False, x),
                        inputs=[use_dual_tracks_prompt],
                        outputs=[audio_prompt, vocal_track, instrumental_track, prompt_start_time, prompt_end_time]
                    )
                
                with gr.Accordion("🤖 Model Selection", open=False):
                    stage1_model = gr.Dropdown(
                        choices=[
                            "m-a-p/YuE-s1-7B-anneal-en-icl",
                            "m-a-p/YuE-s1-7B-anneal-en-cot",
                            "m-a-p/YuE-s1-7B-anneal-zh-icl",
                            "m-a-p/YuE-s1-7B-anneal-zh-cot",
                            "m-a-p/YuE-s1-7B-anneal-jp-kr-icl",
                            "m-a-p/YuE-s1-7B-anneal-jp-kr-cot",
                        ],
                        value=STAGE1_MODEL,
                        label="Stage 1 Model",
                        info="ICL模型支持音频提示，CoT模型为链式思考模式"
                    )
                    
                    stage2_model = gr.Dropdown(
                        choices=[
                            "m-a-p/YuE-s2-1B-general",
                        ],
                        value=STAGE2_MODEL,
                        label="Stage 2 Model",
                        info="Stage 2用于音频精炼"
                    )
                
                generate_btn = gr.Button("🎵 生成音乐 (Generate Music)", variant="primary", size="lg")
            
            with gr.Column(scale=1):
                gr.Markdown("### 🎼 Output")
                
                output_audio = gr.Audio(
                    label="生成的音乐 (Generated Music)",
                    type="filepath"
                )
                
                status_output = gr.Textbox(
                    label="状态信息 (Status)",
                    lines=5,
                    interactive=False
                )
                
                gr.Markdown("""
                ### 💡 Tips & Tricks
                
                - **风格标签**: 推荐包含5个要素：风格、乐器、情绪、性别、音色
                - **歌词格式**: 使用 `[verse]`, `[chorus]`, `[bridge]`, `[outro]` 标签
                - **音频提示**: 双轨模式效果最好，需要分离人声和伴奏
                - **显存要求**: 
                  - 24GB显存：建议≤2个段落
                  - 80GB显存：可生成完整歌曲（4+段落）
                - **生成时间**: 
                  - RTX 4090: ~360秒/30秒音频
                  - H800: ~150秒/30秒音频
                
                ### 📚 Resources
                - [YuE Official Repo](https://github.com/multimodal-art-projection/YuE)
                - [YuE-UI by joeljuvel](https://github.com/joeljuvel/YuE-UI)
                - [Paper](https://arxiv.org/abs/2503.08638)
                """)
        
        # Generation function wrapper
        def generate_wrapper(
            genre, lyrics, segments, batch_size, max_tokens, rep_penalty,
            use_audio, audio_path, start_time, end_time,
            use_dual, vocal_path, inst_path, s1_model, s2_model,
            progress=gr.Progress()
        ):
            # Extract file paths from Gradio Audio components
            # Gradio Audio returns a tuple (file_path, sample_rate) or just file_path
            if isinstance(audio_path, tuple):
                audio_file_path = audio_path[0] if use_audio and audio_path[0] else None
            else:
                audio_file_path = audio_path if use_audio and audio_path else None
            
            if isinstance(vocal_path, tuple):
                vocal_file_path = vocal_path[0] if use_dual and vocal_path[0] else None
            else:
                vocal_file_path = vocal_path if use_dual and vocal_path else None
            
            if isinstance(inst_path, tuple):
                inst_file_path = inst_path[0] if use_dual and inst_path[0] else None
            else:
                inst_file_path = inst_path if use_dual and inst_path else None
            
            audio_output, status = run_inference(
                genre_txt=genre or "",
                lyrics_txt=lyrics or "",
                run_n_segments=int(segments),
                stage2_batch_size=int(batch_size),
                max_new_tokens=int(max_tokens),
                repetition_penalty=float(rep_penalty),
                use_audio_prompt=use_audio,
                audio_prompt_path=audio_file_path,
                prompt_start_time=float(start_time) if start_time else 0.0,
                prompt_end_time=float(end_time) if end_time else 30.0,
                use_dual_tracks_prompt=use_dual,
                vocal_track_prompt_path=vocal_file_path,
                instrumental_track_prompt_path=inst_file_path,
                stage1_model=s1_model,
                stage2_model=s2_model,
                progress=progress
            )
            
            return audio_output, status
        
        generate_btn.click(
            fn=generate_wrapper,
            inputs=[
                genre_input, lyrics_input, run_n_segments, stage2_batch_size,
                max_new_tokens, repetition_penalty,
                use_audio_prompt, audio_prompt, prompt_start_time, prompt_end_time,
                use_dual_tracks_prompt, vocal_track, instrumental_track,
                stage1_model, stage2_model
            ],
            outputs=[output_audio, status_output]
        )
        
        gr.Markdown("""
        ---
        **YuE Music Generation UI** - Based on [YuE-UI](https://github.com/joeljuvel/YuE-UI) design
        """)
    
    return demo

if __name__ == "__main__":
    demo = create_ui()
    demo.launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
        theme=gr.themes.Soft(),  # Theme moved here in Gradio 6.0+
        share=False
    )

