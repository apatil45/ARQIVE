"""
S3 Storage for document files
Uses boto3 for AWS S3 integration with free tier support
"""
import os
import logging
from typing import Optional, BinaryIO
from io import BytesIO
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from config import settings

logger = logging.getLogger(__name__)


class S3Storage:
    """S3 storage handler for document files"""
    
    def __init__(self):
        """Initialize S3 client"""
        self.bucket_name = settings.S3_BUCKET_NAME
        self.region = settings.S3_REGION
        self._s3_client = None
        self._bucket_checked = False
    
    @property
    def s3_client(self):
        """Lazy initialization of S3 client"""
        if self._s3_client is None:
            # Initialize S3 client
            # Use credentials from environment variables or IAM role
            client_kwargs = {
                'service_name': 's3',
                'region_name': self.region,
            }
            
            # Only add credentials if provided (otherwise use IAM role or env vars)
            if hasattr(settings, 'S3_ACCESS_KEY_ID') and settings.S3_ACCESS_KEY_ID:
                client_kwargs['aws_access_key_id'] = settings.S3_ACCESS_KEY_ID
            if hasattr(settings, 'S3_SECRET_ACCESS_KEY') and settings.S3_SECRET_ACCESS_KEY:
                client_kwargs['aws_secret_access_key'] = settings.S3_SECRET_ACCESS_KEY
            
            self._s3_client = boto3.client(**client_kwargs)
            
            # Verify bucket exists or create it (only once)
            if not self._bucket_checked:
                self._ensure_bucket_exists()
                self._bucket_checked = True
        
        return self._s3_client
    
    def _ensure_bucket_exists(self):
        """Ensure S3 bucket exists, create if it doesn't"""
        # Use _s3_client directly to avoid circular reference
        client = self._s3_client
        try:
            client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 bucket '{self.bucket_name}' exists")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                # Bucket doesn't exist, try to create it
                try:
                    if self.region == 'us-east-1':
                        # us-east-1 doesn't need LocationConstraint
                        client.create_bucket(Bucket=self.bucket_name)
                    else:
                        client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    logger.info(f"Created S3 bucket '{self.bucket_name}' in region '{self.region}'")
                except ClientError as create_error:
                    logger.error(f"Failed to create S3 bucket: {create_error}")
                    raise
            else:
                logger.error(f"Error checking S3 bucket: {e}")
                raise
    
    async def upload_file(
        self,
        file_content: bytes,
        s3_key: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload file to S3
        
        Args:
            file_content: File content as bytes
            s3_key: S3 object key (path)
            content_type: MIME type of the file
            
        Returns:
            S3 object key
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            # Upload file
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                **extra_args
            )
            
            logger.info(f"Uploaded file to S3: {s3_key}")
            return s3_key
            
        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise Exception(f"S3 upload failed: {str(e)}")
    
    async def download_file(self, s3_key: str) -> bytes:
        """
        Download file from S3
        
        Args:
            s3_key: S3 object key (path)
            
        Returns:
            File content as bytes
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            file_content = response['Body'].read()
            logger.info(f"Downloaded file from S3: {s3_key}")
            return file_content
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File not found in S3: {s3_key}")
            logger.error(f"Failed to download file from S3: {e}")
            raise Exception(f"S3 download failed: {str(e)}")
    
    async def delete_file(self, s3_key: str) -> bool:
        """
        Delete file from S3
        
        Args:
            s3_key: S3 object key (path)
            
        Returns:
            True if deleted, False if not found
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"Deleted file from S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
    
    def get_file_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """
        Generate presigned URL for file access
        
        Args:
            s3_key: S3 object key (path)
            expires_in: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise Exception(f"Failed to generate presigned URL: {str(e)}")
    
    def file_exists(self, s3_key: str) -> bool:
        """
        Check if file exists in S3
        
        Args:
            s3_key: S3 object key (path)
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

