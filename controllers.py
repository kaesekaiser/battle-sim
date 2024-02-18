from field import *


def can_int(s: str) -> bool:
    try:
        int(s)
    except ValueError:
        return False
    else:
        return True


class Controller(Team):
    def __init__(self, mons: list[MiniMon] = (), **kwargs):
        super().__init__(mons, **kwargs)
        self.field = None

    def set_field(self, field: Field):
        self.field = field

    @property
    def fielded_mons(self) -> list[FieldMon]:
        return [g for g in self.field.fielded_mons if g.team_id == self.id]

    @property
    def opponent_mons(self) -> list[FieldMon]:
        return [g for g in self.field.fielded_mons if g.team_id != self.id]

    def set_actions(self):
        """Sets the next_action attribute for each of its controlled FieldMons."""
        for mon in self.fielded_mons:
            mon.next_action = "!unplugged"

    def get_replacement(self, position: int) -> int:
        """Gets the ID number of a replacement for a mon that fainted in the preceding turn."""
        if self.reserves:
            return self.reserves[0]["id"]
        return None


class Player(Controller):
    def __init__(self, mons: list[MiniMon] = (), **kwargs):
        super().__init__(mons, **kwargs)

    def set_actions(self):
        for mon in self.fielded_mons:
            self.get_action(mon)
            print()

    def get_action(self, mon: FieldMon):
        print(f"What will {mon.name} do?\n" + ("\n".join(g.inline_display() for g in mon.moves.values())))
        while True:
            selection = fix(input("Input a move: "))
            if can_int(selection):
                if not (1 <= int(selection) <= len(mon.moves)):
                    continue
                else:
                    move = mon.move_names[int(selection) - 1]
            elif selection == "switch":
                if not self.reserves:
                    print("There are no available mons to switch to!")
                    continue
                print()
                if (switch := self.switch_dialog(mon)) == "cancel":
                    continue
                else:
                    mon.next_action = f"!switch"
                    mon.targets = [switch]
                    self.mons[mon.id]["field_status"] = "switching out"
                    self.mons[switch]["field_status"] = "switching in"
                    print(f"{MiniMon.from_mini_pack(self.mons[switch]).name} will switch in for {mon.name}.")
                    return
            else:
                move = fixed_moves.get(selection)
            if move in mon.moves:
                if not mon.moves[move].remaining_pp:
                    print(f"{move} has no PP remaining!")
                    continue
                if targets := self.get_targets(mon.position, all_moves[move]):
                    mon.next_action = move
                    mon.targets = targets
                    return

    def get_targets(self, position: int, move: Move) -> list[int]:
        possible_targets = self.field.targets(position, move.target)
        if move.is_single_target and len(possible_targets) > 1:
            while True:
                selection = input("Which position will you target? ")
                try:
                    selection = int(selection.strip())
                except ValueError:
                    continue
                else:
                    if selection - 1 in possible_targets:
                        return [selection - 1]

        if "all" in move.targs and not possible_targets:
            print("No valid targets for that move!")
        return possible_targets

    def switch_dialog(self, outgoing_mon: FieldMon, force: bool = False) -> int | str:
        print(f"{self.inline_display()}\n")
        while True:
            selection = fix(input(f"Which mon will replace {outgoing_mon.name}? "))
            if can_int(selection):
                if self.at(int(selection) - 1) in self.reserves:
                    return self.order[int(selection) - 1]
            if (not force) and selection in ["exit", "back", "cancel"]:
                return "cancel"

    def get_replacement(self, position: int) -> int:
        return self.switch_dialog(self.field.at(position), force=True)
