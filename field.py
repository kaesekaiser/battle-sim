from teams import *
from random import random, randrange


def raw_damage(attacker_level: int, attacking_stat: int, defending_stat: int, power: int):
    return round((2 * attacker_level / 5 + 2) * power * attacking_stat / defending_stat / 50 + 2)


def crit_chance(crit_stages: int = 0):
    return 1 / (24 if crit_stages <= 0 else 8 if crit_stages == 1 else 2 if crit_stages == 2 else 1)


class Field:
    def __init__(self, size: int = 1):
        if not (1 <= size <= 3):
            raise ValueError("Size must be between 1 and 3.")
        self.size = size

        self.positions = {}  # position (int): mon (FieldMon | None)

    def deploy_mon(self, mon: FieldMon | None, position: int):
        self.positions[position] = mon

    def at(self, position: int) -> FieldMon | None:
        return self.positions.get(position)

    @property
    def fielded_mons(self) -> list[FieldMon]:
        return [g for g in self.positions.values() if g is not None]

    @property
    def living_mons(self) -> list[FieldMon]:
        return [g for g in self.fielded_mons if g]

    def targets(self, from_position: int, target: str) -> list[int]:
        if target == "user" or target == "all":
            return [from_position]
        if self.size == 1:
            return [int(not from_position)]

        possible_targets = [g.position for g in self.living_mons]
        args = target.split("-")
        if "adj" in args:
            possible_targets = [g for g in possible_targets if -1 <= g % self.size - from_position % self.size <= 1]
        if "foe" in args:
            possible_targets = [g for g in possible_targets if g // self.size != from_position // self.size]
        if "ally" in args:
            possible_targets = [g for g in possible_targets if g // self.size == from_position // self.size]
        if from_position in possible_targets and "user" not in args:
            possible_targets.remove(from_position)

        return possible_targets

    def diagram(self, select: list[int] = (), from_side: int = 0, include_hp: bool = True):
        ret = [
            f"{'->' if n in select else '  '}[{n + 1}] "
            f"{'---' if not self.at(n) else self.at(n).species_and_form}"
            f"{'' if not self.at(n) or not include_hp else (' ' + self.at(n).hp_display())}"
            f"{'<-' if n in select else '  '}"
            for n in range(self.size * 2)
        ]
        ret = [ret[self.size:], ret[:self.size]]
        if from_side == 1:
            ret = [list(ret[1].__reversed__()), list(ret[0].__reversed__())]
        max_lengths = [max(len(ret[0][g]), len(ret[1][g])) for g in range(self.size)]
        return "\n".join(
            " ".join(j.ljust(max_lengths[n]) for n, j in enumerate(g)) for g in ret
        )

    def move_effectiveness(self, attacker: FieldMon, defender: FieldMon, move: Move) -> float:
        overwrites = {}
        return defender.type_effectiveness(move.type, overwrites)

    def damage_roll(self, attacker: FieldMon, defender: FieldMon, move: Move, **kwargs) -> dict[str]:
        multipliers = []
        if len(attacker.targets) > 1:
            multipliers.append(0.75)

        # other multipliers to be added:
        # 0.25 if second strike of parental bond
        # 1.5 or 0.5 depending on type + weather
        # 2 if target used glaive rush in previous turn
        # 0.5 if lowered by burn
        # 0.25 if it's a z-move that's been protected against
        # "other" multiplier (see https://bulbapedia.bulbagarden.net/wiki/Damage#Generation_V_onward)

        crit = move.get("always_crits", False)
        if kwargs.get("allow_crit", True) and not crit:
            if random() < crit_chance(move.get("crit_rate_modifier", 0)):
                crit = True
        if crit:
            multipliers.append(1.5)

        multipliers.append(kwargs["force_random"] if kwargs.get("force_random") else (randrange(85, 101) / 100))

        type_eff = self.move_effectiveness(attacker, defender, move)
        multipliers.append(type_eff)

        stab = 1
        if attacker.terastallized:
            if move.type == attacker.tera_type:
                stab += 0.5
            if move.type in attacker.types:
                stab += 0.5
        else:
            if move.type in attacker.types:
                stab += 0.5
        multipliers.append(stab)

        attack_stat = self.get_stat(defender if move["use_target_offense"] else attacker, move.attacking_stat)
        defense_stat = self.get_stat(defender, move.defending_stat)

        damage = max(1, round(raw_damage(attacker.level, attack_stat, defense_stat, move.power) * product(multipliers)))
        return {"damage": damage, "effectiveness": type_eff, "crit": crit}

    def get_stat(self, mon: FieldMon, stat: str) -> int:
        return mon.staged_stat(stat, 3 if stat in ("Eva", "Acc") else 2)
