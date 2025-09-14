import ast
import operator
import statistics
from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from api.ext.moneyformat import truncate

if TYPE_CHECKING:
    from api.services.exchange_rate import ExchangeRateService

NO_RATE = Decimal("NaN")
MAX_DEPTH = 8


class ExchangePair:
    def __init__(self, left: str, right: str | None = None) -> None:
        if right is None:
            parts = left.split("_")
            if len(parts) != 2:
                raise Exception(f"Invalid pair: {left}")
            self.left = parts[0]
            self.right = parts[1]
        else:
            self.left = left
            self.right = right

    def __str__(self) -> str:
        return f"{self.left}_{self.right}"

    def __repr__(self) -> str:
        return f"ExchangePair '{self.left}_{self.right}'"

    def inverse(self) -> "ExchangePair":
        return ExchangePair(f"{self.right}_{self.left}")


class ExchangeTransformer(ast.NodeTransformer):
    def __init__(
        self,
        expressions: dict[str, ast.expr],
        *,
        left: str,
        right: str,
        depth: int = 0,
        rates: dict[str, dict[str, Decimal]] | None = None,
    ) -> None:
        self.expressions = expressions
        self.left = left
        self.right = right
        self.depth = depth
        self.functions: dict[str, Callable[..., Decimal]] = {
            "mean": self.calc_mean,
            "median": self.calc_median,
            "normalize": self.normalize,
        }
        self.binary_operators: dict[type[ast.operator], Callable[[Decimal, Decimal], Decimal]] = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
        }
        self.unary_operators: dict[type[ast.unaryop], Callable[[Decimal], Decimal]] = {
            ast.UAdd: operator.pos,
            ast.USub: operator.neg,
        }
        self.rates = rates or defaultdict(dict)
        self.exchanges: set[str] = set()

    def calc_mean(self, *args: Any) -> Decimal:
        num_args = [arg for arg in args if not isinstance(arg, str)]
        if not num_args:
            return NO_RATE
        return sum(num_args) / len(num_args)

    def calc_median(self, *args: Any) -> Decimal:
        num_args = [arg for arg in args if not isinstance(arg, str)]
        if not num_args:
            return NO_RATE
        return statistics.median(num_args)

    def normalize(self, arg: Decimal, decimals: int) -> Decimal:
        # TODO: return back if needed
        # if isinstance(arg, str):
        #     return arg
        return truncate(arg, decimals)

    def find_candidate(self, name: str) -> dict[str, Any] | Decimal:
        pair = ExchangePair(name)
        inversed = pair.inverse()
        candidates: list[dict[str, Any]] = []
        for candidate in [
            {"pair": pair, "priority": 0, "inverse": False},
            {"pair": inversed, "priority": 1, "inverse": True},
            {"pair": ExchangePair(pair.left, "X"), "priority": 2, "inverse": False},
            {"pair": ExchangePair("X", pair.right), "priority": 2, "inverse": False},
            {"pair": ExchangePair(inversed.left, "X"), "priority": 3, "inverse": True},
            {"pair": ExchangePair("X", inversed.right), "priority": 3, "inverse": True},
            {"pair": ExchangePair("X", "X"), "priority": 4, "inverse": False},
        ]:
            if str(candidate["pair"]) in self.expressions:
                candidates.append({**candidate, "expression": self.expressions[str(candidate["pair"])]})
        if not candidates:
            return NO_RATE
        candidates.sort(key=lambda x: x["priority"])
        if candidates[0]["inverse"]:
            candidates[0]["expression"] = ast.BinOp(
                left=ast.Constant(value=1), op=ast.Div(), right=candidates[0]["expression"]
            )
        return candidates[0]

    def visit_Name(self, node: ast.Name) -> Decimal:
        pair = ExchangePair(node.id)
        left = self.left if pair.left == "X" else pair.left
        right = self.right if pair.right == "X" else pair.right
        replaced_pair = ExchangePair(left, right)
        candidate = self.find_candidate(str(replaced_pair))
        if candidate == NO_RATE:
            return NO_RATE
        if self.depth == MAX_DEPTH:
            return NO_RATE
        candidate = cast(dict[str, Any], candidate)
        transformer = ExchangeTransformer(self.expressions, left=left, right=right, depth=self.depth + 1, rates=self.rates)
        result = transformer.visit(candidate["expression"])
        self.exchanges.update(transformer.exchanges)
        return result

    def visit_Call(self, node: ast.Call) -> Decimal:  # TODO: re-check
        ast_args = node.args
        if len(ast_args) == 1 and isinstance(ast_args[0], ast.Name):
            name = ast_args[0].id
            pair = ExchangePair(name)
            if pair.left == "X":
                pair.left = self.left
            if pair.right == "X":
                pair.right = self.right
            args = [str(pair)]
        else:
            args = [self.visit(arg) for arg in ast_args]
        node_func = cast(ast.Name, node.func)
        if node_func.id in self.functions:
            return self.functions[node_func.id](*args)
        self.exchanges.add(node_func.id)
        if len(args) == 1:
            pair = ExchangePair(args[0])
            if pair.left == pair.right:
                return Decimal(1)
        return self.rates[node_func.id].get(*args, NO_RATE)  # type: ignore  # TODO: how??

    def visit_BinOp(self, node: ast.BinOp) -> Decimal | str:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(left, str):
            return left
        if isinstance(right, str):
            return right
        return self.binary_operators[type(node.op)](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Decimal | str:
        operand = self.visit(node.operand)
        if isinstance(operand, str):
            return operand
        return self.unary_operators[type(node.op)](operand)

    def visit_Constant(self, node: ast.Constant) -> Decimal:
        return Decimal(str(node.value))


class ExpressionParser(ast.NodeTransformer):
    def __init__(self, source: str) -> None:
        self.expressions: dict[str, ast.expr] = {}
        self.tree = ast.parse(source, "<string>", "exec")
        self.visit(self.tree)

    def visit_Assign(self, node: ast.Assign) -> str:
        self.expressions[cast(ast.Name, node.targets[0]).id] = node.value
        return ""


# TODO: maybe move to e.g. exchange rates manager?
async def calculate_rules(
    exchange_rate_service: "ExchangeRateService", s: str, left: str, right: str
) -> tuple[Decimal, ExchangePair | None]:
    if not s:
        s = get_default_rules()
    s = exchange_rate_service.default_rules + "\n" + s  # append coin-specific rules
    parser = ExpressionParser(s)
    transformer = ExchangeTransformer(parser.expressions, left=left, right=right)
    candidate = transformer.find_candidate(f"{left}_{right}")
    if candidate == NO_RATE:
        return NO_RATE, None
    candidate = cast(dict[str, Any], candidate)
    transformer.visit(candidate["expression"])
    for exchange in transformer.exchanges:
        transformer.rates[exchange] = await exchange_rate_service.get_rate(exchange)
    ret = transformer.visit(candidate["expression"])
    return ret, candidate["pair"]


def get_default_rules() -> str:
    return "X_X=coingecko(X_X)"
