FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NO_ALBUMENTATIONS_UPDATE=1 \
    OMP_NUM_THREADS=2 \
    TORCH_HOME=/opt/cache/torch \
    HF_HOME=/opt/cache/hf

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch, pinned to the version the checkpoints were trained with.
RUN pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install timm albumentations opencv-python pandas numpy scipy scikit-learn scikit-image \
    Pillow matplotlib pyyaml grad-cam segmentation-models-pytorch \
    fastapi "uvicorn[standard]" python-multipart

# The lesion v2 builder always requests ImageNet encoder weights; cache them at build time
# so container restarts never depend on a download.
RUN python -c "import segmentation_models_pytorch as smp; smp.Unet('resnet34', encoder_weights='imagenet', classes=4)" \
    && chmod -R a+rX /opt/cache

COPY src ./src
RUN useradd --system --uid 10001 retina
USER retina

EXPOSE 8100
CMD ["uvicorn", "src.serve.ai_service:app", "--host", "0.0.0.0", "--port", "8100"]
