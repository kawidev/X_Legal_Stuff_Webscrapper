# X_Legal_Stuff_Webscrapper

Projekt pipeline'u (Python) do zbierania i przetwarzania publicznych postow oraz obrazow z platformy X
na potrzeby analizy merytorycznej tresci tradingowych (ICT i pokrewne zagadnienia).

## Status

Repo zawiera szkielet projektu:
- `collect` - pobieranie postow (`recent`, `timeline`, `all`, `placeholder`)
- `collect` wspiera tryb `all` oraz `filtered` (tagi/frazy)
- `collect --download-images` - pobieranie obrazow z deduplikacja (SHA256)
- `ocr` - ekstrakcja tekstu z obrazow (`placeholder` lub `openai-vision`)
- `extract-knowledge` - semantyczna ekstrakcja wiedzy do JSON AI-ready (OpenAI / placeholder)
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
python -m x_legal_stuff_webscrapper extract-knowledge --backend openai --model gpt-4.1-mini --max-posts 1
python -m x_legal_stuff_webscrapper classify
python -m x_legal_stuff_webscrapper export
```

## Tryby pobierania

1. `all` - pobiera publiczne posty z wybranych kont (w zakresie backendu kolektora).
2. `filtered` - pobiera tylko posty pasujace do wskazanych tagow i/lub fraz.

Backendy `collect`:
1. `placeholder` - dane testowe do developmentu.
2. `recent` / `x-api-recent-search` - X API v2 `search/recent` (okno recent, dobre do selektywnego search).
3. `timeline` / `x-api-user-timeline` - X API v2 user timeline (`/users/{id}/tweets`), lepsze do backfillu profilu.
4. `all` / `x-api-search-all` - X API v2 full archive search (`search/all`), jesli plan X to udostepnia.

### Backend Matrix (praktycznie)

| Backend | Endpoint X API | Kiedy uzywac | Ograniczenie glówne |
|---|---|---|---|
| `recent` | `/2/tweets/search/recent` | szybki selektywny search po frazach/tagach | recent window (ostatnie dni) |
| `timeline` | `/2/users/{id}/tweets` | pobieranie postów konkretnego profilu | do ok. 3200 najnowszych postów |
| `all` | `/2/tweets/search/all` | historyczny backfill + precyzyjne query | wymaga odpowiedniego planu/kredytów |

### Content Mode (typ tresci)

- `with-images` - tylko posty z obrazami
- `only-text` - tylko posty bez obrazow
- `mixed` - wszystko (domyslnie)

Przyklady:

```powershell
python x_scrapper.py collect --account Drevaxtrades --backend timeline --mode all --content-mode mixed
python x_scrapper.py collect --account Drevaxtrades --backend recent --mode filtered --query "Masterclass" --content-mode with-images
python x_scrapper.py collect --account Drevaxtrades --backend all --mode all --content-mode only-text
```

## Pobieranie obrazow i deduplikacja

- `collect --download-images` pobiera obrazy z `source_url`
- pliki sa zapisywane do `data/raw/images/by_sha256/`
- deduplikacja odbywa sie po `SHA256`
- manifest pobran zapisuje sie do `data/index/images_manifest.jsonl`
- requesty X API maja retry/backoff i logowanie rate-limit headers (`x-rate-limit-*`)

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

## Ekstrakcja wiedzy (AI-ready JSON)

- komenda: `extract-knowledge`
- wejscie: `processed/posts.jsonl` + `processed/ocr_results.jsonl`
- wyjscie: `processed/knowledge_extract.jsonl`
- backend `openai` generuje strukture JSON pod dalsza kuracje i klasyfikacje:
  - `knowledge_extract`
  - `trading_context_extract`
  - `contextor_mapping_candidates`
  - `quality_control`
  - `provenance_index`

Przyklad (probka 1 post):

```powershell
$env:DATA_DIR=".\\data\\drevax_ocr_sample_3"
python x_scrapper.py extract-knowledge --backend openai --model gpt-4.1-mini --max-posts 1
```

## Dokumentacja

Szczegoly planu i wymagan formalnych znajduja sie w `docs/`.
