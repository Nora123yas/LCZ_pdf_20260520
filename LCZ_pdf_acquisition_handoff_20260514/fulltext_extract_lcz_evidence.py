from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent
STAGE1 = ROOT / "LCZliterature_screened_stage1.xlsx"
PDF_DIR = ROOT / "fulltext_pdfs"
TEXT_DIR = ROOT / "fulltext_text"
OUT_XLSX = ROOT / "LCZliterature_fulltext_extraction_draft.xlsx"
OUT_CSV = ROOT / "LCZliterature_fulltext_extraction_draft.csv"


METHOD_PATTERNS = {
    "WUDAPT / LCZ Generator": [
        r"\bWUDAPT\b",
        r"LCZ Generator",
        r"training areas?",
    ],
    "Random Forest": [r"random forest", r"\bRF classifier\b"],
    "SVM": [r"support vector machine", r"\bSVM\b"],
    "CNN / deep learning": [
        r"deep learning",
        r"convolutional neural network",
        r"\bCNN\b",
        r"\bResNet\b",
        r"\bU-Net\b",
        r"\bUNet\b",
    ],
    "Object-based": [r"object[- ]based", r"\bOBIA\b"],
    "GEE": [r"Google Earth Engine", r"\bGEE\b"],
    "Sentinel": [r"Sentinel[- ]?1", r"Sentinel[- ]?2", r"\bSentinel\b"],
    "Landsat": [r"\bLandsat\b"],
    "OpenStreetMap": [r"OpenStreetMap", r"Open Street Map", r"\bOSM\b"],
}

ACCURACY_PATTERNS = {
    "overall_accuracy": [
        r"(?:overall accuracy|OA)\s*(?:of|=|:|was|is)?\s*([0-9]+(?:\.[0-9]+)?\s*%?)",
        r"([0-9]+(?:\.[0-9]+)?\s*%)\s*(?:overall accuracy|OA)",
    ],
    "kappa": [
        r"(?:kappa|kappa coefficient)\s*(?:of|=|:|was|is)?\s*([0-9]+(?:\.[0-9]+)?)",
    ],
    "f1": [
        r"(?:F1|F-score|F score)\s*(?:of|=|:|was|is)?\s*([0-9]+(?:\.[0-9]+)?\s*%?)",
    ],
    "confusion_matrix": [r"confusion matrix"],
    "producer_user_accuracy": [r"producer'?s? accuracy", r"user'?s? accuracy"],
    "cross_validation": [r"cross[- ]validation"],
}

PRODUCT_PATTERNS = {
    "repository": [r"Zenodo", r"Figshare", r"Dryad", r"GitHub", r"repository"],
    "supplementary": [r"supplementary", r"supplemental", r"supporting information"],
    "download": [r"download", r"available at", r"available from"],
    "GEE asset": [r"Google Earth Engine", r"\bGEE asset\b"],
    "on request": [r"upon request", r"available from the corresponding author"],
    "map/data product": [r"LCZ map", r"LCZ maps", r"local climate zone map", r"GeoTIFF", r"shapefile"],
    "training samples": [r"training areas?", r"training samples?"],
}

SECTION_HEADERS = [
    "abstract",
    "introduction",
    "materials and methods",
    "methods",
    "methodology",
    "data and methods",
    "study area",
    "classification",
    "accuracy assessment",
    "validation",
    "results",
    "data availability",
    "code availability",
    "supplementary",
    "supporting information",
]


@dataclass
class PdfDoc:
    path: Path
    text: str
    text_hash: str


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"-\n(?=[a-z])", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def pdf_to_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return clean_text("\n".join(pages))


def cache_pdf_text(path: Path) -> PdfDoc:
    raw = path.read_bytes()
    digest = hashlib.sha1(raw).hexdigest()[:16]
    text_path = TEXT_DIR / f"{path.stem}.{digest}.txt"
    if text_path.exists():
        text = text_path.read_text(encoding="utf-8", errors="ignore")
    else:
        text = pdf_to_text(path)
        text_path.write_text(text, encoding="utf-8")
    return PdfDoc(path=path, text=text, text_hash=digest)


def normalize_id(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def title_tokens(title: object) -> set[str]:
    text = "" if pd.isna(title) else str(title).lower()
    words = re.findall(r"[a-z0-9]{4,}", text)
    stop = {
        "with",
        "from",
        "using",
        "based",
        "case",
        "study",
        "local",
        "climate",
        "zones",
        "zone",
    }
    return {w for w in words if w not in stop}


def score_match(row: pd.Series, doc: PdfDoc) -> int:
    filename = doc.path.name.lower()
    text_start = doc.text[:6000].lower()

    score = 0
    doi = normalize_id(row.get("DOI", ""))
    if doi and doi in normalize_id(filename):
        score += 100
    if doi and doi in normalize_id(text_start):
        score += 100

    title = str(row.get("Article Title", "") or "")
    tokens = title_tokens(title)
    if tokens:
        file_hits = sum(1 for token in tokens if token in filename)
        text_hits = sum(1 for token in tokens if token in text_start)
        score += min(60, file_hits * 8 + text_hits * 5)

    first_author = str(row.get("Authors", "") or "").split(";")[0].split(",")[0].strip().lower()
    year = str(row.get("Publication Year", "") or "").split(".")[0]
    if first_author and first_author in filename:
        score += 15
    if year and year in filename:
        score += 8
    return score


def find_best_pdf(row: pd.Series, docs: list[PdfDoc]) -> tuple[PdfDoc | None, int]:
    if not docs:
        return None, 0
    scored = [(doc, score_match(row, doc)) for doc in docs]
    scored.sort(key=lambda item: item[1], reverse=True)
    best_doc, best_score = scored[0]
    if best_score >= 35:
        return best_doc, best_score
    return None, best_score


def find_hits(text: str, pattern_dict: dict[str, list[str]]) -> list[str]:
    hits: list[str] = []
    for label, patterns in pattern_dict.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            hits.append(label)
    return hits


def extract_values(text: str, pattern_dict: dict[str, list[str]]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for label, patterns in pattern_dict.items():
        label_values: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                if match.groups():
                    label_values.append(match.group(1).strip())
                else:
                    label_values.append("mentioned")
        if label_values:
            values[label] = sorted(set(label_values))
    return values


def snippets_for_patterns(text: str, patterns: Iterable[str], max_snippets: int = 3) -> str:
    snippets: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            start = max(0, match.start() - 180)
            end = min(len(text), match.end() + 220)
            snippet = text[start:end].strip()
            snippet = re.sub(r"\s+", " ", snippet)
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet += "..."
            snippets.append(snippet)
            if len(snippets) >= max_snippets:
                return " || ".join(snippets)
    return " || ".join(snippets)


def likely_sections(text: str) -> str:
    hits: list[str] = []
    lower = text.lower()
    for header in SECTION_HEADERS:
        if re.search(rf"\b{re.escape(header)}\b", lower):
            hits.append(header)
    return "; ".join(hits)


def extract_links(text: str) -> str:
    urls = re.findall(r"https?://[^\s\]\)\};,]+", text)
    urls = [url.rstrip(".") for url in urls]
    useful = [
        url
        for url in urls
        if any(
            key in url.lower()
            for key in [
                "zenodo",
                "figshare",
                "github",
                "dryad",
                "earthengine",
                "google",
                "wudapt",
                "lcz-generator",
                "supplement",
            ]
        )
    ]
    return "; ".join(sorted(set(useful)))


def classify_product_access(product_hits: list[str], links: str, text: str) -> str:
    low = text.lower()
    if links and any(k in links.lower() for k in ["zenodo", "figshare", "github", "dryad"]):
        return "repository_candidate"
    if "GEE asset" in product_hits:
        return "gee_asset_candidate"
    if "supplementary" in product_hits:
        return "supplementary_candidate"
    if "on request" in product_hits:
        return "request_required_candidate"
    if product_hits and ("not publicly available" in low or "not available" in low):
        return "not_available_candidate"
    if product_hits:
        return "unclear_candidate"
    return "not_detected"


def main() -> None:
    TEXT_DIR.mkdir(exist_ok=True)
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    docs = [cache_pdf_text(path) for path in pdfs]

    df = pd.read_excel(STAGE1, sheet_name="screened_stage1")
    review_rows: list[dict[str, object]] = []

    for _, row in df.iterrows():
        doc, score = find_best_pdf(row, docs)
        if doc is None:
            review_rows.append(
                {
                    "fulltext_pdf_file": "",
                    "fulltext_match_score": score,
                    "fulltext_checked": "no_pdf_matched",
                    "fulltext_sections_detected": "",
                    "fulltext_method_hits": "",
                    "fulltext_accuracy_hits": "",
                    "fulltext_accuracy_values": "",
                    "fulltext_product_hits": "",
                    "fulltext_product_access_candidate": "",
                    "fulltext_links": "",
                    "evidence_method_fulltext": "",
                    "evidence_accuracy_fulltext": "",
                    "evidence_data_availability_fulltext": "",
                    "fulltext_review_date": "",
                }
            )
            continue

        text = doc.text
        method_hits = find_hits(text, METHOD_PATTERNS)
        accuracy_values = extract_values(text, ACCURACY_PATTERNS)
        accuracy_hits = list(accuracy_values.keys())
        product_hits = find_hits(text, PRODUCT_PATTERNS)
        links = extract_links(text)

        method_patterns = [p for label in method_hits for p in METHOD_PATTERNS[label]]
        accuracy_patterns = [p for label in accuracy_hits for p in ACCURACY_PATTERNS[label]]
        product_patterns = [p for label in product_hits for p in PRODUCT_PATTERNS[label]]

        review_rows.append(
            {
                "fulltext_pdf_file": doc.path.name,
                "fulltext_match_score": score,
                "fulltext_checked": "auto_extracted",
                "fulltext_sections_detected": likely_sections(text),
                "fulltext_method_hits": "; ".join(method_hits),
                "fulltext_accuracy_hits": "; ".join(accuracy_hits),
                "fulltext_accuracy_values": "; ".join(
                    f"{key}: {', '.join(vals)}" for key, vals in accuracy_values.items()
                ),
                "fulltext_product_hits": "; ".join(product_hits),
                "fulltext_product_access_candidate": classify_product_access(product_hits, links, text),
                "fulltext_links": links,
                "evidence_method_fulltext": snippets_for_patterns(text, method_patterns),
                "evidence_accuracy_fulltext": snippets_for_patterns(text, accuracy_patterns),
                "evidence_data_availability_fulltext": snippets_for_patterns(text, product_patterns),
                "fulltext_review_date": date.today().isoformat(),
            }
        )

    result = pd.concat([df, pd.DataFrame(review_rows)], axis=1)
    result.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="fulltext_draft", index=False)
        summary = pd.DataFrame(
            {
                "metric": [
                    "source_records",
                    "pdf_files",
                    "records_with_pdf_matched",
                    "records_with_accuracy_candidate",
                    "records_with_product_candidate",
                    "records_with_links",
                ],
                "value": [
                    len(result),
                    len(pdfs),
                    int((result["fulltext_checked"] == "auto_extracted").sum()),
                    int(result["fulltext_accuracy_hits"].fillna("").ne("").sum()),
                    int(result["fulltext_product_hits"].fillna("").ne("").sum()),
                    int(result["fulltext_links"].fillna("").ne("").sum()),
                ],
            }
        )
        summary.to_excel(writer, sheet_name="summary", index=False)

    print(f"PDF files found: {len(pdfs)}")
    print(f"Records: {len(result)}")
    print(f"Matched PDFs: {(result['fulltext_checked'] == 'auto_extracted').sum()}")
    print(f"Wrote: {OUT_XLSX.name}")
    print(f"Wrote: {OUT_CSV.name}")


if __name__ == "__main__":
    main()
