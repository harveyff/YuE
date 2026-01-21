# Docker 推送 400 错误深度解决方案

## 问题分析

**错误：** `400 Bad request` 在推送 blob 时

**最可能的原因：**
1. ⭐ **单个层太大**（> 10GB）- Docker Hub 限制
2. 镜像总体太大
3. 网络问题

---

## 立即诊断

### 步骤 1：检查镜像大小

```bash
# 检查本地镜像大小
docker images harveyff/yue:v0.0.1

# 检查镜像层大小
docker history harveyff/yue:v0.0.1 --human --format "{{.CreatedBy}} - {{.Size}}"
```

**如果看到某个层 > 10GB，那就是问题所在！**

---

## 解决方案

### 方案 1：优化 Dockerfile（多阶段构建）- 最有效

**问题：** PyTorch 安装层可能太大（> 10GB）

**解决：** 使用多阶段构建，将大层拆分

```dockerfile
# 阶段 1：构建阶段
FROM nvidia/cuda:13.1.0-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 安装系统依赖
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
    apt-get clean && \
    rm -f /usr/bin/python /usr/bin/python3 && \
    ln -s /usr/bin/python3.10 /usr/bin/python && \
    ln -s /usr/bin/python3.10 /usr/bin/python3 && \
    git lfs install

WORKDIR /app

# 安装 PyTorch（单独一层，但会很大）
ENV TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0;12.0"
ENV CMAKE_CUDA_ARCHITECTURES="70;75;80;86;89;90;120"
ENV MAX_JOBS=4

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu131 || \
    (echo "Nightly CUDA 13.1 failed, trying CUDA 12.8..." && \
     pip install --no-cache-dir --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128) || \
    (echo "Nightly builds failed, falling back to stable CUDA 12.1" && \
     pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121) && \
    rm -rf /root/.cache/pip /tmp/*

# 安装其他依赖（分开层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn && \
    rm -rf /root/.cache/pip /tmp/*

# 安装 FlashAttention（单独层）
RUN TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0;12.0" \
    MAX_JOBS=4 \
    pip install --no-cache-dir flash-attn --no-build-isolation || \
    echo "FlashAttention installation failed, continuing..." && \
    rm -rf /root/.cache/pip /tmp/*

# 阶段 2：运行阶段（只包含运行时）
FROM nvidia/cuda:13.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV PORT=8000
ENV HOST=0.0.0.0

# 只安装运行时依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.10 \
        python3-pip \
        git \
        git-lfs \
        ffmpeg \
        libsndfile1 \
        && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    rm -f /usr/bin/python /usr/bin/python3 && \
    ln -s /usr/bin/python3.10 /usr/bin/python && \
    ln -s /usr/bin/python3.10 /usr/bin/python3 && \
    git lfs install && \
    rm -rf /tmp/*

WORKDIR /app

# 从构建阶段复制 Python 环境（关键：这会创建新层，但不会太大）
COPY --from=builder /usr/local/lib/python3.10 /usr/local/lib/python3.10
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY --from=builder /app /app

RUN mkdir -p /app/output /app/.cache/huggingface /app/prompt_egs && \
    chmod +x /app/api_server.py /app/verify_sm120.py && \
    rm -rf /tmp/*

EXPOSE 8000

CMD ["python", "/app/api_server.py"]
```

**关键优化：**
- ✅ 使用 runtime 而不是 devel（节省 ~2GB）
- ✅ 多阶段构建，减少最终镜像大小
- ✅ 每个 RUN 后清理缓存

---

### 方案 2：使用压缩推送

```bash
# 尝试使用压缩推送
docker buildx build \
    --platform linux/amd64 \
    -t harveyff/yue:v0.0.1 \
    --push \
    --compress \
    .
```

**注意：** 这可能会增加构建时间，但可能解决推送问题

---

### 方案 3：检查并优化大层

如果 PyTorch 层太大，可以尝试：

```dockerfile
# 分步安装 PyTorch（如果可能）
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/nightly/cu131 && \
    rm -rf /root/.cache/pip /tmp/*

RUN pip install --no-cache-dir torchvision --index-url https://download.pytorch.org/whl/nightly/cu131 && \
    rm -rf /root/.cache/pip /tmp/*

RUN pip install --no-cache-dir torchaudio --index-url https://download.pytorch.org/whl/nightly/cu131 && \
    rm -rf /root/.cache/pip /tmp/*
```

---

### 方案 4：使用其他 Registry（如果 Docker Hub 限制太严格）

#### GitHub Container Registry

```bash
# 推送到 GitHub Container Registry
docker buildx build \
    --platform linux/amd64 \
    -t ghcr.io/harveyff/yue:v0.0.1 \
    --push \
    .

# 需要先登录
echo $GITHUB_TOKEN | docker login ghcr.io -u harveyff --password-stdin
```

#### 使用私有 Registry

```bash
# 推送到私有 registry
docker buildx build \
    --platform linux/amd64 \
    -t your-registry.com/yue:v0.0.1 \
    --push \
    .
```

---

## 推荐执行步骤

### 步骤 1：检查镜像大小

```bash
# 先加载到本地检查
docker buildx build \
    --platform linux/amd64 \
    -t harveyff/yue:v0.0.1 \
    --load \
    .

# 检查大小
docker images harveyff/yue:v0.0.1
docker history harveyff/yue:v0.0.1 --human
```

### 步骤 2：如果镜像太大，使用优化后的 Dockerfile

使用上面的多阶段构建 Dockerfile

### 步骤 3：重新构建并推送

```bash
docker buildx build \
    --platform linux/amd64 \
    -t harveyff/yue:v0.0.1 \
    --push \
    --progress=plain \
    .
```

---

## 快速测试：使用压缩

如果不想修改 Dockerfile，先试试压缩：

```bash
docker buildx build \
    --platform linux/amd64 \
    -t harveyff/yue:v0.0.1 \
    --push \
    --compress \
    --progress=plain \
    .
```

---

## 如果仍然失败

### 使用 GitHub Container Registry

```bash
# 1. 创建 GitHub Personal Access Token
# Settings -> Developer settings -> Personal access tokens -> Generate new token
# 权限：write:packages

# 2. 登录
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u harveyff --password-stdin

# 3. 构建并推送
docker buildx build \
    --platform linux/amd64 \
    -t ghcr.io/harveyff/yue:v0.0.1 \
    --push \
    .
```

---

## 总结

**最可能的原因：** PyTorch 安装层太大（> 10GB）

**推荐解决方案：**
1. ✅ 使用多阶段构建（使用 runtime 而不是 devel）
2. ✅ 尝试压缩推送
3. ✅ 如果还不行，使用 GitHub Container Registry

**立即尝试：**
```bash
# 先试试压缩推送
docker buildx build \
    --platform linux/amd64 \
    -t harveyff/yue:v0.0.1 \
    --push \
    --compress \
    .
```




