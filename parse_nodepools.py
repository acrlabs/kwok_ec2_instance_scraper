import json

# Parse a nodepools.json
# TODO: needs clean up especially output formatting

with open("nodepools.json") as f:

    data = json.load(f)

    nodepools = []

    items = data.get("items")
    for nodepool in items:
        reqs = (
            nodepool.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("requirements")
        )
        name = (
            nodepool.get("spec", [])
            .get("template", {})
            .get("metadata", {})
            .get("labels", {})
            .get("yelp.com/pool")
        )
        min_cpu, max_cpu = 0, 0
        itypes = []
        ifamily = []
        capacity_type = []
        instance_family = []
        for r in reqs:
            key = r.get("key")
            op = r.get("operator")
            values = r.get("values")
            if key == "node.kubernetes.io/instance-type":
                itypes = values
            elif key == "karpenter.sh/capacity-type":
                capacity_type = values
            elif key == "karpenter.k8s.aws/instance-family":
                ifamily = values
            elif key == "karpenter.k8s.aws/instance-cpu":
                if op == "Gt":
                    min_cpu = int(values[0]) + 1
                elif op == "Lt":
                    max_cpu = int(values[0]) - 1

        record = (name, itypes, ifamily, min_cpu, max_cpu, capacity_type)

        if record not in nodepools:
            nodepools.append(record)

    print(nodepools)
