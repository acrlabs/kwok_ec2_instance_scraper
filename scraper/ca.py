import io
import typing as t

from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.type_defs import InstanceTypeInfoTypeDef
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

from scraper.common import convert_arch
from scraper.common import fetch_spot_prices
from scraper.common import is_valid_usage_class
from scraper.common import make_resource_map

PROVIDER_CONFIG = """
apiVersion: v1alpha1
readNodesFrom: configmap
nodegroups:
    fromNodeLabelKey: "kwok-nodegroup"
configmap:
    name: kwok-provider-templates
"""


class KwokNodeList:
    def __init__(self, ec2: EC2Client, aws_region) -> None:
        self.nodes: t.List[t.Mapping[str, t.Any]] = []
        self.aws_region = aws_region
        self.spot_prices = fetch_spot_prices(ec2)

    def add_instance_types(
        self,
        instance_type: InstanceTypeInfoTypeDef,
        zones: t.List[str],
        disable_spot: bool,
    ) -> None:
        name = instance_type["InstanceType"]
        for arch in instance_type["ProcessorInfo"]["SupportedArchitectures"]:
            if arch not in {"x86_64", "arm64"}:
                continue

            for z in zones:
                for cl in instance_type["SupportedUsageClasses"]:
                    if not is_valid_usage_class(
                        cl, name, z, self.spot_prices.keys(), disable_spot
                    ):
                        continue

                    node_group_name = f"ng-{name}-{z}"
                    labels = {
                        "kubernetes.io/arch": arch,
                        "kubernetes.io/os": "linux",
                        "node.kubernetes.io/instance-type": name,
                        "topology.kubernetes.io/region": self.aws_region,
                        "topology.kubernetes.io/zone": z,
                        "kwok-nodegroup": node_group_name,
                        "type": "virtual",
                    }
                    if cl == "spot":
                        node_group_name += "-spot"
                        labels["ec2.aws.com/lifecycle"] = "spot"

                    resources = make_resource_map(instance_type)
                    if "pods" not in resources:
                        resources["pods"] = "110"

                    self.nodes.append(
                        {
                            "apiVersion": "v1",
                            "kind": "Node",
                            "metadata": {
                                "annotations": {
                                    "cluster-autoscaler.kwok.nodegroup/name": node_group_name,
                                    "kwok.x-k8s.io/node": "fake",
                                },
                                "labels": labels,
                            },
                            "status": {
                                "allocatable": resources,
                                "capacity": resources,
                                "nodeInfo": {
                                    "architecture": convert_arch(arch),
                                    "operatingSystem": "linux",
                                    "kubeletVersion": "1.29.0",
                                },
                            },
                        }
                    )

    def serialize(self, writer: t.IO[str]) -> None:
        nodes_stream = io.StringIO()
        yaml = YAML()
        yaml.explicit_start = True
        yaml.dump(self.nodes, nodes_stream)

        provider_config = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "kwok-provider-config",
                "namespace": "kube-system",
            },
            "data": {"config": LiteralScalarString(PROVIDER_CONFIG)},
        }
        yaml.dump(provider_config, writer)

        nodes_str = LiteralScalarString(nodes_stream.getvalue())
        provider_templates = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "kwok-provider-templates",
                "namespace": "kube-system",
            },
            "data": {
                "templates": {
                    "apiVersion": "v1",
                    "kind": "List",
                    "items": nodes_str,
                },
            },
        }
        yaml.dump(provider_templates, writer)
