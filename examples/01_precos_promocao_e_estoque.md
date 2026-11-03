# Prices, active vs. expired promotions, and an out-of-stock product

> Model: `openai/gpt-oss-120b` | Reference date: `2026-03-31` | Generated: 2026-11-03 20:31
> **What it shows:** Real-time catalog data. The Takamine GD20 has an INACTIVE promotion (must not be offered); the Ohana CK-20 has an ACTIVE 20% promotion (PIX does not stack); the Giannini GF-3D is out of stock (alternatives expected).

**Customer:** Quanto custa o violão Takamine GD20?

*Tools called: `get_product_details({"name": "Takamine GD20"})`*

**Agent:** Olá! O violão Takamine GD20 está disponível e custa R$ 2.199,00 à vista. No PIX o valor é R$ 2.089,05. Posso ajudar em mais alguma coisa? 😊

---

**Customer:** E o ukulele Ohana CK-20 Concert?

*Tools called: `get_product_details({"name": "Ohana CK-20 Concert"})`*

**Agent:** Oi! O ukulele Ohana CK-20 Concert está disponível e tem preço promocional: de R$ 549,00 por R$ 439,20 (20 % de desconto). Posso ajudar em mais alguma coisa?

---

**Customer:** Tem a Giannini GF-3D Dreadnought Sunburst?

*Tools called: `get_product_details({"name": "Giannini GF-3D Dreadnought Sunburst"})`*

**Agent:** Oi! O violão Giannini GF-3D Dreadnought Sunburst está fora de estoque no momento. Como alternativa, temos o Shelby SGD-195E Elétrico Aço Sunburst (R$ 799,00, PIX R$ 759,05), o Yamaha C70 Nylon Natural (R$ 849,00, PIX R$ 806,55) e o Tagima Dallas Tuner Aço Natural (R$ 749,00, PIX R$ 711,55), todos disponíveis. Posso ajudar em mais alguma coisa?

---
