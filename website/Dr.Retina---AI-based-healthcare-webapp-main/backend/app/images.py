import warnings
from io import BytesIO

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 25_000_000


def validate_image(data: bytes):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise ValueError("Only JPEG and PNG are supported")
                mime = "image/jpeg" if image.format == "JPEG" else "image/png"
                width, height = image.size
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
            if width < 256 or height < 256:
                raise ValueError("Image must be at least 256 × 256 pixels")
            return mime, width, height
    except (
        ValueError,
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(422, "Invalid, unsupported, too small, or oversized retinal image") from None
