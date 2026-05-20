from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "LCZliterature_screened_stage1.xlsx"
PDF_DIR = ROOT / "fulltext_pdfs"
PAGE_DIR = ROOT / "fulltext_pages"
OUT_CSV = ROOT / "fulltext_acquisition_log.csv"
OUT_XLSX = ROOT / "fulltext_acquisition_log.xlsx"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def norm(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def clean_doi(value: object) -> str:
    doi = norm(value)
    doi = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
    doi = doi.strip().strip(".")
    return doi


def safe_name(value: str, max_len: int = 120) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return value[:max_len] or "untitled"


def request_url(url: str, accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", timeout: int = 25):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final_url = resp.geturl()
            status = getattr(resp, "status", 200)
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            return {
                "ok": True,
                "url": url,
                "final_url": final_url,
                "status": status,
                "content_type": content_type,
                "data": data,
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "url": url,
            "final_url": exc.geturl(),
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "data": exc.read() if exc.fp else b"",
            "error": f"HTTPError: {exc}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "final_url": "",
            "status": "",
            "content_type": "",
            "data": b"",
            "error": repr(exc),
        }


def html_text(data: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.I)
    if match:
        charset = match.group(1)
    try:
        return data.decode(charset, errors="ignore")
    except LookupError:
        return data.decode("utf-8", errors="ignore")


def absolutize(url: str, base: str) -> str:
    url = unescape(url).strip()
    if url.startswith("//"):
        return "https:" + url
    return urllib.parse.urljoin(base, url)


def extract_pdf_candidates(html: str, base_url: str) -> list[str]:
    candidates: list[str] = []

    # Common scholarly metadata tags, e.g. citation_pdf_url.
    meta_patterns = [
        r'<meta[^>]+(?:name|property)=["\'](?:citation_pdf_url|dc\.identifier|eprints\.document_url|og:url)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:citation_pdf_url|dc\.identifier|eprints\.document_url)["\']',
    ]
    for pattern in meta_patterns:
        for match in re.finditer(pattern, html, flags=re.I):
            url = match.group(1)
            if "pdf" in url.lower() or url.lower().endswith(".pdf"):
                candidates.append(absolutize(url, base_url))

    # Direct anchor links. Keep broad patterns because publishers vary widely.
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html, flags=re.I):
        href = match.group(1)
        low = href.lower()
        if (
            low.endswith(".pdf")
            or "/pdf" in low
            or "article-pdf" in low
            or "downloadpdf" in low
            or "pdfdownload" in low
            or "pdf=true" in low
        ):
            candidates.append(absolutize(href, base_url))

    deduped: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        if url not in seen and not url.lower().startswith("javascript:"):
            seen.add(url)
            deduped.append(url)
    return deduped


def heuristic_pdf_candidates(doi: str, landing_url: str) -> list[str]:
    doi_enc = urllib.parse.quote(doi, safe="/")
    candidates: list[str] = []
    low = landing_url.lower()

    if "tandfonline.com" in low:
        candidates.append(f"https://www.tandfonline.com/doi/pdf/{doi_enc}?download=true")
    if "nature.com/articles/" in low:
        article_id = landing_url.rstrip("/").split("/")[-1]
        candidates.append(f"https://www.nature.com/articles/{article_id}.pdf")
    if "frontiersin.org" in low:
        candidates.append(landing_url.rstrip("/") + "/pdf")
    if "mdpi.com" in low:
        candidates.append(landing_url.rstrip("/") + "/pdf")
    if "sciencedirect.com/science/article/pii/" in low or "linkinghub.elsevier.com/retrieve/pii/" in low:
        pii = landing_url.rstrip("/").split("/")[-1].split("?")[0]
        candidates.append(f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft?isDTMRedir=true&download=true")
        candidates.append(f"https://reader.elsevier.com/reader/sd/pii/{pii}?download=true")
    if "springer.com" in low or "link.springer.com" in low:
        candidates.append(f"https://link.springer.com/content/pdf/{doi_enc}.pdf")
    if "copernicus.org" in low:
        candidates.append(landing_url.rstrip("/") + ".pdf")

    return candidates


def unpaywall_candidates(doi: str, email: str) -> tuple[list[str], str]:
    if not email:
        return [], ""
    api = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(email)}"
    resp = request_url(api, accept="application/json")
    if not resp["ok"]:
        return [], resp["error"] or str(resp["status"])
    try:
        data = json.loads(resp["data"].decode("utf-8", errors="ignore"))
    except Exception as exc:
        return [], repr(exc)
    urls: list[str] = []
    best = data.get("best_oa_location") or {}
    for key in ["url_for_pdf", "url"]:
        if best.get(key):
            urls.append(best[key])
    for loc in data.get("oa_locations") or []:
        for key in ["url_for_pdf", "url"]:
            if loc.get(key):
                urls.append(loc[key])
    return list(dict.fromkeys(urls)), ""


def is_pdf_response(resp: dict) -> bool:
    ctype = str(resp.get("content_type", "")).lower()
    data = resp.get("data", b"")
    return "application/pdf" in ctype or data[:5] == b"%PDF-"


def save_page(record_id: str, html: str) -> str:
    PAGE_DIR.mkdir(exist_ok=True)
    path = PAGE_DIR / f"{safe_name(record_id)}.html"
    path.write_text(html, encoding="utf-8", errors="ignore")
    return str(path)


def process_record(row: pd.Series, email: str, download: bool, sleep_seconds: float) -> dict[str, object]:
    record_id = norm(row.get("record_id")) or safe_name(norm(row.get("UT (Unique WOS ID)")))
    title = norm(row.get("Article Title"))
    doi = clean_doi(row.get("DOI"))

    out = {
        "record_id": record_id,
        "title": title,
        "doi": doi,
        "screening_priority": norm(row.get("screening_priority")),
        "landing_url": "",
        "landing_status": "",
        "landing_content_type": "",
        "landing_error": "",
        "saved_landing_page": "",
        "pdf_candidate_count": 0,
        "pdf_candidates": "",
        "download_status": "not_attempted",
        "downloaded_pdf": "",
        "download_error": "",
    }

    if not doi:
        out["landing_error"] = "missing DOI"
        out["download_status"] = "missing_doi"
        return out

    doi_url = f"https://doi.org/{urllib.parse.quote(doi, safe='/')}"
    landing = request_url(doi_url)
    out["landing_url"] = landing["final_url"] or doi_url
    out["landing_status"] = landing["status"]
    out["landing_content_type"] = landing["content_type"]
    out["landing_error"] = landing["error"]

    html = ""
    if landing["data"] and not is_pdf_response(landing):
        html = html_text(landing["data"], landing["content_type"])
        if "<html" in html.lower() or "<!doctype" in html.lower():
            out["saved_landing_page"] = save_page(record_id, html)

    candidates: list[str] = []
    if is_pdf_response(landing):
        candidates.append(out["landing_url"])
    if html:
        candidates.extend(extract_pdf_candidates(html, out["landing_url"]))
    candidates.extend(heuristic_pdf_candidates(doi, out["landing_url"]))
    oa_candidates, oa_error = unpaywall_candidates(doi, email)
    candidates.extend(oa_candidates)

    candidates = list(dict.fromkeys(candidates))
    out["pdf_candidate_count"] = len(candidates)
    out["pdf_candidates"] = "; ".join(candidates[:12])
    if oa_error:
        out["download_error"] = f"Unpaywall: {oa_error}"

    if not download:
        out["download_status"] = "candidates_only"
        return out

    PDF_DIR.mkdir(exist_ok=True)
    for candidate in candidates:
        time.sleep(sleep_seconds)
        resp = request_url(candidate, accept="application/pdf,*/*")
        if is_pdf_response(resp):
            filename = f"{safe_name(record_id)}_{safe_name(doi)}.pdf"
            path = PDF_DIR / filename
            path.write_bytes(resp["data"])
            out["download_status"] = "downloaded"
            out["downloaded_pdf"] = str(path)
            out["download_error"] = ""
            return out
        err = resp["error"] or f"status={resp['status']} type={resp['content_type']}"
        out["download_error"] = (str(out["download_error"]) + " | " + f"{candidate}: {err}").strip(" |")

    out["download_status"] = "no_pdf_downloaded" if candidates else "no_pdf_candidate"
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire legally accessible PDFs from WOS DOI records.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--sheet", default="screened_stage1")
    parser.add_argument("--priority", default="high,medium", help="Comma list, or all.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--email", default="", help="Optional email for Unpaywall OA lookup.")
    parser.add_argument("--no-download", action="store_true", help="Only find candidate PDF URLs.")
    parser.add_argument("--sleep", type=float, default=0.8)
    args = parser.parse_args()

    df = pd.read_excel(args.input, sheet_name=args.sheet)
    if args.priority.lower() != "all":
        priorities = {p.strip() for p in args.priority.split(",") if p.strip()}
        df = df[df["screening_priority"].isin(priorities)].copy()
    df = df.iloc[args.start :]
    if args.limit:
        df = df.head(args.limit)

    rows = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        result = process_record(row, email=args.email, download=not args.no_download, sleep_seconds=args.sleep)
        rows.append(result)
        print(f"{i}/{len(df)} {result['record_id']} {result['download_status']} {result['doi']}")
        time.sleep(args.sleep)

    log = pd.DataFrame(rows)
    log.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        log.to_excel(writer, sheet_name="acquisition_log", index=False)
        summary = log.groupby("download_status").size().reset_index(name="records")
        summary.to_excel(writer, sheet_name="summary", index=False)

    print(f"Wrote: {OUT_CSV.name}")
    print(f"Wrote: {OUT_XLSX.name}")


if __name__ == "__main__":
    main()
