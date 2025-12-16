#!/usr/bin/env python3
"""
Find Knowledge Base IDs

This script helps find knowledge base IDs and generates environment variable
settings that can be added to your .env file.
"""

import os
import sys
import boto3
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("find_kb_ids")

# Load environment variables
load_dotenv()

# Valid domains
VALID_DOMAINS = ["hpc", "quantum", "genai", "visual", "spatial", "iot", "partners"]

def find_knowledge_bases(region=None):
    """Find all knowledge bases in the region"""
    region = region or os.environ.get("AWS_REGION", "us-east-1")
    
    try:
        # Initialize Bedrock client
        bedrock = boto3.client('bedrock', region_name=region)
        
        # List all knowledge bases
        response = bedrock.list_knowledge_bases()
        
        # Filter knowledge bases
        kb_list = []
        for kb in response.get('knowledgeBases', []):
            kb_list.append({
                'id': kb['knowledgeBaseId'],
                'name': kb['name'],
                'description': kb.get('description', ''),
                'status': kb.get('status', '')
            })
        
        return kb_list
    except Exception as e:
        logger.error(f"Error listing knowledge bases: {e}")
        return []

def generate_env_settings(kbs):
    """Generate environment variable settings for knowledge bases"""
    env_settings = []
    
    # Try to match knowledge bases to domains
    for domain in VALID_DOMAINS:
        # Look for exact matches first
        exact_match = None
        for kb in kbs:
            if f"advcomp-{domain}-knowledge" == kb["name"]:
                exact_match = kb
                break
        
        # If no exact match, look for partial matches
        if not exact_match:
            for kb in kbs:
                if domain in kb["name"].lower():
                    exact_match = kb
                    break
        
        # Add environment variable setting if found
        if exact_match:
            env_settings.append(f"{domain.upper()}_KNOWLEDGE_BASE_ID={exact_match['id']}  # {exact_match['name']}")
    
    return env_settings

def main():
    # Get region from command line or environment
    import argparse
    parser = argparse.ArgumentParser(description="Find knowledge base IDs")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"), help="AWS region")
    args = parser.parse_args()
    
    # Find knowledge bases
    logger.info(f"Finding knowledge bases in region {args.region}...")
    kbs = find_knowledge_bases(args.region)
    
    if not kbs:
        logger.error("No knowledge bases found")
        sys.exit(1)
    
    # Print all knowledge bases
    logger.info(f"Found {len(kbs)} knowledge bases:")
    for kb in kbs:
        logger.info(f"  - {kb['name']} (ID: {kb['id']}, Status: {kb['status']})")
        logger.info(f"    Description: {kb['description']}")
    
    # Generate environment variable settings
    env_settings = generate_env_settings(kbs)
    
    if env_settings:
        logger.info("\nAdd these lines to your .env file:")
        for setting in env_settings:
            print(setting)
    else:
        logger.warning("Could not match any knowledge bases to domains")

if __name__ == "__main__":
    main()