from mons import *


class Team:
    def __init__(self, mons: list[MiniMon] = (), **kwargs):
        self._size = kwargs.get("size", 6)

        self.mons = {}
        self.order = []
        for mon in mons:
            self.add_mon(mon)

        self.id = kwargs.get("id", -1)
        self.trainer = kwargs.get("trainer", "Trainer")

    def __getitem__(self, item: int) -> dict | None:
        return self.mons.get(item)

    def __len__(self):
        return len(self.mons)

    def json(self):
        return {"trainer": self.trainer, "mons": [g for g in self.mons.values()]} | \
            ({"id": self.id} if self.id != -1 else {}) | \
            ({"size": self._size} if self._size != 6 else {})

    @staticmethod
    def from_json(js: dict):
        return Team(**js)

    def set_mon(self, mon: MiniMon | dict, id_no: int):
        if isinstance(mon, dict):
            self.mons[id_no] = mon | {"id": id_no}
        else:
            self.mons[id_no] = mon.deploy(id=id_no).json()

    def add_mon(self, mon: MiniMon):
        if len(self.mons) < self._size:
            self.set_mon(mon, len(self.mons))
            self.order.append(len(self.order))

    def swap_ids(self, id1: int, id2: int):
        transfer = self.mons[id1]
        self.mons[id1] = self.mons[id2] | {"id": id1}
        self.mons[id2] = transfer | {"id": id2}

    def swap_positions(self, pos1: int, pos2: int):
        if pos1 != pos2:
            self.order[pos1], self.order[pos2] = self.order[pos2], self.order[pos1]

    def change_id(self, new_id: int):
        self.id = new_id
        for old_id, mon in self.mons.items():
            mon["id"] = round(mon["id"] + new_id * self._size)
            mon["team_id"] = new_id
            del self.mons[old_id]
            self.mons[mon["id"]] = mon
        self.order = list(self.mons)

    @property
    def ordered_mons(self) -> list[dict]:
        return [self.mons[g] for g in self.order]

    def at(self, position: int) -> dict:
        return self.mons[self.order[position]]

    def inline_display(self, ignore: int = 0):
        return "\n".join(
            f"[{n + 1}] {FieldMon.from_json(g).inline_display()}" + (" (on field)" if g.get("on_field") else "")
            for n, g in enumerate(self.ordered_mons) if n >= ignore
        )

    def has_reserves(self, field_size: int = 1):
        return not all(g.get("fainted") for g in self.ordered_mons[field_size:])
