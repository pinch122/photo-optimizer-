import io
import asyncio
from PIL import Image
from app.logging_config import logger

class ThumbnailService:
    @staticmethod
    def generate_thumbnail_sync(file_path: str, size: int = 300) -> bytes:
        """
        Synchronously opens an image file, rotates it according to EXIF orientation,
        crops it center-weighted to a square, resizes it using Lanczos resampling,
        and saves it to WebP binary bytes.
        """
        try:
            with Image.open(file_path) as img:
                # Apply EXIF rotation standard
                img = ThumbnailService.auto_rotate(img)
                
                width, height = img.size
                
                # Perform center crop to obtain square thumbnail
                min_dim = min(width, height)
                left = (width - min_dim) // 2
                top = (height - min_dim) // 2
                right = left + min_dim
                bottom = top + min_dim
                
                img_cropped = img.crop((left, top, right, bottom))
                img_cropped.thumbnail((size, size), Image.Resampling.LANCZOS)
                
                out_buffer = io.BytesIO()
                img_cropped.save(out_buffer, format="WEBP", quality=80)
                return out_buffer.getvalue()
        except Exception as e:
            logger.error(f"Error executing synchronous thumbnail generation: {e}")
            raise ValueError(f"Failed to generate thumbnail: {e}")

    @staticmethod
    def auto_rotate(img: Image.Image) -> Image.Image:
        """
        Examines EXIF orientation tag (0x0112 / 274) and rotates image accordingly.
        """
        try:
            exif = img.getexif()
            if not exif:
                return img
            
            # Orientation tag code
            orientation = exif.get(274)
            if orientation == 3:
                return img.rotate(180, expand=True)
            elif orientation == 6:
                return img.rotate(270, expand=True)
            elif orientation == 8:
                return img.rotate(90, expand=True)
        except Exception as e:
            logger.warning(f"Could not apply EXIF orientation auto-rotation: {e}")
        return img

    @classmethod
    async def generate_thumbnail(cls, file_path: str, size: int = 300) -> bytes:
        """
        Offloads the CPU-intensive PIL resizing work to the default loop thread pool.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            cls.generate_thumbnail_sync,
            file_path,
            size
        )
