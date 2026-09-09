# Review templatki FastAPI

Stan wyjściowy: `master` (`db63eb1`) oraz otwarty PR #1. Cel: mała templatka
feature-based z warstwami routes → services → repository, Pythonem 3.14 i niską
złożonością kodu. PR #1 zachowano i rozwinięto; jego kierunek był poprawny, ale
sam nie domykał architektury ani części przypadków brzegowych.

## Co było dobrze zrobione

- **Cienkie route'y i małe serwisy use case'ów.** Przepływ jest jawny, bez kontenera
  DI i rozbudowanej hierarchii klas. Zachowano ten styl.
- **Repozytoria bez commitów.** Własność transakcji jest czytelna: use case HTTP
  kończy transakcję, a worker korzysta z jednego session scope. Testy savepointów
  pozwalają sprawdzać prawdziwy commit/rollback.
- **Zależności ładujące zasoby.** `ValidItem` usuwa powtarzające się fetch/404 i
  korzysta z cache zależności FastAPI w ramach requestu.
- **Async SQLAlchemy, psycopg, migracje i realny PostgreSQL w testach.** To dobra
  baza do projektów korzystających z relacyjnej bazy danych.
- **UUIDv7, timestampy ze strefą, naming conventions i check constraints.** Spójne
  podstawy modelowania bez własnego frameworka persistence.
- **Jawny kontrakt błędów i test rejestru kluczy.** Stabilne klucze i18n mogą zostać,
  jeżeli projekty używają wspólnego klienta/frontendowego tłumaczenia komunikatów.
- **Cykl życia workerów.** Stała pętla async na proces, late ACK i prefetch=1 są
  wartościowe, kiedy projekt rzeczywiście potrzebuje Celery.

## Wykryte problemy i wdrożone poprawki

| Priorytet | Problem | Zmiana |
|---|---|---|
| P1 | Limit body sprawdzał tylko Content-Length; chunked omijał limit, a niepoprawny nagłówek powodował 500. | Liczenie odebranych bajtów oraz odpowiedzi 400/413; testy chunked, błędnego nagłówka i wartości granicznej. |
| P1 | Globalny handler 500 działał poza dodanymi middleware. Błędy traciły CORS, security headers i request ID. | Zewnętrzne wrappery ASGI otaczają cały FastAPI; test rzeczywistego błędu endpointu sprawdza nagłówki. |
| P1 | Synchroniczne publikowanie Celery z `async def` blokowało pętlę API. | Endpoint enqueue jest synchroniczny, więc FastAPI uruchamia go w thread poolu. |
| P1 | Klient Bedrock był tworzony podczas importu modułu agenta, mimo deklarowanej inicjalizacji po fork. | Agent i provider powstają w cache'owanej fabryce przy pierwszym użyciu; import nie wymaga AWS. |
| P2 | Window count zwracał zero na stronie poza zakresem. Sortowanie po samym created_at nie ustalało kolejności remisów. | Osobny COUNT i sortowanie created_at + id. Pusta strona zachowuje total_count/total_pages. |
| P2 | Feature był rozdzielony między features i centralne repositories; repozytoria zawierały również zależności HTTP. | Model, repository, dependencies, schemas, routes i services są w jednym katalogu feature'a. |
| P2 | Serwisy używały FastAPI-owego AsyncDb, a serializer walidował model Pydantic, robił dict i oddawał go do ponownej walidacji. | Konstruktor przyjmuje AsyncSession, serwisy zwracają encje/TypedDict, Pydantic serializuje na granicy HTTP. |
| P2 | Testy budowały schema przez create_all, więc nie sprawdzały migracji. Modele nie deklarowały serwerowych defaultów obecnych w migracji. | Testy używają Alembica; modele/defaulty są zgodne, CI sprawdza drift i pełny upgrade/downgrade. |
| P2 | Alembic czytał URL inaczej niż aplikacja, a kod SET search_path wymagał ręcznego domykania transakcji. | Jeden odczyt settings env/.env, poprawne escapowanie %, transakcję migracji prowadzi Alembic. |
| P2 | Testy i fixture'y mogły korzystać z różnych pętli przy wspólnej puli async. | Jeden session loop dla obu. |
| P2 | Ustawienia nadpisywały jawne wartości, miały przykładowe domeny produkcyjne i arbitralnie większe pule na produkcji. | Proste, jawne defaulty; puste CORS i zero overflow są zachowane; ENVIRONMENT jest walidowane. |
| P2 | Wyłączenie dokumentacji pozostawiało endpoint OpenAPI. | Wspólne SHOW_DOCS steruje docs, redoc i openapi.json. |
| P2 | Każda replika API uruchamiała migracje w entrypoincie, a worker mógł wystartować przed nimi. | Osobna usługa migrate; API i worker czekają na jej zakończenie. |
| P2 | Kod aplikacji nie zamykał puli DB przy shutdown. Child disposował odziedziczone połączenia z close=True. | Cleanup w lifespan i dispose(close=False) przy inicjalizacji childa. |
| P3 | Pusta po trimowaniu nazwa przechodziła walidację. | Normalizacja przed sprawdzeniem długości. |
| P3 | Soft timeout z globalnej konfiguracji przewyższał hard timeout krótszych tasków. | Jawne soft limity poniżej hard limitów. |

## Co uproszczono lub usunięto

- Python **3.14** we wszystkich środowiskach; `uuid.uuid7()` zastępuje `uuid-utils`
  i wrapper. Zaktualizowano zależności binarne niezgodne ze starym lockiem na 3.14.
- **Celery/Redis oraz AI są extras.** Core uruchamia publiczne CRUD bez brokera i AWS.
  Instalacja `ai` dodaje przykład endpointu AI; `workers` wystarcza do zadań bez LLM.
- Jednomodułowy router nie potrzebuje osobnego katalogu. Usunięto pośredni serializer
  oraz nieużywany mechanizm wyliczania FK w factory.
- Zachowano z PR #1 usunięcie `fastapi-guard`, scalenie modułów DB i nazwę `enqueue.py`.
  Małe middleware obsługują potrzebne funkcje; polityki rate limiting/WAF konfiguruje ingress.
- Usunięto hipotetyczne wyjątki dużych uploadów oraz niestandardowe nazwy kluczy AWS.
- Skrócono i ujednolicono instrukcje kodowania. Nie ma obowiązku rozbijania prostych
  operacji na prywatną metodę dla każdego kroku ani trzymania indeksów poza metadata.

## Czytelność i complexipy

PR #1 wprowadził właściwe narzędzie: **complexipy**, limit **10 na funkcję**, wspólny
dla `app`, `tests` i `alembic`, uruchamiany lokalnie oraz w CI. Zachowano tę bramkę
oraz Ruff i Pyright. Najwyższy wynik po zmianach: **7**.

Wynik traktujemy jako ograniczenie zagnieżdżeń i rozgałęzień. Osobne klasy/funkcje
nie poprawiają czytelności automatycznie; nie warto rozdrabniać sekwencyjnego
trzywierszowego use case'a wyłącznie dla struktury. Typowane wyniki i jawne
transakcje pomagają bardziej niż kolejna warstwa abstrakcji.

## Czego świadomie nie dodano

Auth/RBAC, generic CRUD, kontenera DI, rozbudowanego Unit of Work, cache, outboxa,
metryk i gotowych workflowów deploymentu. Ich wymagania zależą od projektu;
nie powinny być obowiązkowe w podstawowej templatce.

Przykład AI zabezpiecza przed ponownym przetworzeniem już zapisanej odpowiedzi,
nie przed równoczesnymi wywołaniami ani awarią między wywołaniem modelu i commitem.
Prawdziwe exactly-once dla zewnętrznego efektu wymaga dodatkowych gwarancji.
Osobny COUNT i lista przy READ COMMITTED mogą zobaczyć równoczesne zmiany; API nie
obiecuje snapshotu. `/up` sprawdza proces, nie gotowość wszystkich zależności.
Te ograniczenia są jawne w README, bez dokładania niepotrzebnej infrastruktury.

## Weryfikacja

- Python 3.14.7 i PostgreSQL 18: pełny wariant AI **51 testów**, bez wywołań modelu.
- Osobne czyste instalacje core i workers oraz testy importu runtime bez dev dependencies.
- Ruff format/check, Pyright, complexipy oraz zgodność locka.
- Alembic upgrade/check/downgrade/upgrade i brak różnic metadata względem migracji.
- Budowanie obrazów Docker i walidacja konfiguracji Compose.
- CI wykonuje kontrole w macierzy core/workers/ai na Pythonie 3.14.

Nie testowano rzeczywistego wywołania Bedrock ani wysyłania telemetry do Sentry;
nie są potrzebne do sprawdzenia podstawowej templatki.

## Źródła decyzji dotyczących bibliotek

- [Python 3.14: uuid.uuid7](https://docs.python.org/3.14/library/uuid.html#uuid.uuid7).
- [Complexipy: próg i konfiguracja](https://github.com/rohaquinlop/complexipy/blob/main/README.md).
- [Starlette: CORS Global Enforcement](https://starlette.dev/middleware/#corsmiddleware-global-enforcement).
- [SQLAlchemy: async i wiele pętli zdarzeń](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-multiple-asyncio-event-loops).
