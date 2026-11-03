"""Tool schemas shown to the LLM and a safe dispatcher."""
import inspect
import json

from .checkout import calculate_shipping, payment_options
from .orders import check_return, get_order_status
from .policies import search_policies
from .products import get_product_details, search_products

_FUNCTIONS = {f.__name__: f for f in (
    search_products, get_product_details, get_order_status, check_return,
    calculate_shipping, payment_options, search_policies,
)}

_VERIFY = {
    "order_id": {"type": "integer", "description": "Número do pedido"},
    "email": {"type": "string", "description": "E-mail do cliente (prova de identidade)"},
    "phone_last4": {"type": "string", "description": "4 últimos dígitos do telefone (alternativa ao e-mail)"},
}


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required or []},
    }}


TOOL_SCHEMAS = [
    _tool("search_products",
          "Busca produtos no catálogo com filtros. Use SEMPRE antes de citar preço, estoque ou promoção. "
          "Preços filtrados são o que o cliente paga.",
          {"category": {"type": "string", "description": "Ex.: violão, guitarra, ukulele, bateria"},
           "query": {"type": "string", "description": "Palavras-chave (marca, modelo, características)"},
           "min_price": {"type": "number"}, "max_price": {"type": "number"},
           "only_available": {"type": "boolean"},
           "sort": {"type": "string", "enum": ["price_asc", "price_desc"]},
           "limit": {"type": "integer"}}),
    _tool("get_product_details",
          "Detalhes de UM produto pelo nome (preço, promoção, PIX, parcelas, specs). "
          "Se indisponível, traz alternativas.",
          {"name": {"type": "string"}}, ["name"]),
    _tool("get_order_status",
          "Status de um pedido. EXIGE número do pedido e e-mail OU 4 últimos dígitos do telefone.",
          _VERIFY, ["order_id"]),
    _tool("check_return",
          "Verifica prazos de devolução/troca/garantia de um pedido. Mesma verificação de identidade.",
          _VERIFY, ["order_id"]),
    _tool("calculate_shipping",
          "Frete e prazo de entrega pela cidade do cliente e valor da compra.",
          {"city": {"type": "string"}, "order_total": {"type": "number"},
           "product_name": {"type": "string", "description": "Opcional: detecta frete especial"}},
          ["city", "order_total"]),
    _tool("payment_options",
          "Parcelamento permitido e se pode combinar formas de pagamento para um valor.",
          {"amount": {"type": "number"}}, ["amount"]),
    _tool("search_policies",
          "Consulta o manual da loja: horário, trocas, garantia, rastreamento, formas de pagamento, LGPD.",
          {"query": {"type": "string"}}, ["query"]),
]


def dispatch(name: str, arguments: str | dict | None) -> dict:
    """Run a tool call from the LLM. Never raises: errors come back as data."""
    func = _FUNCTIONS.get(name)
    if func is None:
        return {"error": f"unknown tool '{name}'"}
    try:
        args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() \
            else dict(arguments or {})
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"error": "arguments must be a valid JSON object"}
    if not isinstance(args, dict):
        return {"error": "arguments must be a valid JSON object"}
    try:
        inspect.signature(func).bind(**args)
    except TypeError as exc:                 # unknown/missing parameters invented by the model
        return {"error": f"invalid arguments: {exc}"}
    try:
        return func(**args)
    except Exception as exc:                 # keep the agent loop alive
        return {"error": f"tool failed: {type(exc).__name__}"}