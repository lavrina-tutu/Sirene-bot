---
name: research-tools
description: "Research discovery tools umbrella: arXiv paper search (REST"
version: 1.0.1
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Research, Arxiv, Papers, Academic, RSS, Blogs, Feed-Reader, Wiki, Knowledge-Base, Monitoring]
    related_skills: [research-paper-writing, obsidian, ocr-and-documents]
---

# Research Tools — Discovery, Monitoring & Knowledge Base

> **Umbrella skill.** Routes to the right tool:
>
> | Task | Section |
> |------|---------|
> | Search academic papers on arXiv | [Section A — arXiv Search](#section-a--arxiv-search) |
> | Monitor blogs and RSS feeds | [Section B — Blogwatcher](#section-b--blogwatcher) |
> | Build/query a personal knowledge base | [Section C — LLM Wiki](#section-c--llm-wiki) |

---

## Section A — arXiv Search

Search and retrieve academic papers via arXiv's free REST API. No API key, no dependencies — just curl.

### Quick Reference

| Action | Command |
|--------|---------|
| Search papers | `curl "https://export.arxiv.org/api/query?search_query=all:QUERY&max_results=5"` |
| Get specific paper | `curl "https://export.arxiv.org/api/query?id_list=2402.03300"` |
| Read abstract (web) | `web_extract(urls=["https://arxiv.org/abs/2402.03300"])` |
| Read full paper (PDF) | `web_extract(urls=["https://arxiv.org/pdf/2402.03300"])` |

### Search Query Syntax

| Prefix | Searches | Example |
|--------|----------|---------|
| `all:` | All fields | `all:transformer+attention` |
| `ti:` | Title | `ti:large+language+models` |
| `au:` | Author | `au:vaswani` |
| `abs:` | Abstract | `abs:reinforcement+learning` |
| `cat:` | Category | `cat:cs.AI` |

**Boolean:** AND (default), OR, ANDNOT. Exact phrase: `ti:"chain+of+thought"`

### Clean Output (parse XML)

```bash
curl -s "https://export.arxiv.org/api/query?search_query=all:QUERY&max_results=5&sortBy=submittedDate&sortOrder=descending" | python3 -c "
import sys, xml.etree.ElementTree as ET
ns = {'a': 'http://www.w3.org/2005/Atom'}
root = ET.parse(sys.stdin).getroot()
for i, entry in enumerate(root.findall('a:entry', ns)):
    title = entry.find('a:title', ns).text.strip().replace('\n', ' ')
    arxiv_id = entry.find('a:id', ns).text.strip().split('/abs/')[-1]
    published = entry.find('a:published', ns).text[:10]
    authors = ', '.join(a.find('a:name', ns).text for a in entry.findall('a:author', ns))
    summary = entry.find('a:summary', ns).text.strip()[:200]
    cats = ', '.join(c.get('term') for c in entry.findall('a:category', ns))
    print(f'{i+1}. [{arxiv_id}] {title}')
    print(f'   Authors: {authors}')
    print(f'   Published: {published} | Categories: {cats}')
    print(f'   Abstract: {summary}...')
    print(f'   PDF: https://arxiv.org/pdf/{arxiv_id}')
    print()
"
```

**Python helper script:** `references/search_arxiv.py` (formerly `scripts/search_arxiv.py`)

### Sort and Pagination

| Parameter | Options |
|-----------|---------|
| `sortBy` | `relevance` (default), `lastUpdatedDate`, `submittedDate` |
| `sortOrder` | `descending` (default), `ascending` |
| `start` | Offset (e.g., `start=10` for page 2 of 10) |
| `max_results` | Up to 2000 per request; default 10 |

### Tips

- For PDFs, `web_extract` converts to markdown text automatically
- Rate limit: be gentle, add 3s between bulk requests
- For authors with common names, combine: `au:lecun+AND+cat:cs.LG`

---

## Section B — Blogwatcher

Track blog and RSS/Atom feed updates with `blogwatcher-cli`.

### Installation

```bash
# Linux amd64
curl -sL https://github.com/JulienTant/blogwatcher-cli/releases/latest/download/blogwatcher-cli_linux_amd64.tar.gz | tar xz -C /usr/local/bin blogwatcher-cli

# Go
go install github.com/JulienTant/blogwatcher-cli/cmd/blogwatcher-cli@latest
```

### Common Commands

```bash
# Add a blog (auto-discovers feed)
blogwatcher-cli add "My Blog" https://example.com

# Add with explicit feed URL
blogwatcher-cli add "My Blog" https://example.com --feed-url https://example.com/feed.xml

# Add with HTML scraping (no RSS)
blogwatcher-cli add "My Blog" https://example.com --scrape-selector "article h2 a"

# List tracked blogs
blogwatcher-cli blogs

# Scan all blogs for new posts
blogwatcher-cli scan

# List unread articles
blogwatcher-cli articles --unread

# Mark article as read
blogwatcher-cli read <article-id>

# Mark all as read
blogwatcher-cli read --all

# Remove a blog
blogwatcher-cli remove "My Blog" --yes

# Import from OPML
blogwatcher-cli import subscriptions.opml
```

### Automated Scanning (cron)

```
# Add to crontab or hermes cronjob
0 8 * * * blogwatcher-cli scan
```

### Pitfalls

- Default DB at `~/.blogwatcher-cli/blogwatcher-cli.db` — back it up before upgrades
- Some sites block RSS scrapers — try `--scrape-selector` or manual feed discovery
- Docker: use a volume to persist DB across container restarts (`-e BLOGWATCHER_DB=/data/db`)

---

## Section C — LLM Wiki (Karpathy Pattern)

Build and maintain a persistent, compounding knowledge base as interlinked markdown files.
Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

**Key insight:** Unlike RAG (rediscovers per query), the wiki compiles once, keeps current. Cross-references are pre-built. Synthesis is cumulative.

### Wiki Location

Set via `WIKI_PATH` env var (default: `~/wiki`). The wiki is just a directory of markdown files — open in Obsidian, VS Code, or any editor.

### Architecture: Three Layers

```
wiki/
├── SCHEMA.md           # Conventions, structure rules, domain config
├── index.md            # Sectioned content catalog with one-line summaries
├── log.md              # Chronological action log (append-only, rotated yearly)
├── raw/                # Layer 1: Immutable source material
│   └── YYYY-MM-DD-slug.md
├── notes/              # Layer 2: Curated summaries with cross-links
│   └── topic-slug.md
└── synthesis/          # Layer 3: Synthesized insights across multiple notes
    └── topic-slug.md
```

**Division of labor:** Human curates sources and directs analysis. Agent summarizes, cross-references, files, and maintains consistency.

### Core Operations

**Ingest a source:**
1. Save raw content to `raw/YYYY-MM-DD-slug.md` (verbatim, no editing)
2. Summarize key claims, quotes, and concepts into `notes/<topic>.md`
3. Add cross-links to related notes (`[[related-topic]]`)
4. Update `index.md` with a one-line summary under the right section
5. Append to `log.md`: `YYYY-MM-DD | ingested | source-slug | one-liner`

**Query the wiki:**
1. Search index.md for relevant sections
2. Read the notes files (not raw — too verbose)
3. Check synthesis files for pre-built cross-domain insights

**Lint/audit the wiki:**
1. Check for broken cross-links (`[[topic]]` references to non-existent files)
2. Flag notes with no cross-links (isolated knowledge)
3. Flag synthesis files more than 6 months old (may need refresh)

### Pitfalls

- Don't edit raw/ — it's the immutable record
- Don't make synthesis/ too specific (then it won't surface in diverse searches)
- Periodically re-synthesize after significant new ingestions
