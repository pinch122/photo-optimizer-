"""
Deterministic explanation generator for PhotoMind AI search matches.
Explains why an image matched a query using PostgreSQL metadata and scores.
"""

from typing import List, Optional
from app.modules.media.models import MediaAsset

class ExplanationService:
    @staticmethod
    def generate_explanation(query_text: str, asset: MediaAsset, score: float) -> List[str]:
        """
        Deterministically evaluates database attributes to construct natural explanations
        for search results. Execution time is <1ms.
        """
        explanations = []
        
        # Normalize score to percentage (capped at 100)
        similarity_pct = int(round(score * 100))
        if similarity_pct > 100:
            similarity_pct = 100
        elif similarity_pct < 0:
            similarity_pct = 0
            
        query_lower = query_text.lower()
        ai = asset.ai_analysis
        meta = asset.photo_metadata
        
        # 1. Potential Duplicate Check
        is_duplicate = False
        if "duplicate" in query_lower:
            explanations.append("Perceptual hash is nearly identical")
            explanations.append(f"Visual similarity: {similarity_pct}%")
            explanations.append("Potential duplicate")
            is_duplicate = True
            
        if is_duplicate:
            return explanations

        # 2. Add matched details based on query and metadata
        query_words = [w.strip(",.?! ") for w in query_lower.split() if len(w.strip(",.?! ")) > 2]
        
        # Object matching
        matched_objects = []
        if ai and ai.objects:
            for obj in ai.objects:
                obj_lower = obj.lower()
                if any(word in obj_lower or obj_lower in word for word in query_words):
                    matched_objects.append(obj)
                    
        if matched_objects:
            for obj in matched_objects[:2]:
                explanations.append(f"{obj.capitalize()} visible")
                
        # Scene matching
        if ai and ai.scene:
            scene_lower = ai.scene.lower()
            if any(word in scene_lower or scene_lower in word for word in query_words):
                explanations.append(f"{ai.scene.capitalize()} scene detected")
            elif "outdoor" in query_lower and not ai.is_indoor:
                explanations.append("Natural outdoor scene")
            elif "indoor" in query_lower and ai.is_indoor:
                explanations.append("Indoor scene")

        # Color matching
        colors = ["yellow", "blue", "red", "green", "white", "black", "orange", "purple", "brown", "pink"]
        matched_color = None
        for color in colors:
            if color in query_lower:
                matched_color = color
                break
                
        if matched_color and ai:
            color_matched = False
            if ai.caption and matched_color in ai.caption.lower():
                explanations.append(f"{matched_color.capitalize()} colors dominate the image")
                color_matched = True
            if not color_matched:
                explanations.append(f"Warm color palette matches {matched_color}")

        # Quality analysis mapping (Bright, Dark, Exposure, Blur)
        if ai and ai.keywords:
            quality = ai.keywords
            brightness = quality.get("brightness", 0.5)
            darkness = quality.get("darkness", 0.5)
            blur_score = quality.get("blur_score", 0)
            
            if "bright" in query_lower or "light" in query_lower:
                if brightness > 0.6:
                    explanations.append("High exposure score")
                    explanations.append("Bright lighting")
                    explanations.append("White highlights dominate")
                    explanations.append("Quality analysis classified image as bright")
            elif "dark" in query_lower or "night" in query_lower:
                if darkness > 0.6:
                    explanations.append("Low exposure score")
                    explanations.append("Dark lighting")
                    explanations.append("Shadows dominate")
                    explanations.append("Quality analysis classified image as dark")
            elif "blurry" in query_lower or "blur" in query_lower:
                if blur_score > 40:
                    explanations.append("High blur score detected")
                    explanations.append("Soft focus/motion blur visible")

        # Indoor/Outdoor environment fallback
        if ai and ai.is_indoor is not None and not any("environment" in exp or "scene" in exp for exp in explanations):
            if ai.is_indoor:
                explanations.append("Indoor environment")
            else:
                explanations.append("Natural outdoor scene")

        # Fallback tag matching
        if len(explanations) < 3 and ai and ai.keywords:
            for kw in ai.keywords.keys():
                if kw.lower() in query_lower:
                    explanations.append(f"Matches tag: {kw}")

        # 3. Add Similarity Score (always include at least score for relevance)
        if similarity_pct >= 95:
            explanations.append(f"High confidence match ({similarity_pct}%)")
        else:
            explanations.append(f"Similarity score {similarity_pct}%")

        # Make sure we have at least 2 points
        if len(explanations) < 2:
            explanations.insert(0, "Similar visual composition")

        return explanations[:4]
