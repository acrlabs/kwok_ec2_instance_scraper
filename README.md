# ec2_instance_scraper
Scrape the public AWS pricing API to generate an instance list for KWOK + karpenter/KCA

## Basic Usage

```
python -m scraper.run --target cluster-autoscaler
python -m scraper.run --target karpenter
```

## Options

```
usage: ec2_instances_scraper [-h] [--aws-region AWS_REGION] [--instance-types INSTANCE_TYPES] [--disable-spot] [--filters FILTERS [FILTERS ...]]
                             --target {karpenter,cluster-autoscaler} [--output OUTPUT]

Scrape EC2 instances and save them to a KWOK-compatible configmap

options:
  -h, --help            show this help message and exit
  --aws-region AWS_REGION
  --instance-types INSTANCE_TYPES
  --disable-spot
  --filters FILTERS [FILTERS ...]
  --target {karpenter,cluster-autoscaler}
  --output, -o OUTPUT
```

## Filters

You can specify a filtered list of EC2 instances by passing in the `--filters` option; this corresponds directly with
the `--filters` option on [`describe-instance-types`](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-instance-types.html).

For example,

```
python -m scraper.run --target karpenter --filters instance-type=c6a.xlarge
```
