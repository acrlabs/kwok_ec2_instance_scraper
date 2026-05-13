import typing as t

import arrow
import requests
from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.literals import InstanceTypeType
from mypy_boto3_ec2.type_defs import InstanceTypeInfoTypeDef

AWS_PRICING_API_ROOT = "https://pricing.us-east-1.amazonaws.com"
EC2_PRICING_REGION_INDEX_URL = (
    f"{AWS_PRICING_API_ROOT}/offers/v1.0/aws/AmazonEC2/current/region_index.json"
)


def convert_arch(arch: str) -> str:
    if arch == "x86_64":
        return "amd64"
    return arch


def fetch_instance_types(
    ec2: EC2Client, families: list[str], min_cpu: int, max_cpu: int
) -> list[str]:
    prefixes = tuple(map(lambda x: x + ".", families))
    print(prefixes)
    # Fetch the instance types
    paginator = ec2.get_paginator("describe_instance_types")
    instance_types = []

    for page in paginator.paginate():
        for instance in page["InstanceTypes"]:
            # Filter by family and CPU constraints
            name = instance["InstanceType"]

            if not name.startswith(prefixes):
                continue

            vcpus = instance["VCpuInfo"]["DefaultVCpus"]

            if min_cpu <= vcpus <= max_cpu:
                instance_types.append(name)

    return instance_types


def fetch_ondemand_prices(aws_region: str) -> t.Mapping[str, float]:
    # This is ugly AF, but I blame AWS

    print(f"  fetching per-region pricing urls from {EC2_PRICING_REGION_INDEX_URL}")
    region_data = requests.get(EC2_PRICING_REGION_INDEX_URL).json()
    # This is not great but we are pinning us-east-1 for on demand pricing since
    # the us-east-1 region has the most complete pricing document. We are
    # most interested in relative pricing but we should see if we get better
    # pricing from the pricing API at some point.
    region_url = (
        AWS_PRICING_API_ROOT + region_data["regions"]["us-east-1"]["currentVersionUrl"]
    )

    print(f"  fetching on-demand pricing data for {aws_region} from {region_url}")
    prices = requests.get(f"{region_url}").json()

    skus_by_instance_type = {
        deets["attributes"]["instanceType"]: sku
        for sku, deets in prices["products"].items()
        if deets["attributes"].get("usagetype").startswith("BoxUsage")
        and deets["attributes"]["operatingSystem"] == "Linux"  # noqa
    }

    prices_by_instance_type = dict()
    for instance_type, sku in skus_by_instance_type.items():
        block = prices["terms"]["OnDemand"][sku]
        price_dimensions = list(block.values())[0]["priceDimensions"]
        prices_by_instance_type[instance_type] = float(
            list(price_dimensions.values())[0]["pricePerUnit"]["USD"]
        )

    return prices_by_instance_type


def fetch_spot_prices(
    ec2: EC2Client,
) -> t.Mapping[t.Tuple[InstanceTypeType, str], float]:
    print("  fetching spot pricing data")
    paginator = ec2.get_paginator("describe_spot_price_history")
    end = arrow.utcnow()
    start = end.shift(minutes=-1)

    spot_prices_by_instance_type = dict()
    for page in paginator.paginate(
        Filters=[{"Name": "product-description", "Values": ["Linux/UNIX"]}],
        StartTime=start.format("YYYY-MM-DDTHH:mm:ssZ"),
        EndTime=end.format("YYYY-MM-DDTHH:mm:ssZ"),
    ):
        for item in page["SpotPriceHistory"]:
            spot_prices_by_instance_type[
                (item["InstanceType"], item["AvailabilityZone"])
            ] = float(item["SpotPrice"])

    return spot_prices_by_instance_type


def make_resource_map(
    instance_type: InstanceTypeInfoTypeDef,
) -> t.MutableMapping[str, str]:
    resource_map = {}

    cpu = instance_type.get("VCpuInfo", {}).get("DefaultVCpus")
    if cpu is not None:
        resource_map["cpu"] = str(cpu)

    memory = instance_type.get("MemoryInfo", {}).get("SizeInMiB")
    if memory is not None:
        resource_map["memory"] = str(memory) + "Mi"

    local_storage = instance_type.get("InstanceStorageInfo", {}).get("TotalSizeInGB")
    if local_storage is not None:
        resource_map["ephemeral-storage"] = str(local_storage) + "G"

    gpus = instance_type.get("GpuInfo", {}).get("Gpus", [])
    for gpu in gpus:
        if gpu.get("Manufacturer") == "NVIDIA":
            resource_map["nvidia.com/gpu"] = str(gpu.get("Count"))

    return resource_map


def is_valid_usage_class(
    cl: str,
    name: str,
    zone: str,
    spot_instances: t.KeysView[t.Tuple[InstanceTypeType, str]],
    capacity_type: list[str],
) -> bool:
    return cl in capacity_type and (name, zone) in spot_instances
