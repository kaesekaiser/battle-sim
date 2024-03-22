from controllers import *
import time
from math import ceil


stat_change_texts = {
    4: "can't go any higher",
    3: "rose drastically",
    2: "rose sharply",
    1: "rose",
    -1: "fell",
    -2: "harshly fell",
    -3: "severely fell",
    -4: "can't go any lower"
}
status_condition_texts = {
    burn: "was burned",
    freeze: "was frozen solid",
    paralysis: "was paralyzed",
    mild_poison: "was poisoned",
    bad_poison: "was badly poisoned",
    sleep: "fell asleep"
}
weather_texts = {
    rain: ["It started to rain!", "Rain continues to fall.", "The rain stopped."],
    heavy_rain: ["A heavy rain began to fall!", "Heavy rain continues to fall.", "The heavy rain stopped."],
    sandstorm: ["A sandstorm kicked up!", "The sandstorm is raging.", "The sandstorm subsided."],
    snow: ["It started to snow!", "Snow continues to fall.", "The snow stopped."],
    sun: ["The sunlight turned harsh!", "The sunlight is strong.", "The harsh sunlight faded."],
    extreme_sun: ["The sunlight turned extremely harsh!", "The sunlight is extremely strong.",
                  "The extremely harsh sunlight faded."],
    winds: ["Mysterious winds are protecting Flying-type Pok\u00e9mon!", "Mysterious winds continue to blow.",
            "The mysterious winds dissipated."]
}
terrain_texts = {
    electric_terrain: "An electric current ran across the battlefield!",
    grassy_terrain: "Grass grew to cover the battlefield!",
    misty_terrain: "Mist swirled around the battlefield!",
    psychic_terrain: "The battlefield got weird!"
}
announce_on_send_out = [  # Abilities that either proc immediately or should be announced when a mon is sent out.
    "Intimidate",
    *list(ruinous_abilities), *list(weather_spawning_abilities), *list(terrain_spawning_abilities)
]


class Battle:
    def __init__(self, teams: list[Controller], size: int = 1, pov: int = 0):
        self.teams = teams[:2]
        teams[0].change_id(0)
        teams[1].change_id(1)

        if not (1 <= size <= 3):
            raise ValueError("Size must be between 1 and 3.")
        self.size = size
        self.pov = pov

        self.field = Field(size=self.size)
        self.teams[0].set_field(self.field)
        self.teams[1].set_field(self.field)

        self.last_output = ""
        self.turn_count = 0

    def output(self, text: str, sleep_time: float = 0.5) -> None:
        print(text)
        self.last_output = text.split("\n")[-1]
        if sleep_time:
            time.sleep(sleep_time)

    def spaced(self, text: str) -> str:
        return ("\n" if self.last_output else "") + text

    def deploy_mon(self, team_id: int, mon_id: int, position: int, announce: bool = True, proc_ability: bool = True):
        if packed_mon := self.teams[team_id][mon_id]:
            if self.at(position):
                if announce:
                    self.output(f"{self.teams[team_id].trainer} recalled {self.at(position).name}!")
                self.teams[team_id].recall_mon(self.at(position))
            self.field.deploy_mon(FieldMon.from_json(packed_mon | {"position": position}), position)
            packed_mon["field_status"] = "on field"
            if announce:
                self.output(f"{self.teams[team_id].trainer} sent out {self.at(position).verbose_name}!")
                if proc_ability:
                    self.proc_ability_on_send_out(self.at(position))
        else:
            self.field.deploy_mon(None, position)

    def at(self, position: int) -> FieldMon | None:
        return self.field.at(position)

    def team(self, side: int | FieldMon) -> Controller:
        if isinstance(side, FieldMon):
            return self.teams[side.team_id]
        else:
            return self.teams[side]

    def possessive(self, team: int | FieldMon | Team, caps: bool = False) -> str:
        if isinstance(team, FieldMon):
            team_id = team.team_id
        elif isinstance(team, Team):
            team_id = team.id
        else:
            team_id = team
        return f"{'Y' if caps else 'y'}our" if team_id == self.pov else f"{'T' if caps else 't'}he opposing"

    def name(self, mon: FieldMon, caps: bool = True) -> str:
        if mon.team_id == self.pov:
            return mon.name
        else:
            return f"{self.possessive(mon, caps)} {mon.name}"

    @property
    def fielded_mons(self) -> list[FieldMon]:
        return self.field.fielded_mons

    def get_stat(self, mon: FieldMon, stat: str) -> int:
        return self.field.get_stat(mon, stat)

    def init_battle(self):
        for n in range(self.size):
            self.deploy_mon(0, n, n, proc_ability=False)
        for n in range(self.size, self.size * 2):
            self.deploy_mon(1, n % self.size + 6, self.size * 3 - 1 - n, proc_ability=False)  # deploy to trainer's left

        for mon in self.turn_order():  # proc any send-out abilities in normal move order AFTER all mons are deployed
            self.proc_ability_on_send_out(mon)

    def next_to_move(self) -> FieldMon | None:
        try:
            return self.turn_order()[0]
        except IndexError:
            return None

    def turn_order(self) -> list[FieldMon]:
        priorities = [
            [
                g.next_action_priority,
                self.field.get_stat(g, "Spe") * (-1 if self.field.trick_room else 1),
                random.random(),
                g.position
            ] for g in self.fielded_mons if not g.has_taken_turn and not g.fainted
        ]
        return [self.at(g[3]) for g in sorted(priorities, reverse=True)]

    def double_check_targets(self, mon: FieldMon):
        if not mon.move_selection:
            return
        move = self.field.apply_conditionals(mon, mon.move_selection)
        possible_targets = self.field.targets(mon.position, move.target)

        if move.is_single_target:
            if not mon.targets[0] not in possible_targets:  # if the mon's original target is no longer valid
                if same_side := [g for g in possible_targets if g // self.size == mon.targets[0] // self.size]:
                    mon.targets = [same_side[0]]  # try to target to a valid mon on the same side
                else:
                    mon.targets = []  # this will prevent move execution entirely
        else:
            mon.targets = possible_targets

    def damage(self, mon: FieldMon, damage: int, description: str = "damage"):
        damage_dealt = mon.damage(damage)
        self.output(f"{self.name(mon)} took {damage_dealt} {description}! (-> {mon.hp_display()} HP)")
        self.check_fainted(mon)

    def heal(self, mon: FieldMon, healing: int, description: str = "HP"):
        healing_done = mon.heal(healing)
        self.output(f"{self.name(mon)} regained {healing_done} {description}! (-> {mon.hp_display()} HP)")

    def announce_ability(self, mon: FieldMon):
        self.output(f"== {self.name(mon)}'s {mon.ability}! ==")

    def proc_ability_on_send_out(self, mon: FieldMon):
        if not mon.has_ability(*announce_on_send_out):
            return
        self.announce_ability(mon)

        if mon.has_ability("Intimidate"):
            for opponent in self.team(mon).opponent_mons:
                if self.are_adjacent(mon, opponent):
                    self.apply_stat_change(opponent, {"Atk": -1})
        if mon.has_ability(*list(ruinous_abilities)):
            self.output(
                f"{self.name(mon)} lowered the {stat_names[ruinous_abilities[mon.ability]]} "
                f"of surrounding Pok\u00e9mon!"
            )
        if mon.has_ability(*list(weather_spawning_abilities)):
            if self.field.can_change_weather(weather_spawning_abilities[mon.ability]):
                self.change_weather(weather_spawning_abilities[mon.ability])
        if mon.has_ability(*list(terrain_spawning_abilities)):
            self.change_terrain(terrain_spawning_abilities[mon.ability])

    def are_adjacent(self, pos1: int | FieldMon, pos2: int | FieldMon) -> bool:
        if isinstance(pos1, FieldMon):
            pos1 = pos1.position
        if isinstance(pos2, FieldMon):
            pos2 = pos2.position
        return abs((pos1 % self.size) - (pos2 % self.size)) <= 1

    def can_execute(self, attacker: FieldMon, move: Move):
        """Checks that prevent the execution of a move (e.g. being frozen, priority on PTerrain) before it happens."""
        if attacker.status_condition == freeze:
            if move["thaws_user"] or (random.random() < 0.2):  # note to self: prevent thawing if Burn Up would fail
                self.apply_status(attacker, None)
                self.output(f"{self.name(attacker)} thawed out!")
            else:
                self.output(f"{self.name(attacker)} is frozen solid!")
                return False
        elif attacker.status_condition == paralysis:
            if random.random() < 0.25:
                self.output(f"{self.name(attacker)} is paralyzed! It can't move!")
                return False
        elif attacker.status_condition == sleep:
            if attacker.status_timer == 0:
                self.output(f"{self.name(attacker)} woke up!")
                self.apply_status(attacker, None)
            else:
                self.output(f"{self.name(attacker)} is fast asleep.")
                attacker.status_timer -= 1
                return False

        if attacker["flinching"]:
            self.output(f"{self.name(attacker)} flinched!")
            return False

        if attacker["confused"]:
            attacker["confusion_timer"] -= 1
            if attacker["confusion_timer"] == 0:
                self.output(f"{self.name(attacker)} snapped out of its confusion!")
                attacker.clear("confused")
                attacker.clear("confusion_timer")
            else:
                self.output(f"{self.name(attacker)} is confused!")
                if random.random() < 1/3:
                    self.output("It hurt itself in its confusion!")
                    damage = self.field.damage_roll(attacker, attacker, confusion_self_attack, allow_crit=False)
                    self.damage(attacker, damage["damage"])
                    return False

        return True

    def accuracy_check(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if not move.accuracy:
            return True
        if random.random() < move.accuracy / 100 * self.get_stat(attacker, "Acc") / self.get_stat(defender, "Eva"):
            return True
        return False

    def but_it_failed(self, attacker: FieldMon, defender: FieldMon, move: Move) -> bool | None:
        if move["first_turn_only"] and attacker.turn_on_field > 1:
            return self.output("But it failed!")
        if move["after_you"] and defender.has_taken_turn:
            return self.output("But it failed!")

        if defender["protecting"]:
            return self.output(f"{self.name(defender)} protected itself!")
        if self.field.move_effectiveness(attacker, defender, move) == 0 and move.category != status:
            return self.output(f"It doesn't affect {self.name(defender, False)}...")
        if self.field.terrain == psychic_terrain and move.priority > 0 and self.field.is_grounded(defender):
            return self.output(f"{self.name(defender)} is protected by Psychic Terrain!")
        if not self.accuracy_check(attacker, defender, move):
            if len(attacker.targets) > 1:
                return self.output(f"{self.name(defender)} avoided the attack!")
            else:
                return self.output(f"{self.name(attacker)}'s attack missed!")

        if move.category == status and len(attacker.targets) == 1:
            if move.total_key_effects == 1:  # moves that have exactly one job
                if move.status_condition and \
                        not self.field.can_apply_status(attacker, defender, move.status_condition.condition):
                    return self.output("But it failed!")
                if move["change_weather"] and not self.field.can_change_weather(move["change_weather"]):
                    return self.output("But it failed!")
                if move["change_terrain"] is not None and self.field.terrain == move["change_terrain"]:
                    return self.output("But it failed!")
                if move["confuse"] is not None and not self.field.can_confuse(defender):
                    return self.output("But it failed!")

        if not attacker.has_landed_move:  # moves with multiple targets that only actually fire once, e.g. Reflect
            if move["reflect"] and self.field.side(attacker).reflect:
                return self.output("But it failed!")
            if move["light_screen"] and self.field.side(attacker).light_screen:
                return self.output("But it failed!")
            if move["aurora_veil"] and (self.field.side(attacker).aurora_veil or self.field.weather != snow):
                return self.output("But it failed!")

        return True

    def move_modifications(self, attacker: FieldMon, defender: FieldMon, move: Move):
        power_multipliers = []  # https://bulbapedia.bulbagarden.net/wiki/Power#Generation_IX
        if self.field.terrain == misty_terrain and move.type == dragon and self.field.is_grounded(defender):
            power_multipliers.append(0.5)
        if self.field.terrain == electric_terrain and move.type == electric and self.field.is_grounded(attacker):
            power_multipliers.append(1.3)
        elif self.field.terrain == grassy_terrain and move.type == grass and self.field.is_grounded(attacker):
            power_multipliers.append(1.3)
        elif self.field.terrain == psychic_terrain and move.type == psychic and self.field.is_grounded(attacker):
            power_multipliers.append(1.3)

        move.power = round(move.power * product(power_multipliers))

    def apply_stat_change(self, mon: FieldMon, stat_change: StatChange | dict):
        changes = mon.apply(stat_change)
        self.display_stat_change(mon, changes)

    def display_stat_change(self, mon: FieldMon, stat_change: dict[str, int]):
        for stat, change in stat_change.items():
            self.output(f"{self.name(mon)}'s {stat_names[stat]} {stat_change_texts[change]}!")

    def apply_status(self, mon: FieldMon, condition: str | None):
        mon.status_condition = condition
        if condition == sleep:
            mon.status_timer = random.choice([1, 2, 3])
        else:
            mon.status_timer = 0
        if condition:
            self.output(f"{self.name(mon)} {status_condition_texts[condition]}!")

    def change_weather(self, weather: str | None, turns: int = 5):
        if weather:
            self.field.set_weather(weather, turns)
            self.output(weather_texts[weather][0])
        elif self.field.weather is not None:
            self.output(weather_texts[self.field.weather][2])
            self.field.set_weather(None)

    def change_terrain(self, terrain: str | None, turns: int = 5):
        if terrain:
            self.field.set_terrain(terrain, turns)
            self.output(terrain_texts[terrain])
        elif self.field.terrain is not None:
            self.output(f"The {self.field.terrain} terrain dissipated.")
            self.field.set_terrain(None)

    def pre_hit_effects(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if move["removes_screens"]:
            if self.field.side(defender).reflect:
                self.field.side(defender).set_reflect(False)
                self.output(f"{self.possessive(defender, True)} team's Reflect was removed!")
            if self.field.side(defender).light_screen:
                self.field.side(defender).set_light_screen(False)
                self.output(f"{self.possessive(defender, True)} team's Light Screen was removed!")
            if self.field.side(defender).aurora_veil:
                self.field.side(defender).set_aurora_veil(False)
                self.output(f"{self.possessive(defender, True)} team's Aurora Veil was removed!")

    def move_effects(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if defender.status_condition == freeze and move.thaws_target:
            self.apply_status(defender, None)
            self.output(f"{self.name(defender)} was thawed out!")

        if move.contact:
            if defender.has_ability("Aftermath") and defender.fainted:
                self.announce_ability(defender)
                self.damage(attacker, ceil(attacker.hp / 4))
            if defender.has_ability("Effect Spore") and (r := random.random()) < 0.3:
                if not (grass in attacker.types):
                    if r < 0.1 and self.field.can_apply_status(defender, attacker, mild_poison):
                        self.announce_ability(defender)
                        self.apply_status(attacker, mild_poison)
                    elif 0.1 <= r < 0.2 and self.field.can_apply_status(defender, attacker, paralysis):
                        self.announce_ability(defender)
                        self.apply_status(attacker, paralysis)
                    elif 0.2 <= r and self.field.can_apply_status(defender, attacker, sleep):
                        self.announce_ability(defender)
                        self.apply_status(attacker, sleep)
            if defender.has_ability("Flame Body") and random.random() < 0.3:
                if self.field.can_apply_status(defender, attacker, burn):
                    self.announce_ability(defender)
                    self.apply_status(attacker, burn)
            if defender.has_ability("Gooey", "Tangling Hair"):
                self.announce_ability(defender)
                self.apply_stat_change(attacker, {"Spe": -1})
            if defender.has_ability("Iron Barbs", "Rough Skin"):
                self.announce_ability(defender)
                self.damage(attacker, ceil(attacker.hp / 8))
            if defender.has_ability("Poison Point") and random.random() < 0.3:
                if self.field.can_apply_status(defender, attacker, mild_poison):
                    self.announce_ability(defender)
                    self.apply_status(attacker, mild_poison)
            if defender.has_ability("Static") and random.random() < 0.3:
                if self.field.can_apply_status(defender, attacker, paralysis):
                    self.announce_ability(defender)
                    self.apply_status(attacker, paralysis)

        if move.user_stat_changes:
            if random.random() < move.user_stat_changes.chance / 100:
                self.apply_stat_change(attacker, move.user_stat_changes)
        if move.target_stat_changes:
            if random.random() < move.target_stat_changes.chance / 100:
                self.apply_stat_change(defender, move.target_stat_changes)
        if move.status_condition:
            if self.field.can_apply_status(attacker, defender, move.status_condition.condition) and \
                    (random.random() < move.status_condition.chance / 100):
                self.apply_status(defender, move.status_condition.condition)

        if move["change_weather"] and self.field.can_change_weather(move["change_weather"]):
            self.change_weather(move["change_weather"])

        if move["change_terrain"] and self.field.terrain != move["change_terrain"]:
            self.change_terrain(move["change_terrain"])

        if move["reflect"] and not self.field.side(attacker).reflect:
            self.field.side(attacker).set_reflect()
            self.output(f"Reflect protected {self.possessive(attacker)} team against physical moves!")

        if move["light_screen"] and not self.field.side(attacker).light_screen:
            self.field.side(attacker).set_light_screen()
            self.output(f"Light Screen protected {self.possessive(attacker)} team against special moves!")

        if move["aurora_veil"] and not self.field.side(attacker).aurora_veil:
            self.field.side(attacker).set_aurora_veil()
            self.output(f"Aurora Veil protected {self.possessive(attacker)} team against physical and special moves!")

        if move["confuse"] and self.field.can_confuse(defender):
            if random.random() < move["confuse"] / 100:
                defender["confused"] = True
                defender["confusion_timer"] = random.choice([2, 3, 4])
                self.output(f"{self.name(defender)} became confused!")

        if move["flinch"]:
            if random.random() < move["flinch"] / 100:
                defender["flinching"] = True

        if move["protect"]:
            if random.random() < 1 / (3 ** attacker.get("successive_uses", 0)):
                attacker["protecting"] = True
                attacker["successive_uses"] = attacker.get("successive_uses", 0) + 1
                self.output(f"{self.name(attacker)} protected itself!")
            else:
                attacker.clear("successive_uses")
                self.output("But it failed!")

        if move["after_you"]:
            defender["moving_next"] = True
            self.output(f"{self.name(defender)} took the kind offer!")

        if move["trick_room"]:
            self.field.toggle_trick_room()
            if self.field.trick_room:
                self.output(f"{self.name(attacker)} twisted the dimensions!")
            else:
                self.output("The twisted dimensions returned to normal.")

        if move["absorbent"]:
            self.output(f"{self.name(defender)} had its energy drained!")
            self.heal(attacker, ceil(defender.get("last_damage_taken", 0) * 0.5))

    def use_move(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if attacker.has_taken_turn and not attacker.has_executed_move:
            return  # if the mon previously failed to execute its move against a different target, don't try again

        attacker.has_taken_turn = True

        if not (attacker.has_executed_move or self.can_execute(attacker, move)):
            return

        if not attacker.has_executed_move:
            self.output(f"{self.name(attacker)} used {move.name}!")
            move.deduct_pp()
            attacker.has_executed_move = True

        move = self.field.apply_conditionals(attacker, move)

        if not self.but_it_failed(attacker, defender, move):
            attacker.failed_last_attack = True
            return
        else:
            attacker.failed_last_attack = False

        self.move_modifications(attacker, defender, move)

        self.pre_hit_effects(attacker, defender, move)

        attacker.has_landed_move = True

        if move.category != status:
            damage = self.field.damage_roll(attacker, defender, move)

            if damage.get("crit"):
                self.output(
                    f"A critical hit on {self.name(defender, False)}!"
                    if len(attacker.targets) > 1 else "A critical hit!"
                )

            if damage.get("effectiveness", 1) > 1:
                self.output(
                    f"It's super effective on {self.name(defender, False)}!"
                    if len(attacker.targets) > 1 else "It's super effective!"
                )
            elif damage.get("effectiveness", 1) < 1:
                self.output(
                    f"It's not very effective on {self.name(defender, False)}..."
                    if len(attacker.targets) > 1 else "It's not very effective..."
                )

            self.damage(defender, damage["damage"])
            defender["last_damage_taken"] = damage["damage"]

        self.move_effects(attacker, defender, move)

    def individual_end_of_turn(self, mon: FieldMon):
        if not mon.fainted:
            mon.has_taken_turn = False
            mon.has_executed_move = False
            mon.has_landed_move = False
            mon.next_action = None
            mon.targets = []

            mon.clear("protecting")
            mon.clear("flinching")

            if mon.status_condition == burn:
                self.damage(mon, ceil(mon.hp / 16), "damage from its burn")
            elif mon.status_condition == mild_poison:
                self.damage(mon, ceil(mon.hp / 8), "damage from poison")
            elif mon.status_condition == bad_poison:
                mon.status_timer += 1
                self.damage(mon, ceil(mon.hp * mon.status_timer / 16), "damage from poison")
            if mon.fainted:
                return

            if self.field.active_weather == sandstorm and not mon.immune_to_sand:
                self.damage(mon, ceil(mon.hp / 16), "damage from the sandstorm")
            if mon.fainted:
                return

            if self.field.terrain == grassy_terrain and self.field.is_grounded(mon):
                self.heal(mon, ceil(mon.hp / 16), "HP from Grassy Terrain")

            self.team(mon).update_mon(mon)

    def send_out_replacements(self):
        for mon in self.fielded_mons:
            if mon.fainted:
                if self.team(mon).reserves:
                    self.deploy_mon(mon.team_id, self.team(mon).get_replacement(mon.position), mon.position)
                else:
                    self.field.deploy_mon(None, mon.position)

    def end_of_turn(self):
        for mon in self.fielded_mons:
            self.individual_end_of_turn(mon)
        if self.check_winner() is not None:
            return

        for n, side in enumerate(self.field.sides):
            if side.reflect and side.reflect_timer > 0:
                side.reflect_timer -= 1
                if side.reflect_timer == 0:
                    side.set_reflect(False)
                    self.output(("Your team's" if n == self.pov else "Opponent's") + " Reflect wore off!")
            if side.light_screen and side.light_screen_timer > 0:
                side.light_screen_timer -= 1
                if side.light_screen_timer == 0:
                    side.set_light_screen(False)
                    self.output(("Your team's" if n == self.pov else "Opponent's") + " Light Screen wore off!")
            if side.aurora_veil and side.aurora_veil_timer > 0:
                side.aurora_veil_timer -= 1
                if side.aurora_veil_timer == 0:
                    side.set_aurora_veil(False)
                    self.output(("Your team's" if n == self.pov else "Opponent's") + " Aurora Veil wore off!")

        if self.last_output:
            self.output("", 0)
        if self.field.weather is not None and self.field.weather_timer > 0:
            self.field.weather_timer -= 1
            if self.field.weather_timer == 0:
                self.change_weather(None)
            else:
                self.output(weather_texts[self.field.weather][1])
        if self.field.terrain is not None and self.field.terrain_timer > 0:
            self.field.terrain_timer -= 1
            if self.field.terrain_timer == 0:
                self.change_terrain(None)
        if self.field.trick_room:
            self.field.trick_room_timer -= 1
            if self.field.trick_room_timer == 0:
                self.field.trick_room = False
                self.output("The twisted dimensions returned to normal.")

        if self.last_output:
            self.output("", 0)
        self.send_out_replacements()

    def check_fainted(self, mon: FieldMon):
        if mon.remaining_hp == 0 and not mon.fainted:
            mon.fainted = True
            self.output(f"{self.name(mon)} fainted!")
            self.team(mon).recall_mon(mon)

    def check_winner(self) -> int | None:
        for n, t in enumerate(self.teams):
            if all(g.get("fainted") for g in t.mons.values()):
                return int(not n)

    def output_winner(self):
        if (winner := self.check_winner()) is not None:
            return self.output(self.spaced(f"{self.team(winner).trainer} wins!"), 0)

    def special_actions(self, mon: FieldMon):
        mon.has_taken_turn = True
        if mon.next_action == "!unplugged":
            self.output(f"{self.name(mon)}'s Controller is unplugged. Try using a Player or BasicAI object.")
        if mon.next_action == "!switch":
            self.deploy_mon(mon.team_id, mon.targets[0], mon.position)

    def run(self):
        self.init_battle()

        while True:
            self.turn_count += 1
            for mon in self.fielded_mons:
                mon.turn_on_field += 1
            self.output(self.spaced(
                f"[ TURN {self.turn_count} ]\n\n" +
                (f"{self.field.summary()}\n\n" if self.field.summary() else "") +
                f"{self.field.diagram(from_side=self.pov)}\n"
            ))

            for team in self.teams:
                team.set_actions()

            while mon := self.next_to_move():  # dynamic turn order - iterate over each mon once
                mon.clear("moving_next")
                if mon.next_action.startswith("!"):
                    self.special_actions(mon)
                else:
                    self.double_check_targets(mon)
                    if not mon.targets:
                        self.output(f"{self.name(mon)} has no valid targets for {mon.move_selection.name}!")
                    else:
                        for target in mon.targets:
                            self.use_move(mon, self.at(target), mon.moves[mon.next_action])
                            if self.check_winner() is not None:
                                return self.output_winner()
                self.output("", 0)

            self.end_of_turn()
            if self.check_winner() is not None:
                return self.output_winner()
