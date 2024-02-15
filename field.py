from teams import *


class Field:
    def __init__(self, size: int = 1):
        if not (1 <= size <= 3):
            raise ValueError("Size must be between 1 and 3.")
        self.size = size

        self.positions = {}  # position (int): mon (FieldMon | None)

    def deploy_mon(self, mon: FieldMon | None, position: int):
        self.positions[position] = mon

    def at(self, position: int) -> FieldMon | None:
        return self.positions.get(position)

    @property
    def fielded_mons(self) -> list[FieldMon]:
        return [g for g in self.positions.values() if g is not None]

    @property
    def living_mons(self) -> list[FieldMon]:
        return [g for g in self.fielded_mons if g]

    def targets(self, from_position: int, target: str) -> list[int]:
        if target == "user" or target == "all":
            return [from_position]
        if self.size == 1:
            return [int(not from_position)]

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

    def diagram(self, select: list[int] = (), from_side: int = 0, include_hp: bool = True):
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
        return "\n".join(
            " ".join(j.ljust(max_lengths[n]) for n, j in enumerate(g)) for g in ret
        )
