#!/usr/bin/env python3
"""Sync publications from ORCID into _bibliography/papers.bib.

Pipeline (stdlib only):

    ORCID public API   -> canonical list of your works (+ DOIs)
    Crossref API       -> venue, authors, pages, publisher, month, type
    Semantic Scholar   -> abstract + open-access HTML/PDF link
    OpenAI (optional)  -> reads ONLY the resolved doi.org landing page to fill
                          in a missing abstract or a specific venue

New works (not already present in papers.bib, matched by DOI or title) are
emitted as BibTeX entries in the al-folio style used by this repo. Existing
entries are never touched, so hand-curated abstracts/thumbnails are preserved.

Usage:
    python bin/orcid_sync.py --dry-run          # print new entries, write nothing
    python bin/orcid_sync.py                     # prepend new entries to papers.bib
    python bin/orcid_sync.py --output new.bib     # write new entries to a separate file
    python bin/orcid_sync.py --orcid 0000-0002-1825-0097
    python bin/orcid_sync.py --no-llm             # skip the DOI-page LLM step

The ORCID iD is resolved from (in order): --orcid, $ORCID_ID, _data/socials.yml.
The OpenAI key is read from $OPENAI_API_KEY (never stored in the repo). The LLM
step is skipped automatically when that variable is not set.
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BIB_PATH = REPO_ROOT / "_bibliography" / "papers.bib"
SOCIALS_PATH = REPO_ROOT / "_data" / "socials.yml"

# A contact email makes us a "polite" Crossref API user (better rate limits).
CONTACT_EMAIL = os.environ.get("ORCID_SYNC_EMAIL", "judy.wang@hosei.ac.jp")
USER_AGENT = f"orcid_sync.py (+https://judywang.jp; mailto:{CONTACT_EMAIL})"

# Map Crossref work "type" -> (bibtex entry type, container field name).
TYPE_MAP = {
    "journal-article": ("article", "journal"),
    "proceedings-article": ("inproceedings", "booktitle"),
    "book-chapter": ("incollection", "booktitle"),
    "book": ("book", None),
    "monograph": ("book", None),
    "posted-content": ("article", "journal"),  # preprints (arXiv, etc.)
    "report": ("techreport", "institution"),
    "dataset": ("misc", None),
}

MONTHS = [
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
]

# Generic book series that Crossref sometimes returns as the "venue". When we
# see one of these we keep it as `series` and try to recover the real venue
# (the specific conference/workshop/book title) from the DOI landing page.
KNOWN_SERIES = {
    "lecture notes in computer science",
    "lecture notes in artificial intelligence",
    "communications in computer and information science",
    "lecture notes in networks and systems",
    "advances in intelligent systems and computing",
    "smart innovation, systems and technologies",
}

# OpenAI Chat Completions endpoint used for the optional DOI-page extraction.
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = os.environ.get("ORCID_SYNC_MODEL", "gpt-4o-mini")


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def http_get_json(url: str, accept: str = "application/json", retries: int = 3):
    """GET a URL and parse JSON, with polite retry/backoff. Returns None on failure."""
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = 2 ** attempt * 3
                sys.stderr.write(f"  [{exc.code}] backing off {wait}s: {url}\n")
                time.sleep(wait)
                continue
            sys.stderr.write(f"  HTTP {exc.code} for {url}\n")
            return None
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            sys.stderr.write(f"  request failed for {url}: {exc}\n")
            return None
    return None


# --------------------------------------------------------------------------- #
# ORCID iD resolution
# --------------------------------------------------------------------------- #
def resolve_orcid(cli_value: str | None) -> str | None:
    candidate = cli_value or os.environ.get("ORCID_ID")
    if not candidate and SOCIALS_PATH.exists():
        text = SOCIALS_PATH.read_text(encoding="utf-8")
        # Only pick up an *uncommented* orcid_id line.
        match = re.search(r"^\s*orcid_id:\s*([0-9Xx-]{19})", text, re.MULTILINE)
        if match:
            candidate = match.group(1)
    if not candidate:
        return None
    candidate = candidate.strip()
    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dXx]", candidate):
        sys.stderr.write(f"ORCID iD '{candidate}' is not in the expected 0000-0000-0000-0000 form.\n")
        return None
    return candidate.upper()


# --------------------------------------------------------------------------- #
# ORCID -> list of works
# --------------------------------------------------------------------------- #
def fetch_orcid_dois(orcid: str) -> list[dict]:
    """Return a list of {doi, title, year} dicts for all works on the ORCID record."""
    data = http_get_json(f"https://pub.orcid.org/v3.0/{orcid}/works")
    if not data:
        return []
    works = []
    for group in data.get("group", []):
        summaries = group.get("work-summary", [])
        if not summaries:
            continue
        summary = summaries[0]
        # Extract DOI from external ids (prefer the group-level ids).
        doi = None
        ext_ids = group.get("external-ids", {}).get("external-id", [])
        for eid in ext_ids:
            if eid.get("external-id-type", "").lower() == "doi":
                doi = eid.get("external-id-value", "").strip().lower()
                break
        title = ""
        title_obj = summary.get("title", {}).get("title", {})
        if title_obj:
            title = title_obj.get("value", "")
        year = ""
        pub_date = summary.get("publication-date") or {}
        if pub_date.get("year"):
            year = pub_date["year"].get("value", "")
        works.append({"doi": doi, "title": title, "year": year})
    return works


# --------------------------------------------------------------------------- #
# Crossref + Semantic Scholar enrichment
# --------------------------------------------------------------------------- #
def strip_jats(text: str) -> str:
    """Remove JATS/XML tags Crossref sometimes wraps abstracts in."""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_crossref(doi: str) -> dict | None:
    data = http_get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
    if not data:
        return None
    return data.get("message")


def fetch_semantic_scholar(doi: str) -> dict | None:
    fields = "abstract,openAccessPdf,url,externalIds,title"
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{urllib.parse.quote(doi)}?fields={fields}"
    return http_get_json(url)


def format_authors(cr: dict) -> str:
    parts = []
    for author in cr.get("author", []):
        family = author.get("family", "").strip()
        given = author.get("given", "").strip()
        if family and given:
            parts.append(f"{family}, {given}")
        elif family:
            parts.append(family)
        elif author.get("name"):
            parts.append(author["name"].strip())
    return " and ".join(parts)


def http_post_json(url: str, payload: dict, headers: dict, retries: int = 3):
    """POST JSON and parse the JSON response, with polite retry/backoff."""
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:200]
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt * 3)
                continue
            sys.stderr.write(f"  OpenAI HTTP {exc.code}: {detail}\n")
            return None
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            sys.stderr.write(f"  OpenAI request failed: {exc}\n")
            return None
    return None


def fetch_doi_page(doi: str) -> str | None:
    """Fetch the HTML of the resolved https://doi.org/<doi> landing page."""
    url = f"https://doi.org/{doi}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            # A browser-like UA; some publishers reject unknown agents.
            "User-Agent": "Mozilla/5.0 (compatible; orcid_sync/1.0; +https://judywang.jp)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, "ignore")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        sys.stderr.write(f"  could not fetch DOI page for {doi}: {exc}\n")
        return None


def doi_page_content(html: str) -> str:
    """Distil a DOI landing page into venue/abstract-relevant text for the LLM.

    Pulls the citation_* / description meta tags (where publishers usually put
    the venue and abstract), any JSON-LD blocks, then a slice of visible text.
    """
    metas: dict[str, str] = {}
    for tag in re.findall(r"<meta[^>]+>", html, re.IGNORECASE):
        name = re.search(r'(?:name|property)\s*=\s*["\']([^"\']+)["\']', tag, re.IGNORECASE)
        content = re.search(r'content\s*=\s*["\']([^"\']*)["\']', tag, re.IGNORECASE)
        if name and content:
            metas[name.group(1).lower()] = htmllib.unescape(content.group(1))

    wanted = [
        "citation_journal_title", "citation_conference_title", "citation_inbook_title",
        "citation_book_title", "citation_abstract", "dc.description",
        "description", "og:description",
    ]
    lines = [f"{key}: {metas[key]}" for key in wanted if metas.get(key)]

    for block in re.findall(r"(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>", html):
        lines.append("JSON-LD: " + re.sub(r"\s+", " ", block).strip()[:2000])

    stripped = re.sub(r"(?is)<(script|style|noscript|head).*?</\1>", " ", html)
    text = htmllib.unescape(re.sub(r"(?s)<[^>]+>", " ", stripped))
    lines.append("PAGE TEXT: " + re.sub(r"\s+", " ", text).strip()[:6000])
    return "\n".join(lines)[:12000]


def llm_extract(doi: str, title: str, api_key: str) -> dict | None:
    """Ask the model to pull venue/abstract from ONLY the DOI landing page."""
    html = fetch_doi_page(doi)
    if not html:
        return None
    content = doi_page_content(html)
    prompt = (
        "You extract bibliographic metadata from a single academic publication's "
        "landing page. Use ONLY the page content provided below; never use outside "
        "knowledge and never guess. Return a JSON object with keys \"venue\" and "
        "\"abstract\". \"venue\" is the specific journal name, or the conference / "
        "workshop / proceedings / book title where this paper appeared -- NOT a "
        "generic book series such as 'Lecture Notes in Computer Science'. "
        "\"abstract\" is the paper's abstract copied verbatim. Use null for any "
        "field that is not clearly present on the page.\n\n"
        f"Paper title: {title}\n\nPage content:\n{content}"
    )
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    resp = http_post_json(OPENAI_API_URL, payload, {"Authorization": f"Bearer {api_key}"})
    if not resp:
        return None
    try:
        info = json.loads(resp["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None
    result: dict[str, str] = {}
    if isinstance(info.get("venue"), str) and info["venue"].strip():
        result["venue"] = info["venue"].strip()
    if isinstance(info.get("abstract"), str) and info["abstract"].strip():
        result["abstract"] = info["abstract"].strip()
    return result or None


def build_entry(work: dict, llm_key: str | None = None) -> tuple[str, str] | None:
    """Return (bibtex_key, bibtex_text) for one work, or None if unusable."""
    doi = work["doi"]
    cr = fetch_crossref(doi) if doi else None
    s2 = fetch_semantic_scholar(doi) if doi else None

    # Title / authors / year come from Crossref when available, else ORCID.
    title = ""
    if cr and cr.get("title"):
        title = cr["title"][0]
    title = title or work.get("title", "")
    if not title:
        return None

    authors = format_authors(cr) if cr else ""
    year = work.get("year", "")
    if cr and cr.get("issued", {}).get("date-parts"):
        dp = cr["issued"]["date-parts"][0]
        if dp and dp[0]:
            year = str(dp[0])

    cr_type = cr.get("type", "") if cr else ""
    entry_type, container_field = TYPE_MAP.get(cr_type, ("misc", None))

    # Container (venue) + optional series. A generic series is set aside so we
    # can try to recover the specific venue from the DOI page.
    container = ""
    series_val = ""
    if cr and container_field:
        if cr.get("container-title"):
            container = cr["container-title"][0]
        elif entry_type == "article" and cr_type == "posted-content":
            container = cr.get("group-title", "") or "arXiv preprint"
    if container and container.strip().lower() in KNOWN_SERIES:
        series_val = container
        container = ""

    # Abstract from the APIs (Semantic Scholar clean text preferred).
    abstract = ""
    if s2 and s2.get("abstract"):
        abstract = s2["abstract"].strip()
    elif cr and cr.get("abstract"):
        abstract = strip_jats(cr["abstract"])

    # Optional LLM gap-fill from the DOI landing page ONLY, and only when a gap
    # remains after the APIs (keeps token usage minimal).
    if llm_key and doi and container_field and (not abstract or not container):
        info = llm_extract(doi, title, llm_key)
        if info:
            if not container and info.get("venue"):
                container = info["venue"]
                sys.stderr.write("    (venue filled from DOI page)\n")
            if not abstract and info.get("abstract"):
                abstract = info["abstract"]
                sys.stderr.write("    (abstract filled from DOI page)\n")

    # Assemble the BibTeX fields in a stable, repo-consistent order.
    fields: list[tuple[str, str]] = [("bibtex_show", "true"), ("title", title)]
    if authors:
        fields.append(("author", authors))
    if container_field and container:
        fields.append((container_field, container))
    if series_val:
        fields.append(("series", series_val))
    if cr:
        if cr.get("volume"):
            fields.append(("volume", str(cr["volume"])))
        if cr.get("issue"):
            fields.append(("number", str(cr["issue"])))
        if cr.get("page"):
            fields.append(("pages", str(cr["page"]).replace("-", "--")))
        if cr.get("publisher"):
            fields.append(("publisher", cr["publisher"]))
    if year:
        fields.append(("year", str(year)))

    # Month (numeric -> 3-letter lowercase, matching the repo style).
    if cr and cr.get("issued", {}).get("date-parts"):
        dp = cr["issued"]["date-parts"][0]
        if len(dp) >= 2 and dp[1] and 1 <= int(dp[1]) <= 12:
            fields.append(("month", MONTHS[int(dp[1]) - 1]))

    if doi:
        fields.append(("doi", doi))

    # HTML link: prefer an open-access landing/PDF page, else the DOI resolver.
    html_link = ""
    if s2:
        oa = s2.get("openAccessPdf") or {}
        html_link = oa.get("url") or s2.get("url") or ""
    if not html_link and doi:
        html_link = f"https://doi.org/{doi}"
    if html_link:
        fields.append(("html", html_link))

    if abstract:
        fields.append(("abstract", abstract))
    if not doi:
        fields.append(("note", "TODO: no DOI on ORCID record; verify metadata"))

    key = make_key(authors, title, year)
    return key, render_bibtex(entry_type, key, fields)


# --------------------------------------------------------------------------- #
# BibTeX rendering / key generation
# --------------------------------------------------------------------------- #
def ascii_slug(text: str) -> str:
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def make_key(authors: str, title: str, year: str) -> str:
    first_last = ""
    if authors:
        first_last = authors.split(" and ")[0].split(",")[0]
    first_last = ascii_slug(first_last) or "anon"
    first_word = ""
    for word in re.split(r"\s+", title.strip()):
        slug = ascii_slug(word)
        if slug:
            first_word = slug
            break
    return f"{first_last}{year}{first_word}"


def escape_bibtex(value: str) -> str:
    # Keep it simple: entries live inside { }, so only braces need balancing.
    return value.replace("\\", "\\\\").strip()


def render_bibtex(entry_type: str, key: str, fields: list[tuple[str, str]]) -> str:
    width = max(len(name) for name, _ in fields)
    lines = [f"@{entry_type}{{{key},"]
    for name, value in fields:
        lines.append(f"  {name.ljust(width)} = {{{escape_bibtex(value)}}},")
    lines.append("}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Dedup against existing papers.bib
# --------------------------------------------------------------------------- #
def existing_index(bib_text: str) -> tuple[set[str], set[str]]:
    """Return (set of lowercased DOIs, set of normalized titles) already present."""
    dois = {m.lower() for m in re.findall(r"doi\s*=\s*[{\"]([^}\"]+)", bib_text, re.IGNORECASE)}
    titles = {
        ascii_slug(m) for m in re.findall(r"title\s*=\s*[{\"]([^}\"]+)", bib_text, re.IGNORECASE)
    }
    return dois, titles


# --------------------------------------------------------------------------- #
# OpenAI key self-test
# --------------------------------------------------------------------------- #
def check_openai() -> int:
    """Send a trivial request to confirm OPENAI_API_KEY works. Returns exit code."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.stderr.write("OPENAI_API_KEY is not set in this environment.\n")
        return 2
    sys.stderr.write(f"Pinging OpenAI with model {OPENAI_MODEL} ...\n")
    resp = http_post_json(
        OPENAI_API_URL,
        {
            "model": OPENAI_MODEL,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "max_tokens": 5,
            "temperature": 0,
        },
        {"Authorization": f"Bearer {key}"},
    )
    if resp and resp.get("choices"):
        reply = resp["choices"][0].get("message", {}).get("content", "").strip()
        sys.stderr.write(f"OpenAI key OK — model replied: {reply!r}\n")
        return 0
    sys.stderr.write("OpenAI check FAILED (see error above). Key may be invalid or lack quota.\n")
    return 1


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Sync ORCID publications into papers.bib")
    parser.add_argument("--orcid", help="ORCID iD (overrides socials.yml / $ORCID_ID)")
    parser.add_argument("--dry-run", action="store_true", help="print new entries, write nothing")
    parser.add_argument("--output", help="write new entries to this file instead of papers.bib")
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds between works (rate limiting)")
    parser.add_argument(
        "--no-llm", action="store_true",
        help="skip the DOI-page LLM enrichment even if OPENAI_API_KEY is set",
    )
    parser.add_argument(
        "--check-openai", action="store_true",
        help="verify OPENAI_API_KEY authenticates, then exit (no ORCID work done)",
    )
    args = parser.parse_args()

    # Ensure UTF-8 output even on a legacy Windows console (dry-run readability).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    if args.check_openai:
        return check_openai()

    orcid = resolve_orcid(args.orcid)
    if not orcid:
        sys.stderr.write(
            "No ORCID iD found. Set it in _data/socials.yml (orcid_id:), "
            "pass --orcid, or export ORCID_ID.\n"
        )
        return 2

    llm_key = None if args.no_llm else os.environ.get("OPENAI_API_KEY")
    if llm_key:
        sys.stderr.write(f"DOI-page LLM enrichment: ON (model {OPENAI_MODEL}).\n")
    else:
        sys.stderr.write("DOI-page LLM enrichment: OFF (no OPENAI_API_KEY or --no-llm).\n")

    sys.stderr.write(f"Fetching works for ORCID {orcid} ...\n")
    works = fetch_orcid_dois(orcid)
    if not works:
        sys.stderr.write("No works returned from ORCID (empty record or API error).\n")
        return 1
    sys.stderr.write(f"ORCID record lists {len(works)} works.\n")

    bib_text = BIB_PATH.read_text(encoding="utf-8") if BIB_PATH.exists() else ""
    known_dois, known_titles = existing_index(bib_text)

    new_entries: list[str] = []
    seen_keys: set[str] = set()
    for work in works:
        doi = work.get("doi")
        norm_title = ascii_slug(work.get("title", ""))
        if doi and doi in known_dois:
            continue
        if norm_title and norm_title in known_titles:
            continue

        result = build_entry(work, llm_key)
        time.sleep(args.sleep)
        if not result:
            continue
        key, entry = result
        # Guard against duplicate keys within this run.
        if key in seen_keys:
            key = f"{key}b"
            entry = entry.replace(entry.split("{", 1)[1].split(",", 1)[0], key, 1)
        seen_keys.add(key)
        new_entries.append(entry)
        sys.stderr.write(f"  + {key}\n")

    if not new_entries:
        sys.stderr.write("No new publications to add. papers.bib is up to date.\n")
        return 0

    block = "\n\n".join(new_entries) + "\n"

    if args.dry_run:
        sys.stdout.write(block)
        sys.stderr.write(f"\n{len(new_entries)} new ent(y/ies) above (dry-run, nothing written).\n")
        return 0

    if args.output:
        Path(args.output).write_text(block, encoding="utf-8")
        sys.stderr.write(f"Wrote {len(new_entries)} new entries to {args.output}.\n")
        return 0

    # Prepend after the Jekyll front matter ("---\n---\n") so newest stays on top.
    fm = re.match(r"^(---\s*\n---\s*\n)", bib_text)
    if fm:
        head = fm.group(1)
        rest = bib_text[len(head):]
        new_text = head + "\n" + block + "\n" + rest.lstrip("\n")
    else:
        new_text = block + "\n" + bib_text
    BIB_PATH.write_text(new_text, encoding="utf-8")
    sys.stderr.write(f"Prepended {len(new_entries)} new entries to {BIB_PATH}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
