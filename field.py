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
terrains = electric_terrain, grassy_terrain, misty_terrain, psychic_terrain = "electric", "grassy", "misty", "psychic"


weather_spawning_abilities = {
    "Drizzle": rain,
    "Drought": sun,
    "Sand Stream": sandstorm,
    "Snow Warning": snow
}
terrain_spawning_abilities = {
    "Electric Surge": electric_terrain,
    "Grassy Surge": grassy_terrain,
    "Misty Surge": misty_terrain,
    "Psychic Surge": psychic_terrain
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


def plural(s: str, n: int | float, plural_form: str = "{}s"):
    return s if n == 1 else plural_form.format(s)


class Fieldside:
    def __init__(self):
        self.reflect = False
        self.reflect_timer = 0
        self.light_screen = False
        self.light_screen_timer = 0
        self.aurora_veil = False
        self.aurora_veil_timer = 0

    def summary(self) -> list[str]:
        ret = []
        if self.reflect:
            ret.append(f"Reflect: {self.reflect_timer} {plural('turn', self.reflect_timer)}")
        if self.light_screen:
            ret.append(f"Light Screen: {self.light_screen_timer} {plural('turn', self.light_screen_timer)}")
        if self.aurora_veil:
            ret.append(f"Aurora Veil: {self.aurora_veil_timer} {plural('turn', self.aurora_veil_timer)}")
        return ret

    def pretty_summary(self) -> list[str]:
        if len(self.summary()) > 1:
            end = len(self.summary()) - 1
            return [f"{'└' if n == end else '┬' if n == 0 else '├'} {g}" for n, g in enumerate(self.summary())]
        else:
            return [f"─ {g}" for g in self.summary()]

    def set_reflect(self, set_to: bool = True, turns: int = 5):
        self.reflect = set_to
        self.reflect_timer = turns if set_to else 0

    def set_light_screen(self, set_to: bool = True, turns: int = 5):
        self.light_screen = set_to
        self.light_screen_timer = turns if set_to else 0

    def set_aurora_veil(self, set_to: bool = True, turns: int = 5):
        self.aurora_veil = set_to
        self.aurora_veil_timer = turns if set_to else 0


class Field:
    def __init__(self, size: int = 1):
        if not (1 <= size <= 3):
            raise ValueError("Size must be between 1 and 3.")
        self.size = size

        self.sides = Fieldside(), Fieldside()
        self.positions = {}  # position (int): mon (FieldMon | None)
        self.weather = None
        self.weather_timer = 0
        self.terrain = None
        self.terrain_timer = 0

    def deploy_mon(self, mon: FieldMon | None, position: int):
        self.positions[position] = mon

    def at(self, position: int) -> FieldMon | None:
        return self.positions.get(position)

    def side(self, team_id: int | FieldMon) -> Fieldside:
        if isinstance(team_id, FieldMon):
            return self.sides[team_id.team_id]
        else:
            return self.sides[team_id]

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
            return [from_position if "ally" in target else int(not from_position)]

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

    def summary(self):
        ret = []
        if self.weather:
            ret.append(f"{weather_names[self.weather]}: {self.weather_timer} {plural('turn', self.weather_timer)}")
        if self.terrain:
            ret.append(f"{self.terrain.title()} Terrain: {self.terrain_timer} {plural('turn', self.terrain_timer)}")
        return "\n".join(ret)

    def diagram(self, select: list[int] = (), from_side: int = 0, include_hp: bool = True):
        positions = [list(range(self.size, self.size * 2)), list(range(self.size))]
        if from_side == 1:
            positions = [list(positions[1].__reversed__()), list(positions[0].__reversed__())]
        ret = [  # rows
            [  # cells
                [  # lines
                    f"{'->' if n in select else '  '}[{n + 1}] "
                    f"{'---' if not self.at(n) else self.at(n).verbose_name}"
                    f"{'' if not self.at(n) or not include_hp else (' [' + self.at(n).hp_display() + ']')}"
                    f"{'<-' if n in select else '  '}",
                    *join_and_wrap((self.at(n).battle_info() if self.at(n) else []), "; ", 24, "   └  ")
                ] for n in row
            ] for row in positions
        ]
        if any(g.summary() for g in self.sides):
            ret[0].append(self.side(1 - from_side).pretty_summary())
            ret[1].append(self.side(from_side).pretty_summary())
        max_heights = [max(len(g) for g in row) for row in ret]  # align rows across cells by padding empty space
        ret = [[[*cell, *([""] * (max_heights[n] - len(cell)))] for cell in row] for n, row in enumerate(ret)]
        columns = [[g for row in ret for g in row[column]] for column in range(len(ret[0]))]
        max_lengths = [max(len(g) for g in column) for column in columns]  # align lines within columns
        return "\n".join(
            " ".join(cell[line].ljust(max_lengths[n]) for n, cell in enumerate(row)).rstrip()
            for row in ret for line in range(len(row[0]))
        )

    def ability_on_field(self, *abilities: str) -> bool:
        return any(g.has_ability(*abilities) for g in self.living_mons)

    def meets_conditional(self, user: FieldMon, conditional: dict[str]) -> bool:
        condition = conditional["condition"]
        if condition.get("weather") is not None and self.weather != condition["weather"]:
            return False
        if condition.get("user_in_terrain") is not None:
            if self.terrain != condition["user_in_terrain"] or not self.is_grounded(user):
                return False
        return True

    def apply_conditionals(self, user: FieldMon, move: Move) -> Move:
        overwrites = {}
        for conditional in move.conditionals:
            if self.meets_conditional(user, conditional):
                overwrites.update(conditional)
        return move.clone(overwrites)

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

        if not crit:
            if move.category == physical and (self.side(defender).reflect or self.side(defender).aurora_veil):
                multipliers.append(2/3 if self.size > 1 else 0.5)
            elif move.category == special and (self.side(defender).light_screen or self.side(defender).aurora_veil):
                multipliers.append(2/3 if self.size > 1 else 0.5)

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
            defender if move["use_target_offense"] else attacker, move.attacking_stat, ignore_negative_stages=crit
        )
        defense_stat = self.get_stat(
            defender, move.defending_stat, ignore_positive_stages=crit
        )

        damage = raw_damage(attacker.level, attack_stat, defense_stat, move.power)
        if not move["unmodified_damage"]:
            damage = max(1, round(damage * product(multipliers)))

        return {"damage": damage, "effectiveness": type_eff, "crit": crit}

    def get_stat(self, mon: FieldMon, stat: str, **kwargs) -> int:
        multipliers = []

        if stat == "Atk":
            if self.ability_on_field("Tablets of Ruin") and not mon.has_ability("Tablets of Ruin"):
                multipliers.append(0.75)

        if stat == "Def":
            if self.active_weather == snow and ice in mon.types:
                multipliers.append(1.5)
            if self.ability_on_field("Sword of Ruin") and not mon.has_ability("Sword of Ruin"):
                multipliers.append(0.75)

        if stat == "SpA":
            if self.ability_on_field("Vessel of Ruin") and not mon.has_ability("Vessel of Ruin"):
                multipliers.append(0.75)

        if stat == "SpD":
            if self.active_weather == sandstorm and rock in mon.types:
                multipliers.append(1.5)
            if self.ability_on_field("Beads of Ruin") and not mon.has_ability("Beads of Ruin"):
                multipliers.append(0.75)

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
        if self.terrain == misty_terrain and self.is_grounded(defender):
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
            if electric in defender.types:
                return False
        if condition in [mild_poison, bad_poison]:
            if poison in defender.types or steel in defender.types:
                return False
        if condition == sleep:
            if self.terrain == electric_terrain and self.is_grounded(defender):
                return False
        return True

    def is_grounded(self, mon: FieldMon):
        # ungrounded if: has Levitate, holding Air Balloon, under Magnet Rise or Telekinesis, in semi-invulnerable turn
        # re-grounded if: holding Iron Ball, under Ingrain or Smack Down or Thousand Arrows, Gravity in effect
        if flying in mon.types:
            return False
        return True

    def can_change_weather(self, weather: str | None):
        if weather is not None and self.weather == weather:
            return False
        return (self.weather not in [extreme_sun, heavy_rain, winds]) or (weather in [extreme_sun, heavy_rain, winds])

    def set_weather(self, weather: str | None, turns: int = 5):
        self.weather = weather
        self.weather_timer = turns if weather else 0

    def set_terrain(self, terrain: str | None, turns: int = 5):
        self.terrain = terrain
        self.terrain_timer = turns if terrain else 0

    def can_confuse(self, mon: FieldMon):
        if self.terrain == misty_terrain:
            return False
        return True
