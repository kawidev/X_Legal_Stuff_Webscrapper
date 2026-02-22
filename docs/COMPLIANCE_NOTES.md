# Compliance Notes (Draft)

## Wazne zastrzezenie

Publiczna dostepnosc tresci nie oznacza automatycznie prawa do dowolnej redystrybucji lub uzycia treningowego.

## Obszary do weryfikacji przed produkcyjnym uzyciem

1. Aktualne warunki korzystania z platformy X (ToS, automation/scraping, API terms).
2. Zakres dozwolonego pobierania i przechowywania tresci publicznych.
3. Prawa autorskie do obrazow i materialow edukacyjnych.
4. Podstawy prawne i ograniczenia dalszego wykorzystania danych (szczegolnie trening modeli).
5. Zgodnosc przesylania obrazow/tekstow do zewnetrznych API (w tym OpenAI API).

## Wymagania operacyjne

1. Preferowac oficjalne API lub backend zgodny z warunkami platformy.
2. Dla backendu X API dokumentowac uzyty endpoint, parametry query i zakres czasowy (np. `recent search`).
2. Zachowac provenance i zrodlo dla kazdego rekordu.
3. Nie publikowac ponownie pobranych obrazow bez podstawy prawnej.
4. Oznaczyc projekt jako narzedzie analityczne, nie zrodlo porad inwestycyjnych.
5. Rozdzielac rekordy dopuszczone do kuracji od rekordow odrzuconych (`knowledge_library_ready` vs `knowledge_library_rejects`) i zachowac powod odrzucenia.

## Governance danych (jakość i audyt)

Projekt posiada warstwe kontroli jakosci przed ingestem do biblioteki wiedzy:
- canonicalizer + validator (`qa-knowledge`)
- severity policy / export gate (`gate-knowledge-export`)
- profile rygoru (`strict`, `balanced`, `permissive`)

To nie jest gwarancja prawna poprawnosci danych, ale:
- ogranicza ryzyko użycia rekordow z broken lineage,
- poprawia audytowalnosc pochodzenia i transformacji danych,
- pozwala swiadomie dobierac poziom rygoru do celu (kuracja vs research).
