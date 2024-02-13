import json


class HeldItem:
    def __init__(self, name: str, category: str, **kwargs):
        self.name = name
        self.category = category
        self.data = kwargs

    def __getitem__(self, item):
        return self.data.get(item)

    @staticmethod
    def from_json(js: dict):
        return HeldItem(**js)

    def json(self):
        return {"name": self.name, "category": self.category, **self.data}


all_items = {g: HeldItem.from_json(j) for g, j in json.load(open("data/items.json")).items()}
