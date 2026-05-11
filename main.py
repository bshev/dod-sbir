__author__ = "Brian Shevitski"
__email__ = "brian.shevitski@gmail.com"
__version__ = "1.0.0"
__status__ = "Production"
__date__ = "2026/05/08"

# Scrapes open DoD SBIR/STTR topics from dodsbirsttr.mil and stores them in a
# local SQLite database (dod_sbir.db). Fetches topic stubs via the public search
# API, then retrieves per-topic details. Strips HTML from text fields.

import sys
import time
import json
import sqlite3
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from loguru import logger

BASE_URL = "https://www.dodsbirsttr.mil"

SEARCH_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "referer": f"{BASE_URL}/topics-app/",
}

SEARCH_PARAM = {
    "searchText": None,
    "components": None,
    "programYear": None,
    "solicitationCycleNames": ["openTopics"],
    "releaseNumbers": [],
    "topicReleaseStatus": None,
    "modernizationPriorities": None,
    "sortBy": "finalTopicCode,asc",
}

PAGE_SIZE = 50

# Fields pulled from the topic stub (search response). Strings get HTML-stripped.
TOPIC_FIELD_MAP = {
    "topicTitle": "title",
    "component": "component",
    "command": "command",
    "cycleName": "cycle_name",
}

# Fields pulled from the topic detail response. Strings get HTML-stripped.
DETAIL_FIELD_MAP = {
    "keywords": "keywords",
    "focusAreas": "modernization_priorities",
    "technologyAreas": "technology_areas",
    "objective": "objective",
    "description": "description",
    "phase1Description": "phase1_description",
    "phase2Description": "phase2_description",
    "phase3Description": "phase3_description",
    "referenceDocuments": "referenceDocuments",
}

# sqlite db
COLUMNS = [
    "topic_id", "topic_code", "status", "program", "solicitation",
    "open_date", "close_date",
    "title", "objective", "description", "component", "command", "cycle_name",
    "keywords", "modernization_priorities", "technology_areas",
    "phase1_description", "phase2_description", "phase3_description",
    "referenceDocuments",
    "phase1_configured", "phase2_configured",
]


def safe_get(session, url, desc="request", timeout=10, **kwargs):
    try:
        r = session.get(url, timeout=timeout, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        logger.error(f"{desc} failed: {url} | {e}")
        return None


def fetch_topic_list(session):
    """Fetch the open-topic stubs (no per-topic details)."""
    safe_get(session, f"{BASE_URL}/topics-app/", desc="session seed")

    r = safe_get(
        session,
        f"{BASE_URL}/topics/api/public/topics/solicitations",
        desc="solicitations",
    )
    if not r:
        logger.error("Failed to fetch solicitations.")
        return []
    solicitations = r.json().get("active", [])
    logger.debug(f"{len(solicitations)} open solicitations")

    exclude = "INACTIVE,READY_FOR_RELEASE,READY_TO_CERTIFY,READY_TO_REVIEW,REVISION_REQUESTED"
    r = safe_get(
        session,
        f"{BASE_URL}/core/api/public/dropdown/lookup?type=topics.release_status&excludeLookupItem={exclude}",
        desc="release status codes",
    )
    if not r:
        logger.error("Failed to fetch release status codes, aborting")
        return []
    release_codes = {d.get("label"): d.get("value") for d in r.json()}

    search_param = {
        **SEARCH_PARAM,
        "topicReleaseStatus": [
            release_codes.get("Pre-Release"),
            release_codes.get("Open"),
        ],
    }

    all_topics = []
    page = 0
    while True:
        r = safe_get(
            session,
            f"{BASE_URL}/topics/api/public/topics/search",
            desc=f"topics page {page}",
            params={
                "searchParam": json.dumps(search_param, separators=(",", ":")),
                "size": PAGE_SIZE,
                "page": page,
            },
        )
        if not r:
            logger.warning(f"Stopping pagination at page {page}")
            break
        data = r.json()
        topics = data.get("data", [])
        if not topics:
            break
        all_topics.extend(topics)
        logger.debug(
            f"Page {page}: {len(topics)} topics (total: {len(all_topics)}/{data['total']})"
        )
        if len(all_topics) >= data["total"]:
            break
        page += 1
        time.sleep(0.125)

    return all_topics


def fetch_topic_detail(session, topic):
    tid = topic["topicId"]
    r = safe_get(
        session,
        f"{BASE_URL}/topics/api/public/topics/{tid}/details",
        desc=topic["topicCode"],
    )
    return r.json() if r else None


def parse_topic(stub, detail):

    def strip_html(text):
        if not text:
            return text
        return BeautifulSoup(text, "html.parser").get_text(strip=True)

    def _normalize(val):
        """Lists become '; '-joined strings, strings get HTML-stripped."""
        if isinstance(val, list):
            val = "; ".join(map(str, val))
        if isinstance(val, str):
            val = strip_html(val)
        return val

    def parse_references(refs):
        if not isinstance(refs, list):
            return refs
        titles = [r.get("referenceTitle", "") for r in refs if r.get("referenceTitle")]
        return "\n".join(titles) if titles else None
    
    def epoch_to_date(dt_ms):
        if not dt_ms:
            return None
        return datetime.fromtimestamp(dt_ms / 1000, tz=timezone.utc).strftime("%Y/%m/%d")

    def get_phase_hierarchy(item):
        """Return (phase1_configured, phase2_configured) as raw 'Y'/'N' strings."""
        raw = item.get("phaseHierarchy")
        if not raw:
            return None, None

        config = json.loads(raw).get("config", [])
        p1, p2 = None, None
        for c in config:
            if c.get("phase") == "1":
                p1 = c.get("hasConfiguration")
            elif c.get("phase") == "2":
                p2 = c.get("hasConfiguration")
        return p1, p2

    row = {
        "topic_id": stub.get("topicId"),
        "topic_code": stub.get("topicCode"),
        "status": stub.get("topicStatus"),
        "program": stub.get("program"),
        "solicitation": stub.get("solicitationTitle"),
        "open_date": epoch_to_date(stub.get("topicStartDate")),
        "close_date": epoch_to_date(stub.get("topicEndDate")),
    }
    for src, dest in TOPIC_FIELD_MAP.items():
        row[dest] = _normalize(stub.get(src))
    for src, dest in DETAIL_FIELD_MAP.items():
        val = detail.get(src)
        if src == "referenceDocuments":
            row[dest] = parse_references(val)
        else:
            row[dest] = _normalize(val)

    p1, p2 = get_phase_hierarchy(stub)
    row["phase1_configured"] = p1
    row["phase2_configured"] = p2

    desc = row.get("description") or ""
    phase_note = f"\n\nPhase 1 Configured: {p1 or 'N/A'}\nPhase 2 Configured: {p2 or 'N/A'}"
    row["description"] = desc + phase_note

    return row


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    cols = ", ".join(
        "topic_id TEXT PRIMARY KEY" if c == "topic_id"
        else f"{c} TEXT"
        for c in COLUMNS
    )
    conn.execute(f"CREATE TABLE IF NOT EXISTS topics ({cols})")
    conn.commit()
    return conn


def upsert_rows(conn, rows):
    placeholders = ", ".join("?" * len(COLUMNS))
    updates = ", ".join(f"{c} = excluded.{c}" for c in COLUMNS if c != "topic_id")
    sql = f"""
        INSERT INTO topics ({", ".join(COLUMNS)})
        VALUES ({placeholders})
        ON CONFLICT(topic_id) DO UPDATE SET {updates}
    """
    def serialize(val):
        if val is None:
            return None
        return str(val)

    conn.executemany(sql, [[serialize(r.get(c)) for c in COLUMNS] for r in rows])
    conn.commit()


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="DEBUG", colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")
    logger.add("scraper.log", level="DEBUG", rotation="10 MB", retention="1 year",
               format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}")

    logger.info("Starting scrape")
    try:
        conn = init_db("dod_sbir.db")
        with requests.Session() as session:
            session.headers.update(SEARCH_HEADERS)

            topics = fetch_topic_list(session)
            if not topics:
                logger.warning("No topics found")
                sys.exit(0)
            logger.debug(f"{len(topics)} topics found")

            ok, failed = 0, 0
            for stub in tqdm(topics, desc="Fetching details"):
                detail = fetch_topic_detail(session, stub)
                if not detail:
                    failed += 1
                    time.sleep(0.25)
                    continue
                try:
                    row = parse_topic(stub, detail)
                    upsert_rows(conn, [row])
                    ok += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"parse/upsert failed for {stub.get('topicCode')}: {e}")
                time.sleep(0.25)

            logger.info(f"Done. {ok} upserted, {failed} failed")
        conn.close()
    except Exception as e:
        logger.exception(f"Fatal unhandled error: {e}")
        sys.exit(1)