# Docker 推送错误排查与解决方案

## 错误分析

### 错误信息
```
ERROR: failed to solve: failed to push harveyff/yue:v0.0.1: unexpected status from PUT request to https://registry-1.docker.io/v2/harveyff/yue/blobs/uploads/...: 400 Bad request
```

### 可能的原因

1. **镜像层太大** ⭐ 最可能
   - Docker Hub 对单个层有大小限制（通常 10GB）
   - 您的镜像可能包含很大的层（PyTorch、CUDA 等）

2. **镜像总体太大**
   - Docker Hub 对镜像大小有限制
   - 免费账户：无明确限制，但建议 < 10GB

3. **网络问题**
   - 推送过程中网络中断
   - 超时

4. **认证问题**
   - Docker Hub token 过期
   - 权限不足

---

## 解决方案

### 方案 1：检查镜像大小（首先执行）

```bash
# 检查镜像大小
docker images harveyff/yue:v0.0.1

# 检查镜像层大小
docker history harveyff/yue:v0.0.1

# 检查各层详细信息
docker inspect harveyff/yue:v0.0.1
```

**如果镜像 > 10GB，需要优化**

---

### 方案 2：优化 Dockerfile（推荐）

#### 2.1 使用多阶段构建

```dockerfile
# 构建阶段
FROM nvidia/cuda:13.1.0-devel-ubuntu22.04 AS builder

# ... 安装和编译 ...

# 运行阶段（只包含运行时）
FROM nvidia/cuda:13.1.0-runtime-ubuntu22.04

# 只复制必要的文件
COPY --from=builder /usr/local/lib/python3.10 /usr/local/lib/python3.10
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# 这样可以节省 ~2-3GB
```

#### 2.2 使用 runtime 而不是 devel

```dockerfile
# 如果不需要编译，使用 runtime（更小）
FROM nvidia/cuda:13.1.0-runtime-ubuntu22.04

# 而不是 devel（更大）
# FROM nvidia/cuda:13.1.0-devel-ubuntu22.04
```

**注意：** 如果需要在运行时编译 FlashAttention，可能需要 devel

#### 2.3 清理缓存和临时文件

```dockerfile
# 在每个 RUN 命令后清理
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
    rm -rf /tmp/*

# 安装 Python 包后清理
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ... && \
    rm -rf /root/.cache/pip && \
    rm -rf /tmp/*
```

#### 2.4 合并 RUN 命令减少层数

```dockerfile
# 不好的做法（多个层）
RUN apt-get update
RUN apt-get install -y python3.10
RUN pip install torch

# 好的做法（一个层）
RUN apt-get update && \
    apt-get install -y python3.10 && \
    pip install torch && \
    rm -rf /var/lib/apt/lists/*
```

---

### 方案 3：分块推送（如果镜像必须很大）

#### 3.1 使用 Docker Buildx

```bash
# 启用 buildx
docker buildx create --use

# 构建并推送（支持分块）
docker buildx build --platform linux/amd64 \
    -t harveyff/yue:v0.0.1 \
    --push \
    .
```

#### 3.2 使用压缩推送

```bash
# 使用压缩推送
docker push harveyff/yue:v0.0.1 --compress
```

---

### 方案 4：检查网络和认证

#### 4.1 重新登录 Docker Hub

```bash
# 登出
docker logout

# 重新登录
docker login

# 使用 token（推荐）
echo "YOUR_DOCKER_HUB_TOKEN" | docker login -u harveyff --password-stdin
```

#### 4.2 检查网络连接

```bash
# 测试 Docker Hub 连接
curl -I https://registry-1.docker.io/v2/

# 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

---

### 方案 5：使用其他 Registry（如果 Docker Hub 限制）

#### 5.1 使用 GitHub Container Registry

```bash
# 构建并推送到 GitHub
docker build -t ghcr.io/harveyff/yue:v0.0.1 .
docker push ghcr.io/harveyff/yue:v0.0.1
```

#### 5.2 使用私有 Registry

```bash
# 推送到私有 registry
docker tag harveyff/yue:v0.0.1 your-registry.com/yue:v0.0.1
docker push your-registry.com/yue:v0.0.1
```

---

## 优化后的 Dockerfile 示例

```dockerfile
# 多阶段构建版本
FROM nvidia/cuda:13.1.0-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 安装依赖（合并 RUN 命令）
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

# 安装 PyTorch
ENV TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0;12.0"
ENV CMAKE_CUDA_ARCHITECTURES="70;75;80;86;89;90;120"
ENV MAX_JOBS=4

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu131 || \
    (echo "Nightly CUDA 13.1 failed, trying CUDA 12.8..." && \
     pip install --no-cache-dir --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128) || \
    (echo "Nightly builds failed, falling back to stable CUDA 12.1" && \
     pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121) && \
    rm -rf /root/.cache/pip

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn && \
    rm -rf /root/.cache/pip

# 安装 FlashAttention
RUN TORCH_CUDA_ARCH_LIST="7.0;7.5;8.0;8.6;8.9;9.0;12.0" \
    MAX_JOBS=4 \
    pip install --no-cache-dir flash-attn --no-build-isolation || \
    echo "FlashAttention installation failed, continuing..." && \
    rm -rf /root/.cache/pip

# 复制代码
COPY . .

# 运行阶段（只包含运行时）
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
    git lfs install

WORKDIR /app

# 从构建阶段复制 Python 环境
COPY --from=builder /usr/local/lib/python3.10 /usr/local/lib/python3.10
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY --from=builder /app /app

RUN mkdir -p /app/output /app/.cache/huggingface /app/prompt_egs && \
    chmod +x /app/api_server.py /app/verify_sm120.py

EXPOSE 8000

CMD ["python", "/app/api_server.py"]
```

---

## 快速修复步骤

### 步骤 1：检查镜像大小

```bash
docker images harveyff/yue:v0.0.1
```

### 步骤 2：如果镜像太大，优化 Dockerfile

使用上面的多阶段构建示例

### 步骤 3：重新构建

```bash
docker build -t harveyff/yue:v0.0.1 .
```

### 步骤 4：检查新镜像大小

```bash
docker images harveyff/yue:v0.0.1
```

### 步骤 5：重新推送

```bash
docker push harveyff/yue:v0.0.1
```

---

## 如果仍然失败

### 1. 检查 Docker Hub 限制

- 免费账户：无明确限制，但建议 < 10GB
- Pro 账户：无限制

### 2. 使用 Docker Buildx

```bash
docker buildx build --platform linux/amd64 \
    -t harveyff/yue:v0.0.1 \
    --push \
    --progress=plain \
    .
```

### 3. 分步推送

```bash
# 先保存镜像
docker save harveyff/yue:v0.0.1 | gzip > yue.tar.gz

# 然后手动上传（如果 Docker Hub 支持）
```

### 4. 使用其他 Registry

- GitHub Container Registry (ghcr.io)
- Google Container Registry (gcr.io)
- AWS ECR
- 私有 Registry

---

## 常见问题

### Q: 为什么会出现 400 Bad request？

A: 通常是因为：
1. 镜像层太大（> 10GB）
2. 镜像总体太大
3. 网络问题
4. 认证问题

### Q: 如何知道镜像有多大？

A: 使用 `docker images` 命令查看

### Q: 如何优化镜像大小？

A: 
1. 使用多阶段构建
2. 使用 runtime 而不是 devel
3. 清理缓存和临时文件
4. 合并 RUN 命令

### Q: Docker Hub 有大小限制吗？

A: 
- 免费账户：建议 < 10GB
- Pro 账户：无限制
- 单个层：建议 < 10GB



