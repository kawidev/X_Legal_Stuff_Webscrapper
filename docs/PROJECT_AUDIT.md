# Project Audit (2026-02-22)

## Zakres audytu

Audyt funkcjonalny i dokumentacyjny projektu `X_Legal_Stuff_Webscrapper` po wdrozeniu:
- `qa-knowledge`
- `schema-knowledge`
- `gate-knowledge-export`
- `export-knowledge-library`
- profili polityk ingestu (`strict`, `balanced`, `permissive`)

## Podsumowanie stanu

Projekt jest na etapie **roboczego pipeline'u end-to-end z kontrola jakosci danych**.

Dziala:
1. Collect z backendami X API (`recent`, `timeline`, `all`) + `placeholder`
2. Pobieranie obrazow + deduplikacja SHA256
3. OCR (`placeholder`, `openai-vision`)
4. `extract-knowledge` (AI-ready JSON)
5. `qa-knowledge` (canonicalizer + validator + QA report)
6. `schema-knowledge` (JSON Schema dla canonical record)
7. `gate-knowledge-export` (severity policy + run/record gate)
8. `export-knowledge-library` (`ready/rejects`)

## Mocne strony (aktualnie)

1. **Kontrola kontraktu danych**
- schema drift jest normalizowany przez canonicalizer
- walidacja strukturalna i semantyczna jest rozdzielona od promptu/modelu

2. **Provenance i audytowalnosc**
- sprawdzanie broken refs
- metryki `evidence_resolution_rate` i `provenance_utilization_rate`
- canonicalization trace per item (`_canonicalized`, `_canonicalization_notes`)

3. **Operacyjna gotowosc do kuracji**
- `knowledge_library_ready.jsonl`
- `knowledge_library_rejects.jsonl` z jawnymi powodami odrzucenia
- profile polityk ingestu (`strict|balanced|permissive`)

## Gaps / ryzyka (najblizsze)

1. **Koszty i throughput**
- OCR / `extract-knowledge` zalezne od kosztow i limitow OpenAI API
- X API kredyty / limity nadal wymagaja monitoringu kosztowego na realnych wolumenach

2. **Idempotencja eksportu biblioteki**
- brak dedykowanego klucza idempotencji / dedupu dla `knowledge_library_ready`

3. **Governance polityk**
- profile sa juz dostepne, ale brak osobnej dokumentacji progow i procedury zmiany polityk

4. **Warstwa review/human curation**
- `ready` stream jest gotowy, ale brakuje jeszcze dedykowanego workflow narzedziowego do recznej kuracji

## Rekomendowane nastepne kroki (priorytet)

1. Dodac `policy README` (intencja progow + kiedy uzywac `strict/balanced/permissive`)
2. Dodac `shadow mode` porownania profili na tym samym runie bez nadpisywania eksportu
3. Dodac dedup/idempotency key do `knowledge_library_ready`
4. Dodac review workflow (manual curation + feedback do policy/prompt)

## Status dokumentacji

Dokumentacja zostala zaktualizowana o:
- warstwe quality gates i kontraktu danych
- eksport do biblioteki wiedzy
- profile polityk ingestu
- governance i wymagania operacyjne (QA/gate artifacts)
