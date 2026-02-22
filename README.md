# X_Legal_Stuff_Webscrapper

Projekt pipeline'u (Python) do zbierania i przetwarzania publicznych postow oraz obrazow z platformy X
na potrzeby analizy merytorycznej tresci tradingowych (ICT i pokrewne zagadnienia).

## Status

Repo zawiera szkielet projektu:
- `collect` - pobieranie postow (placeholder)
- `ocr` - ekstrakcja tekstu z obrazow (placeholder)
- `classify` - wzbogacanie i klasyfikacja tresci (placeholder)
- `export` - eksport prostego datasetu JSONL

## Uruchomienie (MVP skeleton)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]
copy .env.example .env
python -m x_legal_stuff_webscrapper collect --account example_handle
python -m x_legal_stuff_webscrapper ocr
python -m x_legal_stuff_webscrapper classify
python -m x_legal_stuff_webscrapper export
```

## Dokumentacja

Szczegoly planu i wymagan formalnych znajduja sie w `docs/`.
