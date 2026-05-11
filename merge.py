import json
import os

merged = {}
output = []

for file in os.scandir(path="yelp"):
    if file.is_file():
        with open(file.path, "r", encoding="utf-8") as f:
            blob = json.load(f)

            for item in blob:
                name = item["name"]
                if name not in merged.keys():
                    merged[name] = {**item, "offerings": {}}

                offers = merged[name]["offerings"]

                for offer in item["offerings"]:
                    reqs = {req["key"]: req["values"] for req in offer["requirements"]}

                    zones = sorted(reqs.get("topology.kubernetes.io/zone", []))
                    capacity_type = sorted(reqs.get("karpenter.sh/capacity-type", []))

                    for z in zones:
                        for c in capacity_type:
                            key = (z, c)
                            # overwrites if already exists
                            offers[key] = offer

for item in merged.values():
    output.append({**item, "offerings": list(item["offerings"].values())})

with open("merged.json", "w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)
