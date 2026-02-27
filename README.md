# Web Scraper CLI (`one.py`)

Et produksjonsklart scraping-program i Python med robust feilhåndtering, retries, logging og fleksibel output.

## 1) Oppsett med virtual environment (anbefalt)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 2) Kjøring

```bash
python one.py --url https://example.com --selector h2 --format text
```

Eller via wrapper som oppretter/bruker `.venv` automatisk:

```bash
./run.sh --url https://example.com --selector h2 --format json
```

## Nyttige argumenter

- `--url` (påkrevd)
- `--selector` (default: `h2`)
- `--timeout` (default: `10`)
- `--retries` (default: `3`)
- `--backoff` (default: `0.5`)
- `--format` (`text` eller `json`)
- `--output` (skriv til fil)
- `--verbose` (debug-logging)
