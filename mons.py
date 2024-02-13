from moves import *
from items import *
from random import choices
import re


genders = male, female, genderless = "Male", "Female", "Genderless"
six_stats = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]


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
            return choices([female, male], [int(c) for c in self.gender_ratio.split(":")])[0]


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
        self.ability = self.form.primary_ability if kwargs.get("ability") not in self.form.legal_abilities \
            else kwargs.get("ability")
        self.held_item = None if kwargs.get("held_item") not in all_items \
            else kwargs.get("held_item")
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
    def species_and_form(self):
        if not self.form.name:
            return self.species.name
        else:
            return f"{self.species.name}-{'-'.join(self.form.name.split())}"

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
            (f" @ {self.held_item}" if self.held_item else "")
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
            "held_item": self.held_item, "tera_type": self.tera_type
        } | ({"move_names": self.move_names} if include_move_names else {})

    def build(self):
        return FieldMon(**self.mini_pack())


all_species = {k: Species.from_json(v) for k, v in json.load(open("data/mons.json")).items()}
fixed_species_and_forms = {fix(g): (g, "") for g in all_species} | {
    fix(MiniMon(species=sp, form=fm).species_and_form): (sp, fm.name)
    for sp, v in all_species.items() for fm in v.forms.values()
}


class FieldMon(MiniMon):
    def __init__(self, **kwargs):  # should never be called directly; use other functions to build
        super().__init__(**kwargs)

        if moves := kwargs.pop("moves"):
            self.moves = {g["name"]: Move.from_pack(**g) for g in moves}
            self.move_names = list(self.moves.keys())
        else:
            self.moves = {g: Move.from_pack(g, -1) for g in self.move_names}

        if self.gender not in genders:  # set_gender call should be unnecessary but it can't hurt
            self.gender = self.set_gender(self.species.random_gender())

        self.remaining_hp = self.hp - kwargs.pop("damage", 0)
        self.status_condition = kwargs.pop("status_condition")
        self.status_timer = kwargs.pop("status_timer", 0)
        self.terastallized = kwargs.pop("terastallized", False)

        self.other_data = kwargs

    def __getitem__(self, item):
        return self.other_data.get(item)

    def __setitem__(self, key, value):
        self.other_data[key] = value

    @staticmethod
    def from_json(js: dict):
        return FieldMon(**js)

    def json(self):
        return {**self.mini_pack(False), "moves": [g.pack() for g in self.moves.values()]} | \
            ({"nickname": self.nickname} if self.nickname else {}) | \
            ({"damage": round(self.hp - self.remaining_hp)} if self.hp != self.remaining_hp else {}) | \
            ({"status_condition": self.status_condition} if self.status_condition else {}) | \
            ({"status_timer": self.status_timer} if self.status_timer else {}) | \
            ({"terastallized": True} if self.terastallized else {})
