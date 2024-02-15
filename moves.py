import re
import json
from math import floor
from copy import copy


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
        return {"name": self.name, "type": self.type, "category": self.category, "pp": self.pp,
                "remaining_pp": self.remaining_pp, "power": self.power, "accuracy": self.accuracy,
                "priority": self.priority, **self.attributes}

    @property
    def accuracy_str(self):
        return f"{self.accuracy}%" if self.accuracy else "—"

    @property
    def power_str(self):
        return self.power if self.power else "—"

    def inline_display(self):
        return f"[{self.name.ljust(16)} {str(self.remaining_pp).rjust(2, '0')}/{str(self.pp).rjust(2, '0')}]"

    def deduct_pp(self, deduction: int = 1):
        self.remaining_pp = max(0, self.remaining_pp - deduction)


all_moves = {g: Move.from_json(j) for g, j in json.load(open("data/moves.json", "r")).items()}
fixed_moves = {fix(g): g for g in all_moves}


def find_move(s: str) -> Move:
    try:
        return copy(fixed_moves[fix(s)])
    except KeyError:
        raise ValueError(f"Invalid move: {s}")
