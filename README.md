# X_Legal_Stuff_Webscrapper

Projekt pipeline'u (Python) do zbierania i przetwarzania publicznych postow oraz obrazow z platformy X
na potrzeby analizy merytorycznej tresci tradingowych (ICT i pokrewne zagadnienia).

## Status

Repo zawiera szkielet projektu:
- `collect` - pobieranie postow (`placeholder` lub `x-api-recent-search`)
- `collect` wspiera tryb `all` oraz `filtered` (tagi/frazy)
- `collect --download-images` - pobieranie obrazow z deduplikacja (SHA256)
- `ocr` - ekstrakcja tekstu z obrazow (`placeholder` lub `openai-vision`)
- `classify` - wzbogacanie i klasyfikacja tresci (placeholder)
- `export` - eksport prostego datasetu JSONL

## Uruchomienie (MVP skeleton)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
copy .env.example .env
python -m x_legal_stuff_webscrapper collect --account example_handle
python -m x_legal_stuff_webscrapper collect --account example_handle --backend x-api-recent-search --mode filtered --tag ICT --query "LECTURE #1" --download-images
python -m x_legal_stuff_webscrapper collect --account example_handle --mode filtered --tag ICT --tag MENTORSHIP --query "ICT 2026 Mentorship" --query "LECTURE #1"
python -m x_legal_stuff_webscrapper ocr --backend openai-vision --model gpt-4.1-mini
python -m x_legal_stuff_webscrapper classify
python -m x_legal_stuff_webscrapper export
```

## Tryby pobierania

1. `all` - pobiera publiczne posty z wybranych kont (w zakresie backendu kolektora).
2. `filtered` - pobiera tylko posty pasujace do wskazanych tagow i/lub fraz.

Backendy `collect`:
1. `placeholder` - dane testowe do developmentu.
2. `x-api-recent-search` - oficjalny endpoint X API v2 (`/2/tweets/search/recent`) z filtrowaniem po stronie zrodla.

## Pobieranie obrazow i deduplikacja

- `collect --download-images` pobiera obrazy z `source_url`
- pliki sa zapisywane do `data/raw/images/by_sha256/`
- deduplikacja odbywa sie po `SHA256`
- manifest pobran zapisuje sie do `data/index/images_manifest.jsonl`

Przyklady selektywnych filtrów:
- tagi: `ICT`, `MENTORSHIP`, `LECTURE`
- frazy: `ICT 2026 Mentorship`, `LECTURE #x`

## Mapowanie selektywnych fraz do taxonomii

Klasyfikator rozszerza klasyfikacje o mapowanie regex:
- `ICT 2026 Mentorship` -> seria `ICT 2026 Mentorship` / label `ICT Full Mentoring 2026`
- `LECTURE #x` -> modul `Lecture #x` w serii `ICT 2026 Mentorship`

## OCR OpenAI (vision)

- backend `ocr --backend openai-vision` korzysta z `OPENAI_API_KEY`
- domyslny model konfigurowalny przez `OPENAI_OCR_MODEL`
- OCR pracuje na lokalnych plikach pobranych przez `--download-images`

## Dokumentacja

Szczegoly planu i wymagan formalnych znajduja sie w `docs/`.
