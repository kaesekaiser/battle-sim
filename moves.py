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


types = normal, fire, water, electric, grass, ice, fighting, poison, ground, flying, psychic, bug, rock, ghost, \
    dragon, dark, steel, fairy = "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", \
    "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
categories = physical, special, status = "Physical", "Special", "Status"


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

        self.attributes = kwargs

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
    def from_json(js: dict):
        return Move(**js)

    def json(self):
        return {"name": self.name, "type": self.type, "category": self.category, "pp": self.pp,
                "remaining_pp": self.remaining_pp, "power": self.power, "accuracy": self.accuracy,
                "priority": self.priority, **self.attributes}

    def __copy__(self):
        return Move.from_json(self.json())

    @property
    def accuracy_str(self):
        return f"{self.accuracy}%" if self.accuracy else "—"

    @property
    def power_str(self):
        return self.power if self.power else "—"


moves = {g: Move.from_json(j) for g, j in json.load(open("data/moves.json", "r")).items()}


def find_move(s: str) -> Move:
    try:
        return [copy(j) for g, j in moves.items() if fix(g) == fix(s)][0]
    except IndexError:
        raise ValueError(f"Invalid move: {s}")
