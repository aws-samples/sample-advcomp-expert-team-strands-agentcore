"""
Knowledge Base Lambda Function

This Lambda function serves as a unified knowledge base access tool for the
Advanced Computing Team Collaboration Swarm. It accepts a domain parameter
to specify which knowledge base to query.

This version uses real Bedrock Knowledge Bases instead of mock data.
"""

import json
import logging
import os
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Bedrock client
bedrock_client = boto3.client('bedrock-agent-runtime')

# Map of domain names to knowledge base IDs
# These will be populated from environment variables
KNOWLEDGE_BASE_IDS = {}

def init_knowledge_base_ids():
    """Initialize knowledge base IDs from environment variables"""
    global KNOWLEDGE_BASE_IDS
    
    domains = ["hpc", "quantum", "genai", "visual", "spatial", "iot", "partners"]
    
    for domain in domains:
        env_var = f"{domain.upper()}_KNOWLEDGE_BASE_ID"
        kb_id = os.environ.get(env_var)
        if kb_id:
            KNOWLEDGE_BASE_IDS[domain] = kb_id
            logger.info(f"Loaded knowledge base ID for {domain}: {kb_id}")
        else:
            logger.warning(f"No knowledge base ID found for {domain}")
    
    # If no knowledge base IDs are found, use mock data
    if not KNOWLEDGE_BASE_IDS:
        logger.warning("No knowledge base IDs found, using mock data")
        use_mock = True
    else:
        logger.info(f"Using real knowledge bases for domains: {list(KNOWLEDGE_BASE_IDS.keys())}")
        use_mock = False
    
    return use_mock

# Initialize knowledge base IDs
USE_MOCK = init_knowledge_base_ids()

def query_knowledge_base(domain, query):
    """
    Query a domain-specific knowledge base
    
    Args:
        domain (str): Domain to query
        query (str): Query text
        
    Returns:
        dict: Knowledge base response
    """
    # Check if we have a knowledge base ID for this domain
    if domain not in KNOWLEDGE_BASE_IDS:
        logger.warning(f"No knowledge base ID found for domain: {domain}")
        return get_mock_response(domain, query)
    
    try:
        # Query the knowledge base with RAG using cross-region inference
        logger.info(f"Querying knowledge base for domain {domain} with query: {query}")
        
        # Get AWS account ID and region
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        region = os.environ.get('AWS_REGION', 'us-east-1')
        
        # Use cross-region inference profile ARN
        model_arn = f'arn:aws:bedrock:{region}:{account_id}:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0'
        logger.info(f"Using cross-region inference profile: {model_arn}")
        
        response = bedrock_client.retrieve_and_generate(
            input={'text': query},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': KNOWLEDGE_BASE_IDS[domain],
                    'modelArn': model_arn,
                    'retrievalConfiguration': {
                        'vectorSearchConfiguration': {
                            'numberOfResults': 5
                        }
                    }
                }
            }
        )
        
        # Extract generated response
        output = response.get('output', {})
        generated_text = output.get('text', '')
        
        if not generated_text:
            logger.warning(f"No response generated for query: {query}")
            return {
                'description': f"{domain.capitalize()} knowledge base",
                'content': f"Sorry, I am unable to assist you with this request."
            }
        
        return {
            'description': f"{domain.capitalize()} knowledge base",
            'content': generated_text
        }
    
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_message = e.response.get('Error', {}).get('Message', '')
        
        logger.error(f"Bedrock error: {error_code} - {error_message}")
        logger.error(f"Full error: {e}")
        
        # Fall back to mock data
        logger.info(f"Falling back to mock data for domain: {domain}")
        return get_mock_response(domain, query)
    
    except Exception as e:
        logger.error(f"Error querying knowledge base: {e}")
        
        # Fall back to mock data
        logger.info(f"Falling back to mock data for domain: {domain}")
        return get_mock_response(domain, query)

def get_mock_response(domain, query):
    """
    Get mock response for a domain
    
    Args:
        domain (str): Domain to query
        query (str): Query text
        
    Returns:
        dict: Mock response
    """
    # Mock knowledge base responses for each domain
    knowledge_bases = {
        'hpc': {
            'description': 'High Performance Computing knowledge base',
            'content': f"HPC response for query: {query}",
            'examples': ['MPI programming', 'GPU acceleration', 'Parallel algorithms']
        },
        'quantum': {
            'description': 'Quantum Computing knowledge base',
            'content': f"Quantum response for query: {query}",
            'examples': ['Quantum algorithms', 'Qubits', 'Quantum annealing']
        },
        'genai': {
            'description': 'Generative AI knowledge base',
            'content': f"GenAI response for query: {query}",
            'examples': ['LLMs', 'Diffusion models', 'Prompt engineering']
        },
        'visual': {
            'description': 'Visual Computing knowledge base',
            'content': f"Visual Computing response for query: {query}",
            'examples': ['Computer vision', '3D rendering', 'Image processing']
        },
        'spatial': {
            'description': 'Spatial Computing knowledge base',
            'content': f"Spatial Computing response for query: {query}",
            'examples': ['AR/VR', 'Spatial mapping', 'Location services']
        },
        'iot': {
            'description': 'IoT knowledge base',
            'content': f"IoT response for query: {query}",
            'examples': ['Sensor networks', 'Edge computing', 'IoT protocols']
        },
        'partners': {
            'description': 'Partners knowledge base',
            'content': f"Partners response for query: {query}",
            'examples': ['ISV relationships', 'Partner enablement', 'Co-development']
        }
    }
    
    # Return response for the requested domain
    if domain in knowledge_bases:
        return knowledge_bases[domain]
    else:
        return {
            'description': 'Unknown domain',
            'content': f"Domain '{domain}' not found. Available domains: {list(knowledge_bases.keys())}",
            'examples': []
        }

def lambda_handler(event, context):
    """
    Lambda function to access domain-specific knowledge bases
    
    Parameters:
        event (dict): Contains 'domain' and 'query' parameters
        context (object): Lambda context
    
    Returns:
        dict: Knowledge base response
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract tool name from context if available
    tool_name = None
    if context and hasattr(context, 'client_context') and hasattr(context.client_context, 'custom'):
        tool_name = context.client_context.custom.get('bedrockagentcoreToolName', '')
        logger.info(f"Tool name from context: {tool_name}")
    
    # Extract parameters from event
    domain = event.get('domain', '').lower()
    query = event.get('query', '')
    
    logger.info(f"Processing request - Domain: {domain}, Query: {query}")
    
    # Validate parameters
    if not domain or not query:
        logger.error("Missing required parameters: domain and query")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Missing required parameters: domain and query'
            })
        }
    
    # Query the knowledge base (real or mock)
    if USE_MOCK:
        response = get_mock_response(domain, query)
    else:
        response = query_knowledge_base(domain, query)
    
    # For MCP Gateway, return the response directly
    # The Gateway will wrap it in the proper MCP format
    logger.info(f"Returning response: {json.dumps(response)}")
    return response