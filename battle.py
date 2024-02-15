from controllers import *
from time import sleep
from random import random, randrange


def raw_damage(attacker_level: int, attacking_stat: int, defending_stat: int, power: int):
    return round((2 * attacker_level / 5 + 2) * power * attacking_stat / defending_stat / 50 + 2)


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
            if announce:
                if self.at(position):
                    self.output(f"{self.teams[team_id].trainer} recalled {self.at(position).name}!")
            self.field.deploy_mon(FieldMon.from_json(mon | {"position": position}), position)
            mon["on_field"] = True
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

    def get_damage(self, attacker: FieldMon, defender: FieldMon, move: Move):
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
        # 1.5 if it's a crit

        multipliers.append(randrange(85, 101) / 100)

        type_eff = defender.type_effectiveness(move.type)
        if type_eff > 1:
            self.output(
                f"It's super effective on {defender.name}!" if len(attacker.targets) > 1
                else "It's super effective!"
            )
        if type_eff < 1:
            self.output(
                f"It's not very effective on {defender.name}..." if len(attacker.targets) > 1
                else "It's not very effective..."
            )
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

        attack_stat = attacker.atk if move.category == physical else attacker.spa
        defense_stat = defender.dfn if move.category == physical else defender.spd

        return max(1, round(raw_damage(attacker.level, attack_stat, defense_stat, move.power) * product(multipliers)))

    def use_move(self, attacker: FieldMon, defender: FieldMon, move: Move):
        if not (self.can_execute(attacker, move) or attacker["has_executed"]):
            return

        if not attacker["has_executed"]:
            self.output(f"{attacker.name} used {move.name}!")
            move.deduct_pp()
            attacker["has_executed"] = True

        move = copy(move)  # create copy after deducting PP to avoid permanently changing move power, etc.

        if not self.accuracy_check(attacker, defender, move):
            return self.output(f"{attacker.name}'s attack missed!")

        damage = self.get_damage(attacker, defender, move)
        damage_dealt = defender.damage(damage)
        self.output(f"{defender.name} took {damage_dealt} damage! (-> {defender.remaining_hp}/{defender.hp} HP)")
        self.check_fainted(defender)

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
            self.teams[mon.team_id].update_mon(mon)

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
