import argparse
import datetime
import logging
import os

import boto3
import pandas as pd
from botocore.config import Config
from botocore.exceptions import ClientError

LOGGER = logging.getLogger(__name__)

AWS_DEFAULT_REGION = "us-west-2"

parser = argparse.ArgumentParser()
parser.add_argument("-dir", "--directory", type=str)
parser.add_argument(
    "-namespace",
    "--namespace",
    type=str,
    default="PyTorch/EC2/Benchmarks/TorchDynamo/Inductor",
)
parser.add_argument("-model_suite", "--model_suite", type=str)
parser.add_argument("-precision", "--precision", type=str)
parser.add_argument("-workload", "--workload", type=str)


def get_boto3_session(region=AWS_DEFAULT_REGION):
    """Get boto3 session with us-east-1 as default region used to connect to AWS services."""
    return boto3.session.Session(region_name=region)


def get_cloudwatch_client(region=AWS_DEFAULT_REGION):
    """Get AWS CloudWatch client object. Currently assume region is IAD (us-east-1)"""
    return get_boto3_session(region=region).client("cloudwatch")


def put_metric_data(metric_name, namespace, unit, value, dimensions):
    """Puts data points to cloudwatch metrics"""
    cloudwatch_client = get_cloudwatch_client()
    current_timestamp = datetime.datetime.utcnow()
    try:
        response = cloudwatch_client.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Dimensions": dimensions,
                    "Value": value,
                    "Unit": unit,
                    "Timestamp": current_timestamp,
                }
            ],
        )
    except ClientError as e:
        LOGGER.error(
            "Error: Cannot put data to cloudwatch metric: {}".format(metric_name)
        )
        LOGGER.error("Exception: {}".format(e))
        raise e


def read_metric(csv_file):
    df = pd.read_csv(csv_file)
    value = df[df.columns[-1]].iloc[0]
    if isinstance(value, str):
        for i in range(len(value)):
            if value[i].isdecimal() or value[i] == ".":
                continue
            else:
                return float(value[:i])
    return float(value)


if __name__ == "__main__":
    args = parser.parse_args()
    dimensions = [
        {"Name": "InstanceType", "Value": os.environ["INSTANCE_TYPE"]},
        {"Name": "ModelSuite", "Value": args.model_suite},
        {"Name": "Precision", "Value": args.precision},
        {"Name": "WorkLoad", "Value": args.workload},
    ]
    print(dimensions)
    speedup = read_metric(os.path.join(args.directory, "geomean.csv"))
    comp_time = read_metric(os.path.join(args.directory, "comp_time.csv"))
    memory = read_metric(os.path.join(args.directory, "memory.csv"))
    passrate = read_metric(os.path.join(args.directory, "passrate.csv"))
    assert passrate > 0
    assert speedup > 1
    put_metric_data("Speedup", args.namespace, "None", speedup, dimensions)
    put_metric_data("CompilationTime", args.namespace, "Seconds", comp_time, dimensions)
    put_metric_data(
        "PeakMemoryFootprintCompressionRatio",
        args.namespace,
        "None",
        memory,
        dimensions,
    )
    put_metric_data("PassRate", args.namespace, "Percent", passrate, dimensions)
