# Marketplace Assistant v2

Railway-ready mobile dashboard and matching engine.

Includes mobile rules, keyword/exclusion filtering, max-price filtering,
duplicate protection, deal scoring, SQLite history, health endpoint and
a connector-neutral worker.

The app does not bypass logins, CAPTCHAs, or marketplace restrictions.
Permitted/authorized listing adapters can feed new listings to `POST /api/listings`.
