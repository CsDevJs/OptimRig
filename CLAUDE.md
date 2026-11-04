# PC Configurator

## Catalog import

After any catalog import or matching change, run the merge-consistency check, and open 10 random merged
products from every store and compare name, capacity and price with the live page before saying it's done.

From `backend/`:
- merge-consistency check over the last crawl: `.venv\Scripts\python -m pytest -q tests/test_catalog_import.py -k whole_crawl`
  (the load itself also stops on any merge conflict and lists them);
- live spot check, 10 merged products per store: `.venv\Scripts\python -m scripts.spot_check 10`.
