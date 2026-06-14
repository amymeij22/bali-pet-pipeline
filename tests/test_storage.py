import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Add src to python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from biometeo_worker.config import Settings
from biometeo_worker.storage import get_s3_client, upload_run_folder


def test_get_s3_client_missing_credentials():
    settings = Settings(
        database_url=None,
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url=None,
        s3_access_key_id=None,
        s3_secret_access_key=None,
        s3_bucket_name="mybucket",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=3,
        request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5,
    )
    with pytest.raises(ValueError, match="S3 credentials tidak lengkap"):
        get_s3_client(settings)


@patch("biometeo_worker.storage.boto3.client")
def test_get_s3_client_success(mock_boto_client):
    settings = Settings(
        database_url=None,
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url="http://localhost:9000",
        s3_access_key_id="access",
        s3_secret_access_key="secret",
        s3_bucket_name="mybucket",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=3,
        request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5,
    )
    client = get_s3_client(settings)
    mock_boto_client.assert_called_once_with(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="access",
        aws_secret_access_key="secret",
        region_name="ap-southeast-1",
    )
    assert client == mock_boto_client.return_value


@patch("biometeo_worker.storage.boto3.client")
def test_upload_run_folder_success_and_failures(mock_boto_client, tmp_path):
    settings = Settings(
        database_url=None,
        db_user=None,
        db_password=None,
        db_host=None,
        db_port=None,
        db_name=None,
        s3_endpoint_url="http://localhost:9000",
        s3_access_key_id="access",
        s3_secret_access_key="secret",
        s3_bucket_name="mybucket",
        s3_region="ap-southeast-1",
        app_env="dev",
        keep_local_artifacts=True,
        output_parent_dir="reports",
        request_timeout_seconds=30,
        request_retry_count=3,
        request_retry_delay_seconds=2.0,
        request_delay_seconds=0.5,
    )

    # Setup dummy directory layout
    run_dir = tmp_path / "run_20260614_1151"
    run_dir.mkdir()
    file1 = run_dir / "results.json"
    file1.write_text("{}")
    file2 = run_dir / "data.csv"
    file2.write_text("a,b,c")
    file3 = run_dir / "image.png"
    file3.write_bytes(b"\x00\x01\x02")

    # We will mock the client object
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    # To test both success and failure, make the second call raise ClientError
    def upload_file_side_effect(Filename, Bucket, Key, ExtraArgs=None):
        if "data.csv" in Filename:
            raise ClientError(
                error_response={"Error": {"Code": "SomeError", "Message": "Gagal"}},
                operation_name="PutObject"
            )
        return None

    mock_s3.upload_file.side_effect = upload_file_side_effect

    res = upload_run_folder(str(run_dir), settings)

    assert res["prefix"] == "run_20260614_1151"
    # Depending on OS/walk order, results might vary in order, but we can verify set contents
    assert set(res["uploaded"]) == {"results.json", "image.png"}
    assert len(res["failed"]) == 1
    assert res["failed"][0]["file"] == "data.csv"
    assert "SomeError" in res["failed"][0]["error"]
