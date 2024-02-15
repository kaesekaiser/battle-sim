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
        if available := [g for g in self.mons.values() if not (g.get("on_field") or g.get("fainted"))]:
            return available[0]["id"]
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
            selection = input("Input a move: ")
            if can_int(selection):
                if not (1 <= int(selection) <= len(mon.moves)):
                    continue
                else:
                    move = mon.move_names[int(selection) - 1]
            else:
                move = fixed_moves.get(fix(selection))
            if move in mon.moves and (targets := self.get_targets(mon.position, all_moves[move])):
                mon.next_action = move
                mon.targets = targets
                return

    def get_targets(self, position: int, move: Move) -> list[int]:
        possible_targets = self.field.targets(position, move.target)
        if move.is_single_target:
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

    def get_replacement(self, position: int) -> int:
        outgoing_mon = self.field.at(position)
        print(f"{self.inline_display()}\n")
        while True:
            selection = input(f"Which mon will replace {outgoing_mon.name}? ")
            try:
                selection = int(selection.strip())
            except ValueError:
                continue
            else:
                if self.at(selection - 1) in self.reserves:
                    print()
                    return self.order[selection - 1]
