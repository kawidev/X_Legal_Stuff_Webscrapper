# Project Plan

## Cel

Zbudowac pipeline do:
1. Pobierania publicznych postow wybranych kont X (tekst + obrazy + metadane).
   - tryb calosciowy (`all`)
   - tryb selektywny (`filtered`) po tagach/frazach
2. Ekstrakcji tresci z obrazow (OCR + analiza LLM).
3. Klasyfikacji tresci do zdefiniowanej taxonomii.
4. Uszczelnienia kontraktu danych (`canonicalizer + validator + QA report`).
5. Kontrolowanego eksportu do biblioteki wiedzy (TRADING_WORD) w trybach `strict/balanced/permissive`.
6. Eksportu ustrukturyzowanych danych do dalszej analizy/modelowania.

## Moduly

1. `collector_x`
   - lista kont zrodlowych
   - pobieranie postow i metadanych
   - backend `x-api-recent-search` (X API v2 recent search)
   - pobieranie obrazow + deduplikacja SHA256
   - deduplikacja
2. `vision_ocr`
   - OCR obrazow (placeholder / OpenAI vision)
   - confidence score
3. `llm_enrichment`
   - normalizacja tresci
   - ekstrakcja pojec
4. `knowledge_extractor`
   - JSON AI-ready pod kuracje semantyczna i przyszly Contextor
   - provenance / observed vs inferred vs uncertain
5. `knowledge_quality`
   - canonicalizer aliasow i typow
   - strict validator + contract checks
   - QA report i canonicalization trace
6. `knowledge_gate`
   - severity policy
   - record/run-level export gate
   - profile ingest (`strict/balanced/permissive`)
7. `knowledge_library_export`
   - `ready/rejects` stream pod TRADING_WORD
   - quality snapshot + curation hints
8. `classifier`
   - klasyfikacja regulowa + (pozniej) LLM/ML
9. `storage`
   - JSONL/SQLite (MVP)
10. `exporter`
   - eksport danych do datasetow

## Etapy realizacji (stan)

1. MVP collector (placeholder -> backend zgodny z X ToS). ✅
   - wsparcie filtrow po hashtagach/slowach kluczowych/frazach
   - filtracja po stronie zrodla (query X API) zamiast wyłącznie po pobraniu
2. MVP OCR. ✅
3. MVP klasyfikacji regulowej. ✅ (wersja robocza)
4. Walidacja probki danych. ✅ (sample pack + QA)
5. Integracja OpenAI API. ✅ (OCR + extract-knowledge)
6. Schema hardening + quality gates v1. ✅
7. Export gate + library ready/rejects v1. ✅
8. Skalowanie i automatyzacja. ⏳

## Backlog techniczny (najblizszy)

1. Dodac `policy README` / opis progow dla `strict|balanced|permissive`.
2. Dodac `shadow mode` (porownanie profili bez zmiany eksportu).
3. Dodac export-level dedup / idempotency key dla `knowledge_library_ready`.
4. Dodac SQLite/Postgres index dla lineage (`posts/images/ocr/knowledge/gate/export`).
5. Rozszerzyc review workflow (manual QA + feedback loop do promptu i policy).
