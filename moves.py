import json
import re
import random
from copy import copy
from math import floor


def fix(s: str, joiner: str = "-"):
    return re.sub(
        f"{joiner}+", joiner, re.sub(
            f"[^a-z0-9{joiner}]+", "", re.sub(
                r"\s+", joiner, s.lower().replace("é", "e")
            )
        )
    )


def load_type_chart(path: str = "data/types.json") -> dict[str | None, dict[str, float]]:
    return json.load(open(path))


types = normal, fire, water, electric, grass, ice, fighting, poison, ground, flying, psychic, bug, rock, ghost, \
    dragon, dark, steel, fairy = "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", \
    "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
categories = physical, special, status = "Physical", "Special", "Status"
type_effectiveness = load_type_chart()


class StatChange:
    def __init__(self, chance: int = 100, **stats: int):
        self.stats = stats
        self.chance = chance

    def __bool__(self):
        return bool(self.stats) and bool(self.chance)

    def __mul__(self, other: int | float):
        return StatChange.from_json(self.json() | {"chance": min(max(round(self.chance * other), 0), 100)})

    def __neg__(self):
        return self ** -1

    def __pow__(self, other: int | float, modulo: int | float = None):
        return StatChange.from_json(self.json() | {g: round(j * other) for g, j in self.stats.items()})

    def json(self):
        return self.stats | ({"chance": self.chance} if self.chance != 100 else {})

    @staticmethod
    def from_json(js: dict):
        return StatChange(**js)

    def items(self):
        return self.stats.items()


class StatusCondition:
    def __init__(self, condition: str = None, multi: list[str] = (), chance: int = 100):
        self.multi = multi
        if multi:
            self.condition = random.choice(self.multi)
        else:
            self.condition = condition
        self.chance = chance

    def __bool__(self):
        return bool(self.condition) and bool(self.chance)

    def json(self):
        return ({"multi": self.multi} if self.multi else {"condition": self.condition}) | \
            ({"chance": self.chance} if self.chance else {})

    @staticmethod
    def from_json(js: dict):
        return StatusCondition(**js)

    def randomize(self):
        if self.multi:
            self.condition = random.choice(self.multi)


class Move:
    def __init__(self, name: str, type: str, category: str, pp: int, power: int | str, accuracy: int, **kwargs):
        self.name = name
        self.type = type
        self.category = category
        self.pp = pp
        self.remaining_pp = kwargs.pop("remaining_pp", -1)  # set to -1 if not needed (e.g. during teambuilding)
        self.power = power
        self.accuracy = accuracy
        self.priority = kwargs.pop("priority", 0)
        self.target = kwargs.pop("target", "any-adj")

        self.user_stat_changes = StatChange.from_json(kwargs["user_stat_changes"]) \
            if kwargs.get("user_stat_changes") else None
        self.target_stat_changes = StatChange.from_json(kwargs["target_stat_changes"]) \
            if kwargs.get("target_stat_changes") else None
        self.status_condition = StatusCondition.from_json(kwargs["status"]) if kwargs.get("status") else None

        self.conditionals = kwargs.get("conditionals", [])

        self.attributes = kwargs

    def __copy__(self):
        return Move.from_json(self.json())

    def __getitem__(self, item):
        return self.attributes.get(item)

    def __setitem__(self, key, value):
        self.attributes[key] = value

    def __str__(self):
        ret = [
            f"Type: {self.type} / Category: {self.category}",
            f"Power: {self.power_str} / Accuracy: {self.accuracy_str} / "
            f"PP: {(str(self.remaining_pp) + '/') if self.remaining_pp != -1 else ''}{self.pp}"
        ]
        padding = max(2, max(len(g) for g in ret) - len(self.name) - 2)
        ret.insert(0, f"{'=' * (floor(padding / 2) + padding % 2)} {self.name} {'=' * floor(padding / 2)}")
        return "\n".join(ret)

    @staticmethod
    def from_pack(name: str, remaining_pp: int = None):
        if remaining_pp == -1:
            remaining_pp = all_moves[name].pp
        return Move.from_json(
            all_moves[name].json() | ({"remaining_pp": remaining_pp} if remaining_pp is not None else {})
        )

    def pack(self):
        return {"name": self.name} | ({"remaining_pp": self.remaining_pp} if self.remaining_pp != -1 else {})

    @staticmethod
    def from_json(js: dict):
        return Move(**js)

    def json(self):
        return {
            "name": self.name, "type": self.type, "category": self.category, "pp": self.pp,
            "remaining_pp": self.remaining_pp, "power": self.power, "accuracy": self.accuracy,
            "priority": self.priority, "target": self.target, **self.attributes
        }

    def clone(self, overwrites: dict[str] = ()):
        return Move.from_json(self.json() | {k: v for k, v in dict(overwrites).items() if k != "condition"})

    def get(self, attribute: str, default_value=None):
        return self.attributes.get(attribute, default_value)

    @property
    def accuracy_str(self):
        return f"{self.accuracy}%" if self.accuracy else "—"

    @property
    def power_str(self):
        return self.power if self.power else "—"

    @property
    def targs(self):
        return self.target.split("-")

    @property
    def is_single_target(self):
        return "any" in self.targs or self.target == "user"

    def inline_display(self):
        return f"[{self.name.ljust(16)} {str(self.remaining_pp).rjust(2, '0')}/{str(self.pp).rjust(2, '0')}]"

    def deduct_pp(self, deduction: int = 1):
        self.remaining_pp = max(0, self.remaining_pp - deduction)

    @property
    def attacking_stat(self) -> str:
        return self.get("attacking_stat", "Atk" if self.category == physical else "SpA")

    @property
    def defending_stat(self) -> str:
        return self.get("defending_stat", "Def" if self.category == physical else "SpD")

    @property
    def total_effects(self):
        return sum(1 if g else 0 for g in [
            self.target_stat_changes, self.user_stat_changes, self.status_condition, self["change_weather"]
        ])

    @property
    def thaws_target(self):
        return (self.type == fire and self.category != status) or self["thaws_target"]


all_moves = {g: Move.from_json(j) for g, j in json.load(open("data/moves.json", "r")).items()}
fixed_moves = {fix(g): g for g in all_moves}


def find_move(s: str) -> Move:
    try:
        return copy(fixed_moves[fix(s)])
    except KeyError:
        raise ValueError(f"Invalid move: {s}")
