import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from app.logging_config import logger

class MetadataService:
    @staticmethod
    def extract_metadata_sync(file_path: str) -> Dict[str, Any]:
        """
        Synchronously parses EXIF and dimension properties from the specified file.
        Returns a dictionary populated with extracted values, defaulting to None where tags are absent.
        """
        metadata = {
            "width": 0,
            "height": 0,
            "camera_make": None,
            "camera_model": None,
            "exposure_time": None,
            "f_number": None,
            "iso_speed": None,
            "gps_latitude": None,
            "gps_longitude": None,
            "taken_at": None
        }

        try:
            with Image.open(file_path) as img:
                metadata["width"], metadata["height"] = img.size
                
                # Extract raw EXIF dictionary
                exif_data = img.getexif()
                if not exif_data:
                    return metadata
                
                # Check for standard EXIF tags
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    if tag_name == "Make":
                        metadata["camera_make"] = str(value).strip()
                    elif tag_name == "Model":
                        metadata["camera_model"] = str(value).strip()
                    elif tag_name == "ExposureTime":
                        metadata["exposure_time"] = str(value)
                    elif tag_name == "FNumber":
                        try:
                            metadata["f_number"] = f"f/{float(value):.2f}"
                        except Exception:
                            metadata["f_number"] = str(value)
                    elif tag_name == "ISOSpeedRatings":
                        if isinstance(value, (tuple, list)):
                            metadata["iso_speed"] = int(value[0]) if value else None
                        else:
                            metadata["iso_speed"] = int(value)
                    elif tag_name == "DateTimeOriginal":
                        try:
                            dt_str = str(value).strip()
                            # EXIF formats timestamps as YYYY:MM:DD HH:MM:SS
                            dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                            metadata["taken_at"] = dt.replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                    elif tag_name == "GPSInfo":
                        # GPS info dictionary contains nested mappings
                        gps_dict = {}
                        for gps_tag_id, gps_val in value.items():
                            gps_tag_name = GPSTAGS.get(gps_tag_id, gps_tag_id)
                            gps_dict[gps_tag_name] = gps_val
                        
                        lat_val = gps_dict.get("GPSLatitude")
                        lat_ref = gps_dict.get("GPSLatitudeRef")
                        lng_val = gps_dict.get("GPSLongitude")
                        lng_ref = gps_dict.get("GPSLongitudeRef")

                        if lat_val and lat_ref:
                            metadata["gps_latitude"] = MetadataService.get_decimal_from_dms(lat_val, lat_ref)
                        if lng_val and lng_ref:
                            metadata["gps_longitude"] = MetadataService.get_decimal_from_dms(lng_val, lng_ref)

                # Fallback check inside EXIF subclass blocks if tags are not populated at base level
                # get_ifd(0x8769) extracts the EXIF specific sub-IFD directory
                try:
                    exif_sub_ifd = exif_data.get_ifd(0x8769)
                    if exif_sub_ifd:
                        for tag_id, value in exif_sub_ifd.items():
                            tag_name = TAGS.get(tag_id, tag_id)
                            if tag_name == "DateTimeOriginal" and not metadata["taken_at"]:
                                try:
                                    dt_str = str(value).strip()
                                    dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                                    metadata["taken_at"] = dt.replace(tzinfo=timezone.utc)
                                except Exception:
                                    pass
                            elif tag_name == "ExposureTime" and not metadata["exposure_time"]:
                                metadata["exposure_time"] = str(value)
                            elif tag_name == "FNumber" and not metadata["f_number"]:
                                try:
                                    metadata["f_number"] = f"f/{float(value):.2f}"
                                except Exception:
                                    metadata["f_number"] = str(value)
                            elif tag_name == "ISOSpeedRatings" and not metadata["iso_speed"]:
                                if isinstance(value, (tuple, list)):
                                    metadata["iso_speed"] = int(value[0]) if value else None
                                else:
                                    metadata["iso_speed"] = int(value)
                except Exception:
                    pass

                # GPS sub-IFD check 0x8825 if not found in base tags
                try:
                    gps_ifd = exif_data.get_ifd(0x8825)
                    if gps_ifd and not metadata["gps_latitude"]:
                        lat_val = gps_ifd.get(2)  # GPSLatitude tag index is 2
                        lat_ref = gps_ifd.get(1)  # GPSLatitudeRef tag index is 1
                        lng_val = gps_ifd.get(4)  # GPSLongitude tag index is 4
                        lng_ref = gps_ifd.get(3)  # GPSLongitudeRef tag index is 3

                        if lat_val and lat_ref:
                            metadata["gps_latitude"] = MetadataService.get_decimal_from_dms(lat_val, lat_ref)
                        if lng_val and lng_ref:
                            metadata["gps_longitude"] = MetadataService.get_decimal_from_dms(lng_val, lng_ref)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error parsing metadata for file: {file_path}. Exception: {e}")
        
        return metadata

    @staticmethod
    def get_decimal_from_dms(dms: Any, ref: Any) -> Optional[float]:
        """
        Converts GPS degrees, minutes, seconds tuple format into standard decimal degrees coordinate.
        """
        try:
            degrees = float(dms[0])
            minutes = float(dms[1])
            seconds = float(dms[2])
            
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            if ref in ['S', 'W', 's', 'w']:
                decimal = -decimal
            return decimal
        except Exception:
            return None

    @classmethod
    async def extract_metadata(cls, file_path: str) -> Dict[str, Any]:
        """
        Spawns CPU-bound metadata readings on separate worker threads.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            cls.extract_metadata_sync,
            file_path
        )
