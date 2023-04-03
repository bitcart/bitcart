import ast
import operator
import statistics
from collections import defaultdict
from decimal import Decimal

from api import settings
from api.ext.moneyformat import truncate

NO_RATE = Decimal("NaN")
MAX_DEPTH = 8


class ExchangePair:
    def __init__(self, left, right=None):
        if right is None:
            parts = left.split("_")
            if len(parts) != 2:
                raise Exception(f"Invalid pair: {left}")
            self.left = parts[0]
            self.right = parts[1]
        else:
            self.left = left
            self.right = right

    def __str__(self):
        return f"{self.left}_{self.right}"

    def __repr__(self):
        return f"ExchangePair '{self.left}_{self.right}'"

    def inverse(self):
        return ExchangePair(f"{self.right}_{self.left}")


class ExchangeTransformer(ast.NodeTransformer):
    def __init__(self, expressions, left=None, right=None, depth=0, rates=None):
        self.expressions = expressions
        self.left = left
        self.right = right
        self.depth = depth
        self.functions = {"mean": self.calc_mean, "median": self.calc_median, "normalize": self.normalize}
        self.operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.UAdd: operator.pos,
            ast.USub: operator.neg,
        }
        self.rates = rates or defaultdict(dict)
        self.exchanges = set()

    def calc_mean(self, *args):
        args = [arg for arg in args if not isinstance(arg, str)]
        if not args:
            return NO_RATE
        return sum(args) / len(args)

    def calc_median(self, *args):
        args = [arg for arg in args if not isinstance(arg, str)]
        if not args:
            return NO_RATE
        return statistics.median(args)

    def normalize(self, arg, decimals):
        if isinstance(arg, str):
            return arg
        return truncate(arg, decimals)

    def find_candidate(self, name):
        pair = ExchangePair(name)
        inversed = pair.inverse()
        candidates = []
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
            candidates[0]["expression"] = ast.BinOp(left=ast.Num(n=1), op=ast.Div(), right=candidates[0]["expression"])
        return candidates[0]

    def visit_Name(self, node):
        pair = ExchangePair(node.id)
        left = self.left if pair.left == "X" else pair.left
        right = self.right if pair.right == "X" else pair.right
        replaced_pair = ExchangePair(left, right)
        candidate = self.find_candidate(str(replaced_pair))
        if candidate == NO_RATE:
            return NO_RATE
        if self.depth == MAX_DEPTH:
            return NO_RATE
        transformer = ExchangeTransformer(self.expressions, left=left, right=right, depth=self.depth + 1, rates=self.rates)
        result = transformer.visit(candidate["expression"])
        self.exchanges.update(transformer.exchanges)
        return result

    def visit_Call(self, node):
        args = node.args
        if len(args) == 1 and isinstance(args[0], ast.Name):
            name = node.args[0].id
            pair = ExchangePair(name)
            if pair.left == "X":
                pair.left = self.left
            if pair.right == "X":
                pair.right = self.right
            args = [str(pair)]
        else:
            args = [self.visit(arg) for arg in args]
        if node.func.id in self.functions:
            return self.functions[node.func.id](*args)
        else:
            self.exchanges.add(node.func.id)
            if len(args) == 1:
                pair = ExchangePair(args[0])
                if pair.left == pair.right:
                    return Decimal(1)
            return self.rates[node.func.id].get(*args, NO_RATE)

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(left, str):
            return left
        if isinstance(right, str):
            return right
        return self.operators[type(node.op)](left, right)

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        if isinstance(operand, str):
            return operand
        return self.operators[type(node.op)](operand)

    def visit_Constant(self, node):
        return Decimal(str(node.value))


class ExpressionParser(ast.NodeTransformer):
    def __init__(self, source):
        self.expressions = {}
        self.tree = ast.parse(source, "<string>", "exec")
        self.visit(self.tree)

    def visit_Assign(self, node):
        self.expressions[node.targets[0].id] = node.value
        return ""


async def calculate_rules(s, left, right):
    if not s:
        s = get_default_rules()
    s = settings.settings.exchange_rates.default_rules + "\n" + s  # append coin-specific rules
    parser = ExpressionParser(s)
    transformer = ExchangeTransformer(parser.expressions, left=left, right=right)
    candidate = transformer.find_candidate(f"{left}_{right}")
    if candidate == NO_RATE:
        return NO_RATE, None
    transformer.visit(candidate["expression"])
    for exchange in transformer.exchanges:
        transformer.rates[exchange] = await settings.settings.exchange_rates.get_rate(exchange)
    ret = transformer.visit(candidate["expression"])
    return ret, candidate["pair"]


def get_default_rules():
    return "X_X=coingecko(X_X)"
