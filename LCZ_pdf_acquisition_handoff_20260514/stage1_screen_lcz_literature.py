from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "LCZliterature.xlsx"
OUTPUT_CSV = ROOT / "LCZliterature_screened_stage1.csv"
OUTPUT_XLSX = ROOT / "LCZliterature_screened_stage1.xlsx"


LCZ_TERMS = [
    "local climate zone",
    "local climate zones",
    "lcz",
    "lczs",
    "wudapt",
    "world urban database and access portal tools",
    "lcz generator",
]

MAPPING_TERMS = [
    "map",
    "maps",
    "mapping",
    "mapped",
    "classification",
    "classify",
    "classifier",
    "random forest",
    "support vector machine",
    "svm",
    "deep learning",
    "convolutional neural network",
    "cnn",
    "object-based",
    "remote sensing",
    "sentinel",
    "landsat",
    "training area",
    "training areas",
    "training sample",
    "training samples",
    "earth observation",
]

METHOD_TERMS = {
    "random_forest": ["random forest", "rf classifier"],
    "svm": ["support vector machine", " svm"],
    "cnn_deep_learning": ["deep learning", "convolutional neural network", " cnn", "resnet", "u-net", "unet"],
    "object_based": ["object-based", "obia", "object based"],
    "rule_based_or_gis": ["gis", "rule-based", "rule based"],
    "wudapt_workflow": ["wudapt", "training area", "training areas", "lcz generator"],
    "gee": ["google earth engine", " gee"],
}

ACCURACY_TERMS = {
    "OA": ["overall accuracy", " oa "],
    "Kappa": ["kappa"],
    "F1": ["f1", "f-score", "f score"],
    "precision": ["precision"],
    "recall": ["recall"],
    "producer_accuracy": ["producer accuracy", "producer's accuracy"],
    "user_accuracy": ["user accuracy", "user's accuracy"],
    "confusion_matrix": ["confusion matrix"],
    "cross_validation": ["cross-validation", "cross validation"],
    "validation": ["validation", "validated", "accuracy", "accuracies"],
}

DATA_TERMS = [
    "dataset",
    "data set",
    "data availability",
    "available at",
    "supplementary",
    "supplemental",
    "repository",
    "zenodo",
    "figshare",
    "dryad",
    "github",
    "google earth engine",
    " gee",
    "download",
    "open data",
    "training areas",
    "benchmark",
]

EXISTING_USE_TERMS = [
    "using local climate zone",
    "based on local climate zone",
    "lcz map was used",
    "lcz maps were used",
    "according to lcz",
    "urban heat island",
    "land surface temperature",
    "thermal environment",
    "heat exposure",
]

DATA_SOURCE_TERMS = {
    "Sentinel": ["sentinel-1", "sentinel-2", "sentinel"],
    "Landsat": ["landsat"],
    "MODIS": ["modis"],
    "Google Earth Engine": ["google earth engine", " gee"],
    "OpenStreetMap": ["openstreetmap", "open street map", " osm"],
    "building morphology": ["building height", "building footprint", "building density", "urban morphology"],
    "street view": ["street view", "google street view"],
    "nighttime light": ["nighttime light", "night-time light", "viirs", "dmsp"],
    "SAR": ["synthetic aperture radar", "sar", "sentinel-1"],
}

PRODUCT_TYPE_TERMS = {
    "global_map": ["global map", "global lcz"],
    "continental_map": ["europe", "continental", "conus"],
    "national_map": ["national", "countrywide", "china", "united states", "conus"],
    "city_map": ["city", "cities", "urban agglomeration"],
    "patch_dataset": ["patch", "benchmark"],
    "training_areas": ["training area", "training areas", "training sample", "training samples"],
}


def normalize(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def contains_any(text: str, terms: list[str]) -> bool:
    padded = f" {text.lower()} "
    return any(term in padded for term in terms)


def matched_terms(text: str, terms: list[str]) -> list[str]:
    padded = f" {text.lower()} "
    return [term for term in terms if term in padded]


def matched_from_dict(text: str, terms: dict[str, list[str]]) -> list[str]:
    padded = f" {text.lower()} "
    hits: list[str] = []
    for label, patterns in terms.items():
        if any(pattern in padded for pattern in patterns):
            hits.append(label)
    return hits


def evidence_snippet(text: str, hits: list[str], max_chars: int = 280) -> str:
    if not text or not hits:
        return ""
    low = text.lower()
    positions = [low.find(hit.strip()) for hit in hits if low.find(hit.strip()) >= 0]
    if not positions:
        return text[:max_chars]
    start = max(0, min(positions) - 90)
    end = min(len(text), start + max_chars)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet += "..."
    return snippet


def classify(row: pd.Series) -> dict[str, str]:
    title = normalize(row.get("Article Title", ""))
    abstract = normalize(row.get("Abstract", ""))
    text = f"{title}. {abstract}".strip()
    text_lower = f" {text.lower()} "

    lcz_hits = matched_terms(text, LCZ_TERMS)
    mapping_hits = matched_terms(text, MAPPING_TERMS)
    data_hits = matched_terms(text, DATA_TERMS)
    existing_hits = matched_terms(text, EXISTING_USE_TERMS)
    method_hits = matched_from_dict(text, METHOD_TERMS)
    source_hits = matched_from_dict(text, DATA_SOURCE_TERMS)
    product_type_hits = matched_from_dict(text, PRODUCT_TYPE_TERMS)
    accuracy_hits = matched_from_dict(text, ACCURACY_TERMS)

    is_lcz_related = "yes" if lcz_hits else "no"
    if not lcz_hits and ("climate zone" in text_lower or "urban climatic map" in text_lower):
        is_lcz_related = "unclear"

    has_mapping_evidence = bool(lcz_hits and mapping_hits)
    has_accuracy_evidence = bool(lcz_hits and accuracy_hits)
    has_data_evidence = bool(lcz_hits and data_hits)

    if is_lcz_related == "no":
        priority = "exclude"
    elif has_mapping_evidence or has_accuracy_evidence or has_data_evidence:
        priority = "high"
    elif existing_hits:
        priority = "medium"
    else:
        priority = "low"

    if is_lcz_related == "no":
        mapping_role = "not_lcz_mapping"
    elif has_mapping_evidence and any(t in text_lower for t in ["develop", "create", "generat", "produc", "classif", "map"]):
        mapping_role = "unclear"
    elif existing_hits:
        mapping_role = "uses_existing_lcz_map"
    else:
        mapping_role = "unclear"

    has_lcz_map_result = "unclear" if has_data_evidence or has_mapping_evidence else "no"
    if is_lcz_related == "no":
        has_lcz_map_result = "no"

    if "zenodo" in text_lower or "figshare" in text_lower or "github" in text_lower or "repository" in text_lower:
        map_result_access = "repository"
    elif "google earth engine" in text_lower or " gee " in text_lower:
        map_result_access = "gee_asset"
    elif "supplementary" in text_lower or "supplemental" in text_lower:
        map_result_access = "supplementary_file"
    elif "available from" in text_lower or "upon request" in text_lower:
        map_result_access = "request_required"
    elif has_lcz_map_result == "no":
        map_result_access = "not_available"
    else:
        map_result_access = "unclear"

    has_accuracy = "unclear" if has_accuracy_evidence else "no"
    if is_lcz_related == "no":
        has_accuracy = "no"

    review_status = "auto_screened"
    if priority in {"high", "medium"}:
        review_status = "needs_fulltext"
    if priority == "exclude":
        review_status = "exclude"

    all_hits = lcz_hits + mapping_hits + accuracy_hits + data_hits
    evidence = evidence_snippet(text, all_hits)

    return {
        "screening_priority": priority,
        "is_lcz_related": is_lcz_related,
        "is_lcz_mapping_paper": "unclear" if is_lcz_related != "no" and has_mapping_evidence else "no",
        "mapping_role": mapping_role,
        "has_lcz_map_result": has_lcz_map_result,
        "map_result_access": map_result_access,
        "map_result_type": "; ".join(product_type_hits) if product_type_hits else ("unclear" if has_lcz_map_result == "unclear" else "not_applicable"),
        "has_accuracy_assessment": has_accuracy,
        "accuracy_metrics": "; ".join([hit for hit in accuracy_hits if hit != "validation"]),
        "accuracy_values": "",
        "has_confusion_matrix": "unclear" if "confusion_matrix" in accuracy_hits else "no",
        "has_training_samples": "unclear" if any("training" in hit for hit in mapping_hits + data_hits) else "no",
        "has_validation_samples": "unclear" if has_accuracy_evidence else "no",
        "possible_mapping_methods": "; ".join(method_hits),
        "possible_input_data": "; ".join(source_hits),
        "data_or_map_link": "",
        "supplementary_link": "",
        "code_link": "",
        "evidence_source": "WOS title/abstract",
        "evidence_text": evidence,
        "review_status": review_status,
        "reviewer": "auto_stage1",
        "review_date": date.today().isoformat(),
        "review_notes": "; ".join(
            [
                f"LCZ terms: {', '.join(lcz_hits)}" if lcz_hits else "",
                f"mapping terms: {', '.join(mapping_hits[:8])}" if mapping_hits else "",
                f"accuracy terms: {', '.join(accuracy_hits)}" if accuracy_hits else "",
                f"data terms: {', '.join(data_hits[:8])}" if data_hits else "",
            ]
        ).strip("; "),
    }


def main() -> None:
    df = pd.read_excel(INPUT, sheet_name="LCZliterature")
    review = pd.DataFrame([classify(row) for _, row in df.iterrows()])
    out = pd.concat([df, review], axis=1)

    out.insert(0, "record_id", [f"WOS{i + 1:04d}" for i in range(len(out))])

    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        out.to_excel(writer, index=False, sheet_name="screened_stage1")
        summary = (
            out.groupby(["screening_priority", "is_lcz_related", "review_status"])
            .size()
            .reset_index(name="records")
            .sort_values(["screening_priority", "is_lcz_related", "review_status"])
        )
        summary.to_excel(writer, index=False, sheet_name="summary")

    print(f"records: {len(out)}")
    print("priority counts:")
    print(out["screening_priority"].value_counts(dropna=False).to_string())
    print("\nLCZ related counts:")
    print(out["is_lcz_related"].value_counts(dropna=False).to_string())
    print("\nreview status counts:")
    print(out["review_status"].value_counts(dropna=False).to_string())
    print(f"\nwrote: {OUTPUT_CSV.name}")
    print(f"wrote: {OUTPUT_XLSX.name}")


if __name__ == "__main__":
    main()
