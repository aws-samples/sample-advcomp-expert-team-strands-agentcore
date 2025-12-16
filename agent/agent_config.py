"""
Agent Configuration

This module provides configuration for the Advanced Computing Team Collaboration Swarm.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Default model ID
DEFAULT_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

# Agent-specific model configuration
AGENT_MODELS = {
    "coordinator": "us.anthropic.claude-haiku-4-5-20251001-v1:0",  # Haiku for faster coordination with higher limits  
    "hpc_expert": DEFAULT_MODEL_ID,  
    "genai_expert": DEFAULT_MODEL_ID,
    "quantum_expert": DEFAULT_MODEL_ID,
    "visual_expert": DEFAULT_MODEL_ID,
    "spatial_expert": DEFAULT_MODEL_ID,
    "iot_expert": DEFAULT_MODEL_ID,
    "partners_expert": DEFAULT_MODEL_ID
}

# Agent-specific model parameters
AGENT_PARAMS = {
    "coordinator": {"temperature": 0.2},  # Lower temperature for more focused domain selection
    "hpc_expert": {"temperature": 0.4},
    "genai_expert": {"temperature": 0.4},
    "quantum_expert": {"temperature": 0.4},
    "visual_expert": {"temperature": 0.4},
    "spatial_expert": {"temperature": 0.4},
    "iot_expert": {"temperature": 0.4},
    "partners_expert": {"temperature": 0.4}
}

def get_model_for_agent(agent_name):
    """
    Get the model ID for a specific agent.
    
    Args:
        agent_name (str): The name of the agent
        
    Returns:
        str: The model ID to use for the agent
    """
    return AGENT_MODELS.get(agent_name, DEFAULT_MODEL_ID)


def get_agent_params(agent_name):
    """
    Get the model parameters for a specific agent.
    
    Args:
        agent_name (str): The name of the agent
        
    Returns:
        dict: The model parameters to use for the agent
    """
    return AGENT_PARAMS.get(agent_name, {"temperature": 0.4})