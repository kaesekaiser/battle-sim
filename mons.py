from moves import *
from items import *


six_stats = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]
stat_names = {
    "Atk": "Attack", "Def": "Defense", "SpA": "Special Attack", "SpD": "Special Defense", "Spe": "Speed",
    "Acc": "accuracy", "Eva": "evasion"
}


genders = male, female, genderless = "Male", "Female", "Genderless"
status_conditions = burn, freeze, paralysis, mild_poison, bad_poison, sleep = \
    "burn", "freeze", "paralysis", "poison", "toxic", "sleep"
status_adjectives = {
    burn: "Burned",
    freeze: "Frozen",
    paralysis: "Paralyzed",
    mild_poison: "Poisoned",
    bad_poison: "Badly poisoned",
    sleep: "Asleep"
}
status_abbreviations = {
    burn: "BRN",
    freeze: "FRZ",
    paralysis: "PAR",
    mild_poison: "PSN",
    bad_poison: "TOX",
    sleep: "SLP"
}


ruinous_abilities = {
    "Vessel of Ruin": "SpA",
    "Sword of Ruin": "Def",
    "Tablets of Ruin": "Atk",
    "Beads of Ruin": "SpD"
}


def sign(n: int | float) -> int:
    return 1 if n > 0 else -1 if n < 0 else 0


def product(iterable: iter) -> int | float:
    ret = 1
    for i in iterable:
        ret *= i
    return ret


class Form:
    def __init__(self, hp: int, atk: int, dfn: int, spa: int, spd: int, spe: int, type1: str, type2: str | None,
                 height: float, weight: float, abilities: dict[str, str | None], name: str = ""):
        self.hp = hp
        self.atk = atk
        self.dfn = dfn
        self.spa = spa
        self.spd = spd
        self.spe = spe
        self.type1 = type1
        self.type2 = type2
        self.height = height
        self.weight = weight
        self.primary_ability = abilities.get("primary")
        self.secondary_ability = abilities.get("secondary")
        self.hidden_ability = abilities.get("hidden")
        self.name = name

    @staticmethod
    def from_json(js: dict):
        return Form(**js)

    @property
    def base_stats(self):
        return {"HP": self.hp, "Atk": self.atk, "Def": self.dfn, "SpA": self.spa, "SpD": self.spd, "Spe": self.spe}

    @property
    def legal_abilities(self):
        return [g for g in [self.primary_ability, self.secondary_ability, self.hidden_ability] if g]

    def json(self):
        return {
            "hp": self.hp, "atk": self.atk, "dfn": self.dfn, "spa": self.spa, "spd": self.spd, "spe": self.spe,
            "type1": self.type1, "type2": self.type2, "height": self.height, "weight": self.weight,
            "abilities": {k: v for k, v in {
                "primary": self.primary_ability, "secondary": self.secondary_ability, "hidden": self.hidden_ability
            }.items() if v}
        } | ({"name": self.name} if self.name else {})


class Species:
    def __init__(self, name: str, forms: list[Form], gender_ratio: str = "1:1"):
        self.name = name
        self.forms = {g.name: g for g in forms}
        self.gender_ratio = gender_ratio

    @staticmethod
    def from_json(js: dict):
        return Species(js["name"], [Form.from_json(g) for g in js["forms"]], js.get("gender_ratio", "1:1"))

    @property
    def has_gendered_forms(self):
        return set(self.forms) == {"", "F"}

    def json(self):
        return {"name": self.name, "gender_ratio": self.gender_ratio, "forms": [g.json() for g in self.forms.values()]}

    def get_form(self, name: str = "") -> Form:
        if isinstance(name, Form):
            return self.get_form(name.name)
        if name in genders:
            if not self.has_gendered_forms:
                raise KeyError(f"Invalid form name for {self.name}: {name}")
            return self.forms["F" if name == female else ""]
        if (not name) or fix(name) == "base" or name == male:
            return self.forms[list(self.forms)[0]]
        for form in self.forms:
            if fix(name) == fix(form):
                return self.forms[form]
        raise KeyError(f"Invalid form name for {self.name}: {name}")

    def random_gender(self):
        if self.gender_ratio in genders:
            return self.gender_ratio
        else:
            return random.choices([female, male], [int(c) for c in self.gender_ratio.split(":")])[0]


class Evolution:
    def __init__(self, into: str, **kwargs):
        self.into = into
        self.reqs = kwargs

    def __getitem__(self, item):
        return self.reqs.get(item)

    def __eq__(self, other):
        return isinstance(other, Evolution) and (self.into == other.into)

    def __bool__(self):
        return self.into != "NONE"

    @staticmethod
    def from_json(js: dict):
        return Evolution(**js)

    @staticmethod
    def null():
        return Evolution("NONE")

    @property
    def method(self):
        return self["method"]

    @property
    def first_method(self) -> dict:
        if self["multiple"]:
            return self["multiple"][0]
        return self.reqs

    def read_out(self, using_gerund: bool):
        if self["multiple"]:
            return "; or, ".join(Evolution(self.into, **g).read_out(using_gerund) for g in self["multiple"])

        if self.method == "specific":
            return self["by"] if using_gerund else self["desc"]

        if self.method == "level":
            if self["level"]:
                ret = f"at level {self['level']}" if using_gerund else f"Level {self['level']}"
            else:
                ret = "upon levelling up" if using_gerund else "Level up"
        elif self.method == "friendship":
            ret = ("upon levelling" if using_gerund else "Level") + " up with high friendship"
        elif self.method == "trade":
            ret = "when traded" if using_gerund else "Trade"
        elif self.method == "use":
            ret = ("with" if using_gerund else "Use") + \
                  f" a{'n' if self['item'][0].lower() in 'aeiou' else ''} {self['item']}"
        elif self.method == "steps":
            ret = ("after walking" if using_gerund else "Walk") + " 1000 steps using the Let's Go feature"
        elif self.method == "move":
            ret = ("after using" if using_gerund else "Use") + f" {self['move']}"
        else:
            return "Not known"

        if self["special_req"]:
            ret += f" {self['special_req']}"

        if self["holding"]:
            ret += f" while holding a{'n' if self['holding'][0].lower() in 'aeiou' else ''} {self['holding']}"
        if self["knowing"]:
            ret += f" while knowing {self['knowing']}"

        if self["location"]:
            ret += f" in {self['location']}"
        if self["time"]:
            ret += f" at {self['time']}"
        if self["gender"]:
            ret += f" ({self['gender']})"
        if self["game"]:
            ret += f" (in {self['game']})"

        return ret

    def sentence(self, preposition: str = "into"):
        if self.into == "NONE":
            return "Does not evolve."
        if self.into == "Shedinja":
            return f"A **{self.into}** appears in the player's party {self.read_out(True)}."
        return f"Evolves {preposition} **{self.into}** {self.read_out(True)}."

    @property
    def phrase(self):
        if self.into == "NONE":
            return "Does not evolve"
        return self.read_out(False)


evolutions = {g: [Evolution.from_json(k) for k in j] for g, j in json.load(open("data/evolutions.json")).items()}


nature_table = [
    # -Atk      -Def      -SpA       -SpD       -Spe
    'Hardy',  'Lonely', 'Adamant', 'Naughty', 'Brave',    # +Atk
    'Bold',   'Docile', 'Impish',  'Lax',     'Relaxed',  # +Def
    'Modest', 'Mild',   'Bashful', 'Rash',    'Quiet',    # +SpA
    'Calm',   'Gentle', 'Careful', 'Quirky',  'Sassy',    # +SpD
    'Timid',  'Hasty',  'Jolly',   'Naive',   'Serious'   # +Spe
]


class MiniMon:
    def __init__(self, species_and_form: str = None, **kwargs):
        self.nickname = kwargs.get("nickname")
        if species_and_form:
            species, form = fixed_species_and_forms[fix(species_and_form)]
            self.species = all_species[species]
            self.form = self.species.get_form(form)
        elif species := kwargs.get("species"):
            if isinstance(species, Species):
                self.species = species
            else:
                self.species = all_species[species]
            self.form = self.species.get_form(kwargs.get("form"))
        else:
            raise ValueError("Species must be provided.")
        self.level = kwargs.get("level", 100)
        self.gender = self.set_gender(kwargs.get("gender"))
        self.nature = "Quirky" if kwargs.get("nature") not in nature_table \
            else kwargs.get("nature")
        self.ivs = kwargs.get("ivs", [31, 31, 31, 31, 31, 31])
        self.evs = kwargs.get("evs", [0, 0, 0, 0, 0, 0])
        self.ability = self.form.primary_ability if not kwargs.get("ability") \
            else kwargs.get("ability")
        self.held_item = None if kwargs.get("held_item") not in all_items \
            else all_items[kwargs.get("held_item")]
        self.tera_type = self.form.type1 if kwargs.get("tera_type") not in types \
            else kwargs.get("tera_type")
        self.move_names = [g for g in kwargs.get("move_names", []) if g in all_moves][:4]

    def set_gender(self, gender: str = "random") -> str:
        if self.species.gender_ratio in genders:
            return self.species.gender_ratio
        if gender != male and gender != female:
            gender = male if self.species.has_gendered_forms else "random"
        if self.species.has_gendered_forms:
            self.form = self.species.get_form(gender)
        return gender

    @property
    def name(self):
        return self.nickname if self.nickname else self.species_and_form

    @property
    def species_and_form(self):
        if not self.form.name:
            return self.species.name
        else:
            return f"{self.species.name}-{'-'.join(self.form.name.split())}"

    @property
    def verbose_name(self):
        return f"{self.nickname} ({self.species_and_form})" if self.nickname else self.species_and_form

    @property
    def nature_index(self):
        return nature_table.index(self.nature)

    @property
    def nature_effects(self):
        return {
            six_stats[g + 1]: round((self.nature_index // 5 == g) - (self.nature_index % 5 == g))
            for g in range(5)
        }

    @property
    def base_stats(self):
        return self.form.base_stats

    @property
    def hp(self):
        if self.species.name == "Shedinja":
            return 1
        return floor((2 * self.form.hp + self.ivs[0] + floor(self.evs[0] / 4)) * self.level / 100) + self.level + 10

    @property
    def atk(self):
        return floor(
            (floor((2 * self.form.atk + self.ivs[1] + floor(self.evs[1] / 4)) * self.level / 100) + 5) *
            (1 + 0.1 * ((self.nature_index // 5 == 0) - (self.nature_index % 5 == 0)))
        )

    @property
    def dfn(self):
        return floor(
            (floor((2 * self.form.dfn + self.ivs[2] + floor(self.evs[2] / 4)) * self.level / 100) + 5) *
            (1 + 0.1 * ((self.nature_index // 5 == 1) - (self.nature_index % 5 == 1)))
        )

    @property
    def spa(self):
        return floor(
            (floor((2 * self.form.spa + self.ivs[3] + floor(self.evs[3] / 4)) * self.level / 100) + 5) *
            (1 + 0.1 * ((self.nature_index // 5 == 2) - (self.nature_index % 5 == 2)))
        )

    @property
    def spd(self):
        return floor(
            (floor((2 * self.form.spd + self.ivs[4] + floor(self.evs[4] / 4)) * self.level / 100) + 5) *
            (1 + 0.1 * ((self.nature_index // 5 == 3) - (self.nature_index % 5 == 3)))
        )

    @property
    def spe(self):
        return floor(
            (floor((2 * self.form.spe + self.ivs[5] + floor(self.evs[5] / 4)) * self.level / 100) + 5) *
            (1 + 0.1 * ((self.nature_index // 5 == 4) - (self.nature_index % 5 == 4)))
        )

    @property
    def stats(self):
        return {"HP": self.hp, "Atk": self.atk, "Def": self.dfn, "SpA": self.spa, "SpD": self.spd, "Spe": self.spe}

    @property
    def has_nontrivial_gender(self):
        return self.gender in genders and not (self.species.has_gendered_forms or self.species.gender_ratio in genders)

    def pokepaste(self):
        name_line = (f"{self.nickname} ({self.species_and_form})" if self.nickname else self.species_and_form) + \
            (f" ({self.gender[0]})" if self.has_nontrivial_gender else "") + \
            (f" @ {self.held_item.name}" if self.held_item else "")
        nontrivial_evs = [f"{self.evs[n]} {six_stats[n]}" for n in range(6) if self.evs[n] != 0]
        nontrivial_ivs = [f"{self.ivs[n]} {six_stats[n]}" for n in range(6) if self.ivs[n] != 31]
        return (
            f"{name_line}\n"
            f"Level: {self.level}\n"
            f"{self.nature} Nature\n" +
            (f"Tera Type: {self.tera_type}\n" if self.tera_type != self.form.type1 else "") +
            f"Ability: {self.ability}\n" +
            (f"EVs: {' / '.join(nontrivial_evs)}\n" if nontrivial_evs else "") +
            (f"IVs: {' / '.join(nontrivial_ivs)}\n" if nontrivial_ivs else "") +
            "\n".join(f"- {g}" for g in self.move_names)
        ).strip("\n")

    @staticmethod
    def from_pokepaste(paste: str):
        ret = {}
        move_names = []
        for line in paste.splitlines():
            if not ret:
                if not (match := re.match(  # modified from https://github.com/felixphew/pokepaste/blob/v3/syntax.go
                    r"^(?:(?P<nick>.* \()(?P<species1>[A-Z][a-z0-9:'éé]+\.?(?:[- ][A-Za-z][a-z0-9:'éé]*\.?)*)"
                    r"(\))|(?P<species2>[A-Z][a-z0-9:'éé]+\.?(?:[- ][A-Za-z][a-z0-9:'éé]*\.?)*))(?:( \()"
                    r"(?P<gender>[MF])(\)))?(?:( @ )(?P<item>[A-Za-z0-9:'éé]*(?:[- ][A-Za-z0-9:'éé]*)*))?( *)$", line
                )):
                    continue
                else:
                    if match.group("species1"):
                        ret["species_and_form"] = match.group("species1")
                    elif match.group("species2"):
                        ret["species_and_form"] = match.group("species2")
                    if match.group("nick"):
                        ret["nickname"] = match.group("nick")[:-2]
                    if match.group("gender"):
                        ret["gender"] = male if match.group("gender") == "M" else female
                    if match.group("item"):
                        ret["held_item"] = match.group("item")

            elif match := re.fullmatch(r"Level: (?P<level>\d+)", line):
                ret["level"] = int(match.group("level"))

            elif match := re.fullmatch(r"(?P<nature>[A-Za-z]+) Nature", line):
                ret["nature"] = match.group("nature")

            elif match := re.fullmatch(  # from the same git repo as above
                r"(?a)EVs: ((?P<hp>\d+) HP)?( / )?((?P<atk>\d+) Atk)?( / )?((?P<def>\d+) Def)?( / )?"
                r"((?P<spa>\d+) SpA)?( / )?((?P<spd>\d+) SpD)?( / )?((?P<spe>\d+) Spe)?( *)", line
            ):
                ret["evs"] = [int(g) if g is not None else 0 for g in match.groupdict().values()]

            elif match := re.fullmatch(
                r"(?a)IVs: ((?P<hp>\d+) HP)?( / )?((?P<atk>\d+) Atk)?( / )?((?P<def>\d+) Def)?( / )?"
                r"((?P<spa>\d+) SpA)?( / )?((?P<spd>\d+) SpD)?( / )?((?P<spe>\d+) Spe)?( *)", line
            ):
                ret["ivs"] = [int(g) if g is not None else 31 for g in match.groupdict().values()]

            elif match := re.fullmatch(r"Ability: (?P<ability>[A-Za-z \-'()]+)", line):
                ret["ability"] = match.group("ability")

            elif match := re.fullmatch(r"Tera Type: (?P<tera>[A-Za-z]+)", line):
                ret["tera_type"] = match.group("tera")

            elif match := re.fullmatch(  # modified from above git repo
                r"- ?(?P<name>[A-Za-z0-9']*(?:[\- ,][A-Za-z0-9']*)*)(?: \[(?P<type>[A-Z][a-z]+)])?", line
            ):
                move_names.append(match.group("name") + (f" [{match.group('type')}]" if match.group("type") else ""))

        ret["move_names"] = move_names
        return MiniMon(**ret)

    def mini_pack(self, include_move_names: bool = True):
        return {
            "species_and_form": self.species_and_form, "level": self.level, "gender": self.gender,
            "nature": self.nature, "ivs": self.ivs, "evs": self.evs, "ability": self.ability,
            "held_item": (self.held_item.name if self.held_item else None), "tera_type": self.tera_type
        } | ({"move_names": self.move_names} if include_move_names else {}) | \
            ({"nickname": self.nickname} if self.nickname else {})

    @staticmethod
    def from_mini_pack(mini_pack: dict):
        return MiniMon(**mini_pack)

    def deploy(self, **kwargs):
        return FieldMon(**self.mini_pack(), **kwargs)


all_species = {k: Species.from_json(v) for k, v in json.load(open("data/mons.json")).items()}
fixed_species_and_forms = {fix(g): (g, "") for g in all_species} | {
    fix(MiniMon(species=sp, form=fm).species_and_form): (sp, fm.name)
    for sp, v in all_species.items() for fm in v.forms.values()
}


class FieldMon(MiniMon):
    def __init__(self, **kwargs):  # should never be called directly; use other functions to build
        super().__init__(**kwargs)

        if moves := kwargs.pop("moves", []):
            self.moves = {g["name"]: Move.from_pack(**g) for g in moves}
            self.move_names = list(self.moves.keys())
        else:
            self.moves = {g: Move.from_pack(g, -1) for g in self.move_names}

        if self.gender not in genders:  # set_gender call should be unnecessary but it can't hurt
            self.gender = self.set_gender(self.species.random_gender())

        self.remaining_hp = kwargs.pop("remaining_hp", self.hp)
        self.status_condition = kwargs.pop("status_condition", None)
        self.status_timer = kwargs.pop("status_timer", 0)
        self.terastallized = kwargs.pop("terastallized", False)

        self.type1 = self.form.type1
        self.type2 = self.form.type2
        self.type3 = None

        self.stat_stages = kwargs.pop(
            "stat_stages", {"Atk": 0, "Def": 0, "SpA": 0, "SpD": 0, "Spe": 0, "Acc": 0, "Eva": 0}
        )

        self.id = kwargs.pop("id", -1)
        self.team_id = kwargs.pop("team_id", -1)
        self.position = kwargs.pop("position", -1)
        self.next_action = ""
        self.targets = []
        self.turn_on_field = 0

        self.has_taken_turn = False
        self.has_executed_move = False
        self.has_landed_move = False
        self.failed_last_attack = False

        self.fainted = kwargs.pop("fainted", False)  # set manually to keep from sending multiple "x fainted!" messages
        self.other_data = kwargs

    def __bool__(self):
        return not self.fainted

    def __getitem__(self, item):
        return self.other_data.get(item)

    def __setitem__(self, key, value):
        self.other_data[key] = value

    @staticmethod
    def from_json(js: dict):
        return FieldMon(**js)

    def json(self):
        return {
            **self.mini_pack(False),
            "moves": [g.pack() for g in self.moves.values()],
            "field_status": self.field_status} | \
            ({"nickname": self.nickname} if self.nickname else {}) | \
            ({"remaining_hp": self.remaining_hp} if self.hp != self.remaining_hp else {}) | \
            ({"status_condition": self.status_condition} if (self.status_condition and not self.fainted) else {}) | \
            ({"status_timer": self.status_timer} if (self.status_condition == sleep and not self.fainted) else {}) | \
            ({"terastallized": True} if (self.terastallized and not self.fainted) else {}) | \
            ({"id": self.id} if self.id != -1 else {}) | \
            ({"team_id": self.team_id} if self.team_id != -1 else {}) | \
            ({"fainted": True} if self.fainted else {})

    def get(self, item: str, default_value=None):
        return self.other_data.get(item, default_value)

    def clear(self, item: str):
        if item in self.other_data:
            del self.other_data[item]

    @property
    def original_types(self):
        return tuple(g for g in [self.type1, self.type2, self.type3] if g is not None)

    @property
    def types(self):
        return (self.tera_type, ) if self.terastallized else self.original_types

    @property
    def move_selection(self) -> Move | None:
        return self.moves.get(self.next_action)

    @property
    def next_action_priority(self):
        if self["moving_next"]:
            return 12
        if self.next_action in self.moves:
            return self.moves[self.next_action].priority
        if self.next_action.startswith("!switch"):
            return 10
        return 0

    @property
    def field_status(self):
        return "fainted" if self.fainted else "on field" if self.position != -1 else "benched"

    @property
    def immune_to_sand(self):
        return any(g in self.types for g in (rock, ground, steel))

    def has_ability(self, *abilities: str) -> bool:
        return bool({self.ability}.intersection(set(abilities)))

    def heal(self, healing: int) -> int:
        initial_hp = self.remaining_hp
        self.remaining_hp = min(self.hp, self.remaining_hp + healing)
        return self.remaining_hp - initial_hp

    def damage(self, damage: int) -> int:
        initial_hp = self.remaining_hp
        self.remaining_hp = max(0, self.remaining_hp - damage)
        return initial_hp - self.remaining_hp

    def type_effectiveness(self, attacking_type: str, overwrites: dict[tuple[str, str], float] = ()) -> float:
        if not attacking_type:
            return 1
        return round(product(
            dict(overwrites).get((attacking_type, g), type_effectiveness[attacking_type][g])
            for g in self.types
        ), 3)

    def hp_display(self, percentage: bool = False):
        return f"{round(100 * self.remaining_hp / self.hp)}%" if percentage else f"{self.remaining_hp}/{self.hp}"

    def inline_display(self, hp_percentage: bool = False):
        return f"{self.verbose_name} " \
               f"{('[' + status_abbreviations[self.status_condition] + '] ') if self.status_condition else ''}" \
               f"[{self.hp_display(hp_percentage)}]"

    def battle_info(self) -> list[str]:
        ret = []

        for k, v in self.stat_stages.items():
            if v != 0:
                ret.append(f"{'+' if v > 0 else ''}{v} {k}")

        if self.status_condition is not None:
            ret.append(status_adjectives[self.status_condition])

        if self["confused"]:
            ret.append("Confused")

        return ret

    def staged_stat(self, stat: str, doubled_after: int = 2) -> int:
        return round(
            self.stats.get(stat, 1) *
            (doubled_after + max(self.stat_stages[stat], 0)) /
            (doubled_after - min(self.stat_stages[stat], 0))
        )

    def apply(self, stat_change: StatChange | dict) -> dict[str, int]:
        if isinstance(stat_change, dict):
            stat_change = StatChange.from_json(stat_change)
        ret = {}
        for stat, change in stat_change.items():
            if actual_change := (min(max(self.stat_stages[stat] + change, -6), 6) - self.stat_stages[stat]):
                ret[stat] = actual_change
                self.stat_stages[stat] += actual_change
            else:
                ret[stat] = 4 * sign(change)
        return ret
