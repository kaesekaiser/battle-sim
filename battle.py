from teams import *
from time import sleep
from random import random, randrange


def can_int(s: str) -> bool:
    try:
        int(s)
    except ValueError:
        return False
    else:
        return True


def raw_damage(attacker_level: int, attacking_stat: int, defending_stat: int, power: int):
    return round((2 * attacker_level / 5 + 2) * power * attacking_stat / defending_stat / 50 + 2)


class Battle:
    def __init__(self, teams: list[Team], size: int = 1):
        self.teams = teams[:2]
        teams[0].change_id(0)
        teams[1].change_id(1)

        if not (1 <= size <= 3):
            raise ValueError("Size must be between 1 and 3.")
        self.size = size

        self.field_positions = {}  # position (int): mon (FieldMon | None)
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
            self.field_positions[position] = FieldMon.from_json(mon | {"position": position})
            mon["on_field"] = True
            if announce:
                self.output(f"{self.teams[team_id].trainer} sent out {self.at(position).name}!")
        else:
            self.field_positions[position] = None

    def at(self, position: int) -> FieldMon | None:
        return self.field_positions.get(position)

    @property
    def active_mons(self) -> list[FieldMon]:
        return [g for g in self.field_positions.values() if g is not None]

    def field_diagram(self, select: list[int] = (), from_side: int = 0, include_hp: bool = True):
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
        return ("" if self.last_output == "" else "\n") + ("\n".join(
            " ".join(j.ljust(max_lengths[n]) for n, j in enumerate(g)) for g in ret
        )) + "\n"

    def init_battle(self):
        for n in range(self.size):
            self.deploy_mon(0, n, n)
        for n in range(self.size, self.size * 2):
            self.deploy_mon(1, n % self.size + 6, self.size * 3 - 1 - n)  # deploy to trainer's left

    def get_targets(self, from_position: int, target: str, return_possible: bool = False) -> list[int]:
        if target == "user" or target == "all":
            return [from_position]
        if self.size == 1:
            return [int(not from_position)]

        possible_targets = [k for k, v in self.field_positions.items() if v]
        args = target.split("-")
        if "adj" in args:
            possible_targets = [g for g in possible_targets if -1 <= g % self.size - from_position % self.size <= 1]
        if "foe" in args:
            possible_targets = [g for g in possible_targets if g // self.size != from_position // self.size]
        if "ally" in args:
            possible_targets = [g for g in possible_targets if g // self.size == from_position // self.size]
        if from_position in possible_targets and "user" not in args:
            possible_targets.remove(from_position)

        if return_possible:
            return possible_targets

        if "all" in args or len(possible_targets) == 1:
            if not possible_targets:
                self.output("No valid targets for this move!")
            return possible_targets
        else:
            # self.output(self.field_diagram(select=possible_targets, from_side=(from_position >= self.size)), 0)
            while True:
                selection = input("Which position will you target? ")
                try:
                    selection = int(selection.strip())
                except ValueError:
                    continue
                else:
                    if selection - 1 in possible_targets:
                        return [selection - 1]

    def get_action(self, mon: FieldMon):
        self.output(f"What will {mon.name} do?\n" + ("\n".join(g.inline_display() for g in mon.moves.values())), 0)
        while True:
            selection = input("Input a move: ")
            if can_int(selection):
                if not (1 <= int(selection) <= len(mon.moves)):
                    continue
                else:
                    move = mon.move_names[int(selection) - 1]
            else:
                move = fixed_moves.get(fix(selection))
            if move in mon.moves and (targets := self.get_targets(mon.position, all_moves[move].target)):
                mon.next_action = move
                mon.targets = targets
                self.output("", 0)
                return

    def turn_order(self) -> list[FieldMon]:
        priorities = [
            [
                g.next_action_priority,
                g.spe,
                random(),
                g.position
            ] for g in self.active_mons
        ]
        return [self.field_positions[g[3]] for g in sorted(priorities, reverse=True)]

    def double_check_targets(self, mon: FieldMon):
        if not mon.move_selection:
            return
        possible_targets = self.get_targets(mon.position, mon.move_selection.target, return_possible=True)
        if not (new_targets := [g for g in mon.targets if g in possible_targets]):
            if len(mon.targets) == 1 and len(possible_targets) >= 1:
                mon.targets = [possible_targets[0]]
            else:
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
        for mon in self.active_mons:
            self.individual_end_of_turn(mon)

    def individual_end_of_turn(self, mon: FieldMon):
        if mon.fainted:
            if self.teams[mon.team_id].has_reserves(self.size):
                self.deploy_mon(mon.team_id, self.get_replacement(mon.position), mon.position)
            else:
                self.field_positions[mon.position] = None
        else:
            mon["has_executed"] = False
            mon.next_action = None
            mon.targets = []

    def get_replacement(self, position: int) -> int:
        outgoing_mon = self.at(position)
        team = self.teams[outgoing_mon.team_id]
        self.output(("" if self.last_output == "" else "\n") + f"{team.inline_display()}\n", 0)
        while True:
            selection = input(f"Which mon will replace {outgoing_mon.name}? ")
            try:
                selection = int(selection.strip())
            except ValueError:
                continue
            else:
                if selection - 1 in range(len(team)) and not team.at(selection - 1).get("fainted") \
                        and not team.at(selection - 1).get("on_field"):
                    return team.order[selection - 1]

    def check_fainted(self, mon: FieldMon):
        if mon.remaining_hp == 0 and not mon.fainted:
            mon.fainted = True
            self.output(f"{mon.name} fainted!")
            self.teams[mon.team_id].set_mon(mon.json(), mon.id)

    def check_winner(self) -> int | None:
        for n, t in enumerate(self.teams):
            if all(g.get("fainted") for g in t.mons.values()):
                return int(not n)

    def output_winner(self):
        if (winner := self.check_winner()) is not None:
            return self.output(f"{self.teams[winner].trainer} wins!", 0)

    def run(self):
        self.init_battle()

        while True:
            self.output(self.field_diagram())

            for mon in self.active_mons:
                self.get_action(mon)

            for mon in self.turn_order():
                if not mon.fainted:
                    self.double_check_targets(mon)
                    for target in mon.targets:
                        self.use_move(mon, self.at(target), mon.moves[mon.next_action])
                        if self.check_winner() is not None:
                            return self.output_winner()
                    self.output("", 0)

            self.end_of_turn()
