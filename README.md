# ec2_instance_scraper

Scrape the public AWS pricing API to generate an instance list for KWOK + karpenter/KCA

## Basic Usage

```sh
python -m scraper.run --target cluster-autoscaler
python -m scraper.run --target karpenter
```

## Options

usage:
```sh
ec2_instances_scraper [-h] [--aws-region AWS_REGION] [--instance-types INSTANCE_TYPES] 
    [--instance-families INSTANCE_FAMILIES] [--min-cpu MIN_CPU] [--max-cpu MAX_CPU] [--capacity-type {on-demand, spot}]
    [--filters FILTERS [FILTERS ...]] --target {karpenter,cluster-autoscaler} [--output OUTPUT]
```

Scrape EC2 instances and save them to a KWOK-compatible configmap

options:
```sh
  -h, --help            show this help message and exit
  --aws-region AWS_REGION
  --instance-types INSTANCE_TYPES
  --instance-families INSTANCE_FAMILIES
  --min-cpu MIN_CPU
  --max-cpu MAX_CPU
  --capacity-type {on-demand,spot}
  --filters FILTERS [FILTERS ...]
  --target {karpenter,cluster-autoscaler}
  --output, -o OUTPUT
```

## Running

```sh
poetry install
poetry run python scraper.run --target karpenter --instance-families c5,c5a --
```

## Filters

For advanced filtering you can specify a filtered list of EC2 instances by passing in the `--filters` option; this corresponds directly with the `--filters` option on [`describe-instance-types`](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-instance-types.html).

## Pricing notes

Currently configured to use `us-east-1` for all on-demand pricing, regardless of region, this is the most complete 
reference available. Spot pricing is queried from the region specified in `--aws-region`.
