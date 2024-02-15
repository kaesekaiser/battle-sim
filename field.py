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
    def active_mons(self) -> list[FieldMon]:
        return [g for g in self.positions.values() if g is not None]

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
