# YuE Music Generation Model - Dockerfile
# Supports CUDA 13.x and RTX 50 series (Blackwell architecture, sm_120)
# Based on NVIDIA CUDA 13 devel image (needed for compiling FlashAttention)
FROM nvidia/cuda:13.1.0-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/root/.cache/huggingface

# Install Python 3.10+ and system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.10 \
        python3.10-dev \
        python3-pip \
        git \
        git-lfs \
        curl \
        wget \
        ffmpeg \
        libsndfile1 \
        build-essential \
        ninja-build \
        && \
    rm -rf /var/lib/apt/lists/* && \
    rm -f /usr/bin/python /usr/bin/python3 && \
    ln -s /usr/bin/python3.10 /usr/bin/python && \
    ln -s /usr/bin/python3.10 /usr/bin/python3 && \
    git lfs install

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Set CUDA architecture flags for RTX 50 series (sm_120) support FIRST
# This ensures custom CUDA kernels are compiled for Blackwell architecture
# Must be set before installing PyTorch and FlashAttention
ENV TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0;12.0"
ENV CMAKE_CUDA_ARCHITECTURES="70;75;80;86;89;90;120"
ENV MAX_JOBS=4

# Install PyTorch with CUDA 13 support (using nightly for RTX 50 series support)
# For stable version, use: torch==2.5.0+cu121 (CUDA 12.1)
# For RTX 50 series (sm_120), use nightly builds with CUDA 13.1
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu131 || \
    (echo "Nightly CUDA 13.1 failed, trying CUDA 12.8..." && \
     pip install --no-cache-dir --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128) || \
    (echo "Nightly builds failed, falling back to stable CUDA 12.1 (may not support sm_120)" && \
     pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121)

# Install Python dependencies (requirements.txt already includes fastapi, uvicorn, gradio)
RUN pip install --no-cache-dir -r requirements.txt

# Install FlashAttention (required for YuE)
# Note: This may take a while and requires CUDA toolkit
# For RTX 50 series, ensure it's compiled with sm_120 support
# MAX_JOBS limits parallel compilation to avoid OOM during build
# Try multiple installation methods for better compatibility
RUN echo "Attempting to install FlashAttention..." && \
    (TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0;12.0" \
     MAX_JOBS=2 \
     pip install --no-cache-dir flash-attn --no-build-isolation 2>&1 | tee /tmp/flash_attn_install.log) || \
    (echo "FlashAttention installation failed, trying with pre-built wheel..." && \
     pip install --no-cache-dir flash-attn --no-build-isolation --no-deps 2>&1 | tee -a /tmp/flash_attn_install.log || \
     echo "FlashAttention installation failed, continuing without it. Check /tmp/flash_attn_install.log for details.")

# Copy project code
COPY . .

# Copy API server and Gradio UI scripts
# Note: COPY . . above should include all files, but we copy explicitly to ensure they're present
COPY api_server.py /app/api_server.py
COPY verify_sm120.py /app/verify_sm120.py

# Copy Gradio UI file (required for new version)
# This will fail the build if file doesn't exist, ensuring we catch missing files early
COPY gradio_ui.py /app/gradio_ui.py

# Copy top tags file for Gradio UI
COPY top_200_tags.json /app/top_200_tags.json

# Download xcodec_mini_infer if not present (required for inference)
# This uses git-lfs to download large model files
RUN cd /app/inference && \
    if [ ! -d "xcodec_mini_infer" ] || [ -z "$(ls -A xcodec_mini_infer 2>/dev/null)" ]; then \
        echo "Downloading xcodec_mini_infer..." && \
        git clone https://huggingface.co/m-a-p/xcodec_mini_infer || \
        echo "Warning: xcodec_mini_infer download failed, may need manual download"; \
    else \
        echo "xcodec_mini_infer already exists"; \
    fi

# Create necessary directories
RUN mkdir -p /app/output /app/.cache/huggingface /app/prompt_egs && \
    chmod +x /app/api_server.py /app/gradio_ui.py /app/verify_sm120.py

# Set execute permissions for check scripts (already copied by COPY . . above)
# Use conditional chmod to handle cases where files might not exist
RUN chmod +x /app/check_version.sh /app/check_gradio.sh 2>/dev/null || \
    echo "Warning: Some check scripts may not be present"

# Set up HuggingFace cache directory
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose port for API service
EXPOSE 8000

# Default command - run API server
# Can be overridden to run inference directly: python inference/infer.py ...
CMD ["python", "/app/api_server.py"]

