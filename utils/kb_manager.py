"""
Knowledge Base Manager

Utility functions for managing knowledge bases, including:
- Listing knowledge bases and buckets
- Uploading documents
- Tracking unsynced documents
- Syncing knowledge bases
"""

import os
import json
import logging
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("kb_manager")

# Valid domains
VALID_DOMAINS = ["hpc", "quantum", "genai", "visual", "spatial", "iot", "partners"]

class KnowledgeBaseManager:
    """Manager for knowledge base operations"""
    
    def __init__(self, region=None):
        """Initialize the manager"""
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.bedrock_client = boto3.client('bedrock-agent', region_name=self.region)
        
        # Cache for knowledge bases and buckets
        self._kb_cache = None
        self._bucket_cache = None
        self._domain_map = None
        
        # Check for manually specified knowledge base IDs
        self.manual_kb_ids = {}
        for domain in VALID_DOMAINS:
            env_var = f"{domain.upper()}_KNOWLEDGE_BASE_ID"
            kb_id = os.environ.get(env_var)
            if kb_id:
                self.manual_kb_ids[domain] = kb_id
                logger.info(f"Using manually specified knowledge base ID for {domain}: {kb_id}")
        
        # Track unsynced documents
        self.unsynced_docs = {}
        self._load_unsynced_docs()
    
    def _load_unsynced_docs(self):
        """Load unsynced documents from tracking file"""
        try:
            tracking_file = os.path.join(os.path.dirname(__file__), 'unsynced_docs.json')
            if os.path.exists(tracking_file):
                with open(tracking_file, 'r', encoding='utf-8') as f:
                    self.unsynced_docs = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load unsynced documents: {e}")
            self.unsynced_docs = {}
    
    def _save_unsynced_docs(self):
        """Save unsynced documents to tracking file"""
        try:
            tracking_file = os.path.join(os.path.dirname(__file__), 'unsynced_docs.json')
            with open(tracking_file, 'w', encoding='utf-8') as f:
                json.dump(self.unsynced_docs, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save unsynced documents: {e}")
    
    def list_knowledge_base_buckets(self):
        """List all knowledge base buckets"""
        if self._bucket_cache is not None:
            return self._bucket_cache
            
        try:
            # List all buckets
            response = self.s3_client.list_buckets()
            
            # Filter knowledge base buckets
            kb_buckets = []
            for bucket in response['Buckets']:
                name = bucket['Name']
                if 'advcomp-' in name and '-kb-' in name:
                    kb_buckets.append(name)
            
            self._bucket_cache = kb_buckets
            return kb_buckets
        except Exception as e:
            logger.error(f"Error listing buckets: {e}")
            return []
    
    def list_knowledge_bases(self):
        """List all knowledge bases"""
        if self._kb_cache is not None:
            return self._kb_cache
            
        try:
            # List all knowledge bases
            response = self.bedrock_client.list_knowledge_bases()
            
            # Filter Advanced Computing knowledge bases
            kb_list = []
            for kb in response.get('knowledgeBases', []):
                name = kb['name']
                if name.startswith('advcomp-'):
                    kb_list.append({
                        'id': kb['knowledgeBaseId'],
                        'name': name,
                        'description': kb.get('description', ''),
                        'status': kb.get('status', '')
                    })
            
            self._kb_cache = kb_list
            return kb_list
        except Exception as e:
            logger.error(f"Error listing knowledge bases: {e}")
            return []
    
    def get_domain_map(self):
        """Map domains to buckets and knowledge base IDs"""
        if self._domain_map is not None:
            return self._domain_map
            
        # Check environment variables for knowledge base IDs
        env_kb_ids = {}
        for domain in VALID_DOMAINS:
            env_var = f"{domain.upper()}_KNOWLEDGE_BASE_ID"
            kb_id = os.environ.get(env_var)
            if kb_id:
                env_kb_ids[domain] = kb_id
                logger.info(f"Found knowledge base ID in environment for {domain}: {kb_id}")
            
        # Get knowledge base buckets
        buckets = self.list_knowledge_base_buckets()
        
        # Get knowledge bases
        kbs = self.list_knowledge_bases()
        
        # Map domain to bucket and knowledge base ID
        domain_map = {}
        for bucket in buckets:
            for domain in VALID_DOMAINS:
                if f"advcomp-{domain}-kb-" in bucket:
                    if domain not in domain_map:
                        domain_map[domain] = {"bucket": bucket}
                        
                        # Add knowledge base ID from environment if available
                        if domain in env_kb_ids:
                            domain_map[domain]["kb_id"] = env_kb_ids[domain]
                            domain_map[domain]["status"] = "ACTIVE"
        
        # Use environment variable knowledge base IDs (these are the real ones)
        for domain in VALID_DOMAINS:
            env_var = f"{domain.upper()}_KNOWLEDGE_BASE_ID"
            kb_id = os.environ.get(env_var)
            if kb_id:
                # Ensure domain exists in map
                if domain not in domain_map:
                    domain_map[domain] = {}
                domain_map[domain]["kb_id"] = kb_id
                domain_map[domain]["status"] = "ACTIVE"
                logger.info(f"Using knowledge base ID from environment for {domain}: {kb_id}")
        
        # For domains without environment variables, try to find in Bedrock
        for domain in VALID_DOMAINS:
            if domain in domain_map and "kb_id" not in domain_map[domain]:
                for kb in kbs:
                    # Try multiple name patterns
                    if (f"advcomp-{domain}" in kb["name"].lower() or 
                        f"{domain}-knowledge" in kb["name"].lower() or
                        domain in kb["name"].lower()):
                        domain_map[domain]["kb_id"] = kb["id"]
                        domain_map[domain]["status"] = kb["status"]
                        logger.info(f"Found knowledge base for {domain}: {kb['id']} ({kb['name']})")
                        break
        
        # Log the domain map for debugging
        logger.info("Domain mapping:")
        for domain, info in domain_map.items():
            bucket = info.get("bucket", "N/A")
            kb_id = info.get("kb_id", "N/A")
            status = info.get("status", "N/A")
            logger.info(f"  - {domain}: Bucket={bucket}, KB ID={kb_id}, Status={status}")
        
        self._domain_map = domain_map
        return domain_map
    
    def upload_file(self, file_path, domain, original_name=None):
        """Upload a file to a domain's S3 bucket"""
        # Validate domain
        if domain not in VALID_DOMAINS:
            logger.error(f"Invalid domain: {domain}")
            return False, f"Invalid domain: {domain}"
        
        # Get domain map
        domain_map = self.get_domain_map()
        
        # Check if domain exists in map
        if domain not in domain_map:
            logger.error(f"No bucket found for domain: {domain}")
            return False, f"No bucket found for domain: {domain}"
        
        # Get bucket
        bucket = domain_map[domain]["bucket"]
        
        try:
            # Use original_name if provided, otherwise get from path
            file_name = original_name if original_name else os.path.basename(file_path)
            
            # Upload file
            logger.info(f"Uploading {file_name} to {bucket}...")
            self.s3_client.upload_file(file_path, bucket, file_name)
            
            # Track unsynced document
            if domain not in self.unsynced_docs:
                self.unsynced_docs[domain] = []
            
            self.unsynced_docs[domain].append({
                "file_name": file_name,
                "upload_time": datetime.now().isoformat(),
                "synced": False
            })
            
            # Save unsynced documents
            self._save_unsynced_docs()
            
            logger.info(f"Successfully uploaded {file_name} to {bucket}")
            return True, f"Successfully uploaded {file_name}"
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return False, f"File not found: {file_path}"
        except ClientError as e:
            logger.error(f"Error uploading file: {e}")
            return False, f"Error uploading file: {str(e)}"
    
    def upload_file_object(self, file_object, file_name, domain):
        """Upload a file object to a domain's S3 bucket"""
        # Validate domain
        if domain not in VALID_DOMAINS:
            logger.error(f"Invalid domain: {domain}")
            return False, f"Invalid domain: {domain}"
        
        # Get domain map
        domain_map = self.get_domain_map()
        
        # Check if domain exists in map
        if domain not in domain_map:
            logger.error(f"No bucket found for domain: {domain}")
            return False, f"No bucket found for domain: {domain}"
        
        # Get bucket
        bucket = domain_map[domain]["bucket"]
        
        try:
            # Preserve original filename (already passed in)
            # Upload file
            logger.info(f"Uploading {file_name} to {bucket}...")
            self.s3_client.upload_fileobj(file_object, bucket, file_name)
            
            # Track unsynced document
            if domain not in self.unsynced_docs:
                self.unsynced_docs[domain] = []
            
            self.unsynced_docs[domain].append({
                "file_name": file_name,
                "upload_time": datetime.now().isoformat(),
                "synced": False
            })
            
            # Save unsynced documents
            self._save_unsynced_docs()
            
            logger.info(f"Successfully uploaded {file_name} to {bucket}")
            return True, f"Successfully uploaded {file_name}"
        except ClientError as e:
            logger.error(f"Error uploading file: {e}")
            return False, f"Error uploading file: {str(e)}"
    
    def get_unsynced_docs(self):
        """Get unsynced documents by domain"""
        return self.unsynced_docs
    
    def clear_missing_docs(self):
        """Clear unsynced documents that no longer exist in S3 buckets"""
        # Get domain map
        domain_map = self.get_domain_map()
        
        # Check each domain
        for domain, docs in list(self.unsynced_docs.items()):
            if domain not in domain_map or "bucket" not in domain_map[domain]:
                # Domain doesn't exist, remove all docs
                del self.unsynced_docs[domain]
                continue
                
            bucket = domain_map[domain]["bucket"]
            
            # Check each document
            updated_docs = []
            for doc in docs:
                file_name = doc["file_name"]
                try:
                    # Check if file exists in S3
                    self.s3_client.head_object(Bucket=bucket, Key=file_name)
                    # File exists, keep it
                    updated_docs.append(doc)
                except Exception:
                    # File doesn't exist, skip it
                    logger.info(f"Removing missing file from unsynced docs: {file_name}")
            
            # Update docs for this domain
            if updated_docs:
                self.unsynced_docs[domain] = updated_docs
            else:
                # No docs left, remove domain
                del self.unsynced_docs[domain]
        
        # Save updated unsynced docs
        self._save_unsynced_docs()
        
        return self.unsynced_docs
    
    def sync_knowledge_base(self, domain):
        """Sync a domain's knowledge base"""
        # Validate domain
        if domain not in VALID_DOMAINS:
            logger.error(f"Invalid domain: {domain}")
            return False, f"Invalid domain: {domain}"
        
        # First check environment variables for knowledge base ID
        env_var = f"{domain.upper()}_KNOWLEDGE_BASE_ID"
        kb_id = os.environ.get(env_var)
        
        if kb_id:
            logger.info(f"Using knowledge base ID from environment variable: {kb_id}")
        
        # If no KB ID in environment variables, try to get it from domain map
        if not kb_id:
            # Get domain map
            domain_map = self.get_domain_map()
            
            # Check if domain exists in map
            if domain not in domain_map:
                logger.error(f"No knowledge base found for domain: {domain}")
                return False, f"No knowledge base found for domain: {domain}"
            
            # Check if knowledge base ID exists
            if "kb_id" not in domain_map[domain]:
                logger.error(f"No knowledge base ID found for domain: {domain}")
                return False, f"No knowledge base ID found for domain: {domain}"
            
            # Get knowledge base ID
            kb_id = domain_map[domain]["kb_id"]
        
        # If we still don't have a KB ID, return error
        if not kb_id:
            logger.error(f"Could not find knowledge base ID for domain: {domain}")
            return False, f"Could not find knowledge base ID for domain: {domain}"
        
        try:
            # Get data sources for this knowledge base
            logger.info(f"Getting data sources for knowledge base {kb_id}...")
            data_sources = self.bedrock_client.list_data_sources(knowledgeBaseId=kb_id)
            
            if not data_sources.get('dataSourceSummaries'):
                logger.error(f"No data sources found for knowledge base {kb_id}")
                return False, f"No data sources found for knowledge base {kb_id}"
            
            # Use the first data source
            data_source_id = data_sources['dataSourceSummaries'][0]['dataSourceId']
            logger.info(f"Using data source ID: {data_source_id}")
            
            # Start ingestion job
            logger.info(f"Starting ingestion job for knowledge base {kb_id}...")
            response = self.bedrock_client.start_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=data_source_id
            )
            
            # Log the full response for debugging
            logger.info(f"Start ingestion job response: {response}")
            
            # Check if ingestionJob is in the response
            if 'ingestionJob' not in response:
                logger.error(f"No ingestionJob in response: {response}")
                return False, f"Error starting ingestion job: No ingestionJob in response"
            
            # Check if ingestionJobId is in the ingestionJob
            if 'ingestionJobId' not in response['ingestionJob']:
                logger.error(f"No ingestionJobId in ingestionJob: {response['ingestionJob']}")
                return False, f"Error starting ingestion job: No ingestionJobId in ingestionJob"
                
            job_id = response['ingestionJob']['ingestionJobId']
            logger.info(f"Ingestion job started with ID: {job_id}")
            
            # Mark documents as synced
            if domain in self.unsynced_docs:
                for doc in self.unsynced_docs[domain]:
                    doc["synced"] = True
                    doc["sync_time"] = datetime.now().isoformat()
                    doc["job_id"] = job_id
            
            # Save unsynced documents
            self._save_unsynced_docs()
            
            return True, f"Ingestion job started with ID: {job_id}"
        except Exception as e:
            logger.error(f"Error starting ingestion job: {e}")
            logger.error(f"Error details: {type(e).__name__}")
            # Print the full response if available
            try:
                if 'response' in locals():
                    logger.error(f"API response: {response}")
            except:
                pass
            return False, f"Error starting ingestion job: {str(e)}"
    
    def get_ingestion_job_status(self, domain, job_id):
        """Get status of an ingestion job"""
        # Validate domain
        if domain not in VALID_DOMAINS:
            logger.error(f"Invalid domain: {domain}")
            return None
        
        # Get domain map
        domain_map = self.get_domain_map()
        
        # Check if domain exists in map
        if domain not in domain_map:
            logger.error(f"No knowledge base found for domain: {domain}")
            return None
        
        # Check if knowledge base ID exists
        if "kb_id" not in domain_map[domain]:
            logger.error(f"No knowledge base ID found for domain: {domain}")
            return None
        
        # Get knowledge base ID
        kb_id = domain_map[domain]["kb_id"]
        
        try:
            # Get job status
            response = self.bedrock_client.get_ingestion_job(
                knowledgeBaseId=kb_id,
                ingestionJobId=job_id
            )
            
            # Log the full response for debugging
            logger.info(f"Get ingestion job response: {response}")
            
            # Check if ingestionJob is in the response
            if 'ingestionJob' in response:
                ingestion_job = response['ingestionJob']
                return {
                    "status": ingestion_job.get("status"),
                    "statistics": ingestion_job.get("statistics", {}),
                    "startTime": ingestion_job.get("startedAt"),
                    "endTime": ingestion_job.get("updatedAt")
                }
            else:
                # Fall back to the old structure if ingestionJob is not present
                return {
                    "status": response.get("status"),
                    "statistics": response.get("statistics", {}),
                    "startTime": response.get("startTime"),
                    "endTime": response.get("endTime")
                }
        except Exception as e:
            logger.error(f"Error getting ingestion job status: {e}")
            logger.error(f"Error details: {type(e).__name__}")
            return None