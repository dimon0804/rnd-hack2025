import boto3
from botocore.config import Config
from ..core.config import settings


def get_s3_client():
    session = boto3.session.Session(
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    cfg = Config(s3={'addressing_style': 'path' if settings.s3_force_path_style else 'virtual'})
    return session.client('s3', endpoint_url=settings.s3_endpoint, config=cfg)


def upload_fileobj(fileobj, key: str, content_type: str = 'application/octet-stream') -> str:
    client = get_s3_client()
    bucket = settings.s3_bucket
    assert bucket, "S3_BUCKET is not configured"
    client.upload_fileobj(fileobj, bucket, key, ExtraArgs={'ContentType': content_type})
    if settings.s3_endpoint and settings.s3_force_path_style:
        return f"{settings.s3_endpoint}/{bucket}/{key}"
    # default virtual-hosted-style url
    host = f"https://{bucket}.s3.{settings.s3_region}.amazonaws.com" if settings.s3_region else f"https://{bucket}.s3.amazonaws.com"
    return f"{host}/{key}"
