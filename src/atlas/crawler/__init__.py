"""The web crawler (docs/crawler_plan.md): a polite, resumable, relevance-steered Scrapy crawler.

    atlas fetch <source>          for a source with `type: crawl` in config/sources.yaml
    python -m atlas.crawler.run   the same, directly (also used by the tests)

Modules: urls (normalize, scope, traps) · relevance (what is worth fetching) · frontier (every URL and its
status, on disk) · archive (raw bytes + manifest) · middlewares (politeness, safety) · spider · docs · report.
"""
