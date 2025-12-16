"""
Advanced Computing Team Collaboration Swarm

This module implements a multi-agent swarm using Strands Agents for collaborative
problem-solving across advanced computing domains with shared memory.
"""

import logging
import os
from datetime import datetime
from strands import Agent
from strands.models import BedrockModel
from strands.multiagent import Swarm
from strands.hooks import AfterInvocationEvent, AgentInitializedEvent, HookProvider, HookRegistry
from strands_tools.agent_core_memory import AgentCoreMemoryToolProvider
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient

# Import telemetry
from telemetry import telemetry

# Import domain-specific prompts
from domain_prompts import (
    HPC_PROMPT, GENAI_PROMPT, QUANTUM_PROMPT, VISUAL_PROMPT,
    SPATIAL_PROMPT, IOT_PROMPT, PARTNERS_PROMPT
)

# Enhanced coordinator prompt with expert team details
COORDINATOR_PROMPT = """You are a coordinator for the Advanced Computing Team Collaboration Swarm.

**MEMORY AND KNOWLEDGE WORKFLOW:**
1. **Check Memory First**: You have long-term memory tools. For questions about topics you've previously explored, search your memory before calling experts.
2. **Provide Detailed Memory Responses**: When memory has relevant information, provide specific details, examples, and actionable insights - not just high-level summaries.
3. **Expert Consultation**: For new technical questions or when memory lacks sufficient actionable detail, use the advcomp_swarm tool.
4. **ALWAYS Save Learning**: After EVERY expert consultation, you MUST use your memory save tool to store: (a) the user's question, (b) which experts were consulted, (c) key technical insights from the response. This is MANDATORY, not optional.

**Available Expert Team:**
- **hpc**: High Performance Computing (parallel computing, clusters, AWS PCS, ParallelCluster, performance optimization)
- **quantum**: Quantum Computing (quantum algorithms, circuits, Amazon Braket, quantum-classical hybrid systems)
- **genai**: Generative AI & ML (ALL AI/ML questions, predictive analytics, computer vision AI, LLMs, machine learning models, multi-agent systems, RAG, AWS Bedrock, SageMaker)
- **visual**: Visual Computing (3D graphics, GPU acceleration, rendering, visualization dashboards)
- **spatial**: Spatial Computing (3D mapping, geospatial, AR/VR/XR, digital twins, facility layouts)
- **iot**: Internet of Things (cameras, sensors, robots, edge devices, edge computing, AWS IoT, real-time data collection, equipment monitoring)
- **partners**: Advanced Computing Partnerships (technology partnerships, ISVs, solutions)

**CRITICAL RULE - AWS SERVICE QUESTIONS:**
If the question mentions ANY AWS or Amazon service name, you MUST use the advcomp_swarm tool. NEVER answer AWS service questions from your training data - always consult experts with knowledge base access.

**AWS Service Detection Examples:**
- "AWS IoT SiteWise" → Use advcomp_swarm with iot expert
- "Amazon Bedrock" → Use advcomp_swarm with genai expert  
- "AWS PCS" or "ParallelCluster" → Use advcomp_swarm with hpc expert
- "Amazon Braket" → Use advcomp_swarm with quantum expert
- "Amazon Rekognition" → Use advcomp_swarm with visual expert
- "Amazon Location Service" → Use advcomp_swarm with spatial expert

**Rule of thumb:** If you see "AWS" or "Amazon" followed by a service name, use advcomp_swarm.

**Decision Process:**
1. **AWS Service Questions**: Does the question mention an AWS service? → Use advcomp_swarm tool with relevant experts
2. **Simple Factual Questions**: For basic non-AWS factual questions (like "What is the capital of Florida?"), answer directly
3. **Advanced Computing Topics (non-AWS)**: Search memory for relevant knowledge first
4. If memory has sufficient information, provide detailed answer
5. **If using advcomp_swarm tool, FIRST think through your expert selection**:
   - Analyze the query and identify ALL relevant domains
   - Check for key indicators:
     * AI/ML keywords (AI, ML, predict, analytics, intelligence, learning, model) → genai
     * Digital twins, 3D mapping, facility layouts, spatial data → spatial
     * Cameras, sensors, robots, edge devices, IoT → iot
     * Parallel computing, clusters, HPC → hpc
     * Quantum algorithms, circuits → quantum
     * 3D graphics, visualization, GPU → visual
   - List out which experts are needed and why
   - Consider: How many distinct technical areas does this touch?
   - Then call advcomp_swarm with your selected experts
6. **MANDATORY**: After expert consultation, immediately save the conversation to memory using your memory save tool

**Examples requiring advcomp_swarm:**
- "What is AWS IoT SiteWise?" → advcomp_swarm with iot expert
- "How does Amazon Bedrock work?" → advcomp_swarm with genai expert
- "What is AWS PCS?" → advcomp_swarm with hpc expert
- "Use AI to predict failures" → Consider genai expert (AI keyword detected)
- "Factory with cameras and predictive maintenance" → Consider iot, genai, and spatial experts (multiple domains)

**Expert Selection Guidelines:**
- **BEFORE calling advcomp_swarm, think through your expert selection**:
  1. What domains does this query touch? (List them out)
  2. Which experts would provide the most value?
  3. How many distinct technical areas are involved?
  4. Final expert list: [list the expert names]
- **Simple queries** ("What is X?", single service questions): 1 expert is typically sufficient
- **Complex queries** (multiple domains, integration needs, architecture): Select the 2-3 MOST relevant experts
- Use expert names exactly: hpc, quantum, genai, visual, spatial, iot, partners
- **IMPORTANT**: Select a maximum of 2-3 experts for best results. More experts may not all participate due to collaboration dynamics.

**Tool Usage:**
Direct Answer: For simple factual questions, answer immediately
Memory: Use memory tools to search and save advanced computing knowledge
Experts: advcomp_swarm(query="your question", experts="hpc,quantum,genai")

For advanced computing topics: check memory first, then consult experts if needed, then save new learning.
For simple facts: answer directly without tools."""

# Import agent model configuration
from agent_config import get_model_for_agent, AGENT_PARAMS

# Configure logging with more verbose output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing logging configuration
)
logger = logging.getLogger("advcomp_swarm")
logger.setLevel(logging.DEBUG)

# Enable all relevant debug logs
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.getLogger("bedrock_agentcore").setLevel(logging.DEBUG)

# Force all loggers to use DEBUG level
logging.root.setLevel(logging.DEBUG)

# Load environment variables
from dotenv import load_dotenv
import os

# Try to load from .env.agents file
load_dotenv('.env.agents')

# Log AWS credentials status (AgentCore provides IAM role credentials)
if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
    logger.info(f"AWS credentials found: {os.environ.get('AWS_ACCESS_KEY_ID')[:4]}...")
else:
    logger.info("Using IAM role credentials (normal for AgentCore Runtime)")
    print(f"🔧 DEBUG: Using IAM role credentials for AWS services")

# Initialize memory client
region = os.environ.get("AWS_REGION", "us-east-1")
memory_enabled = os.environ.get("MEMORY_ENABLED", "true").lower() == "true"
bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

# Initialize MCP client for knowledge base access
gateway_url = os.environ.get("GATEWAY_URL")
gateway_token = None

# OAuth configuration for Gateway authentication
cognito_secret_arn = os.environ.get("COGNITO_SECRET_ARN")
oauth_client_id = None
oauth_client_secret = None
oauth_token_endpoint = None
oauth_scope = None

if cognito_secret_arn:
    try:
        import boto3, json
        secrets_client = boto3.client('secretsmanager', region_name=region)
        secret_data = json.loads(secrets_client.get_secret_value(SecretId=cognito_secret_arn)['SecretString'])
        oauth_client_id = secret_data['client_id']
        oauth_client_secret = secret_data['client_secret']
        oauth_token_endpoint = secret_data['token_endpoint']
        oauth_scope = secret_data['scope']
        logger.info("✅ Loaded OAuth credentials")
    except Exception as e:
        logger.error(f"Failed to load OAuth credentials: {e}")

logger.info(f"DEBUG: Gateway URL: {gateway_url}")

# Check for real gateway URL
if not gateway_url or "mock" in gateway_url.lower():
    logger.warning("No real Gateway URL configured - knowledge base tools will be disabled")
    logger.warning("To enable: 1) Deploy Gateway with 'python deploy.py --gateway-only' 2) Run 'python setup_cognito_user.py' to get token")
    # Keep the values for potential later use, but mark as mock
    if not gateway_url:
        gateway_url = "http://localhost:8080/mock-gateway"
        gateway_token = "mock-token"

# Memory configuration
memory_client = None
memory_name = os.environ.get("MEMORY_NAME", "AdvCompSwarm_STM")
memory_id = os.environ.get("MEMORY_ID")  # Load from environment, will be set during deployment

# Initialize memory client if enabled
if memory_enabled:
    try:
        logger.info(f"Initializing memory client in region {region}")
        print(f"🔧 DEBUG: Attempting to create MemoryClient in region {region}")
        
        # Create memory client - MemoryClient doesn't accept config parameter
        memory_client = MemoryClient(region_name=region)
        
        # Test the memory client by listing memories
        test_memories = memory_client.list_memories()
        logger.info(f"Memory client initialized successfully - found {len(test_memories)} existing memories")
        print(f"🔧 DEBUG: Memory client test successful - {len(test_memories)} memories found")
        
    except Exception as e:
        logger.error(f"Failed to initialize memory client: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print(f"🔧 DEBUG: Memory client initialization failed: {e}")
        memory_enabled = False
        memory_client = None

# Use existing deployed memory resource
def setup_memory():
    # If memory is not enabled or client initialization failed, return None
    if not memory_enabled or not memory_client:
        logger.warning("Memory is not enabled or client initialization failed")
        print(f"🔧 DEBUG: Memory setup skipped - enabled: {memory_enabled}, client: {memory_client is not None}")
        return None
    
    # Use the existing deployed semantic memory
    logger.info(f"Using existing semantic memory: {memory_id}")
    print(f"🔧 DEBUG: Using existing semantic memory: {memory_id}")
    return memory_id

# Enhanced memory hook for learning from swarm interactions with short-term context
class SwarmLearningMemoryHook(HookProvider):
    def __init__(self, memory_id, client, actor_id, session_id):
        self.memory_id = memory_id
        self.client = client
        self.actor_id = actor_id
        self.session_id = session_id
    
    def on_agent_initialized(self, event):
        """Load recent conversation history when agent starts for short-term memory"""
        try:
            # Get recent events from the same session for context using the correct API
            import boto3
            data_client = boto3.client('bedrock-agentcore', region_name=region)
            
            # List recent events from this session
            response = data_client.list_events(
                memoryId=self.memory_id,
                actorId=self.actor_id,
                sessionId=self.session_id,
                maxResults=10,  # Get more events to find conversation pairs
                includePayloads=True
            )
            
            events = response.get('events', [])
            if events:
                # Format recent conversation for context - look for user/assistant pairs
                context_messages = []
                
                # Sort events by timestamp to get chronological order
                sorted_events = sorted(events, key=lambda x: x.get('eventTimestamp', 0))
                
                for event_item in sorted_events[-10:]:  # Last 10 events
                    payload = event_item.get('payload', [])
                    for item in payload:
                        if 'conversational' in item:
                            conv = item['conversational']
                            role = conv.get('role', 'UNKNOWN')
                            content = conv.get('content', {})
                            
                            # Handle different content formats
                            if isinstance(content, dict) and 'text' in content:
                                text = content['text']
                            elif isinstance(content, str):
                                text = content
                            else:
                                text = str(content)
                            
                            if text and text.strip():
                                # Parse user/assistant pairs from the stored format
                                if 'User:' in text and 'Assistant:' in text:
                                    # This is a stored conversation pair
                                    lines = text.split('\n')
                                    for line in lines:
                                        if line.startswith('User:'):
                                            context_messages.append(line)
                                        elif line.startswith('Assistant:'):
                                            context_messages.append(line)
                                else:
                                    # Single message
                                    role_name = 'User' if role.upper() == 'USER' else 'Assistant'
                                    context_messages.append(f"{role_name}: {text}")
                
                if context_messages:
                    # Take only the most recent conversation turns (last 6 messages = 3 exchanges)
                    recent_context = context_messages[-6:]
                    context = "\n".join(recent_context)
                    
                    logger.info(f"Loaded {len(recent_context)} recent conversation messages for context")
                    print(f"🔧 DEBUG: Loaded conversation context: {context[:300]}...")
                    
                    # Add context to agent's system prompt with clear instructions
                    context_instruction = f"\n\nRECENT CONVERSATION CONTEXT:\n{context}\n\nIMPORTANT: Use this context to understand follow-up questions and references like 'that city', 'it', 'the population of that city', etc. If the user refers to something mentioned earlier, use this context to understand what they mean."
                    
                    event.agent.system_prompt += context_instruction
                    
                    logger.info(f"✅ Added conversation context to agent system prompt")
                    print(f"🔧 DEBUG: ✅ Context added to system prompt")
                else:
                    logger.info("No conversation content found in recent events")
                    print(f"🔧 DEBUG: No conversation content found")
            else:
                logger.info("No previous conversation history found")
                print(f"🔧 DEBUG: No previous events found")
                
        except Exception as e:
            logger.error(f"Failed to load conversation context: {e}")
            print(f"🔧 DEBUG: Context loading failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Continue without context - don't fail agent initialization
    
    def save_memories(self, event: AfterInvocationEvent):
        try:
            print(f"🔧 DEBUG: SwarmLearningMemoryHook.save_memories called")
            messages = event.agent.messages
            print(f"🔧 DEBUG: Agent has {len(messages)} messages")
            
            if len(messages) >= 2:
                # Handle different message formats safely
                user_msg = None
                assistant_msg = None
                
                # Extract user message
                if messages[-2]["role"] == "user":
                    content = messages[-2]["content"]
                    if isinstance(content, list) and len(content) > 0:
                        if isinstance(content[0], dict) and "text" in content[0]:
                            user_msg = content[0]["text"]
                        else:
                            user_msg = str(content[0])
                    elif isinstance(content, str):
                        user_msg = content
                
                # Extract assistant message
                if messages[-1]["role"] == "assistant":
                    content = messages[-1]["content"]
                    if isinstance(content, list) and len(content) > 0:
                        if isinstance(content[0], dict) and "text" in content[0]:
                            assistant_msg = content[0]["text"]
                        else:
                            assistant_msg = str(content[0])
                    elif isinstance(content, str):
                        assistant_msg = content
                
                if user_msg and assistant_msg:
                    print(f"🔧 DEBUG: Saving memory for user/assistant exchange")
                    
                    # Use the simplified format from the documentation
                    content = f"User: {user_msg}\nAssistant: {assistant_msg}"
                    
                    # Add swarm execution context if available
                    if os.path.exists('/tmp/swarm_execution_proof.txt'):
                        try:
                            with open('/tmp/swarm_execution_proof.txt', 'r', encoding='utf-8') as f:
                                proof_content = f.read()
                                # Extract expert information for learning
                                import ast
                                for line in proof_content.split('\n'):
                                    if 'SWARM TOOL EXECUTED with experts' in line:
                                        experts_str = line.split('experts ')[1].strip()
                                        try:
                                            experts_list = ast.literal_eval(experts_str)
                                            swarm_context = f"\n\nSWARM_LEARNING: Query required experts {experts_list} for domain expertise."
                                            content += swarm_context
                                            logger.info(f"Added swarm learning context: {experts_list}")
                                            print(f"🔧 DEBUG: Added swarm context: {experts_list}")
                                            break
                                        except:
                                            pass
                        except Exception as e:
                            logger.warning(f"Could not extract swarm context: {e}")
                            print(f"🔧 DEBUG: Swarm context extraction failed: {e}")
                    
                    # Use the correct create_event API format
                    from datetime import datetime, timezone
                    
                    print(f"🔧 DEBUG: Creating memory event with content length: {len(content)}")
                    print(f"🔧 DEBUG: Memory ID: {self.memory_id}")
                    print(f"🔧 DEBUG: Actor ID: {self.actor_id}")
                    print(f"🔧 DEBUG: Session ID: {self.session_id}")
                    
                    # Use the correct create_event API format
                    import boto3
                    from datetime import datetime, timezone
                    
                    data_client = boto3.client('bedrock-agentcore', region_name=region)
                    
                    # Format payload exactly like AgentCoreMemoryToolProvider does
                    formatted_payload = [
                        {"conversational": {"content": {"text": user_msg}, "role": "USER"}},
                        {"conversational": {"content": {"text": assistant_msg}, "role": "ASSISTANT"}}
                    ]
                    
                    # CRITICAL FIX: Use the correct parameter names
                    data_client.create_event(
                        memoryId=self.memory_id,
                        actorId=self.actor_id,
                        sessionId=self.session_id,
                        eventTimestamp=datetime.now(timezone.utc),
                        payload=formatted_payload
                    )
                    
                    # Verify the event was created
                    print(f"🔧 DEBUG: Event created for session {self.session_id}")
                    logger.info(f"Saved enhanced memory with swarm context: {self.actor_id}")
                    print(f"🔧 DEBUG: ✅ Memory saved successfully")
                else:
                    print(f"🔧 DEBUG: No valid user/assistant messages to save")
            else:
                print(f"🔧 DEBUG: Not enough messages to save ({len(messages)} < 2)")
        except Exception as e:
            logger.error(f"Memory save failed: {e}")
            print(f"🔧 DEBUG: ❌ Memory save failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def register_hooks(self, registry: HookRegistry) -> None:
        from strands.hooks import AgentInitializedEvent
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        registry.add_callback(AfterInvocationEvent, self.save_memories)



def create_agent(name, prompt, actor_id, session_id, memory_id, input_tools):
    """
    Create an agent with the specified configuration
    
    Args:
        name: Agent name
        prompt: System prompt
        actor_id: Actor ID for memory
        session_id: Session ID for memory continuity
        memory_id: Memory ID
        input_tools: Input tools (including swarm tool and knowledge base tools)
        
    Returns:
        Agent: Configured agent
    """
    try:
        # Start with the input tools (preserves swarm tool and kb tools)
        tools = list(input_tools) if input_tools else []
        hooks = None
        
        if memory_id and memory_enabled and memory_client:
            try:
                logger.info(f"Attempting to add memory tools to agent {name}")
                print(f"🔧 DEBUG: Memory ID: {memory_id}")
                print(f"🔧 DEBUG: Actor ID: {actor_id}")
                print(f"🔧 DEBUG: Session ID: {session_id}")
                
                # Get the semantic memory strategy ID from the memory
                # Namespace pattern: /strategies/{memoryStrategyId}/actors/{actorId}
                try:
                    import boto3
                    control_client = boto3.client('bedrock-agentcore-control', region_name=region)
                    memory_details = control_client.get_memory(memoryId=memory_id)
                    strategies = memory_details.get('memory', {}).get('strategies', [])
                    if strategies:
                        strategy_id = strategies[0]['strategyId']
                        namespace = f"/strategies/{strategy_id}/actors/{actor_id}"
                        print(f"🔧 DEBUG: Using semantic memory namespace: {namespace}")
                    else:
                        # Fallback to old namespace if no strategies found
                        namespace = f"advcomp/{actor_id}/knowledge"
                        print(f"🔧 DEBUG: No strategies found, using fallback namespace: {namespace}")
                except Exception as e:
                    print(f"🔧 DEBUG: Error getting strategy ID: {e}")
                    namespace = f"advcomp/{actor_id}/knowledge"
                    print(f"🔧 DEBUG: Using fallback namespace: {namespace}")
                
                # Initialize memory provider with all required parameters
                memory_provider = AgentCoreMemoryToolProvider(
                    memory_id=memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    namespace=namespace,
                    region=region
                )
                
                # Test the provider before using it
                memory_tools = memory_provider.tools
                print(f"🔧 DEBUG: Memory provider created {len(memory_tools) if memory_tools else 0} tools")
                
                if memory_tools and len(memory_tools) > 0:
                    tools.extend(memory_tools)
                    logger.info(f"✅ Added {len(memory_tools)} memory tools to agent {name}")
                    print(f"🔧 DEBUG: Memory tools added: {[getattr(tool, 'name', str(tool)) for tool in memory_tools]}")
                    
                    # Create enhanced memory hooks for swarm learning
                    memory_hooks = SwarmLearningMemoryHook(
                        memory_id=memory_id,
                        client=memory_client,
                        actor_id=actor_id,
                        session_id=session_id
                    )
                    hooks = [memory_hooks]
                    print(f"🔧 DEBUG: Memory hooks created successfully")
                else:
                    logger.warning(f"Memory provider created but no tools available for agent {name}")
                    print(f"🔧 DEBUG: No memory tools returned from provider")
                    
            except Exception as e:
                logger.error(f"Failed to add memory tools to agent {name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                print(f"🔧 DEBUG: Memory tool creation failed: {e}")
                # Continue without memory tools but keep other tools
        else:
            if not memory_id:
                print(f"🔧 DEBUG: No memory ID available for agent {name}")
            if not memory_enabled:
                print(f"🔧 DEBUG: Memory not enabled for agent {name}")
            if not memory_client:
                print(f"🔧 DEBUG: No memory client available for agent {name}")
        
        # Input tools already include knowledge base tools and swarm tool
        logger.info(f"Agent {name} starting with {len(tools)} total tools")
        print(f"🔧 DEBUG: Agent {name} final tool count: {len(tools)}")
        
        # Get model ID for this agent
        model_id = get_model_for_agent(name)
        
        # Get agent-specific parameters
        params = AGENT_PARAMS.get(name, {"temperature": 0.4})
        
        # Create a BedrockModel instance
        logger.info(f"Creating model for agent {name} with model ID {model_id} and params {params}")
        
        # For cross-region inference profiles (starting with 'us.'), don't specify region
        model_kwargs = {
            "model_id": model_id,
            "temperature": params.get("temperature", 0.4),
            "streaming": False,  # Disable streaming to avoid ConverseStream issues
        }
        
        # Only add region for non-cross-region models
        if not model_id.startswith('us.'):
            model_kwargs["region_name"] = region
            
        bedrock_model = BedrockModel(**model_kwargs)
        
        # Create the agent
        agent = Agent(
            name=name,
            system_prompt=prompt,
            tools=tools,
            hooks=hooks,
            model=bedrock_model
        )
        
        
        logger.info(f"Created agent {name} with {len(tools)} tools")
        return agent
    except Exception as e:
        logger.error(f"Error creating agent {name}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Fallback to basic agent without memory or tools
        return Agent(name=name, system_prompt=prompt)



# Import swarm tool implementation
from strands import tool
from strands.multiagent import Swarm
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# Predefined expert configurations
EXPERT_CONFIGS = {
    "hpc": {
        "name": "hpc_expert",
        "system_prompt": HPC_PROMPT
    },
    "quantum": {
        "name": "quantum_expert", 
        "system_prompt": QUANTUM_PROMPT
    },
    "genai": {
        "name": "genai_expert",
        "system_prompt": GENAI_PROMPT
    },
    "visual": {
        "name": "visual_expert",
        "system_prompt": VISUAL_PROMPT
    },
    "spatial": {
        "name": "spatial_expert",
        "system_prompt": SPATIAL_PROMPT
    },
    "iot": {
        "name": "iot_expert",
        "system_prompt": IOT_PROMPT
    },
    "partners": {
        "name": "partners_expert",
        "system_prompt": PARTNERS_PROMPT
    }
}

@tool
def advcomp_swarm(query: str, experts: str = "hpc,quantum,genai") -> str:
    """Execute advanced computing swarm with selected experts.
    
    Args:
        query: The question to answer
        experts: Comma-separated list of experts (hpc, quantum, genai, visual, spatial, iot, partners)
    """
    try:
        logger.info(f"🎯 EXPERT SWARM CALLED! Query: {query[:100]}...")
        logger.info(f"🎯 Experts requested: {experts}")
        logger.info(f"🎯 Experts type: {type(experts)}")
        
        # Start tracking async task to keep session alive during long swarm execution
        task_id = None
        try:
            task_id = app.add_async_task("expert_swarm_execution", {
                "query": query[:100],
                "experts": experts,
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"Started async task tracking: {task_id}")
        except Exception as e:
            logger.warning(f"Could not start async task tracking: {e}")
            # Continue without async tracking
        
        # Parse expert list
        expert_list = [e.strip().lower() for e in experts.split(",")]
        logger.info(f"Parsed expert list: {expert_list}")
        logger.info(f"Number of experts: {len(expert_list)}")
        
        # Get MCP tools from Gateway using OAuth client_credentials
        mcp_tools = []
        mcp_client = None
        if gateway_url and "mock" not in gateway_url.lower() and oauth_client_id:
            try:
                import httpx, base64
                
                # Get OAuth access token using client_credentials
                auth_string = f"{oauth_client_id}:{oauth_client_secret}"
                auth_b64 = base64.b64encode(auth_string.encode()).decode()
                
                token_response = httpx.post(
                    oauth_token_endpoint,
                    headers={"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"},
                    data={"grant_type": "client_credentials", "scope": oauth_scope}
                )
                gateway_token = token_response.json()['access_token']
                logger.info("✅ Got OAuth access token")
                
                def create_transport():
                    return streamablehttp_client(gateway_url, headers={"Authorization": f"Bearer {gateway_token}"})
                
                mcp_client = MCPClient(create_transport)
                mcp_client.__enter__()
                mcp_tools = mcp_client.list_tools_sync()
                logger.info(f"✅ Retrieved {len(mcp_tools)} MCP tools")
            except Exception as e:
                logger.error(f"❌ MCP connection failed: {e}")
                mcp_client = None

        # Create agents with MCP tools (connection stays open)
        agents = []
        for expert_type in expert_list:
            if expert_type in EXPERT_CONFIGS:
                config = EXPERT_CONFIGS[expert_type]
                
                team_members = [EXPERT_CONFIGS[e]["name"] for e in expert_list if e in EXPERT_CONFIGS]
                enhanced_prompt = config["system_prompt"] + f"\n\n**YOUR TEAM FOR THIS CONSULTATION:** {', '.join(team_members)}\n**CRITICAL:** After your analysis, explicitly hand off to EACH remaining team member by name."
                
                # Create model without region for cross-region inference profiles
                model_kwargs = {
                    "model_id": bedrock_model_id,
                    "temperature": 0.4,
                    "streaming": False,
                }
                
                # Only add region for non-cross-region models
                if not bedrock_model_id.startswith('us.'):
                    model_kwargs["region_name"] = region
                
                agent = Agent(
                    name=config["name"],
                    system_prompt=enhanced_prompt,
                    tools=mcp_tools if mcp_tools else [],
                    model=BedrockModel(**model_kwargs)
                )
                agents.append(agent)
                logger.info(f"Created {config['name']} with {len(mcp_tools)} tools")
        
        if not agents:
            if mcp_client:
                mcp_client.__exit__(None, None, None)
            return "No valid experts specified. Available: hpc, quantum, genai, visual, spatial, iot, partners"
        
        # Execute swarm with persistent MCP connection
        swarm = Swarm(
            agents,
            max_handoffs=20,
            max_iterations=20,
            execution_timeout=1800.0,
            node_timeout=600.0
        )
        
        logger.info(f"Executing expert swarm with {len(agents)} agents...")
        logger.info(f"Agent names: {[agent.name for agent in agents]}")
        
        result = swarm(query)
        
        # Close MCP connection after swarm completes
        if mcp_client:
            try:
                mcp_client.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing MCP client: {e}")
        

        
        logger.info(f"Swarm completed in {result.execution_time}ms")
        
        # Log node history details
        logger.info(f"Node history length: {len(result.node_history)}")
        logger.info(f"Node IDs: {[node.node_id for node in result.node_history]}")
        
        # Extract individual agent responses for structured output
        individual_responses = {}
        for i, node in enumerate(result.node_history):
            if hasattr(node.executor, 'messages') and node.executor.messages:
                # Collect ALL assistant messages to show complete conversation
                agent_messages = []
                for msg in node.executor.messages:
                    if msg.get('role') == 'assistant' and msg.get('content'):
                        for content_block in msg['content']:
                            if 'text' in content_block:
                                text = content_block['text']
                                if text.strip():  # Only skip empty messages
                                    agent_messages.append(text)
                
                # Combine all messages with separators
                if agent_messages:
                    individual_responses[node.node_id] = "\n\n---\n\n".join(agent_messages)
        
        # Return full individual responses like the test script
        response_parts = []
        for node in result.node_history:
            if node.node_id in individual_responses:
                response_parts.append(individual_responses[node.node_id])
        
        # Extract tool calls from node history
        tool_calls = []
        for node in result.node_history:
            if hasattr(node.executor, 'messages'):
                for msg in node.executor.messages:
                    if msg.get('role') == 'assistant':
                        for content in msg.get('content', []):
                            if 'toolUse' in content:
                                tool_use = content['toolUse']
                                tool_calls.append({
                                    "agent": node.node_id,
                                    "tool_name": tool_use.get('name', 'unknown'),
                                    "input": tool_use.get('input', {}),
                                    "tool_use_id": tool_use.get('toolUseId', ''),
                                    "status": "called"
                                })
                    elif msg.get('role') == 'user':
                        for content in msg.get('content', []):
                            if 'toolResult' in content:
                                tool_result = content['toolResult']
                                tool_use_id = tool_result.get('toolUseId', '')
                                for tc in tool_calls:
                                    if tc.get('tool_use_id') == tool_use_id:
                                        result_text = ''
                                        for res_content in tool_result.get('content', []):
                                            if 'text' in res_content:
                                                result_text = res_content['text']
                                                break
                                        tc['result_preview'] = result_text
                                        tc['status'] = tool_result.get('status', 'success')
                                        break
        
        # Store individual responses for web app parsing - FIXED
        import os
        import json
        try:
            structured_data = {
                "individual_responses": individual_responses,
                "agent_sequence": [node.node_id for node in result.node_history],
                "execution_time_ms": result.execution_time,
                "status": str(result.status),
                "tool_calls": tool_calls
            }
            with open('/tmp/swarm_structured_data.json', 'w', encoding='utf-8') as f:
                json.dump(structured_data, f)
            logger.info(f"Saved structured data with {len(individual_responses)} responses and {len(tool_calls)} tool calls")
        except Exception as e:
            logger.warning(f"Could not save structured data: {e}")
        
        # CRITICAL: Also create proof file to confirm swarm execution
        try:
            with open('/tmp/swarm_execution_proof.txt', 'w', encoding='utf-8') as f:
                f.write(f"SWARM TOOL EXECUTED with experts {[node.node_id for node in result.node_history]}\n")
                f.write(f"Execution time: {result.execution_time}ms\n")
                f.write(f"Status: {result.status}\n")
                f.write(f"Individual responses: {len(individual_responses)}\n")
        except Exception as e:
            logger.warning(f"Could not create proof file: {e}")
        
        # Complete async task tracking
        if task_id:
            try:
                app.complete_async_task(task_id)
                logger.info(f"Completed async task tracking: {task_id}")
            except Exception as e:
                logger.warning(f"Could not complete async task tracking: {e}")
        
        return "\n\n".join(response_parts)
        
    except Exception as e:
        logger.error(f"Expert swarm failed: {e}")
        
        # Complete async task tracking on error
        if 'task_id' in locals() and task_id:
            try:
                app.complete_async_task(task_id)
                logger.info(f"Completed async task tracking on error: {task_id}")
            except Exception as task_e:
                logger.warning(f"Could not complete async task tracking on error: {task_e}")
        
        return f"⚠️ Expert analysis failed: {str(e)}"

def create_coordinator_agent(session_id=None, enable_mcp=True):
    """
    Create a persistent coordinator agent with memory and swarm tool
    
    Args:
        session_id: Optional session ID for memory continuity
        enable_mcp: Whether to enable MCP for knowledge base access
        
    Returns:
        tuple: (coordinator agent, memory ID, session ID)
    """
    # Set up memory
    memory_id = setup_memory()
    
    # Use provided session ID for memory continuity
    if not session_id:
        # Generate a unique session ID if not provided
        import uuid
        session_id = f"advcomp-session-{uuid.uuid4().hex[:12]}"
    
    logger.info(f"Using session ID for memory: {session_id}")
    print(f"🔧 DEBUG: Memory will use session ID: {session_id}")
    
    # The simple expert_swarm tool creates expert agents for collaboration
    logger.info("Using simple expert_swarm tool for expert team creation")
    
    # Create coordinator agent with memory and swarm tool
    coordinator_actor_id = os.environ.get("COORDINATOR_ACTOR_ID", "coordinator-persistent")
    coordinator_tools = [advcomp_swarm]  # Coordinator gets the working expert swarm tool
    
    coordinator = create_agent("coordinator", COORDINATOR_PROMPT, coordinator_actor_id, session_id, memory_id, coordinator_tools)
    
    # Debug: Verify coordinator tools
    if hasattr(coordinator, 'tools'):
        tool_names = [getattr(tool, 'name', str(tool)) for tool in coordinator.tools]
        logger.info(f"✅ Coordinator created with {len(coordinator.tools)} tools: {tool_names}")
        print(f"🔧 DEBUG: Coordinator tools: {tool_names}")
        
        # Check if official swarm tool is properly registered
        swarm_found = any('swarm' in str(tool).lower() for tool in coordinator.tools)
        logger.info(f"{'✅' if swarm_found else '❌'} Official swarm tool found: {swarm_found}")
        print(f"🔧 DEBUG: Official swarm tool found: {swarm_found}")
    
    logger.info(f"Created coordinator agent with simple expert_swarm tool for expert team creation")
    
    return coordinator, memory_id, session_id





# Custom JSON encoder to handle non-serializable objects
import json
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            # Try to convert the object to a string
            return str(obj)
        except:
            # If that fails, return a placeholder
            return f"<non-serializable object of type {type(obj).__name__}>"

# Initialize the AgentCore app
app = BedrockAgentCoreApp()



@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation via AgentCore"""
    # FORCE IMMEDIATE LOGGING - these should appear in CloudWatch immediately
    import sys
    print(f"🚀🚀🚀 AGENT INVOCATION STARTED - Payload: {payload}", flush=True)
    print(f"🚀🚀🚀 Context: {context}", flush=True)
    sys.stdout.flush()
    
    try:
        # Log the start of invocation with more details
        logger.info(f"Starting agent invocation with payload type: {type(payload)}")
        logger.info(f"Context: {context}")
        
        # Log AWS credentials status
        import boto3
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            logger.info(f"AWS identity: {identity['Arn']}")
        except Exception as e:
            logger.error(f"Error getting AWS identity: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Handle different payload formats
        logger.info(f"Received payload type: {type(payload)}")
        
        # Extract session ID from context (AgentCore provides this)
        session_id = None
        if hasattr(context, 'runtime_session_id'):
            session_id = context.runtime_session_id
        elif hasattr(context, 'session_id'):
            session_id = context.session_id
        
        # Debug context attributes
        logger.info(f"Context attributes: {dir(context)}")
        logger.info(f"Extracted session_id: {session_id}")
        
        if isinstance(payload, dict):
            # JSON payload
            query = payload.get("prompt", "No query provided")
            # Use session_id from context, fallback to payload
            session_id = session_id or payload.get("session_id", None)
            enable_mcp = payload.get("enable_mcp", True)
        elif isinstance(payload, str):
            # String payload
            query = payload
            enable_mcp = True
        else:
            # Unknown payload format
            logger.error(f"Unknown payload format: {type(payload)}")
            return {
                "response": f"Error: Unknown payload format: {type(payload)}",
                "status": "error"
            }
        
        logger.info(f"Received query: {query}")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"MCP enabled: {enable_mcp}")
        
        # Initialize telemetry for this session
        telemetry.start_session(session_id)
        telemetry.log_event("query_received", {"query": query})
        
        # Step 1: Initialize the coordinator agent with the session ID from the request
        coordinator, memory_id, session_id = create_coordinator_agent(session_id, enable_mcp)
        
        # Step 2: Use the coordinator agent (which has memory and swarm tool) to handle the query
        try:
            logger.info("Invoking coordinator agent with memory and swarm tool...")
            print(f"🔧 DEBUG: Starting coordinator execution for query: {query[:50]}...")
            
            # Coordinator will decide whether to use memory or swarm tool based on its prompt
            result = coordinator(query)
            print(f"🔧 DEBUG: Coordinator returned result type: {type(result)}")
            
            # Synthesis is now handled internally by the swarm tool
            print(f"🔧 DEBUG: Coordinator execution completed - using tool results directly")
            
            # CRITICAL DEBUG: Check if coordinator actually used tools vs hallucinated
            actual_tool_calls = []
            # Strands doesn't use tool_calls - synthesis detection moved above
            if False:  # Disabled - using message content approach above
                actual_tool_calls = [getattr(call, 'name', str(call)) for call in result.tool_calls]
                print(f"🔧 DEBUG: ✅ Coordinator used {len(result.tool_calls)} tools: {actual_tool_calls}")
                swarm_used = any('swarm' in str(call).lower() for call in result.tool_calls)
                print(f"🔧 DEBUG: Swarm tool used: {swarm_used}")
                
                # Check for swarm_with_experts specifically
                swarm_func_used = any(getattr(call, 'name', '') == 'swarm_with_experts' for call in result.tool_calls)
                print(f"🔧 DEBUG: swarm_with_experts function used: {swarm_func_used}")
            else:
                print(f"🔧 DEBUG: ❌ Coordinator used NO tools - answered from memory or knowledge")
                
            # Check if the swarm execution proof file exists
            proof_file_exists = False
            try:
                if os.path.exists('/tmp/swarm_execution_proof.txt'):
                    with open('/tmp/swarm_execution_proof.txt', 'r', encoding='utf-8') as f:
                        proof_content = f.read()
                        print(f"🔧 DEBUG: ✅ Swarm execution proof file exists: {proof_content[-200:]}")
                        proof_file_exists = True
                else:
                    print(f"🔧 DEBUG: ❌ No swarm execution proof file found - function may not have been called")
            except Exception as e:
                print(f"🔧 DEBUG: Error checking swarm execution proof: {e}")
                
            # Update hallucination check data
            try:
                hallucination_check_data["proof_file_exists"] = proof_file_exists
                hallucination_check_data["actual_tool_calls"] = actual_tool_calls
            except NameError:
                # Initialize if not already defined
                hallucination_check_data = {
                    "proof_file_exists": proof_file_exists,
                    "actual_tool_calls": actual_tool_calls
                }
            
            print(f"🔧 DEBUG: Coordinator execution completed")
            logger.info("Coordinator execution completed successfully")
            
            # Extract response from coordinator result - handle both memory responses and swarm results
            final_response = ""
            agent_sequence = ["coordinator"]
            individual_responses = {}
            status = "COMPLETED"
            execution_time = 0
            domains_involved = []
            
            # Check for structured swarm data
            try:
                if os.path.exists('/tmp/swarm_structured_data.json'):
                    with open('/tmp/swarm_structured_data.json', 'r', encoding='utf-8') as f:
                        structured_data = json.load(f)
                        individual_responses = structured_data.get('individual_responses', {})
                        agent_sequence = ["coordinator"] + structured_data.get('agent_sequence', [])
                        execution_time = structured_data.get('execution_time_ms', 0)
                        status = structured_data.get('status', 'COMPLETED')
                        domains_involved = structured_data.get('agent_sequence', [])
                        logger.info(f"Loaded structured swarm data: {len(individual_responses)} agent responses")
                        print(f"🔧 DEBUG: Loaded structured data with {len(individual_responses)} responses")
            except Exception as e:
                logger.warning(f"Could not load structured swarm data: {e}")
                print(f"🔧 DEBUG: No structured data available: {e}")
            

            
            # FIXED: Better response extraction from coordinator result
            print(f"🔧 DEBUG: Coordinator result type: {type(result)}")
            print(f"🔧 DEBUG: Coordinator result attributes: {[attr for attr in dir(result) if not attr.startswith('_')]}")
            
            # Extract response from coordinator result - HANDLE EMPTY CONTENT CASE
            if hasattr(result, 'message'):
                message = result.message
                print(f"🔧 DEBUG: Message type: {type(message)}, content: {str(message)[:200]}...")
                
                if isinstance(message, dict) and "content" in message:
                    # Extract text from content array safely
                    content = message.get("content", [])
                    if isinstance(content, list) and len(content) > 0:
                        first_content = content[0]
                        if isinstance(first_content, dict) and "text" in first_content:
                            final_response = first_content["text"]
                            print(f"🔧 DEBUG: ✅ Extracted from message.content[0].text: {len(final_response)} chars")
                        else:
                            final_response = str(first_content)
                            print(f"🔧 DEBUG: ✅ Extracted from first_content: {len(final_response)} chars")
                    else:
                        # EMPTY CONTENT - Check if swarm was executed and get tool results
                        print(f"🔧 DEBUG: ⚠️ Empty content array: {content}")
                        if os.path.exists('/tmp/swarm_execution_proof.txt'):
                            print(f"🔧 DEBUG: ✅ Swarm was executed - extracting tool results directly")
                            
                            # The swarm tool should have returned its result directly in the coordinator's response
                            # If we reach here, it means the coordinator didn't include the swarm results
                            final_response = "Swarm executed but coordinator did not include the expert analysis in its response"
                        else:
                            final_response = str(content)
                elif isinstance(message, str):
                    final_response = message
                    print(f"🔧 DEBUG: ✅ Extracted from string message: {len(final_response)} chars")
                else:
                    final_response = str(message)
                    print(f"🔧 DEBUG: ✅ Extracted from message str(): {len(final_response)} chars")
            elif hasattr(result, 'content'):
                # Try content attribute directly
                content = result.content
                print(f"🔧 DEBUG: Content type: {type(content)}, value: {str(content)[:200]}...")
                if isinstance(content, list) and len(content) > 0:
                    if isinstance(content[0], dict) and "text" in content[0]:
                        final_response = content[0]["text"]
                    else:
                        final_response = str(content[0])
                else:
                    final_response = str(content)
            else:
                # Fallback to string representation
                final_response = str(result)
                print(f"🔧 DEBUG: Using string fallback: {final_response[:200]}...")
            
            # Check if the response contains swarm agent responses
            import re
            raw_response = final_response
            
            # Check if swarm was actually executed (proof file is definitive)
            if os.path.exists('/tmp/swarm_execution_proof.txt'):
                print(f"🔧 DEBUG: ✅ Swarm was actually executed (proof file exists)")
                
                # Look for swarm execution patterns in the response
                if "🎯 **Custom Agent Team Execution Complete**" in raw_response or "**Team Size:**" in raw_response:
                    print(f"🔧 DEBUG: ✅ Found swarm markers in response")
                    
                    # Extract agent information from the response
                    if "**Collaboration Chain:**" in raw_response:
                        chain_match = re.search(r'\*\*Collaboration Chain:\*\* (.+)', raw_response)
                        if chain_match:
                            chain = chain_match.group(1)
                            agent_sequence = ["coordinator"] + [agent.strip() for agent in chain.split('→')]
                            domains_involved = [agent for agent in agent_sequence if agent != "coordinator"]
                            logger.info(f"Extracted agent sequence from swarm: {agent_sequence}")
                            print(f"🔧 DEBUG: Agent sequence: {agent_sequence}")
                else:
                    print(f"🔧 DEBUG: ⚠️ Swarm executed but no markers in coordinator response")
                    print(f"🔧 DEBUG: This means coordinator used swarm but didn't include the results")
                    
                    # Try to extract expert names from proof file
                    try:
                        with open('/tmp/swarm_execution_proof.txt', 'r', encoding='utf-8') as f:
                            proof_content = f.read()
                            # Extract expert names from proof file
                            import ast
                            for line in proof_content.split('\n'):
                                if 'SWARM TOOL EXECUTED with experts' in line:
                                    experts_str = line.split('experts ')[1].strip()
                                    try:
                                        experts_list = ast.literal_eval(experts_str)
                                        domains_involved = experts_list
                                        agent_sequence = ["coordinator"] + experts_list
                                        print(f"🔧 DEBUG: Extracted experts from proof: {experts_list}")
                                        break
                                    except:
                                        pass
                    except Exception as e:
                        print(f"🔧 DEBUG: Error reading proof file: {e}")
            else:
                print(f"🔧 DEBUG: ✅ Coordinator answered from memory/knowledge - no swarm needed")
                individual_responses["coordinator"] = raw_response
                
                # Check for swarm execution even with simple result format
                if os.path.exists('/tmp/swarm_execution_proof.txt'):
                    print(f"🔧 DEBUG: ✅ Swarm was executed (proof file exists) despite simple result format")
                else:
                    print(f"🔧 DEBUG: No swarm execution detected (no proof file)")
                    
                # Final hallucination check will be done below
            
        except Exception as e:
            logger.error(f"Error executing coordinator: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Clean up proof file on error
            try:
                if os.path.exists('/tmp/swarm_execution_proof.txt'):
                    os.remove('/tmp/swarm_execution_proof.txt')
            except:
                pass
                
            return {
                "response": f"Error executing coordinator: {str(e)}. This is likely due to missing permissions for the Bedrock model. Please check that the agent's IAM role has the 'bedrock:InvokeModel' permission.",
                "status": "error"
            }
        
        # Skip hallucination detection to prevent double execution
        # CRITICAL DEBUG: Log the final response details
        print(f"🔧 DEBUG: Final response length: {len(final_response)}")
        print(f"🔧 DEBUG: Final response preview: {final_response[:100]}...")
        print(f"ℹ️ Response processing completed")
        
        # Log individual agent responses for telemetry
        for agent_name, response in individual_responses.items():
            telemetry.log_event("agent_response", {
                "agent": agent_name,
                "response": response
            })
        
        # Extract tool calls from structured data file
        tool_calls_info = []
        try:
            if os.path.exists('/tmp/swarm_structured_data.json'):
                with open('/tmp/swarm_structured_data.json', 'r', encoding='utf-8') as f:
                    structured_data = json.load(f)
                    tool_calls_info = structured_data.get('tool_calls', [])
                    logger.info(f"Loaded {len(tool_calls_info)} tool calls from structured data")
        except Exception as e:
            logger.warning(f"Could not extract tool calls from structured data: {e}")
        
        # Add tool calls to telemetry
        if tool_calls_info:
            telemetry.log_event("tool_calls", {
                "count": len(tool_calls_info),
                "calls": tool_calls_info
            })
        
        # End the telemetry session
        telemetry.end_session()
        
        # Clean up temporary files after successful execution
        try:
            if os.path.exists('/tmp/swarm_execution_proof.txt'):
                os.remove('/tmp/swarm_execution_proof.txt')
            if os.path.exists('/tmp/swarm_structured_data.json'):
                os.remove('/tmp/swarm_structured_data.json')
        except:
            pass
        
        # Step 3: Create a JSON-serializable response
        response_dict = {
            "response": final_response,
            "agent_sequence": agent_sequence,
            "domains_involved": domains_involved,
            "status": status,
            "execution_time_ms": execution_time,
            "session_id": session_id,
            "individual_responses": individual_responses,
            "telemetry": telemetry.get_events()
        }
        
        # Ensure the response is JSON serializable
        try:
            # Test JSON serialization
            json.dumps(response_dict, cls=CustomJSONEncoder)
            logger.info("Response is JSON serializable")
        except Exception as e:
            logger.error(f"Response is not JSON serializable: {e}")
            # Create a safe response
            response_dict = {
                "response": str(final_response),
                "agent_sequence": [str(agent) for agent in agent_sequence],
                "domains_involved": [str(domain) for domain in domains_involved],
                "status": str(status),
                "execution_time_ms": float(execution_time) if execution_time else 0,
                "session_id": str(session_id),
                "telemetry": telemetry.get_events()
            }
        
        logger.info("Returning structured response embedded in AgentCore format")
        # Embed structured data in response for frontend parsing
        structured_json = json.dumps(response_dict, cls=CustomJSONEncoder)
        
        # Return AgentCore format with embedded structured data
        return {
            "response": structured_json,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error in agent_invocation: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Clean up temporary files on error
        try:
            if os.path.exists('/tmp/swarm_execution_proof.txt'):
                os.remove('/tmp/swarm_execution_proof.txt')
            if os.path.exists('/tmp/swarm_structured_data.json'):
                os.remove('/tmp/swarm_structured_data.json')
        except:
            pass
            
        return {
            "response": f"Error: {str(e)}",
            "status": "error"
        }

# For local testing
if __name__ == "__main__":
    app.run()

# Clean up any existing temporary files on module load
try:
    if os.path.exists('/tmp/swarm_execution_proof.txt'):
        os.remove('/tmp/swarm_execution_proof.txt')
    if os.path.exists('/tmp/swarm_structured_data.json'):
        os.remove('/tmp/swarm_structured_data.json')
except:
    pass