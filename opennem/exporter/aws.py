"""
OpenNEM S3 Bucket Module

Writes OpennemDataSet's to AWS S3 buckets
"""
import json
import logging
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from opennem.api.stats.schema import OpennemDataSet
from opennem.settings import settings
from opennem.utils.url import urljoin

logger = logging.getLogger(__name__)


class OpennemDataSetSerializeS3:
    bucket_name: str
    debug: bool = False
    exclude_unset: bool = False

    def __init__(self, bucket_name: str, exclude_unset: bool = False, debug: bool = False) -> None:
        self.bucket = boto3.resource("s3").Bucket(bucket_name)
        self.debug = settings.debug

        if debug:
            self.debug = debug

        self.exclude_unset = exclude_unset

    # @TODO return a full OpennemDataSet
    def load(self, key: str) -> Any:
        return json.load(self.bucket.Object(key=key).get()["Body"])

    def dump(self, key: str, stat_set: OpennemDataSet, exclude: Optional[set] = None) -> Any:

        indent = None

        if settings.debug:
            indent = 4

        stat_set_content = stat_set.json(
            exclude_unset=self.exclude_unset, indent=indent, exclude=exclude
        )

        obj = self.bucket.Object(key=key)
        _write_response = obj.put(Body=stat_set_content, ContentType="application/json")

        _write_response["length"] = len(stat_set_content)

        return _write_response


def write_to_s3(
    stat_set: OpennemDataSet, file_path: str, exclude: set = None, exclude_unset: bool = False
) -> int:
    """
    Write an Opennem data set to an s3 bucket using boto
    """
    s3_save_path = urljoin(f"https://{settings.s3_bucket_path}", file_path)

    if not settings.s3_bucket_path:
        raise Exception("Require an S3 bucket to write to")

    s3bucket = OpennemDataSetSerializeS3(settings.s3_bucket_path, exclude_unset=exclude_unset)
    write_response = None

    try:
        write_response = s3bucket.dump(file_path, stat_set, exclude=exclude)
    except ClientError as e:
        logging.error(e)
        return 0

    if "ResponseMetadata" not in write_response:
        raise Exception("Error writing stat set to {} invalid write response".format(file_path))

    if "HTTPStatusCode" not in write_response["ResponseMetadata"]:
        raise Exception("Error writing stat set to {} invalid write response".format(file_path))

    if write_response["ResponseMetadata"]["HTTPStatusCode"] != 200:
        raise Exception(
            "Error writing stat set to {} - response code {}".format(
                file_path, write_response["ResponseMetadata"]["HTTPStatusCode"]
            )
        )

    logger.info("Wrote {} to {}".format(write_response["length"], s3_save_path))

    return write_response["length"]
