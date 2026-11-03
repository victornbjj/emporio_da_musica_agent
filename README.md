# Empório da Música — Customer Service Agent

A customer-service agent for a (fictional) musical instrument store in Campo Grande, Brazil.
It answers questions about products, prices, promotions, orders, returns, shipping, payment
and store policies, in Brazilian Portuguese, using the store's real data.

Built for the Artefact AI Engineer technical case.

**Core idea:** the LLM does *not* know prices, stock or rules. It decides which tool to call and
writes the answer in a friendly tone. Everything that can be calculated or looked up is done by
tested Python code.

## Quickstart

Requires Python 3.10 or newer and a free [Groq](https://console.groq.com) API key.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows (Git Bash): source .venv/Scripts/activate
pip install -e ".[dev]"
cp .env.example .env                 # then put your key in .env
python -m emporio_agent.main         # start the chat (type "sair" to quit)
```

Other commands:

```bash
pytest -q                            # run the test suite
python scripts/run_examples.py       # regenerate the example conversations in examples/
```

### Configuration (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `LLM_API_KEY` | API key of the provider | — |
| `LLM_BASE_URL` | Any OpenAI-compatible endpoint | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | Model name | `openai/gpt-oss-120b` |
| `AS_OF_DATE` | The agent's "today" (see Assumptions) | `2026-03-31` |
| `LLM_REASONING_EFFORT` | Optional (`low`, `medium`, `high`) for gpt-oss | unset |

The `.env` file is never committed; only `.env.example` is.

## What the agent can do

The agent exposes seven tools to the model:

| Tool | Answers questions about | Where the logic lives |
|---|---|---|
| `search_products` | Catalog search with filters (category, price, availability) | `data/repository.py` |
| `get_product_details` | One product: price, promotion, PIX price, installments, alternatives | `data/repository.py`, `rules/pricing.py` |
| `get_order_status` | Order status, delay, tracking (requires identity check) | `tools/orders.py` |
| `check_return` | Which return/exchange/warranty deadlines still apply to an order | `rules/returns.py` |
| `calculate_shipping` | Shipping fee and delivery time by city | `rules/shipping.py` |
| `payment_options` | Allowed installments and combined payment | `rules/pricing.py` |
| `search_policies` | Store hours, exchange rules, warranty, tracking, LGPD | `retrieval/` |

## Architecture

```
customer message
      │
      ▼
  agent.py ── tool-calling loop (hand written, no agent framework)
      │
      ├─► LLM (OpenAI-compatible API; Groq + gpt-oss-120b by default)
      │
      └─► tools/registry.py  (schemas + safe dispatcher)
              │
              ├─ tools/products.py ─► data/repository.py ─► rules/pricing.py
              ├─ tools/orders.py   ─► data/loader.py + rules/returns.py
              ├─ tools/checkout.py ─► rules/shipping.py + rules/pricing.py
              └─ tools/policies.py ─► retrieval/ (section chunks + BM25)
```

Responsibilities are split on purpose:

- **Numbers and conditions go in code** (`rules/`): PIX discount, installments, return deadlines,
  free-shipping threshold. They are deterministic and covered by unit tests.
- **Descriptive text goes in retrieval**: the policy PDF is split by numbered section and
  searched with BM25.
- **Behavior goes in the system prompt**: tone, scope, privacy and escalation rules.

## Key design decisions

| Decision | Why |
|---|---|
| Hand-written tool-calling loop instead of LangChain/LangGraph | The flow is simple (message → tools → answer). A short loop is easier to read, debug and explain than a framework |
| Business rules in Python, not in the prompt | The model must never calculate money or deadlines. Tests can prove the rules |
| `Decimal` for all money | Avoids float rounding errors in prices and installments |
| Only `is_active` promotions are offered | The promotions table has 25 rows but only 4 are active; expired ones must never be promised |
| Availability = `status == active` **and** `stock > 0` | The data has active products with zero stock, and discontinued/coming-soon products with stock |
| Price filters use the price the customer pays | "Up to R$ 1,000" means after any promotion |
| PIX discount is not stacked with promotions | Manual section 6.2 |
| BM25 over manual sections instead of embeddings | The manual is 8 pages (about 25 sections); BM25 is simple, fast and needs no extra service |
| Order lookups need order number **and** e-mail or last 4 phone digits | Privacy. Verification starts from the order's own customer, so the duplicated e-mail in the data (customers 11 and 43) is harmless |
| Same message for "order not found" and "wrong data" | Prevents discovering which order numbers exist |
| Exact stock is never shown | The manual asks for availability, not counts |
| Free Groq tier with `gpt-oss-120b` | Good tool calling at no cost. The endpoint is configurable, so any OpenAI-compatible model works |

## Assumptions

The dataset and manual leave some points open. These are the choices made (details in
[`docs/data_quality.md`](docs/data_quality.md)):

| # | Assumption | Reason |
|---|---|---|
| A1 | "Today" is `2026-03-31` (configurable) | The newest order is from 2026-03-22 |
| A2 | `estimated_delivery` is used as the delivery date of delivered orders | There is no `delivered_at` column |
| A3 | Shipping region comes from `customers.city` | There is no delivery address |
| A4 | `total_brl` is the amount paid | Prices may have changed after purchase |
| A5 | All orders are online orders | There is no sales-channel column |
| A6 | "Metropolitan area" means only the city of Campo Grande | The manual does not define it |

## Data quality findings

The loader audits the data (`python -m emporio_agent.data.loader`) instead of silently fixing it.
Main findings: products whose status and stock disagree, three product categories with no
products, a duplicated customer e-mail, two orders whose total differs from the sum of their
items, and 12 of 20 orders with no estimated delivery date. Each finding and the rule that
handles it is documented in [`docs/data_quality.md`](docs/data_quality.md) (English and Portuguese).

## Example conversations

Generated with the real model by `scripts/run_examples.py`. Each file shows the customer
messages, the tools the agent called and its replies.

| File | What it shows |
|---|---|
| [`01_precos_promocao_e_estoque`](examples/01_precos_promocao_e_estoque.md) | Real-time prices; an expired promotion is not offered; an out-of-stock product gets alternatives |
| [`02_pedido_atrasado`](examples/02_pedido_atrasado.md) | Identity check before showing an order; late delivery acknowledged |
| [`03_devolucao_garantia_legal`](examples/03_devolucao_garantia_legal.md) | Three return deadlines applied to one order (7, 30 and 90 days) |
| [`04_prazo_troca_pagamento_frete`](examples/04_prazo_troca_pagamento_frete.md) | Policy lookup, combined payment, shipping to another city without inventing a fee |
| [`05_privacidade_e_escopo`](examples/05_privacidade_e_escopo.md) | Another customer's e-mail rejected; accessories out of scope; prompt-injection attempt |

## Testing

`pytest -q` runs the suite (rules, data loading, policy retrieval, catalog, tools and the agent loop).
The agent-loop tests use a fake LLM client, so they run offline and are deterministic.
The behavior of the real model was checked by hand with a written checklist and by the
generated example conversations.

## Limitations and next steps

- **No persistent memory.** The conversation lives in RAM; only the last 6 customer messages are
  kept. History is trimmed by turns, not by tokens, so very long tool results can still reach the
  free-tier limit (about 8K tokens per minute). The agent retries with backoff and apologizes
  if it cannot recover.
- **Lexical search.** Both policy search and product text search match words, not meaning. A
  customer saying "iniciante" will not match a description that says "para quem está começando".
  Embeddings or a synonym list would be the next step.
- **Weak identity proof.** An order number plus e-mail (or last 4 phone digits) is enough, and
  there is no limit on attempts. Acceptable for a prototype, not for production.
- **The agent cannot act.** It does not create orders, start returns or exchanges, or change
  anything. It informs and hands the customer to the store team (WhatsApp / phone).
- **Delivery date is an estimate** (A2), so return deadlines are approximate.
- **Model variability.** A free model may phrase answers differently on each run or occasionally
  produce a malformed tool call (the agent retries these). The real model was not covered by
  automated evaluations.
- **Catalog gaps.** The manual mentions 300+ instruments and wind/orchestral categories, but the
  data has 65 products and no products in three categories. The agent trusts the data.

## Use of AI coding assistants


AI assistants were used during development:

- **Claude** acted as a technical mentor: discussing the architecture, reviewing code and
  data findings, and drafting tests, documentation and this README.
- **Github COPILOT CLI** was used to implement and apply parts of the code.
- All generated code was read, run and tested before being committed. Decisions listed in this
  document were reviewed and chosen by the author.

## Project structure

```
src/emporio_agent/
  main.py          command-line chat
  agent.py         tool-calling loop, retries, history trimming
  prompts.py       system prompt (persona, scope, privacy)
  llm.py, config.py, text.py
  data/            loader.py (read + audit CSVs), repository.py (catalog queries)
  rules/           pricing.py, returns.py, shipping.py   (business rules)
  retrieval/       chunker.py, policy_search.py          (policy manual search)
  tools/           registry.py, products.py, orders.py, checkout.py, policies.py
tests/             unit and agent-loop tests
scripts/           run_examples.py
examples/          generated example conversations
docs/              data_quality.md
data/raw/          case data (CSVs and policy PDF)
```
