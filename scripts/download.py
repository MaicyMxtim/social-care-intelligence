"""Download every dataset used by this repository from its published URL.

Running this script is the only supported way to put files into data/raw. Raw
files are never edited by hand. Every download is recorded in
data/raw/MANIFEST.json with the URL it came from, the date it was fetched, the
size in bytes and a SHA256 hash, so that a later run can tell whether a
publisher has changed a file underneath the analysis.

Every source below is published under the Open Government Licence v3.0, except
the Skills for Care workforce estimates, which Skills for Care publishes for
free reuse with attribution.

Usage:
    python scripts/download.py            # download anything missing
    python scripts/download.py --force    # re-download everything
    python scripts/download.py --check    # verify hashes without downloading
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.paths import MANIFEST_PATH, RAW_DIR, ensure_dirs  # noqa: E402

USER_AGENT = (
    "social-care-intelligence/1.0 (open data analysis; "
    "https://github.com/MaicyMxtim/social-care-intelligence)"
)
TIMEOUT_SECONDS = 600

# The Local Authority Districts boundary layer is served by the ONS Open
# Geography Portal as a paged feature service. The query below asks for every
# feature in one response in GeoJSON form with generalised (BUC) geometry.
LAD_BOUNDARY_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "Local_Authority_Districts_May_2024_Boundaries_UK_BUC/FeatureServer/0/query"
    "?where=1%3D1&outFields=LAD24CD,LAD24NM&outSR=4326&f=geojson"
    "&resultRecordCount=400&resultOffset=0"
)

SOURCES: list[dict[str, str]] = [
    # ---------------------------------------------------------------- adult
    {
        "key": "cld_lts_2026_03",
        "filename": "cld_long_term_support_to_march_2026.ods",
        "url": (
            "https://assets.publishing.service.gov.uk/media/"
            "6a42854f5b6406df58c13f78/long-term-support-official-statistics-"
            "in-development-data-to-march-2026.ods.ods"
        ),
        "publisher": "Department of Health and Social Care",
        "description": (
            "Adult social care client level data, long-term support tables, "
            "quarterly update to March 2026. Monthly snapshots April 2025 to "
            "March 2026."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "cld_assessments_2026_03",
        "filename": "cld_assessments_to_march_2026.ods",
        "url": (
            "https://assets.publishing.service.gov.uk/media/"
            "6a4286383413112faed80e09/assessments-official-statistics-"
            "in-development-data-to-march-2026.ods.ods"
        ),
        "publisher": "Department of Health and Social Care",
        "description": (
            "Adult social care client level data, assessments tables, "
            "quarterly update to March 2026."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "cld_lts_2025_12",
        "filename": "cld_long_term_support_to_december_2025.ods",
        "url": (
            "https://assets.publishing.service.gov.uk/media/"
            "6a60c91ab00f3323bf1a2431/long-term-support-official-statistics-"
            "in-development-data-to-december-2025-updated-july-2026.ods"
        ),
        "publisher": "Department of Health and Social Care",
        "description": (
            "Adult social care client level data, long-term support tables, "
            "quarterly update to December 2025, corrected July 2026."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "cld_assessments_2025_12",
        "filename": "cld_assessments_to_december_2025.ods",
        "url": (
            "https://assets.publishing.service.gov.uk/media/"
            "6a60cb4a47af652afa0c8a25/assessments-official-statistics-"
            "in-development-data-to-december-2025-updated-july-2026.ods"
        ),
        "publisher": "Department of Health and Social Care",
        "description": (
            "Adult social care client level data, assessments tables, "
            "quarterly update to December 2025, corrected July 2026."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "cld_lts_2025_09",
        "filename": "cld_long_term_support_to_september_2025.ods",
        "url": (
            "https://assets.publishing.service.gov.uk/media/"
            "6a60c4550dd52549f5f96d28/long-term-support-official-statistics-"
            "in-development-data-to-september-2025-updated-july-2026.ods"
        ),
        "publisher": "Department of Health and Social Care",
        "description": (
            "Adult social care client level data, long-term support tables, "
            "quarterly update to September 2025, corrected July 2026."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "cld_assessments_2025_09",
        "filename": "cld_assessments_to_september_2025.ods",
        "url": (
            "https://assets.publishing.service.gov.uk/media/"
            "6a60c5c234dfb74772f96d2f/assessments-official-statistics-"
            "in-development-data-to-september-2025-updated-july-2026.ods"
        ),
        "publisher": "Department of Health and Social Care",
        "description": (
            "Adult social care client level data, assessments tables, "
            "quarterly update to September 2025, corrected July 2026."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "ascof_2024_25",
        "filename": "ascof_england_2024_to_2025_outcome_and_demographic.ods",
        "url": (
            "https://assets.publishing.service.gov.uk/media/"
            "69736b0821a2f53a6a4fd4f8/dhsc-ascof-england-2024-to-2025-"
            "outcome-and-demographic-data-23-january-2026.ods"
        ),
        "publisher": "Department of Health and Social Care",
        "description": (
            "Measures from the Adult Social Care Outcomes Framework, England, "
            "2024 to 2025. Table 1a carries measure 1A, the social care "
            "related quality of life score."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "sfc_local_area_2024_25",
        "filename": "skills_for_care_local_area_2024_25.xlsx",
        "url": (
            "https://www.skillsforcare.org.uk/Adult-Social-Care-Workforce-Data/"
            "workforceintelligence/resources/Our-data/"
            "Current-year-data-download-local-area-2024-25.xlsx"
        ),
        "publisher": "Skills for Care",
        "description": (
            "Adult Social Care Workforce Data Set local authority area "
            "workforce estimates for 2024/25, including the vacancy rate."
        ),
        "licence": "Skills for Care, free reuse with attribution",
    },
    # ------------------------------------------------------------- children
    {
        "key": "dfe_csww",
        "filename": "dfe_childrens_social_work_workforce.zip",
        "url": (
            "https://content.explore-education-statistics.service.gov.uk/"
            "api/releases/54642595-7462-42ba-b565-08de4c5bcb90/files"
        ),
        "publisher": "Department for Education",
        "description": (
            "Children's social work workforce statistics, all release files. "
            "csww_indicators_2017_to_2025.csv carries turnover, vacancy, "
            "agency, caseload and sickness absence by local authority."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "dfe_cin",
        "filename": "dfe_children_in_need.zip",
        "url": (
            "https://content.explore-education-statistics.service.gov.uk/"
            "api/releases/9d18dcc5-207b-43d3-c0e1-08ddff5126a0/files"
        ),
        "publisher": "Department for Education",
        "description": (
            "Children in need census, all release files. c1 carries referrals "
            "and re-referrals, d3 carries second or subsequent child "
            "protection plans."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "dfe_cla",
        "filename": "dfe_children_looked_after.zip",
        "url": (
            "https://content.explore-education-statistics.service.gov.uk/"
            "api/releases/8c28aca0-6ab9-400b-b7de-c5fc7a148c2e/files"
        ),
        "publisher": "Department for Education",
        "description": (
            "Children looked after in England including adoptions, all release "
            "files. LA_CLA_placement_stability.csv carries children with three "
            "or more placements in the year."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "ofsted_la_outcomes",
        "filename": "ofsted_la_inspection_outcomes_2026.ods",
        "url": (
            "https://assets.publishing.service.gov.uk/media/"
            "6a6c6b2a8319ab05f7caa29d/local_authority_inspection_outcomes_"
            "as_at_31_march_2026_underlying_data.ods"
        ),
        "publisher": "Ofsted",
        "description": (
            "Local authority inspection outcomes as at 31 March 2026. The "
            "ILACS_inspection_history sheet carries every inspection from 2018 "
            "onwards with its date and overall effectiveness grade."
        ),
        "licence": "OGL v3.0",
    },
    # -------------------------------------------------------------- shared
    {
        "key": "ons_mye_2024",
        "filename": "ons_mid_2024_population_estimates.xlsx",
        "url": (
            "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/"
            "populationandmigration/populationestimates/datasets/"
            "estimatesofthepopulationforenglandandwales/"
            "mid20242023localauthorityboundaries/mye24tablesew.xlsx"
        ),
        "publisher": "Office for National Statistics",
        "description": (
            "Mid-2024 population estimates for England and Wales on 2023 local "
            "authority boundaries. The MYE2 - Persons sheet gives population "
            "by single year of age."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "imd_2019_file10",
        "filename": "imd_2019_file_10_la_district_summaries.xlsx",
        "url": (
            "https://assets.publishing.service.gov.uk/media/"
            "5d8b3cfbe5274a08be69aa91/File_10_-_IoD2019_Local_Authority_"
            "District_Summaries__lower-tier__.xlsx"
        ),
        "publisher": "Ministry of Housing, Communities and Local Government",
        "description": (
            "English indices of deprivation 2019, File 10, local authority "
            "district summaries. The IMD sheet gives the average deprivation "
            "score for each district."
        ),
        "licence": "OGL v3.0",
    },
    {
        "key": "lad_boundaries_2024_05",
        "filename": "lad_may_2024_boundaries_buc.geojson",
        "url": LAD_BOUNDARY_URL,
        "publisher": "Office for National Statistics Open Geography Portal",
        "description": (
            "Local Authority Districts, May 2024, ultra generalised clipped "
            "boundaries for the United Kingdom, in GeoJSON."
        ),
        "licence": "OGL v3.0",
    },
]


def sha256_of(path: Path) -> str:
    """Return the SHA256 hash of a file, read in chunks so large files fit in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, destination: Path) -> None:
    """Stream a URL to disk, writing to a temporary file first.

    Writing to a temporary file and renaming it at the end means an interrupted
    download never leaves a half-written file that a later run would mistake for
    a complete one.
    """
    headers = {"User-Agent": USER_AGENT}
    temporary = destination.with_suffix(destination.suffix + ".part")
    with requests.get(url, headers=headers, stream=True, timeout=TIMEOUT_SECONDS) as response:
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                handle.write(chunk)
    temporary.replace(destination)


def fetch_paged_geojson(url: str, destination: Path) -> None:
    """Download an ArcGIS feature service layer, following its paging.

    The Open Geography Portal caps the number of features it returns in a single
    response. This function keeps asking for the next page until the service
    stops setting the exceededTransferLimit flag, then writes one GeoJSON
    FeatureCollection holding every feature.
    """
    headers = {"User-Agent": USER_AGENT}
    features: list[dict] = []
    offset = 0
    page_size = 400
    while True:
        paged_url = url.replace("resultOffset=0", f"resultOffset={offset}")
        response = requests.get(paged_url, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        page = payload.get("features", [])
        features.extend(page)
        if not payload.get("properties", {}).get("exceededTransferLimit") and not page:
            break
        if len(page) < page_size:
            break
        offset += page_size
    collection = {"type": "FeatureCollection", "features": features}
    destination.write_text(json.dumps(collection), encoding="utf-8")


def load_manifest() -> dict:
    """Read the existing manifest, or return an empty one on the first run."""
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    """Download the sources that are missing and refresh the manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="re-download files that already exist"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that files on disk still match the recorded hashes",
    )
    args = parser.parse_args()

    ensure_dirs()
    manifest = load_manifest()

    if args.check:
        problems = 0
        for source in SOURCES:
            path = RAW_DIR / source["filename"]
            recorded = manifest.get(source["key"], {}).get("sha256")
            if not path.exists():
                print(f"MISSING  {source['filename']}")
                problems += 1
            elif recorded and sha256_of(path) != recorded:
                print(f"CHANGED  {source['filename']}")
                problems += 1
            else:
                print(f"ok       {source['filename']}")
        return 1 if problems else 0

    for source in SOURCES:
        path = RAW_DIR / source["filename"]
        if path.exists() and not args.force:
            print(f"have     {source['filename']}")
        else:
            print(f"fetching {source['filename']} ...", flush=True)
            if source["filename"].endswith(".geojson"):
                fetch_paged_geojson(source["url"], path)
            else:
                fetch(source["url"], path)
        manifest[source["key"]] = {
            "filename": source["filename"],
            "url": source["url"],
            "publisher": source["publisher"],
            "description": source["description"],
            "licence": source["licence"],
            "downloaded": date.today().isoformat(),
            "bytes": path.stat().st_size,
            "sha256": sha256_of(path),
        }

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nWrote {MANIFEST_PATH} with {len(manifest)} entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
