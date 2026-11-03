<a name="top"></a>

<p align="center">
  <a href="#english"><img src="https://img.shields.io/badge/Language-English-blue?style=for-the-badge" alt="English"></a>
  &nbsp;
  <a href="#portugues"><img src="https://img.shields.io/badge/Idioma-Portugu%C3%AAs%20(BR)-green?style=for-the-badge" alt="Português (BR)"></a>
</p>

---

<a name="english"></a>

# 🇬🇧 Data Quality Notes

[⬆ Back to top](#top) · [🇧🇷 Ir para Português](#portugues)

This document lists the problems we found in the case data and the manual, and **what the agent does about each one**.

**Main idea:** we do not silently "fix" the data. We detect each problem, write it down here, and handle it with an explicit business rule.

The list is produced by `python -m emporio_agent.data.loader` (function `audit()`).

## 1. Assumptions

| # | Assumption | Why |
|---|---|---|
| A1 | "Today" is `AS_OF_DATE=2026-03-31` (configurable in `.env`) | The newest order is from 2026-03-22, so this date fits the data |
| A2 | `estimated_delivery` is used as the delivery date for delivered orders | There is no `delivered_at` column |
| A3 | The shipping region is taken from `customers.city` | There is no delivery address in the data |
| A4 | `total_brl` is the amount the customer paid | Prices may have changed after the purchase |
| A5 | All orders are treated as **online** orders | There is no sales channel column, and the orders have tracking codes and shipping |
| A6 | "Metropolitan area" = only the city of Campo Grande | The manual does not define it |

## 2. Problems in the data

| # | Problem | Example | What the agent does |
|---|---|---|---|
| D1 | Product is `active` but stock is 0 | Product 96 | Treated as **not available**. Rule: available = `active` **and** `stock > 0`. Suggests similar products |
| D2 | Product is `coming_soon` but has stock | Product 130 (stock 2) | Does not sell it. Says it is "coming soon" |
| D3 | Product is `discontinued` but has stock | Product 136 (stock 13) | Says it is no longer in the catalog. Suggests similar models |
| D4 | Orders contain a `coming_soon` product | Orders 3 and 14 (product 130) | Shows the order as it is. Does not make promises about the product |
| D5 | Categories with no products | Categories 6, 7, 8 (wind and orchestral strings) | Says there are no items available now. Never invents products |
| D6 | Only 4 of 25 promotions are active | — | Only `is_active = 1` counts. Expired promotions are never offered |
| D7 | Some products have more than one promotion row | Products 93, 96, 99 | Uses the active row only. If none is active, uses the normal price |
| D8 | Two customers share one email | Customers 11 and 43 | Never finds a customer by email alone. Order lookup needs the **order number plus** email or phone |
| D9 | Order total is different from the sum of item prices | Order 3 (−48.00), order 20 (−88.00) | Uses `total_brl` as the paid value. Does not recalculate old orders |
| D10 | No `delivered_at` column | 7 delivered orders | See assumption A2 |
| D11 | 12 of 20 orders have no estimated delivery date | Orders 9 to 20 (confirmed, pending, cancelled) | Shows no delivery date and never invents one. The order is not marked as late |
## 3. Problems in the policy manual

| # | Problem | What the agent does |
|---|---|---|
| M1 | Two phone numbers: (67) 3341-4444 (store) and (67) 3321-4500 (WhatsApp) | Uses each one for its own channel |
| M2 | Two email spellings: one with an accent (`empóriodamusica`) and one without | Uses the version without accent (valid email format) |
| M3 | The manual says "300+ instruments", but the data has 65 products | Trusts the data. Does not repeat the "300+" claim |
| M4 | The manual says the store sells winds and orchestral strings, but no such product exists | Same as D5 |
| M5 | The payment table is short (12x, min. R$ 100). Section 3.1 has detailed rules | Uses section 3.1 (3x no minimum, 4–6x min. R$ 80, 7–12x min. R$ 100) |
| M6 | PIX gives 5% off, but **not** on promotional prices | Done in code. Never stacks both discounts |
| M7 | The 7-day return right is **only for online purchases**, counted from receipt | The agent checks the order date and the delivery date before answering |
| M8 | Defect exchange is 30 days from the **purchase**. Legal warranty is 90 days from **receipt** | Code checks both and explains the difference |
| M9 | Free shipping and the R$ 35 fee are only for the Campo Grande metro area | Uses the customer city. Other cities: Correios or Jadlog, quote by ZIP code |
| M10 | The manual is marked "internal use only" | The agent answers with what the customer needs. It does not paste the manual |

## 4. Design decisions

- **Business rules live in Python code, not in the LLM.** Prices, discounts, installments, return deadlines and shipping are calculated by tested functions. The LLM chooses the tool and writes the answer.
- **The agent never states price, stock or deadline without calling a tool.** This follows the manual (section 7.1).
- **Privacy:** order information is only shown after the customer is verified (order number plus email or phone).

[⬆ Back to top](#top)

---

<a name="portugues"></a>

# 🇧🇷 Notas de Qualidade dos Dados

[⬆ Voltar ao topo](#top) · [🇬🇧 Go to English](#english)

Este documento lista os problemas encontrados nos dados do case e no manual, e **o que o agente faz em cada caso**.

**Ideia principal:** nós não "consertamos" os dados em silêncio. Detectamos cada problema, registramos aqui e tratamos com uma regra de negócio explícita.

A lista é gerada por `python -m emporio_agent.data.loader` (função `audit()`).

## 1. Suposições

| # | Suposição | Motivo |
|---|---|---|
| A1 | "Hoje" é `AS_OF_DATE=2026-03-31` (configurável no `.env`) | O pedido mais recente é de 22/03/2026, então essa data combina com os dados |
| A2 | `estimated_delivery` é usada como data de entrega dos pedidos entregues | Não existe a coluna `delivered_at` |
| A3 | A região de frete vem de `customers.city` | Não há endereço de entrega nos dados |
| A4 | `total_brl` é o valor que o cliente pagou | Os preços podem ter mudado depois da compra |
| A5 | Todos os pedidos são tratados como **online** | Não há coluna de canal de venda, e os pedidos têm código de rastreio e frete |
| A6 | "Região metropolitana" = somente a cidade de Campo Grande | O manual não define o termo |
## 2. Problemas nos dados

| # | Problema | Exemplo | O que o agente faz |
|---|---|---|---|
| D1 | Produto `active` com estoque 0 | Produto 96 | Tratado como **indisponível**. Regra: disponível = `active` **e** `stock > 0`. Sugere produtos parecidos |
| D2 | Produto `coming_soon` com estoque | Produto 130 (estoque 2) | Não vende. Informa que é "em breve" |
| D3 | Produto `discontinued` com estoque | Produto 136 (estoque 13) | Informa que saiu do catálogo. Sugere modelos parecidos |
| D4 | Pedidos com produto `coming_soon` | Pedidos 3 e 14 (produto 130) | Mostra o pedido como está. Não faz promessas sobre o produto |
| D5 | Categorias sem produtos | Categorias 6, 7, 8 (sopros e cordas orquestrais) | Diz que não há itens disponíveis agora. Nunca inventa produtos |
| D6 | Só 4 de 25 promoções estão ativas | — | Só vale `is_active = 1`. Promoções vencidas nunca são oferecidas |
| D7 | Alguns produtos têm mais de uma linha de promoção | Produtos 93, 96, 99 | Usa apenas a linha ativa. Se nenhuma estiver ativa, usa o preço normal |
| D8 | Dois clientes com o mesmo e-mail | Clientes 11 e 43 | Nunca identifica o cliente só pelo e-mail. A consulta de pedido exige **número do pedido mais** e-mail ou telefone |
| D9 | Total do pedido diferente da soma dos itens | Pedido 3 (−48,00), pedido 20 (−88,00) | Usa `total_brl` como valor pago. Não recalcula pedidos antigos |
| D10 | Sem coluna `delivered_at` | 7 pedidos entregues | Ver suposição A2 |
| D11 | 12 dos 20 pedidos não têm previsão de entrega | Pedidos 9 a 20 (confirmados, pendentes, cancelados) | Não mostra data de entrega e nunca inventa uma. O pedido não é marcado como atrasado 
## 3. Problemas no manual de políticas

| # | Problema | O que o agente faz |
|---|---|---|
| M1 | Dois telefones: (67) 3341-4444 (loja) e (67) 3321-4500 (WhatsApp) | Usa cada um no seu canal |
| M2 | Duas grafias de e-mail: uma com acento (`empóriodamusica`) e outra sem | Usa a versão sem acento (formato válido de e-mail) |
| M3 | O manual diz "mais de 300 instrumentos", mas os dados têm 65 produtos | Confia nos dados. Não repete o "300+" |
| M4 | O manual diz que a loja vende sopros e cordas orquestrais, mas não existe produto assim | Igual a D5 |
| M5 | A tabela de pagamento é curta (12x, mín. R$ 100). A seção 3.1 tem regras detalhadas | Usa a seção 3.1 (3x sem mínimo, 4–6x mín. R$ 80, 7–12x mín. R$ 100) |
| M6 | PIX dá 5% de desconto, mas **não** sobre preço promocional | Feito no código. Nunca soma os dois descontos |
| M7 | O direito de arrependimento de 7 dias vale **só para compra online**, contado a partir do recebimento | O agente confere a data do pedido e da entrega antes de responder |
| M8 | Troca por defeito: 30 dias a partir da **compra**. Garantia legal: 90 dias a partir do **recebimento** | O código verifica os dois e explica a diferença |
| M9 | Frete grátis e taxa de R$ 35 valem só para a região metropolitana de Campo Grande | Usa a cidade do cliente. Outras cidades: Correios ou Jadlog, cotação por CEP |
| M10 | O manual é marcado como "uso restrito da equipe" | O agente responde com o que o cliente precisa. Não cola o manual |

## 4. Decisões de projeto

- **As regras de negócio ficam em código Python, não no LLM.** Preço, desconto, parcelamento, prazo de devolução e frete são calculados por funções testadas. O LLM escolhe a ferramenta e escreve a resposta.
- **O agente nunca informa preço, estoque ou prazo sem consultar uma ferramenta.** Isso segue o manual (seção 7.1).
- **Privacidade:** dados de pedido só são mostrados depois de verificar o cliente (número do pedido mais e-mail ou telefone).

[⬆ Voltar ao topo](#top)