import json
import sys
import time
import requests
import pandas as pd
from loguru import logger
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from tqdm import tqdm
import sqlite3

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

DETAIL_FIELD_MAP = {
    "keywords": "keywords",
    "focusAreas": "modernization_priorities",
    "technologyAreas": "technology_areas",
    "objective": "objective",
    "description": "description",
    "phase1Description": "phase1Description",
    "phase2Description": "phase2Description",
    "phase3Description": "phase3Description",
    "referenceDocuments": "referenceDocuments",
}

HTML_FIELDS = {"objective", "description"}

def epoch_to_date(dt_ms):
    if not dt_ms:
        return None
    return datetime.fromtimestamp(dt_ms / 1000, tz=timezone.utc).strftime("%Y/%m/%d")


def safe_get(session, url, desc="request", timeout=10, **kwargs):
    try:
        r = session.get(url, timeout=timeout, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        logger.error(f"{desc} failed: {url} | {e}")
        return None


def scrape():
    with requests.Session() as session:
        session.headers.update(SEARCH_HEADERS)

        # Seed cookies
        safe_get(session, f"{BASE_URL}/topics-app/", desc="session seed")

        # Solicitations
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

        # Release status codes
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

        # Paginate topics
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

        if not all_topics:
            logger.warning("No topics found")
            return []
        logger.debug(f"{len(all_topics)} topics found")

        # Fetch details per topic
        for t in tqdm(all_topics, desc="Fetching details"):
            tid = t["topicId"]
            r = safe_get(
                session,
                f"{BASE_URL}/topics/api/public/topics/{tid}/details",
                desc=t["topicCode"],
            )
            t["topic_data"] = r.json() if r else {}
            time.sleep(0.25)

        return all_topics


def strip_html(text):
    if not text:
        return text
    return BeautifulSoup(text, "html.parser").get_text(strip=True)


def parse(scraped):
    rows = []
    for topic in scraped:
        item = topic.get("topic_data") or {}
        row = {
            "topic_id": item.get("topicId"),
            "topic_code": item.get("topicCode"),
            "title": item.get("topicTitle"),
            "status": item.get("topicStatus"),
            "component": item.get("component"),
            "command": item.get("command"),
            "program": item.get("program"),
            "solicitation": item.get("solicitationTitle"),
            "open_date": epoch_to_date(item.get("topicStartDate")),
            "close_date": epoch_to_date(item.get("topicEndDate")),
        }
        for api_key, col_name in DETAIL_FIELD_MAP.items():
            try:
                val = item.get(api_key)
                if isinstance(val, list):
                    val = "; ".join(map(str, val))
                if api_key in HTML_FIELDS and isinstance(val, str):
                    val = strip_html(val)
                row[col_name] = val
            except Exception:
                row[col_name] = None
        rows.append(row)
    return rows

COLUMNS = [
    "topic_id", "topic_code", "title", "status", "component", "command",
    "program", "solicitation", "open_date", "close_date",
    "keywords", "modernization_priorities", "technology_areas",
    "objective", "description", "phase1Description", "phase2Description",
    "phase3Description", "referenceDocuments",
]

def init_db(db_path="dod_topics.db"):
    conn = sqlite3.connect(db_path)
    cols = ", ".join(
        f"{c} TEXT" if c != "topic_id" else "topic_id TEXT PRIMARY KEY"
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
    conn.executemany(sql, [[str(r.get(c)) if r.get(c) is not None else None for c in COLUMNS] for r in rows])
    conn.commit()


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="DEBUG", colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")
    logger.add("scraper.log", level="DEBUG", rotation="10 MB", retention="1 year",
               format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}")

    logger.info("Starting scrape")
    try:
        conn = init_db()
        scraped = scrape()
        if not scraped:
            logger.warning("No data scraped, skipping parse/save")
            sys.exit(0)
        parsed = parse(scraped)
        upsert_rows(conn, parsed)
        logger.info(f"Done — {len(parsed)} rows upserted")
        conn.close()
    except Exception as e:
        logger.exception(f"Fatal unhandled error: {e}")
        sys.exit(1)

