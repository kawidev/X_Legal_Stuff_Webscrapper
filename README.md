# X_Legal_Stuff_Webscrapper

Projekt pipeline'u (Python) do zbierania i przetwarzania publicznych postow oraz obrazow z platformy X
na potrzeby analizy merytorycznej tresci tradingowych (ICT i pokrewne zagadnienia).

## Status

Repo zawiera szkielet projektu:
- `collect` - pobieranie postow (placeholder)
- `collect` wspiera tryb `all` oraz `filtered` (tagi/frazy)
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
python -m x_legal_stuff_webscrapper collect --account example_handle --mode filtered --tag ICT --tag MENTORSHIP --query "ICT 2026 Mentorship" --query "LECTURE #1"
python -m x_legal_stuff_webscrapper ocr
python -m x_legal_stuff_webscrapper classify
python -m x_legal_stuff_webscrapper export
```

## Tryby pobierania

1. `all` - pobiera publiczne posty z wybranych kont (w zakresie backendu kolektora).
2. `filtered` - pobiera tylko posty pasujace do wskazanych tagow i/lub fraz.

Przyklady selektywnych filtrów:
- tagi: `ICT`, `MENTORSHIP`, `LECTURE`
- frazy: `ICT 2026 Mentorship`, `LECTURE #x`

## Dokumentacja

Szczegoly planu i wymagan formalnych znajduja sie w `docs/`.
