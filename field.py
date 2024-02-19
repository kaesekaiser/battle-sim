from teams import *


weather_conditions = rain, heavy_rain, sandstorm, snow, sun, extreme_sun, winds = \
    "rain", "heavy_rain", "sandstorm", "snow", "sun", "extreme_sun", "winds"
weather_names = {
    rain: "Rain",
    heavy_rain: "Heavy rain",
    sandstorm: "Sandstorm",
    snow: "Snow",
    sun: "Harsh sunlight",
    extreme_sun: "Extremely harsh sunlight",
    winds: "Strong winds"
}


def raw_damage(attacker_level: int, attacking_stat: int, defending_stat: int, power: int):
    return round((2 * attacker_level / 5 + 2) * power * attacking_stat / defending_stat / 50 + 2)


def crit_chance(crit_stages: int = 0):
    return 1 / (24 if crit_stages <= 0 else 8 if crit_stages == 1 else 2 if crit_stages == 2 else 1)


def join_and_wrap(ls: list[str], joiner: str, line_width: int, indented_prefix: str = "") -> list[str]:
    if not ls:
        return []
    ret = []
    line = ls[0]
    for s in ls[1:]:
        if len(line + joiner + s + joiner.rstrip()) <= line_width:
            line += joiner + s
        else:
            ret.append(line + joiner.rstrip())
            line = s
    ret.append(line.ljust(line_width))
    if indented_prefix and ret:
        ret[0] = indented_prefix + ret[0]
        ret[1:] = [(" " * len(indented_prefix)) + g for g in ret[1:]]
    return ret


class Field:
    def __init__(self, size: int = 1):
        if not (1 <= size <= 3):
            raise ValueError("Size must be between 1 and 3.")
        self.size = size

        self.positions = {}  # position (int): mon (FieldMon | None)
        self.weather = None
        self.weather_timer = 0

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

    @property
    def active_weather(self):
        return self.weather  # needs to be dynamic to account for Cloud Nine / Air Lock

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
        positions = [list(range(self.size, self.size * 2)), list(range(self.size))]
        if from_side == 1:
            positions = [list(positions[1].__reversed__()), list(positions[0].__reversed__())]
        ret = [  # rows
            [  # cells
                [  # lines
                    f"{'->' if n in select else '  '}[{n + 1}] "
                    f"{'---' if not self.at(n) else self.at(n).species_and_form}"
                    f"{'' if not self.at(n) or not include_hp else (' ' + self.at(n).hp_display())}"
                    f"{'<-' if n in select else '  '}",
                    *join_and_wrap(self.at(n).battle_info(), "; ", 24, "   └  ")
                ] for n in row
            ] for row in positions
        ]
        max_heights = [max(len(g) for g in row) for row in ret]  # align rows across cells by padding empty space
        ret = [[[*cell, *([""] * (max_heights[n] - len(cell)))] for cell in row] for n, row in enumerate(ret)]
        columns = [[g for row in ret for g in row[column]] for column in range(self.size)]
        max_lengths = [max(len(g) for g in column) for column in columns]  # align lines within columns
        return "\n".join(
            " ".join(cell[line].ljust(max_lengths[n]) for n, cell in enumerate(row))
            for row in ret for line in range(len(row[0]))
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
        # 2 if target used glaive rush in previous turn
        # 0.25 if it's a z-move that's been protected against
        # "other" multiplier (see https://bulbapedia.bulbagarden.net/wiki/Damage#Generation_V_onward)

        if self.active_weather in [sun, extreme_sun]:
            if move.type == fire or move["sun_boosted"]:
                multipliers.append(1.5)
            elif move.type == water:
                multipliers.append(0.5)
        elif self.active_weather in [rain, heavy_rain]:
            if move.type == water or move["rain_boosted"]:
                multipliers.append(1.5)
            elif move.type == fire:
                multipliers.append(0.5)

        if attacker.status_condition == burn and move.category == physical:
            multipliers.append(0.5)

        crit = move.get("always_crits", False)
        if kwargs.get("allow_crit", True) and not crit:
            if random.random() < crit_chance(move.get("crit_rate_modifier", 0)):
                crit = True
        if crit:
            multipliers.append(1.5)

        multipliers.append(kwargs["force_random"] if kwargs.get("force_random") else (random.randrange(85, 101) / 100))

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

        attack_stat = self.get_stat(
            defender if move["use_target_offense"] else attacker, move.attacking_stat, ignore_negative_stages=True
        )
        defense_stat = self.get_stat(defender, move.defending_stat, ignore_positive_stages=True)

        damage = max(1, round(raw_damage(attacker.level, attack_stat, defense_stat, move.power) * product(multipliers)))
        return {"damage": damage, "effectiveness": type_eff, "crit": crit}

    def get_stat(self, mon: FieldMon, stat: str, **kwargs) -> int:
        multipliers = []

        if stat == "Def":
            if self.active_weather == snow and ice in mon.types:
                multipliers.append(1.5)

        if stat == "SpD":
            if self.active_weather == sandstorm and rock in mon.types:
                multipliers.append(1.5)

        if stat == "Spe":
            if mon.status_condition == paralysis:
                multipliers.append(0.5)

        if kwargs.get("ignore_stages") or (kwargs.get("ignore_positive_stages") and mon.stat_stages[stat] > 0) or \
                (kwargs.get("ignore_negative_stages") and mon.stat_stages[stat] < 0):
            baseline = mon.stats.get(stat, 1)
        else:
            baseline = mon.staged_stat(stat, 3 if stat in ("Eva", "Acc") else 2)

        return max(1, round(baseline * product(multipliers)))

    def can_apply_status(self, attacker: FieldMon, defender: FieldMon, condition: str) -> bool:
        if defender.status_condition is not None:
            return False
        if condition == burn:
            if fire in defender.types:
                return False
        if condition == freeze:
            if ice in defender.types:
                return False
            if self.active_weather in [sun, extreme_sun]:
                return False
        if condition == paralysis:
            print("hi!")
            if electric in defender.types:
                return False
        if condition == mild_poison:
            if poison in defender.types or steel in defender.types:
                return False
        return True

    def can_change_weather(self, weather: str | None):
        if weather is not None and self.weather == weather:
            return False
        return (self.weather not in [extreme_sun, heavy_rain, winds]) or (weather in [extreme_sun, heavy_rain, winds])

    def set_weather(self, weather: str | None, turns: int = 5):
        self.weather = weather
        self.weather_timer = turns if weather else 0
