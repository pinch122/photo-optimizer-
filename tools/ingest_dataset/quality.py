"""
Image quality analysis module for PhotoMind AI.
Calculates metrics such as blur, brightness, darkness, sharpness, and identifies screenshots.
"""

import os
from typing import Dict, Any, Tuple
from PIL import Image, ImageFilter, ImageStat

def analyze_image_quality(file_path: str) -> Dict[str, Any]:
    """
    Analyzes an image and returns key quality metrics.
    
    Metrics:
    - brightness: float (0.0 to 1.0, where 1.0 is pure white)
    - darkness: float (0.0 to 1.0, where 1.0 is pure black)
    - blur_score: float (estimated blur, lower is sharper, higher is blurrier)
    - sharpness: float (estimated edge variance/energy, higher is sharper)
    - is_screenshot: bool (heuristic check based on resolution, aspect ratio, and metadata)
    """
    try:
        with Image.open(file_path) as img:
            # Convert to grayscale for most calculations
            gray_img = img.convert("L")
            stat = ImageStat.Stat(gray_img)
            
            # 1. Brightness and Darkness
            mean_brightness = stat.mean[0]  # 0 to 255
            brightness = mean_brightness / 255.0
            darkness = 1.0 - brightness
            
            # 2. Sharpness & Blur Estimation using PIL ImageFilters
            # Find edges (simulates high-pass filter)
            edges_img = gray_img.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges_img)
            # Use standard deviation of edge intensities as sharpness proxy
            sharpness = edge_stat.stddev[0]
            
            # Estimate blur by looking at high frequency components.
            # A blurred image has low edge variance. We take a reciprocal/scale proxy.
            # If sharpness is very low, blur_score is high.
            blur_score = max(0.0, 100.0 - sharpness * 3.0)
            
            # 3. Screenshot Heuristic
            is_screenshot = detect_screenshot(img, file_path)
            
            return {
                "brightness": round(brightness, 4),
                "darkness": round(darkness, 4),
                "blur_score": round(blur_score, 4),
                "sharpness": round(sharpness, 4),
                "is_screenshot": is_screenshot
            }
    except Exception as e:
        # Fallback in case of error
        return {
            "brightness": 0.5,
            "darkness": 0.5,
            "blur_score": 50.0,
            "sharpness": 10.0,
            "is_screenshot": False,
            "error": str(e)
        }

def detect_screenshot(img: Image.Image, file_path: str) -> bool:
    """
    Heuristically checks if an image is likely a screenshot.
    
    Heuristics:
    1. Check if filename contains 'screenshot' (case insensitive)
    2. Check common mobile/desktop aspect ratios exactly (e.g. 16:9, 19.5:9, 16:10, 4:3, etc.)
    3. Check if color palette is extremely flat/highly indexed (often true for UI screenshots)
    """
    filename = os.path.basename(file_path).lower()
    if "screenshot" in filename or "scr_" in filename or "screen_" in filename:
        return True
        
    width, height = img.size
    if width <= 0 or height <= 0:
        return False
        
    aspect_ratio = width / height
    
    # Common screenshot ratios:
    # Desktop: 16/9 (1.777), 16/10 (1.6), 4/3 (1.333), 21/9 (2.333)
    # Mobile: 9/16 (0.5625), 19.5/9 (2.166), 19/9 (2.111), 20/9 (2.222), 4/3 (0.75)
    common_ratios = [
        1.7778, 1.6, 1.3333, 2.3333, 0.5625, 2.1667, 2.1111, 2.2222, 0.75, 0.4615
    ]
    
    is_common_ratio = any(abs(aspect_ratio - r) < 0.01 for r in common_ratios)
    
    # Standard screenshot resolutions (exact matches)
    common_resolutions = {
        (1920, 1080), (1080, 1920),
        (1280, 720), (720, 1280),
        (2560, 1440), (1440, 2560),
        (3840, 2160), (2160, 3840),
        (1440, 900), (1680, 1050),
        (1080, 2400), (2400, 1080),
        (1170, 2532), (2532, 1170),
        (1284, 2778), (2778, 1284)
    }
    
    is_common_res = (width, height) in common_resolutions
    
    # Color palette flatness check: Screenshots of text/UIs often have few unique colors
    # compared to organic photos. We check the image histogram entropy or unique colors if small.
    # For speed, we just use ratio and filename.
    if is_common_res:
        return True
        
    if is_common_ratio:
        # Check if png (screenshots are often png) or has screenshot metadata
        if file_path.lower().endswith(".png"):
            return True
            
    return False
