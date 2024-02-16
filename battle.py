from controllers import *
from time import sleep
from random import random


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

    def output(self, text: str, sleep_time: float = 0.5):
        print(text)
        self.last_output = text.split("\n")[-1]
        if sleep_time:
            sleep(sleep_time)

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

    def init_battle(self):
        for n in range(self.size):
            self.deploy_mon(0, n, n)
        for n in range(self.size, self.size * 2):
            self.deploy_mon(1, n % self.size + 6, self.size * 3 - 1 - n)  # deploy to trainer's left

    def turn_order(self) -> list[FieldMon]:
        priorities = [
            [
                g.next_action_priority,
                g.spe,
                random(),
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

    def can_execute(self, attacker: FieldMon, move: Move):
        """Checks that prevent the execution of a move (e.g. being frozen, priority on PTerrain) before it happens."""
        if attacker["no_target"]:
            self.output(f"{attacker.name} has no valid targets for {move.name}!")
            return False
        return True

    def accuracy_check(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if not move.accuracy:
            return True
        if random() < move.accuracy / 100:
            return True
        return False

    def but_it_failed(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if self.field.move_effectiveness(attacker, defender, move) == 0:
            return self.output(f"It doesn't affect {defender.name}...")
        if not self.accuracy_check(attacker, defender, move):
            return self.output(f"{attacker.name}'s attack missed!")
        return True

    def display_stat_change(self, mon: FieldMon, stat_change: dict[str, int]):
        for stat, change in stat_change.items():
            self.output(f"{mon.name}'s {stat_names[stat]} {stat_change_texts[change]}!")

    def move_effects(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if move.user_stat_changes:
            if random() < move.user_stat_changes.chance / 100:
                changes = attacker.apply(move.user_stat_changes)
                self.display_stat_change(attacker, changes)
        if move.target_stat_changes:
            if random() < move.target_stat_changes.chance / 100:
                changes = defender.apply(move.target_stat_changes)
                self.display_stat_change(defender, changes)

    def use_move(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if not (self.can_execute(attacker, move) or attacker["has_executed"]):
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

        if (eff := self.field.move_effectiveness(attacker, defender, move)) > 1:
            self.output(
                f"It's super effective on {defender.name}!"
                if len(attacker.targets) > 1 else "It's super effective!"
            )
        elif eff < 1:
            self.output(
                f"It's not very effective on {defender.name}..."
                if len(attacker.targets) > 1 else "It's not very effective..."
            )

        if move.category != status:
            damage = self.field.damage_roll(attacker, defender, move)
            damage_dealt = defender.damage(damage)
            self.output(f"{defender.name} took {damage_dealt} damage! (-> {defender.remaining_hp}/{defender.hp} HP)")
            self.check_fainted(defender)

        self.move_effects(attacker, defender, move)

    def end_of_turn(self):
        for mon in self.fielded_mons:
            self.individual_end_of_turn(mon)
        if self.last_output:
            self.output("", 0)

    def individual_end_of_turn(self, mon: FieldMon):
        if mon.fainted:
            if self.teams[mon.team_id].reserves:
                self.deploy_mon(mon.team_id, self.teams[mon.team_id].get_replacement(mon.position), mon.position)
            else:
                self.field.deploy_mon(None, mon.position)
        else:
            mon["has_executed"] = False
            mon.next_action = None
            mon.targets = []

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
            return self.output(f"{self.teams[winner].trainer} wins!", 0)

    def special_actions(self, mon: FieldMon):
        if mon.next_action == "!unplugged":
            self.output(f"{mon.name}'s Controller is unplugged. Try using a Player or BasicAI object.")
        if mon.next_action.startswith("!switch"):
            new_id = int(mon.next_action.split(":")[1])
            self.deploy_mon(mon.team_id, new_id, mon.position)

    def run(self):
        self.init_battle()
        self.output("", 0)

        while True:
            self.output(self.field.diagram() + "\n")

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
