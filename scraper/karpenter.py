import typing as t

import simplejson as json
from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.literals import InstanceTypeType
from mypy_boto3_ec2.type_defs import InstanceTypeInfoTypeDef
from typing_extensions import TypedDict

from scraper.common import convert_arch
from scraper.common import fetch_ondemand_prices
from scraper.common import fetch_spot_prices
from scraper.common import is_valid_usage_class
from scraper.common import make_resource_map


class InstanceTypeRequirement(TypedDict):
    key: str
    operator: str
    values: t.List[str]


class InstanceTypeOffering(TypedDict):
    capacityType: str
    zone: str
    price: float
    available: bool
    requirements: t.List[InstanceTypeRequirement]


class InstanceTypeOptions(TypedDict):
    name: InstanceTypeType
    offerings: t.List[InstanceTypeOffering]
    architecture: str
    operatingSystems: t.List[str]
    resources: t.Mapping[str, str]


class InstanceTypeOptionsList:
    def __init__(self, ec2: EC2Client, aws_region: str) -> None:
        self.nodes: t.List[InstanceTypeOptions] = []
        print(f"Fetching EC2 pricing data for {aws_region}")
        self.ondemand_prices = fetch_ondemand_prices(aws_region)
        self.spot_prices = fetch_spot_prices(ec2)

    def add_instance_types(
        self,
        instance_type: InstanceTypeInfoTypeDef,
        zones: t.List[str],
        disable_spot: bool,
    ) -> None:
        self.nodes.extend(
            [
                InstanceTypeOptions(
                    name=instance_type["InstanceType"],
                    offerings=make_offerings(
                        instance_type,
                        zones,
                        self.ondemand_prices,
                        self.spot_prices,
                        disable_spot,
                    ),
                    architecture=convert_arch(arch),
                    operatingSystems=[
                        "linux",
                    ],
                    resources=make_resource_map(instance_type),
                )
                for arch in instance_type["ProcessorInfo"]["SupportedArchitectures"]
                if arch in {"x86_64", "arm64"}
            ]
        )

    def serialize(self, writer: t.IO[str]):
        json.dump(self.nodes, writer)


def make_offerings(
    instance_type: InstanceTypeInfoTypeDef,
    zones: t.List[str],
    ondemand_prices: t.Mapping[str, float],
    spot_prices: t.Mapping[t.Tuple[InstanceTypeType, str], float],
    disable_spot: bool,
) -> t.List[InstanceTypeOffering]:
    name = instance_type["InstanceType"]
    offerings = [
        InstanceTypeOffering(
            available=True,
            requirements=[
                InstanceTypeRequirement(
                    key="topology.kubernetes.io/zone",
                    operator="In",
                    values=[z],
                ),
                InstanceTypeRequirement(
                    key="karpenter.sh/capacity-type",
                    operator="In",
                    values=[cl],
                ),
            ],
            price=(
                ondemand_prices[name] if cl == "on-demand" else spot_prices[(name, z)]
            ),
        )
        for z in zones
        for cl in instance_type["SupportedUsageClasses"]
        if is_valid_usage_class(cl, name, z, spot_prices.keys(), disable_spot)  # noqa
    ]

    return offerings
