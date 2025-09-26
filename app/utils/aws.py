import boto3
from app.core.config import config
from fastapi import UploadFile
from io import BytesIO


def get_s3_client() -> boto3.client:
    if config.ENVIRONMENT == "development":
        session = boto3.Session(
            aws_access_key_id=config.AWS_ACCESS_KEY,
            aws_secret_access_key=config.AWS_SECRET_KEY,
        )
        return session.client("s3", region_name="eu-central-1")
    else:
        return boto3.client("s3", region_name="eu-central-1")


def get_ses_client() -> boto3.client:
    if config.ENVIRONMENT == "development":
        session = boto3.Session(
            aws_access_key_id=config.AWS_ACCESS_KEY,
            aws_secret_access_key=config.AWS_SECRET_KEY,
        )
        return session.client("ses", region_name="eu-central-1")
    else:
        return boto3.client("ses", region_name="eu-central-1")


def upload_file_to_s3(upload_file: UploadFile, s3_bucket: str, s3_key: str) -> tuple[str, str]:
    s3_client = get_s3_client()
    s3_client.upload_fileobj(
        upload_file.file,
        s3_bucket,
        s3_key,
        ExtraArgs={"ContentType": upload_file.content_type or "application/octet-stream"},
    )
    return s3_bucket, s3_key


def upload_pdf_to_s3(pdf_bytes: bytes, s3_bucket: str, s3_key: str) -> tuple[str, str]:
    s3_client = get_s3_client()
    pdf_file = BytesIO(pdf_bytes)
    s3_client.upload_fileobj(
        pdf_file,
        s3_bucket,
        s3_key,
        ExtraArgs={"ContentType": "application/pdf"},
    )
    return s3_bucket, s3_key


def delete_s3_object(s3_bucket: str, s3_key: str) -> None:
    s3_client = get_s3_client()
    s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)


def generate_presigned_url(
    s3_bucket: str | None = None,
    s3_key: str | None = None,
    s3_url: str | None = None,
    expiration: int = 3600,
) -> str:
    s3_client = get_s3_client()

    if s3_url:
        # Parse S3 URL to extract bucket and key
        # URL format: https://bucket.s3.region.amazonaws.com/path/to/file
        url_parts = s3_url.split("/")
        s3_bucket = url_parts[2].split(".")[0]  # Extract bucket name from domain
        s3_key = "/".join(url_parts[3:])  # Everything after domain is the key

    url = s3_client.generate_presigned_url(
        "get_object", Params={"Bucket": s3_bucket, "Key": s3_key}, ExpiresIn=expiration
    )
    return url
