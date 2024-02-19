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


class Battle:
    def __init__(self, teams: list[Controller], size: int = 1):
        self.teams = teams[:2]
        teams[0].change_id(0)
        teams[1].change_id(1)

        if not (1 <= size <= 3):
            raise ValueError("Size must be between 1 and 3.")
        self.size = size

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

    def deploy_mon(self, team_id: int, mon_id: int, position: int, announce: bool = True):
        if mon := self.teams[team_id][mon_id]:
            if self.at(position):
                if announce:
                    self.output(f"{self.teams[team_id].trainer} recalled {self.at(position).name}!")
                self.teams[team_id].recall_mon(self.at(position))
            self.field.deploy_mon(FieldMon.from_json(mon | {"position": position}), position)
            mon["field_status"] = "on field"
            if announce:
                self.output(f"{self.teams[team_id].trainer} sent out {self.at(position).name}!")
        else:
            self.field.deploy_mon(None, position)

    def at(self, position: int) -> FieldMon | None:
        return self.field.at(position)

    @property
    def fielded_mons(self) -> list[FieldMon]:
        return self.field.fielded_mons

    def get_stat(self, mon: FieldMon, stat: str) -> int:
        return self.field.get_stat(mon, stat)

    def init_battle(self):
        for n in range(self.size):
            self.deploy_mon(0, n, n)
        for n in range(self.size, self.size * 2):
            self.deploy_mon(1, n % self.size + 6, self.size * 3 - 1 - n)  # deploy to trainer's left

    def turn_order(self) -> list[FieldMon]:
        priorities = [
            [
                g.next_action_priority,
                self.field.get_stat(g, "Spe"),
                random.random(),
                g.position
            ] for g in self.fielded_mons
        ]
        return [self.at(g[3]) for g in sorted(priorities, reverse=True)]

    def double_check_targets(self, mon: FieldMon):
        if not mon.move_selection:
            return
        possible_targets = self.field.targets(mon.position, mon.move_selection.target)
        if not (new_targets := [g for g in mon.targets if g in possible_targets]):
            if mon.move_selection.is_single_target:
                if same_side_targets := [g for g in possible_targets if g // self.size == mon.targets[0] // self.size]:
                    mon.targets = [same_side_targets[0]]
                    return
            mon["no_target"] = True
            mon.targets = [mon.position]
        else:
            mon.targets = new_targets

    def damage(self, mon: FieldMon, damage: int, description: str = "damage"):
        damage_dealt = mon.damage(damage)
        self.output(f"{mon.name} took {damage_dealt} {description}! (-> {mon.remaining_hp}/{mon.hp} HP)")
        self.check_fainted(mon)

    def can_execute(self, attacker: FieldMon, move: Move):
        """Checks that prevent the execution of a move (e.g. being frozen, priority on PTerrain) before it happens."""
        if attacker.status_condition == freeze:
            if move["thaws_user"] or (random.random() < 0.2):  # note to self: prevent thawing if Burn Up would fail
                self.apply_status(attacker, None)
                self.output(f"{attacker.name} thawed out!")
            else:
                self.output(f"{attacker.name} is frozen solid!")
                return False
        elif attacker.status_condition == paralysis:
            if random.random() < 0.25:
                self.output(f"{attacker.name} is paralyzed! It can't move!")
                return False
        elif attacker.status_condition == sleep:
            if attacker.status_timer == 0:
                self.output(f"{attacker.name} woke up!")
                self.apply_status(attacker, None)
            else:
                self.output(f"{attacker.name} is fast asleep.")
                attacker.status_timer -= 1
                return False
        if attacker["no_target"]:
            self.output(f"{attacker.name} has no valid targets for {move.name}!")
            return False
        return True

    def accuracy_check(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if not move.accuracy:
            return True
        if random.random() < move.accuracy / 100 * self.get_stat(attacker, "Acc") / self.get_stat(defender, "Eva"):
            return True
        return False

    def but_it_failed(self, attacker: FieldMon, defender: FieldMon, move: Move) -> bool | None:
        if self.field.move_effectiveness(attacker, defender, move) == 0:
            return self.output(f"It doesn't affect {defender.name}...")
        if not self.accuracy_check(attacker, defender, move):
            return self.output(f"{attacker.name}'s attack missed!")
        if move.category == status and move.total_effects == 1 and len(attacker.targets) == 1:  # you had one job!
            if move.status_condition and \
                    not self.field.can_apply_status(attacker, defender, move.status_condition.condition):
                return self.output("But it failed!")
            if move["change_weather"] and not self.field.can_change_weather(move["change_weather"]):
                return self.output("But it failed!")
        return True

    def display_stat_change(self, mon: FieldMon, stat_change: dict[str, int]):
        for stat, change in stat_change.items():
            self.output(f"{mon.name}'s {stat_names[stat]} {stat_change_texts[change]}!")

    def apply_status(self, mon: FieldMon, condition: str | None):
        mon.status_condition = condition
        if condition == sleep:
            mon.status_timer = random.choice([1, 2, 3])
        else:
            mon.status_timer = 0
        if condition:
            self.output(f"{mon.name} {status_condition_texts[condition]}!")

    def change_weather(self, weather: str | None, turns: int = 5):
        if weather:
            self.field.set_weather(weather, turns)
            self.output(weather_texts[weather][0])
        elif self.field.weather is not None:
            self.output(weather_texts[self.field.weather][2])
            self.field.set_weather(None)

    def move_effects(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if defender.status_condition == freeze and move.thaws_target:
            self.apply_status(defender, None)
            self.output(f"{defender.name} was thawed out!")

        if move.user_stat_changes:
            if random.random() < move.user_stat_changes.chance / 100:
                changes = attacker.apply(move.user_stat_changes)
                self.display_stat_change(attacker, changes)
        if move.target_stat_changes:
            if random.random() < move.target_stat_changes.chance / 100:
                changes = defender.apply(move.target_stat_changes)
                self.display_stat_change(defender, changes)
        if move.status_condition:
            if self.field.can_apply_status(attacker, defender, move.status_condition.condition) and \
                    (random.random() < move.status_condition.chance / 100):
                self.apply_status(defender, move.status_condition.condition)

        if move["change_weather"] and self.field.can_change_weather(move["change_weather"]):
            self.change_weather(move["change_weather"])

    def use_move(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if attacker["has_attempted"] and not attacker["has_executed"]:
            return  # if the mon previously failed to execute its move against a different target, don't try again

        attacker["has_attempted"] = True

        if not (attacker["has_executed"] or self.can_execute(attacker, move)):
            return

        if not attacker["has_executed"]:
            self.output(f"{attacker.name} used {move.name}!")
            move.deduct_pp()
            attacker["has_executed"] = True

        move = copy(move)  # create copy after deducting PP to avoid permanently changing move power, etc.

        if not self.but_it_failed(attacker, defender, move):
            attacker["failed_attack"] = True
            return
        else:
            attacker["failed_attack"] = False

        if move.category != status:
            damage = self.field.damage_roll(attacker, defender, move)

            if damage["crit"]:
                self.output(f"A critical hit on {defender.name}!" if len(attacker.targets) > 1 else "A critical hit!")

            if damage["effectiveness"] > 1:
                self.output(
                    f"It's super effective on {defender.name}!"
                    if len(attacker.targets) > 1 else "It's super effective!"
                )
            elif damage["effectiveness"] < 1:
                self.output(
                    f"It's not very effective on {defender.name}..."
                    if len(attacker.targets) > 1 else "It's not very effective..."
                )

            self.damage(defender, damage["damage"])

        self.move_effects(attacker, defender, move)

    def individual_end_of_turn(self, mon: FieldMon):
        if not mon.fainted:
            mon["has_attempted"] = False
            mon["has_executed"] = False
            mon.next_action = None
            mon.targets = []

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

            self.teams[mon.team_id].update_mon(mon)

    def send_out_replacements(self):
        for mon in self.fielded_mons:
            if mon.fainted:
                if self.teams[mon.team_id].reserves:
                    self.deploy_mon(mon.team_id, self.teams[mon.team_id].get_replacement(mon.position), mon.position)
                else:
                    self.field.deploy_mon(None, mon.position)

    def end_of_turn(self):
        for mon in self.fielded_mons:
            self.individual_end_of_turn(mon)
        if self.check_winner() is not None:
            return

        if self.last_output:
            self.output("", 0)

        if self.field.weather is not None and self.field.weather_timer > 0:
            self.field.weather_timer -= 1
            if self.field.weather_timer == 0:
                self.change_weather(None)
            else:
                self.output(weather_texts[self.field.weather][1])

        self.send_out_replacements()

    def check_fainted(self, mon: FieldMon):
        if mon.remaining_hp == 0 and not mon.fainted:
            mon.fainted = True
            self.output(f"{mon.name} fainted!")
            self.teams[mon.team_id].recall_mon(mon)

    def check_winner(self) -> int | None:
        for n, t in enumerate(self.teams):
            if all(g.get("fainted") for g in t.mons.values()):
                return int(not n)

    def output_winner(self):
        if (winner := self.check_winner()) is not None:
            return self.output(self.spaced(f"{self.teams[winner].trainer} wins!"), 0)

    def special_actions(self, mon: FieldMon):
        if mon.next_action == "!unplugged":
            self.output(f"{mon.name}'s Controller is unplugged. Try using a Player or BasicAI object.")
        if mon.next_action == "!switch":
            self.deploy_mon(mon.team_id, mon.targets[0], mon.position)

    def run(self):
        self.init_battle()

        while True:
            self.turn_count += 1
            self.output(self.spaced(f"[ TURN {self.turn_count} ]\n\n{self.field.diagram()}\n"))

            for team in self.teams:
                team.set_actions()

            for mon in self.turn_order():
                if not mon.fainted:
                    if mon.next_action.startswith("!"):
                        self.special_actions(mon)
                    else:
                        self.double_check_targets(mon)
                        for target in mon.targets:
                            self.use_move(mon, self.at(target), mon.moves[mon.next_action])
                            if self.check_winner() is not None:
                                return self.output_winner()
                    self.output("", 0)

            self.end_of_turn()
            if self.check_winner() is not None:
                return self.output_winner()
