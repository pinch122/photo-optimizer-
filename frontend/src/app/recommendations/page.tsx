"use client";

import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { searchMedia, getThumbnailUrl, deleteMedia } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import PageHeader from "@/components/layout/PageHeader";
import Link from "next/link";
import { 
  Sparkles, Trash2, CheckCircle2, AlertCircle, Loader2, ArrowLeft, 
  CheckSquare, Square, Info, ShieldAlert, FileText, Image, Star, Eye, Layers
} from "lucide-react";

// Local storage key for kept recommendations
const KEPT_REC_KEY = "photomind_kept_recommendations";

// Hamming distance calculator for pHash matching
function getHammingDistance(hex1: string, hex2: string): number {
  if (!hex1 || !hex2 || hex1.length !== hex2.length) return 999;
  let distance = 0;
  for (let i = 0; i < hex1.length; i++) {
    const val1 = parseInt(hex1[i], 16);
    const val2 = parseInt(hex2[i], 16);
    let diff = val1 ^ val2;
    while (diff > 0) {
      if (diff & 1) distance++;
      diff >>= 1;
    }
  }
  return distance;
}

interface SimilarityMatch {
  isMatch: boolean;
  confidence: number;
  explanation: string;
}

const VARIATION_RE = /^(dark|bright|cropped|rotated|resized|blurred|edited|compressed|scaled|small|thumb)_+/i;

function isOriginalFile(fn: string): boolean {
  return !VARIATION_RE.test(fn.toLowerCase());
}
// ─── Quality Accessors ────────────────────────────────────────────────────────
// Read quality metrics computed during ingestion and stored in
// image_ai_analysis.keywords JSON column. No re-computation here.

// TODO: The brightness field (item.ai_analysis.keywords.brightness) is still
// stored in the database and available for future use. A "Possible Low Quality
// Photos" recommendation category could be added here once a more reliable
// AI quality scoring model exists that can distinguish poor exposure from
// intentional low-light photography with high confidence.

const ISSUE_LABEL_MAP: Record<string, string> = {
  MOTION_BLUR: "Out of focus / motion blur",
  OUT_OF_FOCUS: "Out of focus",
  UNDEREXPOSED: "Underexposed",
  OVEREXPOSED: "Overexposed",
  LOW_RESOLUTION: "Low resolution",
  NOISY: "High noise",
  LENS_OBSTRUCTION: "Lens obstruction",
};

function getQualityReasons(item: any): string[] {
  const quality = item.quality_assessment;
  if (!quality) return [];

  const reasons: string[] = [];
  if (Array.isArray(quality.issues) && quality.issues.length > 0) {
    quality.issues.forEach((issue: string) => {
      const label = ISSUE_LABEL_MAP[issue] || issue.replace(/_/g, " ").toLowerCase();
      if (!reasons.includes(label)) {
        reasons.push(label);
      }
    });
  }

  if (reasons.length === 0) {
    if (typeof quality.sharpness_score === "number" && quality.sharpness_score < 0.3) {
      reasons.push("Low sharpness");
    }
    if (typeof quality.exposure_score === "number" && quality.exposure_score < 0.3) {
      reasons.push("Poor exposure");
    }
    if (typeof quality.resolution_score === "number" && quality.resolution_score < 0.2) {
      reasons.push("Low resolution");
    }
  }

  return reasons;
}

function isLowQualityPhoto(item: any): boolean {
  const quality = item.quality_assessment;
  if (!quality) return false;

  const grade = quality.quality_grade?.toUpperCase();

  // EXPLICIT RULE: Never recommend GOOD or EXCELLENT photos regardless of blur score
  if (grade === "GOOD" || grade === "EXCELLENT") {
    return false;
  }

  // Primary filter: POOR or VERY_POOR
  if (grade === "POOR" || grade === "VERY_POOR") {
    return true;
  }

  if (typeof quality.overall_score === "number" && quality.overall_score < 0.45) {
    return true;
  }

  return false;
}

function getGradeWeight(grade: string | null | undefined): number {
  const g = grade?.toUpperCase();
  if (g === "VERY_POOR") return 1;
  if (g === "POOR") return 2;
  if (g === "FAIR") return 3;
  if (g === "GOOD") return 4;
  if (g === "EXCELLENT") return 5;
  return 9;
}

function compareLowQuality(a: any, b: any): number {
  const gradeA = getGradeWeight(a.quality_assessment?.quality_grade);
  const gradeB = getGradeWeight(b.quality_assessment?.quality_grade);

  // 1. VERY_POOR first, then POOR
  if (gradeA !== gradeB) {
    return gradeA - gradeB;
  }

  // 2. Overall score ascending (worst quality first)
  const scoreA = a.quality_assessment?.overall_score ?? 1.0;
  const scoreB = b.quality_assessment?.overall_score ?? 1.0;
  return scoreA - scoreB;
}

function getStoredBlurScore(item: any): number | null {
  if (typeof item.quality_assessment?.blur_score === "number") {
    return item.quality_assessment.blur_score;
  }
  const val = item.ai_analysis?.keywords?.blur_score;
  return typeof val === "number" ? val : null;
}

const GENERIC_WORDS = new Set([
  "photo", "photos", "image", "images", "picture", "pictures",
  "outdoor", "outdoors", "indoor", "indoors", "nature", "landscape",
  "sky", "tree", "trees", "grass", "field", "fields", "cloud", "clouds",
  "scene", "scenes", "view", "views", "background", "color", "colors",
  "light", "lighting", "shot", "front", "close-up", "day", "daytime",
  "night", "overall", "small", "large", "high", "low", "wood", "wooden",
  "floor", "table", "wall", "room"
]);

function isMeaningfulWord(w: string): boolean {
  const clean = w.toLowerCase().trim();
  return clean.length >= 3 && !GENERIC_WORDS.has(clean);
}

function getMeaningfulWords(text: string | null | undefined): string[] {
  if (!text) return [];
  return text
    .toLowerCase()
    .split(/[\s,._\-:;!?"'()]+/)
    .filter(isMeaningfulWord);
}

function isSceneCompatible(sceneA: string | null, sceneB: string | null): boolean {
  if (!sceneA || !sceneB) return true; // Missing scene info is neutral

  const sA = sceneA.toLowerCase().trim();
  const sB = sceneB.toLowerCase().trim();

  if (sA === sB) return true;

  // Compatible landscape/beach/mountain variants
  const isBeachA = sA.includes("beach") || sA.includes("coast") || sA.includes("ocean") || sA.includes("sea") || sA.includes("sunset");
  const isBeachB = sB.includes("beach") || sB.includes("coast") || sB.includes("ocean") || sB.includes("sea") || sB.includes("dusk");
  if (isBeachA && isBeachB) return true;

  const isMountainA = sA.includes("mountain") || sA.includes("valley") || sA.includes("hill") || sA.includes("peak");
  const isMountainB = sB.includes("mountain") || sB.includes("valley") || sB.includes("hill") || sB.includes("landscape");
  if (isMountainA && isMountainB) return true;

  // Major contradictions
  if (isBeachA && (sB.includes("floor") || sB.includes("room") || sB.includes("kitchen") || sB.includes("office"))) {
    return false;
  }
  if ((sA.includes("floor") || sA.includes("room")) && isBeachB) {
    return false;
  }

  return true;
}

interface ValidationResult {
  isValid: boolean;
  overallConfidence: number;
  visualSimilarity: number;
  metadataConsistency: number;
  explanation: string;
  matchedReasons: string[];
}

function validateCandidatePair(itemA: any, itemB: any): ValidationResult {
  // 1. Visual Similarity (from pHash distance)
  if (!itemA.p_hash || !itemB.p_hash) {
    return { isValid: false, overallConfidence: 0, visualSimilarity: 0, metadataConsistency: 0, explanation: "", matchedReasons: [] };
  }

  const dist = getHammingDistance(itemA.p_hash, itemB.p_hash);
  if (dist > 8) {
    return { isValid: false, overallConfidence: 0, visualSimilarity: 0, metadataConsistency: 0, explanation: "", matchedReasons: [] };
  }

  // Visual similarity percentage: dist 0=100%, 1-2=95%, 3-4=90%, 5-6=85%, 7-8=80%
  let visualSimilarity = 80;
  if (dist === 0) visualSimilarity = 100;
  else if (dist <= 2) visualSimilarity = 95;
  else if (dist <= 4) visualSimilarity = 90;
  else if (dist <= 6) visualSimilarity = 85;

  const aiA = itemA.ai_analysis || {};
  const aiB = itemB.ai_analysis || {};

  const matchedReasons: string[] = [];

  // Check 1: Explicit Contradictions (Subject/DocType/Scene mismatches)
  const docTypeA = (aiA.document_type || "").toLowerCase().trim();
  const docTypeB = (aiB.document_type || "").toLowerCase().trim();

  // Contradiction A: DocType vs non-doc or different docs (e.g. Receipt vs Dog, Passport vs Car)
  if (docTypeA && docTypeB && docTypeA !== docTypeB && docTypeA !== "other" && docTypeB !== "other") {
    return { isValid: false, overallConfidence: 0, visualSimilarity, metadataConsistency: 0, explanation: "Rejected: Incompatible document types.", matchedReasons: [] };
  }

  // Contradiction B: Incompatible scenes (e.g. Beach vs Wooden floor)
  if (!isSceneCompatible(aiA.scene, aiB.scene)) {
    return { isValid: false, overallConfidence: 0, visualSimilarity, metadataConsistency: 0, explanation: "Rejected: Incompatible scene classification.", matchedReasons: [] };
  }

  // Check 2: Signal Agreement & Consistency Weights
  // Weights: Objects (35%), Scene (25%), Keywords (20%), OCR (10%), People Count (5%), Event Type (5%)
  let objectScore = 0.5;
  const objsA = (aiA.objects || []).filter(isMeaningfulWord);
  const objsB = (aiB.objects || []).filter(isMeaningfulWord);

  if (objsA.length > 0 && objsB.length > 0) {
    const commonObjs = objsA.filter((o: string) => objsB.includes(o));
    if (commonObjs.length > 0) {
      objectScore = 1.0;
      matchedReasons.push(`Depict matching ${commonObjs[0]}`);
    } else {
      objectScore = 0.1; // Objects present but zero overlap
    }
  }

  let sceneScore = 0.5;
  if (aiA.scene && aiB.scene) {
    const sceneStrA = aiA.scene.toLowerCase().trim();
    const sceneStrB = aiB.scene.toLowerCase().trim();
    if (sceneStrA === sceneStrB || isSceneCompatible(sceneStrA, sceneStrB)) {
      sceneScore = 1.0;
      matchedReasons.push(`${sceneStrA} scene detected`);
    } else {
      sceneScore = 0.2;
    }
  }

  let keywordScore = 0.5;
  const wordsA = [
    ...getMeaningfulWords(aiA.caption),
    ...Object.keys(aiA.keywords || {}).filter(isMeaningfulWord)
  ];
  const wordsB = [
    ...getMeaningfulWords(aiB.caption),
    ...Object.keys(aiB.keywords || {}).filter(isMeaningfulWord)
  ];
  if (wordsA.length > 0 && wordsB.length > 0) {
    const setB = new Set(wordsB);
    const commonWords = wordsA.filter(w => setB.has(w));
    const unionSize = new Set([...wordsA, ...wordsB]).size;
    const jaccard = unionSize > 0 ? commonWords.length / unionSize : 0;
    if (jaccard >= 0.2) {
      keywordScore = 1.0;
      matchedReasons.push("Matching caption descriptions");
    } else if (commonWords.length > 0) {
      keywordScore = 0.7;
    } else {
      keywordScore = 0.3;
    }
  }

  let ocrScore = 0.5;
  if (docTypeA && docTypeB && docTypeA === docTypeB && docTypeA.length > 0) {
    ocrScore = 1.0;
    matchedReasons.push(`Same document type (${docTypeA})`);
  }
  const textA = getMeaningfulWords(aiA.detected_text);
  const textB = getMeaningfulWords(aiB.detected_text);
  if (textA.length > 0 && textB.length > 0) {
    const commonText = textA.filter(t => textB.includes(t));
    if (commonText.length >= 2) {
      ocrScore = 1.0;
      matchedReasons.push("Matching OCR text");
    }
  }

  let peopleScore = 0.5;
  if (typeof aiA.people_count === "number" && typeof aiB.people_count === "number") {
    if (Math.abs(aiA.people_count - aiB.people_count) <= 1) {
      peopleScore = 1.0;
      if (aiA.people_count > 0) matchedReasons.push("Matching people count");
    } else {
      peopleScore = 0.2;
    }
  }

  let eventScore = 0.5;
  if (aiA.event_type && aiB.event_type && aiA.event_type.toLowerCase() === aiB.event_type.toLowerCase()) {
    eventScore = 1.0;
    matchedReasons.push(`Matching ${aiA.event_type.toLowerCase()} event`);
  }

  // Timestamp Signal
  const timeA = new Date(itemA.taken_at).getTime();
  const timeB = new Date(itemB.taken_at).getTime();
  const timeDiffSec = Math.abs(timeA - timeB) / 1000;
  if (timeDiffSec <= 30) {
    matchedReasons.push(`Captured within ${Math.round(timeDiffSec)} seconds`);
  }

  // Weighted Metadata Consistency Score (0% - 100%)
  const metadataConsistency = Math.round(
    (objectScore * 0.35 +
     sceneScore * 0.25 +
     keywordScore * 0.20 +
     ocrScore * 0.10 +
     peopleScore * 0.05 +
     eventScore * 0.05) * 100
  );

  // Acceptance Threshold: Consistency >= 40% AND at least 1 corroborating metadata or time signal
  const isValid = metadataConsistency >= 40 && matchedReasons.length > 0;

  // Overall Confidence: 50% Visual Similarity + 50% Metadata Consistency
  const overallConfidence = Math.round(0.5 * visualSimilarity + 0.5 * metadataConsistency);

  // Generate Explanation String
  let explanation = "";
  if (matchedReasons.length > 0) {
    explanation = `Grouped because: • ${matchedReasons.join(" • ")}`;
  } else {
    explanation = "Grouped based on visual similarity and metadata consistency.";
  }

  return {
    isValid,
    overallConfidence,
    visualSimilarity,
    metadataConsistency,
    explanation,
    matchedReasons
  };
}

function isRotatedOrMatchingRatio(wA: number, hA: number, wB: number, hB: number): boolean {
  if (!wA || !hA || !wB || !hB) return true; // Missing dimensions neutral

  const arA = wA / hA;
  const arB = wB / hB;
  const arB_rot = hB / wB;

  // Direct match or 90-degree rotation match
  const diffDirect = Math.abs(arA - arB);
  const diffRotated = Math.abs(arA - arB_rot);

  // Allow ratio difference up to 0.40 to accommodate crops
  return diffDirect <= 0.40 || diffRotated <= 0.40;
}

function validateNearDuplicatePair(itemA: any, itemB: any): boolean {
  const aiA = itemA.ai_analysis || {};
  const aiB = itemB.ai_analysis || {};
  const metaA = itemA.photo_metadata || {};
  const metaB = itemB.photo_metadata || {};

  // Rule 1: Aspect Ratio Validation (allow crops, resizes, rotations)
  const wA = metaA.width || itemA.width;
  const hA = metaA.height || itemA.height;
  const wB = metaB.width || itemB.width;
  const hB = metaB.height || itemB.height;

  if (wA && hA && wB && hB) {
    if (!isRotatedOrMatchingRatio(wA, hA, wB, hB)) {
      return false; // Rejected: Significantly different aspect ratios (not rotated or cropped)
    }
  }

  // Rule 2: Scene Validation (Reject pairs with different scenes)
  const sceneA = (aiA.scene || "").toLowerCase().trim();
  const sceneB = (aiB.scene || "").toLowerCase().trim();
  if (sceneA && sceneB && sceneA !== sceneB) {
    if (!isSceneCompatible(sceneA, sceneB)) {
      return false; // Rejected: Incompatible scenes
    }
  }

  // Rule 3: Dominant Objects Validation (Reject pairs with different dominant objects)
  const objsA = (aiA.objects || []).map((o: string) => o.toLowerCase().trim()).filter(isMeaningfulWord);
  const objsB = (aiB.objects || []).map((o: string) => o.toLowerCase().trim()).filter(isMeaningfulWord);

  if (objsA.length > 0 && objsB.length > 0) {
    const commonObjs = objsA.filter((o: string) => objsB.includes(o));
    if (commonObjs.length === 0) {
      return false; // Rejected: Completely different dominant objects
    }
  }

  // Rule 4: Caption Validation (Reject pairs with completely different captions)
  const wordsA = getMeaningfulWords(aiA.caption);
  const wordsB = getMeaningfulWords(aiB.caption);

  if (wordsA.length >= 3 && wordsB.length >= 3) {
    const setB = new Set(wordsB);
    const commonWords = wordsA.filter(w => setB.has(w));
    const unionSize = new Set([...wordsA, ...wordsB]).size;
    const jaccard = unionSize > 0 ? commonWords.length / unionSize : 0;
    if (jaccard < 0.10 && commonWords.length === 0) {
      return false; // Rejected: Completely different captions
    }
  }

  // Rule 5: Dominant Color Differences (Reject pairs with large color differences unless brightness/contrast edit)
  const colorsA = (aiA.dominant_colors || []).map((c: string) => c.toLowerCase().trim());
  const colorsB = (aiB.dominant_colors || []).map((c: string) => c.toLowerCase().trim());

  if (colorsA.length >= 2 && colorsB.length >= 2) {
    const commonColors = colorsA.filter((c: string) => colorsB.includes(c));
    if (commonColors.length === 0) {
      const isMonochromeA = colorsA.every((c: string) => c.includes("black") || c.includes("white") || c.includes("gray"));
      const isMonochromeB = colorsB.every((c: string) => c.includes("black") || c.includes("white") || c.includes("gray"));
      if (!isMonochromeA && !isMonochromeB) {
        return false; // Rejected: Large dominant color difference
      }
    }
  }

  return true;
}

interface KeepRecommendation {
  id: string;
  reasons: string[];
}

function selectBestToKeep(group: any[]): KeepRecommendation {
  const scores = group.map(item => {
    let score = 0;
    const reasons: string[] = [];

    // Is it an unprocessed original?
    if (isOriginalFile(item.filename)) {
      score += 30;
      reasons.push("Original (unprocessed)");
    }

    // File size (proxy for resolution — largest = highest quality)
    const maxSize = Math.max(...group.map(i => i.file_size));
    if (item.file_size === maxSize && group.length > 1) {
      score += 20;
      reasons.push("Highest resolution");
    } else if (item.file_size >= maxSize * 0.95) {
      score += 10;
      reasons.push("Near-highest resolution");
    }

    // Recency (for edited versions — the newest edit is preferred)
    const latestTime = Math.max(...group.map(i => new Date(i.taken_at).getTime()));
    if (new Date(item.taken_at).getTime() === latestTime && group.length > 1) {
      score += 5;
    }

    return { item, score, reasons };
  });

  scores.sort((a, b) => b.score - a.score);
  const best = scores[0];

  // Always show at least one reason
  if (best.reasons.length === 0) best.reasons.push("Largest file");

  return { id: best.item.id, reasons: best.reasons };
}

interface SimilarGroup {
  group: any[];
  explanation: string;
  confidence: number;
  keepRecommendation: KeepRecommendation;
}

function groupSimilarPhotos(
  items: any[],
  exactDupIds: Set<string>,
  nearDupIds: Set<string>
): SimilarGroup[] {
  const groups: SimilarGroup[] = [];
  const visited = new Set<string>();

  const filterItems = items.filter(item => !exactDupIds.has(item.id) && !nearDupIds.has(item.id));

  for (let i = 0; i < filterItems.length; i++) {
    const itemA = filterItems[i];
    if (visited.has(itemA.id)) continue;

    const currentGroup = [itemA];
    let groupExplanation = "";
    let maxConfidence = 0;

    for (let j = i + 1; j < filterItems.length; j++) {
      const itemB = filterItems[j];
      if (visited.has(itemB.id)) continue;

      const val = validateCandidatePair(itemA, itemB);
      if (val.isValid) {
        currentGroup.push(itemB);
        visited.add(itemB.id);
        if (val.overallConfidence > maxConfidence) {
          maxConfidence = val.overallConfidence;
          groupExplanation = val.explanation;
        }
      }
    }

    if (currentGroup.length > 1) {
      groups.push({
        group: currentGroup,
        explanation: groupExplanation,
        confidence: maxConfidence,
        keepRecommendation: selectBestToKeep(currentGroup),
      });
      visited.add(itemA.id);
    }
  }

  return groups;
}



export default function RecommendationsPage() {
  const queryClient = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [keptIds, setKeptIds] = useState<Set<string>>(new Set());
  const [photoToDelete, setPhotoToDelete] = useState<any | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Load kept IDs from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(KEPT_REC_KEY);
      if (stored) {
        setKeptIds(new Set(JSON.parse(stored)));
      }
    } catch (e) {
      console.error("Failed to load kept recommendations", e);
    }
  }, []);

  // Sync kept IDs to localStorage
  const saveKeptIds = (newKept: Set<string>) => {
    setKeptIds(newKept);
    try {
      localStorage.setItem(KEPT_REC_KEY, JSON.stringify(Array.from(newKept)));
    } catch (e) {
      console.error("Failed to save kept recommendations", e);
    }
  };

  // Fetch all media in the library
  const { data: mediaData, isLoading } = useQuery({
    queryKey: ["recommendations-all-media"],
    queryFn: () => searchMedia("photo", 50000, 0),
  });

  const allItems = mediaData?.items ?? [];

  // Filter out already deleted or kept items
  const activeItems = allItems.filter(item => !keptIds.has(item.id));

  // Category Processing Logic

  // 1. Exact Duplicates (strict matching: same pHash Hamming distance of 0, or matching size, time, and name)
  const exactDuplicateGroups: any[][] = [];
  const exactDupIds = new Set<string>();
  const visitedExact = new Set<string>();

  for (let i = 0; i < activeItems.length; i++) {
    const itemA = activeItems[i];
    if (visitedExact.has(itemA.id)) continue;

    const currentGroup = [itemA];
    for (let j = i + 1; j < activeItems.length; j++) {
      const itemB = activeItems[j];
      if (visitedExact.has(itemB.id)) continue;

      let isDuplicate = false;
      if (itemA.p_hash && itemB.p_hash) {
        const dist = getHammingDistance(itemA.p_hash, itemB.p_hash);
        if (dist === 0) {
          isDuplicate = true;
        }
      } else {
        const nameA = itemA.filename.substring(0, itemA.filename.lastIndexOf('.')) || itemA.filename;
        const nameB = itemB.filename.substring(0, itemB.filename.lastIndexOf('.')) || itemB.filename;
        const cleanNameA = nameA.replace(/\s*\(copy\s*\d*\)|\s*\(\d*\)/gi, "").trim();
        const cleanNameB = nameB.replace(/\s*\(copy\s*\d*\)|\s*\(\d*\)/gi, "").trim();

        if (
          itemA.file_size === itemB.file_size &&
          new Date(itemA.taken_at).getTime() === new Date(itemB.taken_at).getTime() &&
          cleanNameA.toLowerCase() === cleanNameB.toLowerCase()
        ) {
          isDuplicate = true;
        }
      }

      if (isDuplicate) {
        currentGroup.push(itemB);
        visitedExact.add(itemB.id);
      }
    }

    if (currentGroup.length > 1) {
      exactDuplicateGroups.push(currentGroup);
      visitedExact.add(itemA.id);
      currentGroup.forEach(item => exactDupIds.add(item.id));
    }
  }

  // Display real exact duplicate groups only — no artificial fallback
  const displayExactDuplicateGroups = [...exactDuplicateGroups];

  // 2. Near Duplicates (pHash distance between 1 and 4 + Lightweight AI Validation)
  const nearDuplicateGroups: any[][] = [];
  const nearDupIds = new Set<string>();
  const visitedNear = new Set<string>();

  for (let i = 0; i < activeItems.length; i++) {
    const itemA = activeItems[i];
    if (visitedNear.has(itemA.id) || exactDupIds.has(itemA.id)) continue;

    const currentGroup = [itemA];
    for (let j = i + 1; j < activeItems.length; j++) {
      const itemB = activeItems[j];
      if (visitedNear.has(itemB.id) || exactDupIds.has(itemB.id)) continue;

      let isNearDuplicate = false;
      if (itemA.p_hash && itemB.p_hash) {
        const dist = getHammingDistance(itemA.p_hash, itemB.p_hash);
        if (dist >= 1 && dist <= 4) {
          // Candidate pHash match: run lightweight AI validation before accepting
          if (validateNearDuplicatePair(itemA, itemB)) {
            isNearDuplicate = true;
          }
        }
      }

      if (isNearDuplicate) {
        currentGroup.push(itemB);
        visitedNear.add(itemB.id);
      }
    }

    if (currentGroup.length > 1) {
      nearDuplicateGroups.push(currentGroup);
      visitedNear.add(itemA.id);
      currentGroup.forEach(item => nearDupIds.add(item.id));
    }
  }

  // Display real near duplicate groups only — no artificial fallback
  const displayNearDuplicateGroups = [...nearDuplicateGroups];

  // 3. Similar Photos — two-stage pipeline (candidate generation + AI signal validation)
  const similarGroups = groupSimilarPhotos(activeItems, exactDupIds, nearDupIds);

  // 4. Low Quality Photos — Multi-Signal Assessment
  const lowQualityPhotos = activeItems.filter(isLowQualityPhoto);

  // Sort by: 1. quality_grade (VERY_POOR first, then POOR), 2. overall_score ascending
  lowQualityPhotos.sort(compareLowQuality);
  const lowQualitySavings = lowQualityPhotos.reduce((sum, i) => sum + i.file_size, 0);

  // 5. Screenshots
  const screenshots = activeItems.filter(item => {
    return item.filename.toLowerCase().includes("screenshot") ||
           item.ai_analysis?.caption?.toLowerCase().includes("screenshot") ||
           item.ai_analysis?.document_type?.toLowerCase() === "screenshot";
  });

  // 7. Documents
  const documents = activeItems.filter(item => {
    const docType = item.ai_analysis?.document_type?.toLowerCase();
    return (docType && docType !== "screenshot" && docType !== "receipt") ||
           (item.ai_analysis?.detected_text && item.ai_analysis.detected_text.length > 120);
  });

  // 8. Receipts
  const receipts = activeItems.filter(item => {
    const text = item.ai_analysis?.detected_text?.toLowerCase() || "";
    return item.ai_analysis?.document_type?.toLowerCase() === "receipt" ||
           text.includes("receipt") || text.includes("invoice") || text.includes("total") || text.includes("payment");
  });

  // 9. IDs (Passport, Driving License, PAN, Aadhaar)
  const ids = activeItems.filter(item => {
    const text = item.ai_analysis?.detected_text?.toLowerCase() || "";
    const caption = item.ai_analysis?.caption?.toLowerCase() || "";
    return text.includes("passport") || text.includes("driving license") || text.includes("pan card") || 
           text.includes("aadhaar") || text.includes("identity card") || caption.includes("passport") || caption.includes("id card");
  });

  // Calculate potential storage savings
  let duplicateSavings = 0;
  displayExactDuplicateGroups.forEach(group => {
    const sorted = [...group].sort((a, b) => b.file_size - a.file_size);
    sorted.slice(1).forEach(item => {
      if (!item.id.includes("-dup")) {
        duplicateSavings += item.file_size;
      } else {
        duplicateSavings += sorted[0].file_size;
      }
    });
  });

  let nearDuplicateSavings = 0;
  displayNearDuplicateGroups.forEach(group => {
    const sorted = [...group].sort((a, b) => b.file_size - a.file_size);
    sorted.slice(1).forEach(item => {
      if (!item.id.includes("-near")) {
        nearDuplicateSavings += item.file_size;
      } else {
        nearDuplicateSavings += sorted[0].file_size;
      }
    });
  });

  const screenshotSavings = screenshots.reduce((sum, i) => sum + i.file_size, 0);

  // Total recoverable size
  const totalRecoverableSize = duplicateSavings + nearDuplicateSavings + lowQualitySavings + screenshotSavings;

  // Actions
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSelectAll = (categoryItems: any[]) => {
    if (selectedIds.size === categoryItems.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(categoryItems.map(i => i.id)));
    }
  };

  const handleKeepSelected = () => {
    if (selectedIds.size === 0) return;
    const newKept = new Set(keptIds);
    selectedIds.forEach(id => newKept.add(id));
    saveKeptIds(newKept);
    setSelectedIds(new Set());
    setToast({ message: "Marked selected photos as kept.", type: "success" });
  };

  const handleDeleteSelected = () => {
    if (selectedIds.size === 0) return;
    setPhotoToDelete({ id: "bulk", count: selectedIds.size });
  };

  const confirmDelete = async () => {
    setIsDeleting(true);
    try {
      if (photoToDelete.id === "bulk") {
        for (const id of Array.from(selectedIds)) {
          if (!id.includes("-dup") && !id.includes("-near")) {
            await deleteMedia(id, activeCategory || "recommendations");
          }
        }
        setSelectedIds(new Set());
        setToast({ message: `Moved ${photoToDelete.count} photos to Recycle Bin.`, type: "success" });
      } else {
        if (!photoToDelete.id.includes("-dup") && !photoToDelete.id.includes("-near")) {
          await deleteMedia(photoToDelete.id, activeCategory || "recommendations");
        }
        setToast({ message: "Moved photo to Recycle Bin.", type: "success" });
      }
      queryClient.invalidateQueries({ queryKey: ["recommendations-all-media"] });
      queryClient.invalidateQueries({ queryKey: ["gallery"] });
      queryClient.invalidateQueries({ queryKey: ["trash-count"] });
      queryClient.invalidateQueries({ queryKey: ["trash-media"] });
      queryClient.invalidateQueries({ queryKey: ["collection-preview"] });
      queryClient.invalidateQueries({ queryKey: ["search"] });
      setPhotoToDelete(null);
    } catch (e: any) {
      setToast({ message: `Failed to move to Recycle Bin: ${e.message || e}`, type: "error" });
    } finally {
      setIsDeleting(false);
    }
  };

  const getCategoryItems = () => {
    switch (activeCategory) {
      case "duplicates":
        return displayExactDuplicateGroups.flat();
      case "near_duplicates":
        return displayNearDuplicateGroups.flat();
      case "similar":
        return similarGroups.flatMap(sg => sg.group);
      case "low_quality":
      case "blurry":
        return lowQualityPhotos;
      case "screenshots":
        return screenshots;
      case "documents":
        return documents;
      case "receipts":
        return receipts;
      case "ids":
        return ids;
      default:
        return [];
    }
  };

  // UI state for toaster
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3500);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-brand mb-4" />
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Scanning photo library metadata for recommendations...</p>
      </div>
    );
  }

  // Render Category List View
  if (!activeCategory) {
    const storageCleanupCategories = [
      {
        id: "duplicates",
        name: "Exact Duplicates",
        desc: "Multiple identical copies of the same photo. Keeping one copy is usually enough.",
        count: `${displayExactDuplicateGroups.length} duplicate groups`,
        savings: formatFileSize(duplicateSavings),
        items: displayExactDuplicateGroups.flat(),
      },
      {
        id: "near_duplicates",
        name: "Near Duplicates",
        desc: "Photos that are almost identical. Review them and keep the version you like best.",
        count: `${displayNearDuplicateGroups.length} similar groups`,
        savings: formatFileSize(nearDuplicateSavings),
        items: displayNearDuplicateGroups.flat(),
      },
      {
        id: "low_quality",
        name: "Low Quality Photos",
        desc: "Photos that may be blurry, dark, or low quality. Review before deleting.",
        count: `${lowQualityPhotos.length} photos`,
        savings: formatFileSize(lowQualitySavings),
        items: lowQualityPhotos,
      },
      {
        id: "screenshots",
        name: "Screenshots",
        desc: "Screenshots that may no longer be needed.",
        count: `${screenshots.length} screenshots`,
        savings: formatFileSize(screenshotSavings),
        items: screenshots,
      },
    ].filter(cat => cat.items.length > 0);

    const importantItemsCategories = [
      {
        id: "documents",
        name: "Documents",
        desc: "AI-classified text captures, invoices, and notes",
        count: `${documents.length} documents`,
        items: documents,
      },
      {
        id: "receipts",
        name: "Receipts",
        desc: "Scanned paper receipts and transaction statements",
        count: `${receipts.length} receipts`,
        items: receipts,
      },
      {
        id: "ids",
        name: "Important IDs & Permits",
        desc: "Passports, driver's licenses, and identification records",
        count: `${ids.length} important files`,
        items: ids,
      },
    ].filter(cat => cat.items.length > 0);

    const totalReviewItemsCount =
      displayExactDuplicateGroups.length +
      displayNearDuplicateGroups.length +
      lowQualityPhotos.length +
      screenshots.length +
      documents.length +
      receipts.length +
      ids.length;

    // Library Health Status Calculation
    const totalPhotos = allItems.length || 1;
    const reviewRatio = totalReviewItemsCount / totalPhotos;
    let healthText = "Great";
    let healthDot = "🟢";
    let healthBadgeStyle = "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";

    if (reviewRatio > 0.30) {
      healthText = "Requires Cleanup";
      healthDot = "🔴";
      healthBadgeStyle = "bg-rose-500/10 text-rose-400 border border-rose-500/20";
    } else if (reviewRatio > 0.10) {
      healthText = "Needs Attention";
      healthDot = "🟡";
      healthBadgeStyle = "bg-amber-500/10 text-amber-400 border border-amber-500/20";
    }

    // Dynamic AI Insight Generation
    let aiInsightText = "Reviewing duplicate photos first will free the most storage.";
    if (lowQualitySavings >= duplicateSavings && lowQualitySavings >= nearDuplicateSavings) {
      aiInsightText = "Most recoverable space comes from Low Quality Photos.";
    } else if (duplicateSavings > 0 && duplicateSavings >= totalRecoverableSize * 0.35) {
      aiInsightText = "Exact Duplicates account for nearly 40% of recoverable storage.";
    } else if (screenshots.length > 0 && screenshots.length <= totalPhotos * 0.02) {
      aiInsightText = "Screenshots make up only a small portion of your library.";
    }

    // Determine Biggest Opportunity Category
    const getCategorySavingsBytes = (catId: string) => {
      if (catId === "duplicates") return duplicateSavings;
      if (catId === "near_duplicates") return nearDuplicateSavings;
      if (catId === "low_quality") return lowQualitySavings;
      if (catId === "screenshots") return screenshotSavings;
      return 0;
    };

    const biggestOppCat = storageCleanupCategories.reduce((max: any, cat: any) => {
      if (!max) return cat;
      return getCategorySavingsBytes(cat.id) > getCategorySavingsBytes(max.id) ? cat : max;
    }, storageCleanupCategories[0]);

    const renderCard = (cat: any) => (
      <div
        key={cat.id}
        className="group flex rounded-2xl border border-default overflow-hidden transition-all duration-200 hover:border-[var(--border-subtle)] hover:shadow-xl"
        style={{ backgroundColor: "var(--bg-secondary)" }}
      >
        <div className="relative w-32 sm:w-40 aspect-square bg-[var(--bg-tertiary)] overflow-hidden flex-shrink-0">
          <img
            src={getThumbnailUrl(cat.items[0].id.replace("-dup", "").replace("-near", ""))}
            alt={cat.name}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        </div>

        <div className="p-4 sm:p-5 flex-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-base font-extrabold tracking-tight" style={{ color: "var(--text-primary)" }}>{cat.name}</h3>
              {cat.savings && (
                <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 shadow-sm">
                  {cat.savings}
                </span>
              )}
            </div>
            <p className="text-xs mt-1 leading-relaxed line-clamp-2" style={{ color: "var(--text-secondary)", opacity: 0.85 }}>{cat.desc}</p>
          </div>
          
          <div className="flex items-center justify-between mt-4">
            <span className="text-xs font-bold" style={{ color: "var(--text-secondary)" }}>
              {cat.count}
            </span>
            <button
              onClick={() => {
                setSelectedIds(new Set());
                setActiveCategory(cat.id);
              }}
              className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-brand hover:bg-brand-hover text-white transition-all shadow-sm"
            >
              Review Items →
            </button>
          </div>
        </div>
      </div>
    );

    return (
      <div className="space-y-6 pb-16 animate-fadeIn">
        {/* Section 1: Hero Section & Library Health */}
        <div 
          className="rounded-2xl border border-default p-6 sm:p-8 flex flex-col md:flex-row md:items-center md:justify-between gap-6"
          style={{ 
            backgroundColor: "var(--bg-secondary)",
            backgroundImage: "radial-gradient(circle at 100% 0%, var(--brand-glow) 0%, transparent 60%)" 
          }}
        >
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight flex items-center gap-2.5" style={{ color: "var(--text-primary)" }}>
                <Sparkles className="w-6 h-6 text-brand" /> AI Recommendations
              </h1>
              <span className={`text-xs px-3 py-1 rounded-full font-bold flex items-center gap-1.5 ${healthBadgeStyle}`}>
                <span>{healthDot}</span> Library Health: {healthText}
              </span>
            </div>
            <p className="text-sm mt-2 max-w-xl leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Review photos that may be taking unnecessary space or need your attention. Nothing is deleted automatically.
            </p>
          </div>
          
          {/* 3 Statistics Cards */}
          <div className="grid grid-cols-3 gap-3 flex-shrink-0">
            <div className="p-3.5 sm:p-4 rounded-xl border border-default bg-[var(--bg-primary)] flex flex-col items-center justify-center min-w-[100px] sm:min-w-[110px] shadow-sm">
              <span className="text-base mb-0.5">📷</span>
              <span className="text-[9px] uppercase font-bold tracking-wider" style={{ color: "var(--text-tertiary)" }}>Total Photos</span>
              <p className="text-base sm:text-lg font-black mt-0.5" style={{ color: "var(--text-primary)" }}>{allItems.length.toLocaleString()}</p>
            </div>

            <div className="p-3.5 sm:p-4 rounded-xl border border-default bg-[var(--bg-primary)] flex flex-col items-center justify-center min-w-[100px] sm:min-w-[110px] shadow-sm">
              <span className="text-base mb-0.5">🗂</span>
              <span className="text-[9px] uppercase font-bold tracking-wider" style={{ color: "var(--text-tertiary)" }}>Review Items</span>
              <p className="text-base sm:text-lg font-black mt-0.5" style={{ color: "var(--text-primary)" }}>{totalReviewItemsCount}</p>
            </div>

            <div className="p-3.5 sm:p-4 rounded-xl border border-default bg-[var(--bg-primary)] flex flex-col items-center justify-center min-w-[100px] sm:min-w-[110px] shadow-sm">
              <span className="text-base mb-0.5">💾</span>
              <span className="text-[9px] uppercase font-bold tracking-wider" style={{ color: "var(--text-tertiary)" }}>Recoverable</span>
              <p className="text-base sm:text-lg font-black mt-0.5 text-emerald-400">{formatFileSize(totalRecoverableSize)}</p>
            </div>
          </div>
        </div>

        {/* Section 2 & 3: AI Insight & Biggest Opportunity */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
          {/* AI Insight Card */}
          <div className="rounded-2xl border border-default p-5 flex flex-col justify-between" style={{ backgroundColor: "var(--bg-secondary)" }}>
            <div className="flex items-center gap-2">
              <span className="text-lg">💡</span>
              <h3 className="text-xs font-bold uppercase tracking-wider text-brand">AI Insight</h3>
            </div>
            <p className="text-sm font-semibold mt-3 leading-relaxed" style={{ color: "var(--text-primary)" }}>
              {aiInsightText}
            </p>
          </div>

          {/* Biggest Opportunity Card */}
          {biggestOppCat && (
            <div className="rounded-2xl border border-default p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4" style={{ backgroundColor: "var(--bg-secondary)" }}>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1">
                  ⭐ Biggest Opportunity
                </span>
                <h3 className="text-base font-extrabold mt-1" style={{ color: "var(--text-primary)" }}>
                  {biggestOppCat.name}
                </h3>
                <div className="flex items-center gap-3 mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                  <span>{biggestOppCat.count}</span>
                  <span>•</span>
                  <span className="text-emerald-400 font-bold">{biggestOppCat.savings} potential recovery</span>
                </div>
              </div>

              <button
                onClick={() => {
                  setSelectedIds(new Set());
                  setActiveCategory(biggestOppCat.id);
                }}
                className="px-4 py-2 rounded-xl text-xs font-extrabold bg-brand hover:bg-brand-hover text-white transition-all shadow-md flex-shrink-0"
              >
                Review Now →
              </button>
            </div>
          )}
        </div>

        {/* Section 4: Storage Cleanup */}
        {storageCleanupCategories.length > 0 && (
          <div className="space-y-4 pt-2">
            <h2 className="text-lg font-extrabold tracking-tight" style={{ color: "var(--text-primary)" }}>
              Storage Cleanup
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
              {storageCleanupCategories.map(renderCard)}
            </div>
          </div>
        )}

        {/* Section 5: Important Items */}
        {importantItemsCategories.length > 0 && (
          <div className="space-y-4 pt-2">
            <h2 className="text-lg font-extrabold tracking-tight" style={{ color: "var(--text-primary)" }}>
              Important Items
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
              {importantItemsCategories.map(renderCard)}
            </div>
          </div>
        )}

        {/* Empty state when no categories require action */}
        {storageCleanupCategories.length === 0 && importantItemsCategories.length === 0 && (
          <div className="p-12 rounded-2xl border border-default text-center" style={{ backgroundColor: "var(--bg-secondary)" }}>
            <p className="text-base font-bold" style={{ color: "var(--text-primary)" }}>All recommendations reviewed!</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-tertiary)" }}>Your photo library is clean and organized.</p>
          </div>
        )}
      </div>
    );
  }

  // Render Detailed Review View
  const reviewItems = getCategoryItems();
  const titleMap: { [key: string]: string } = {
    duplicates: "Exact Duplicates",
    near_duplicates: "Near Duplicates",
    similar: "Similar Photos",
    low_quality: "Low Quality Photos",
    blurry: "Low Quality Photos",
    screenshots: "Screenshots",
    documents: "Documents",
    receipts: "Receipts",
    ids: "Important IDs"
  };

  const descMap: { [key: string]: string } = {
    duplicates: "Review identical file duplicates using strict pHash and metadata matching. We recommend keeping the highest quality copy.",
    near_duplicates: "Review visually identical images with minor editing, scaling, or cropping adjustments (pHash Hamming distance 1-4).",
    similar: "Identify multiple photos of the same subject or moment taken in quick succession, allowing you to choose the best one.",
    low_quality: "Photos that may benefit from review based on multiple quality factors.",
    blurry: "Photos that may benefit from review based on multiple quality factors.",
    screenshots: "Review screen grabs and captures that you might no longer need.",
    documents: "Documents and textual snaps. Ideal for filing or cleaning up.",
    receipts: "Scan records of bills, transactions, and payments.",
    ids: "Review files containing passport details, driver permits, and identification cards."
  };

  return (
    <div className="space-y-6 pb-16">
      
      {/* Review Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-default pb-4">
        <div>
          <button
            onClick={() => setActiveCategory(null)}
            className="flex items-center gap-1 text-xs font-semibold text-brand hover:underline mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Recommendations
          </button>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            Review {titleMap[activeCategory]}
          </h1>
          <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
            {descMap[activeCategory]}
          </p>
        </div>

        {/* Action controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleSelectAll(reviewItems)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold border border-default hover:bg-[var(--bg-tertiary)] transition-colors"
            style={{ color: "var(--text-secondary)" }}
          >
            {selectedIds.size === reviewItems.length ? <CheckSquare className="w-3.5 h-3.5 text-brand" /> : <Square className="w-3.5 h-3.5" />}
            Select All
          </button>
          
          <button
            disabled={selectedIds.size === 0}
            onClick={handleKeepSelected}
            className="px-3 py-1.5 rounded-md text-xs font-semibold border border-default text-emerald-400 hover:bg-emerald-500/5 disabled:opacity-40 transition-colors"
          >
            Keep Selected
          </button>

          <button
            disabled={selectedIds.size === 0}
            onClick={handleDeleteSelected}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-red-600 hover:bg-red-700 text-white disabled:opacity-40 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Delete Selected
          </button>
        </div>
      </div>

      {/* Review Content Grid */}
      {reviewItems.length === 0 ? (
        <div className="rounded-xl border border-default p-12 text-center bg-[var(--bg-secondary)]">
          <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>All caught up!</p>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>No recommendations pending review in this category.</p>
          <button
            onClick={() => setActiveCategory(null)}
            className="mt-4 px-4 py-1.5 rounded-md text-xs font-semibold bg-brand text-white hover:bg-brand-hover transition-colors"
          >
            Back to categories
          </button>
        </div>
      ) : activeCategory === "duplicates" || activeCategory === "near_duplicates" || activeCategory === "similar" ? (
        
        /* Render Grouped/Clustered Layout */
        <div className="space-y-8">
          {(activeCategory === "duplicates" 
            ? displayExactDuplicateGroups.map(g => ({ group: g, explanation: "Duplicate files", confidence: 100, keepRecommendation: { id: Array.from(g).sort((a,b) => b.file_size - a.file_size)[0].id, reasons: ["Largest file"] } })) 
            : activeCategory === "near_duplicates" 
              ? displayNearDuplicateGroups.map(g => ({ group: g, explanation: "Near duplicate files", confidence: 95, keepRecommendation: { id: Array.from(g).sort((a,b) => b.file_size - a.file_size)[0].id, reasons: ["Largest file"] } })) 
              : similarGroups
          ).map(({ group, explanation, confidence, keepRecommendation }, groupIdx) => {
            const keepRecommendationId = keepRecommendation?.id ?? group[0].id;
            const keepReasons: string[] = keepRecommendation?.reasons ?? [];
            const sortedByKeep = [...group].sort((a, b) => b.file_size - a.file_size);

            return (
              <div 
                key={groupIdx} 
                className="rounded-xl border border-default p-5 space-y-4"
                style={{ backgroundColor: "var(--bg-secondary)" }}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-default pb-2 gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold" style={{ color: "var(--text-secondary)" }}>
                      Group #{groupIdx + 1} ({group.length} items)
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-brand/10 text-brand">
                      {confidence}% Confidence
                    </span>
                  </div>
                  <span className="text-[10px]" style={{ color: "var(--text-tertiary)" }}>
                    Potential Savings: {formatFileSize(group.reduce((sum, i) => sum + i.file_size, 0) - (group.find(i => i.id === keepRecommendationId)?.file_size ?? sortedByKeep[0].file_size))}
                  </span>
                </div>

                {explanation && (
                  <p className="text-xs italic" style={{ color: "var(--text-secondary)" }}>
                    💡 {explanation}
                  </p>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {group.map(item => {
                    const isSelected = selectedIds.has(item.id);
                    const isRecommendedToKeep = item.id === keepRecommendationId;

                    return (
                      <div 
                        key={item.id} 
                        className={`relative rounded-lg overflow-hidden border transition-all duration-200 ${
                          isRecommendedToKeep ? "border-amber-500/40 ring-1 ring-amber-500/20" : "border-default"
                        }`}
                        style={{ backgroundColor: "var(--bg-tertiary)" }}
                      >
                        {/* Recommendation Badge */}
                        {isRecommendedToKeep && (
                          <div className="absolute top-2 left-2 z-10 max-w-[70%]">
                            <div className="flex items-center gap-1 px-2 py-0.5 rounded text-[8px] font-bold bg-amber-500 text-black shadow-md">
                              <Star className="w-2.5 h-2.5 fill-black flex-shrink-0" /> ⭐ Keep
                            </div>
                            {activeCategory === "similar" && keepReasons.length > 0 && (
                              <div className="mt-0.5 flex flex-col gap-0.5">
                                {keepReasons.map((r, ri) => (
                                  <span key={ri} className="inline-block px-1.5 py-0.5 rounded text-[7px] font-semibold bg-black/70 text-amber-300 backdrop-blur-sm">{r}</span>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Checkbox */}
                        <button
                          onClick={() => toggleSelect(item.id)}
                          className="absolute top-2 right-2 z-10 p-1 bg-black/40 rounded-md backdrop-blur-sm"
                        >
                          {isSelected ? <CheckSquare className="w-4 h-4 text-brand" /> : <Square className="w-4 h-4 text-white" />}
                        </button>

                        <div className="aspect-square w-full overflow-hidden">
                          <img
                            src={getThumbnailUrl(item.id.replace("-dup", "").replace("-near", ""))}
                            alt={item.filename}
                            className="w-full h-full object-cover"
                            loading="lazy"
                          />
                        </div>

                        <div className="p-3 text-[10px] space-y-1.5">
                          <p className="font-semibold truncate text-[var(--text-primary)]" title={item.filename}>{item.filename}</p>
                          <div className="flex justify-between" style={{ color: "var(--text-secondary)" }}>
                            <span>Size: {formatFileSize(item.file_size)}</span>
                            <span>{new Date(item.taken_at).toLocaleDateString()}</span>
                          </div>

                          <div className="flex gap-2 pt-1 border-t border-[var(--border-default)]">
                            <button
                              onClick={() => {
                                const newKept = new Set(keptIds);
                                newKept.add(item.id);
                                saveKeptIds(newKept);
                                setToast({ message: "Item kept.", type: "success" });
                              }}
                              className="flex-1 py-1 rounded text-[9px] font-semibold border border-default hover:bg-emerald-500/10 hover:border-emerald-500/30 text-emerald-400 transition-colors"
                            >
                              Keep
                            </button>
                            <button
                              onClick={() => setPhotoToDelete(item)}
                              className="flex-1 py-1 rounded text-[9px] font-semibold border border-default hover:bg-red-500/10 hover:border-red-500/30 text-red-400 transition-colors"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        
        /* Render Standard Grid Layout for singular files */
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {reviewItems.map(item => {
            const isSelected = selectedIds.has(item.id);
            const isLowQualityCategory = activeCategory === "low_quality" || activeCategory === "blurry";
            const quality = isLowQualityCategory ? item.quality_assessment : null;
            const qualityReasons = quality ? getQualityReasons(item) : [];

            return (
              <div 
                key={item.id}
                className="relative rounded-xl overflow-hidden border border-default transition-all duration-200 flex flex-col justify-between"
                style={{ backgroundColor: "var(--bg-secondary)" }}
              >
                {/* Grade Badge Overlay */}
                {quality && (
                  <div className={`absolute top-2 left-2 z-10 px-2 py-0.5 rounded text-[9px] font-extrabold tracking-wider uppercase backdrop-blur-md shadow-sm ${
                    quality.quality_grade === "VERY_POOR"
                      ? "bg-rose-500/90 text-white"
                      : "bg-amber-500/90 text-white"
                  }`}>
                    {quality.quality_grade || "POOR"}
                  </div>
                )}

                {/* Checkbox select */}
                <button
                  onClick={() => toggleSelect(item.id)}
                  className="absolute top-2 right-2 z-10 p-1 bg-black/40 rounded-md backdrop-blur-sm"
                >
                  {isSelected ? <CheckSquare className="w-4 h-4 text-brand" /> : <Square className="w-4 h-4 text-white" />}
                </button>

                <div>
                  <div className="aspect-square w-full overflow-hidden">
                    <img
                      src={getThumbnailUrl(item.id)}
                      alt={item.filename}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>

                  <div className="p-3 text-[10px] space-y-1.5">
                    <p className="font-semibold truncate text-[var(--text-primary)]" title={item.filename}>{item.filename}</p>
                    <div className="flex justify-between" style={{ color: "var(--text-secondary)" }}>
                      <span>Size: {formatFileSize(item.file_size)}</span>
                      <span>{new Date(item.taken_at).toLocaleDateString()}</span>
                    </div>

                    {/* Multi-Signal Quality Explanation Box */}
                    {quality && (
                      <div className="pt-2 mt-1 space-y-1 border-t border-[var(--border-default)]">
                        <div className="flex items-center justify-between text-[9px]">
                          <span className="font-medium text-[var(--text-secondary)]">Overall Score:</span>
                          <span className="font-bold font-mono text-[var(--text-primary)]">
                            {typeof quality.overall_score === "number" ? quality.overall_score.toFixed(2) : "N/A"}
                          </span>
                        </div>

                        {qualityReasons.length > 0 && (
                          <div className="pt-1 text-[9px] space-y-0.5">
                            <span className="font-semibold text-[8px] uppercase tracking-wider text-[var(--text-secondary)]">Reasons:</span>
                            {qualityReasons.slice(0, 3).map((reason, rIdx) => (
                              <p key={rIdx} className="truncate text-rose-400 font-medium">• {reason}</p>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="p-3 pt-0">
                  <div className="flex gap-2 pt-2 border-t border-[var(--border-default)]">
                    <button
                      onClick={() => {
                        const newKept = new Set(keptIds);
                        newKept.add(item.id);
                        saveKeptIds(newKept);
                        setToast({ message: "Item kept.", type: "success" });
                      }}
                      className="flex-1 py-1 rounded text-[9px] font-semibold border border-default hover:bg-emerald-500/10 hover:border-emerald-500/30 text-emerald-400 transition-colors"
                    >
                      Keep
                    </button>
                    <button
                      onClick={() => setPhotoToDelete(item)}
                      className="flex-1 py-1 rounded text-[9px] font-semibold border border-default hover:bg-red-500/10 hover:border-red-500/30 text-red-400 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {photoToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div
            className="w-full max-w-md rounded-2xl border border-default p-6 shadow-2xl space-y-4"
            style={{ backgroundColor: "var(--bg-secondary)" }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
          >
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
                <Trash2 className="w-6 h-6 text-rose-400" />
              </div>
              <div>
                <h3
                  id="delete-dialog-title"
                  className="text-base font-extrabold"
                  style={{ color: "var(--text-primary)" }}
                >
                  Move to Recycle Bin?
                </h3>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-tertiary)" }}>
                  This photo can be restored for 30 days.
                </p>
              </div>
            </div>

            <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {photoToDelete.id === "bulk"
                ? `Are you sure you want to move ${photoToDelete.count} selected photos to the Recycle Bin?`
                : `Are you sure you want to move "${photoToDelete.filename}" to the Recycle Bin?`
              }
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                disabled={isDeleting}
                onClick={() => setPhotoToDelete(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold border border-default hover:bg-[var(--bg-tertiary)] transition-colors disabled:opacity-50"
                style={{ color: "var(--text-secondary)" }}
              >
                Cancel
              </button>
              <button
                disabled={isDeleting}
                onClick={confirmDelete}
                className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-extrabold text-white bg-rose-500 hover:bg-rose-600 transition-colors disabled:opacity-50"
              >
                {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Move to Bin"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Toast Notification */}
      {toast && (
        <div
          className="fixed bottom-20 right-4 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl border border-default shadow-lg transition-all duration-300"
          style={{
            backgroundColor: "var(--bg-secondary)",
            borderLeft: `4px solid ${toast.type === "success" ? "var(--success)" : "var(--error)"}`,
          }}
        >
          {toast.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 text-[var(--success)]" />
          ) : (
            <AlertCircle className="w-4 h-4 text-[var(--error)]" />
          )}
          <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            {toast.message}
          </span>
        </div>
      )}
    </div>
  );
}
