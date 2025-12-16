#!/usr/bin/env python3
"""
Knowledge Base Upload Script

Command-line tool for uploading documents to domain-specific knowledge bases
and syncing knowledge bases on demand.
"""

import os
import sys
import argparse
import logging
from kb_manager import KnowledgeBaseManager, VALID_DOMAINS

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("kb_upload")

def main():
    parser = argparse.ArgumentParser(description="Upload and sync documents for knowledge bases")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"), help="AWS region")
    
    # Load knowledge base IDs from environment variables
    for domain in VALID_DOMAINS:
        env_var = f"{domain.upper()}_KNOWLEDGE_BASE_ID"
        kb_id = os.environ.get(env_var)
        if kb_id:
            logger.info(f"Found knowledge base ID for {domain}: {kb_id}")
        else:
            logger.warning(f"No knowledge base ID found for {domain} in environment variables")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List knowledge bases and buckets")
    
    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload documents")
    upload_parser.add_argument("--domain", required=True, choices=VALID_DOMAINS + ["all"], 
                        help="Domain to upload documents for")
    upload_parser.add_argument("--file", help="Single file to upload")
    upload_parser.add_argument("--directory", help="Directory of files to upload")
    
    # Unsynced command
    unsynced_parser = subparsers.add_parser("unsynced", help="List unsynced documents")
    
    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync knowledge bases")
    sync_parser.add_argument("--domain", required=True, choices=VALID_DOMAINS + ["all"], 
                       help="Domain to sync")
    
    args = parser.parse_args()
    
    # Initialize knowledge base manager
    kb_manager = KnowledgeBaseManager(region=args.region)
    
    # Handle commands
    if args.command == "list":
        # List knowledge base buckets
        buckets = kb_manager.list_knowledge_base_buckets()
        if buckets:
            logger.info(f"Found {len(buckets)} knowledge base buckets:")
            for bucket in buckets:
                logger.info(f"  - {bucket}")
        else:
            logger.warning("No knowledge base buckets found")
        
        # List knowledge bases
        kbs = kb_manager.list_knowledge_bases()
        if kbs:
            logger.info(f"\nFound {len(kbs)} knowledge bases:")
            for kb in kbs:
                logger.info(f"  - {kb['name']} (ID: {kb['id']}, Status: {kb['status']})")
                logger.info(f"    Description: {kb['description']}")
        else:
            logger.warning("No knowledge bases found")
        
        # Show domain mapping
        domain_map = kb_manager.get_domain_map()
        logger.info("\nDomain mapping:")
        for domain, info in domain_map.items():
            bucket = info.get("bucket", "N/A")
            kb_id = info.get("kb_id", "N/A")
            status = info.get("status", "N/A")
            logger.info(f"  - {domain}: Bucket={bucket}, KB ID={kb_id}, Status={status}")
    
    elif args.command == "upload":
        # Validate arguments
        if not args.file and not args.directory:
            logger.error("Either --file or --directory is required")
            sys.exit(1)
        
        # Get domains to process
        domains = VALID_DOMAINS if args.domain == "all" else [args.domain]
        
        # Upload file or directory
        for domain in domains:
            if args.file:
                # Upload single file
                success, message = kb_manager.upload_file(args.file, domain)
                if success:
                    logger.info(f"[{domain}] {message}")
                else:
                    logger.error(f"[{domain}] {message}")
            else:
                # Upload directory
                if not os.path.isdir(args.directory):
                    logger.error(f"Directory not found: {args.directory}")
                    continue
                
                # Get all files in directory
                files = []
                for root, _, filenames in os.walk(args.directory):
                    for filename in filenames:
                        files.append(os.path.join(root, filename))
                
                if not files:
                    logger.warning(f"No files found in {args.directory}")
                    continue
                
                # Upload each file
                success_count = 0
                for file_path in files:
                    success, message = kb_manager.upload_file(file_path, domain)
                    if success:
                        success_count += 1
                        logger.info(f"[{domain}] {message}")
                    else:
                        logger.error(f"[{domain}] {message}")
                
                logger.info(f"[{domain}] Successfully uploaded {success_count} of {len(files)} files")
    
    elif args.command == "unsynced":
        # Get unsynced documents
        unsynced_docs = kb_manager.get_unsynced_docs()
        
        if not unsynced_docs:
            logger.info("No unsynced documents found")
            return
        
        # Display unsynced documents by domain
        total_unsynced = 0
        for domain, docs in unsynced_docs.items():
            unsynced = [doc for doc in docs if not doc.get("synced", False)]
            if unsynced:
                logger.info(f"\n{domain.upper()} - {len(unsynced)} unsynced documents:")
                for doc in unsynced:
                    logger.info(f"  - {doc['file_name']} (uploaded: {doc['upload_time']})")
                total_unsynced += len(unsynced)
        
        if total_unsynced == 0:
            logger.info("All documents are synced")
    
    elif args.command == "sync":
        # Get domains to process
        domains = VALID_DOMAINS if args.domain == "all" else [args.domain]
        
        # Sync each domain
        for domain in domains:
            success, message = kb_manager.sync_knowledge_base(domain)
            if success:
                logger.info(f"[{domain}] {message}")
            else:
                logger.error(f"[{domain}] {message}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()