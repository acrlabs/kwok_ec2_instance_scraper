import argparse
import typing as t

import boto3
from typing_extensions import TypedDict

from scraper.ca import KwokNodeList
from scraper.common import fetch_instance_types
from scraper.karpenter import InstanceTypeOptionsList


class Filter(TypedDict):
    Name: str
    Values: t.List[str]


def parse_filters(f: str) -> Filter:
    name, val_str = f.split("=")
    vals = val_str.split(",")

    return Filter(Name=name, Values=vals)


def parse_args() -> argparse.Namespace:
    root_parser = argparse.ArgumentParser(
        prog="ec2_instances_scraper",
        description="Scrape EC2 instances and save them to a KWOK-compatible configmap",
    )

    root_parser.add_argument(
        "--aws-region",
        default="us-east-1",
    )

    root_parser.add_argument(
        "--instance-types", default=list(), type=lambda s: s.split(",")
    )

    root_parser.add_argument(
        "--instance-families", default=list(), type=lambda s: s.split(",")
    )

    root_parser.add_argument("--zones", default=list(), type=lambda s: s.split(","))

    root_parser.add_argument("--min-cpu", type=int, default=0)

    root_parser.add_argument("--max-cpu", type=int, default=float("inf"))

    root_parser.add_argument(
        "--capacity-type",
        default=["on-demand", "spot"],
        type=lambda s: s.split(","),
    )

    root_parser.add_argument(
        "--filters",
        type=parse_filters,
        default=[],
        nargs="+",
    )

    root_parser.add_argument(
        "--target",
        required=True,
        choices=["karpenter", "cluster-autoscaler"],
    )

    root_parser.add_argument(
        "--output",
        "-o",
    )

    return root_parser.parse_args()


def run() -> None:
    args = parse_args()
    ec2 = boto3.client("ec2", region_name=args.aws_region)

    if args.instance_families and args.instance_types:
        raise ValueError(
            "Instance_families and instance_types are mutually exclusive options"
        )

    builder: t.Union[InstanceTypeOptionsList, KwokNodeList]
    if args.target == "karpenter":
        builder = InstanceTypeOptionsList(ec2, args.aws_region)
        if args.output is None:
            args.output = "instance_types.json"
    elif args.target == "cluster-autoscaler":
        builder = KwokNodeList(ec2, args.aws_region)
        if args.output is None:
            args.output = "kwok_provider_config.yaml"

    zones = args.zones
    if not args.zones:
        print(f"Fetching AWS zones for {args.aws_region}")
        zones = [
            az["ZoneName"]
            for az in ec2.describe_availability_zones()["AvailabilityZones"]
        ]

    instance_types = args.instance_types
    if args.instance_families:
        instance_types = fetch_instance_types(
            ec2, args.instance_families, args.min_cpu, args.max_cpu
        )

    print("Fetching EC2 Instance Types")
    paginator = ec2.get_paginator("describe_instance_types")
    for page in paginator.paginate(InstanceTypes=instance_types, Filters=args.filters):
        for instance_type in page["InstanceTypes"]:
            builder.add_instance_types(instance_type, zones, args.capacity_type)

    print(f"Writing data to {args.output}")
    with open(args.output, "w") as f:
        builder.serialize(f)


if __name__ == "__main__":
    run()
