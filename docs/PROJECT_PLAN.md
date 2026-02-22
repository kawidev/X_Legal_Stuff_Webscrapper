# Project Plan

## Cel

Zbudowac pipeline do:
1. Pobierania publicznych postow wybranych kont X (tekst + obrazy + metadane).
   - tryb calosciowy (`all`)
   - tryb selektywny (`filtered`) po tagach/frazach
2. Ekstrakcji tresci z obrazow (OCR + analiza LLM).
3. Klasyfikacji tresci do zdefiniowanej taxonomii.
4. Eksportu ustrukturyzowanych danych do dalszej analizy/modelowania.

## Moduly

1. `collector_x`
   - lista kont zrodlowych
   - pobieranie postow i metadanych
   - backend `x-api-recent-search` (X API v2 recent search)
   - pobieranie obrazow
   - deduplikacja
2. `vision_ocr`
   - OCR obrazow
   - confidence score
3. `llm_enrichment`
   - normalizacja tresci
   - ekstrakcja pojec
4. `classifier`
   - klasyfikacja regulowa + (pozniej) LLM/ML
5. `storage`
   - JSONL/SQLite (MVP)
6. `exporter`
   - eksport danych do datasetow

## Etapy realizacji

1. MVP collector (placeholder -> backend zgodny z X ToS).
   - wsparcie filtrow po hashtagach/slowach kluczowych/frazach
   - filtracja po stronie zrodla (query X API) zamiast wyłącznie po pobraniu
2. MVP OCR.
3. MVP klasyfikacji regulowej.
4. Walidacja probki danych.
5. Integracja OpenAI API.
6. Skalowanie i automatyzacja.

## Backlog techniczny (najblizszy)

1. Dodac pobieranie i zapis plikow obrazow z metadanych `images`.
2. Dodac hash SHA256 i deduplikacje obrazow.
3. Dodac SQLite index (`accounts`, `posts`, `images`, `ocr_results`, `classifications`).
4. Dodac retry/rate limiting i logowanie bledow HTTP dla X API.
5. Rozszerzyc mapowanie fraz (`LECTURE #x`) o mapowanie do konkretnej taxonomii modułowej.
6. Dodac review workflow (manual QA).
