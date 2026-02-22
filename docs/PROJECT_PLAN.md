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
2. MVP OCR.
3. MVP klasyfikacji regulowej.
4. Walidacja probki danych.
5. Integracja OpenAI API.
6. Skalowanie i automatyzacja.

## Backlog techniczny (najblizszy)

1. Dodac rzeczywisty backend kolektora (API/platform adapter).
2. Dodac wyszukiwanie selektywne z mapowaniem fraz do taxonomii (np. `ICT 2026 Mentorship`, `LECTURE #x`).
3. Dodac zapis obrazow + hash SHA256.
4. Dodac SQLite index (`accounts`, `posts`, `images`, `ocr_results`, `classifications`).
5. Dodac retry/rate limiting i logowanie bledow.
6. Dodac review workflow (manual QA).
