# Architecture

This document describes the architecture of the Advanced Computing Team Collaboration Swarm, a multi-agent system built on AWS Bedrock AgentCore.

## Overview

The system implements a coordinator-expert pattern where a coordinator agent analyzes queries and dynamically assembles teams of domain experts (HPC, Quantum, GenAI, Visual, Spatial, IoT, Partners) to collaboratively answer questions. Experts have access to domain-specific knowledge bases via MCP Gateway for real-time AWS documentation retrieval.

## System Architecture

### AWS Infrastructure Architecture

![AWS Architecture Diagram](images/aws-architecture-diagram.png)

### Multi-Agent System Architecture

![Agent Architecture Diagram](images/agent-architecture-diagram.png)

### Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User Interface                              │
│                     (Streamlit Web App)                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AWS Bedrock AgentCore                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    AgentCore Runtime                          │  │
│  │              (Docker Container - ARM64)                       │  │
│  │                                                                │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │         Coordinator Agent (Strands)                     │  │  │
│  │  │  • Analyzes queries                                     │  │  │
│  │  │  • Selects 2-3 relevant experts                         │  │  │
│  │  │  • Has memory tools + advcomp_swarm tool                │  │  │
│  │  └────────────────────────────────────────────────────────┘  │  │
│  │                           │                                    │  │
│  │                           │ calls advcomp_swarm()              │  │
│  │                           ▼                                    │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │         Expert Swarm (Strands Swarm)                    │  │  │
│  │  │  • Creates 2-3 expert agents dynamically                │  │  │
│  │  │  • Each expert has MCP tools for KB access              │  │  │
│  │  │  • Experts collaborate via handoffs                     │  │  │
│  │  │  • Max 20 handoffs, 20 iterations                       │  │  │
│  │  └────────────────────────────────────────────────────────┘  │  │
│  │                           │                                    │  │
│  │                           │ query_knowledge_base()             │  │
│  │                           ▼                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ OAuth JWT (Bearer token)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AgentCore Gateway (MCP)                           │
│  • Protocol: Model Context Protocol (MCP)                           │
│  • Auth: CUSTOM_JWT (Cognito OAuth client_credentials)              │
│  • Tool: query_knowledge_base(domain, query)                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │ IAM role credentials
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Lambda Function                                   │
│              (Knowledge Base Query Handler)                          │
│  • Receives: domain, query                                           │
│  • Calls: bedrock-agent-runtime.retrieve_and_generate()             │
│  • Returns: Formatted response from KB                               │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Amazon Bedrock Knowledge Bases (7 domains)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │   HPC    │ │ Quantum  │ │  GenAI   │ │  Visual  │              │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘              │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐                            │
│  │ Spatial  │ │   IoT    │ │ Partners │                            │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘                            │
│       │            │            │                                    │
│       ▼            ▼            ▼                                    │
│  ┌─────────────────────────────────────────┐                        │
│  │     S3 Buckets (Domain Documents)       │                        │
│  │  • PDF, TXT, MD files                   │                        │
│  │  • Chunked with FIXED_SIZE strategy     │                        │
│  │  • Embedded with Titan Embed v1         │                        │
│  └─────────────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    AgentCore Memory                                  │
│  • Type: Semantic memory (90-day retention)                          │
│  • Stores: User/Assistant conversation pairs                         │
│  • Namespace: advcomp/{actor_id}/knowledge                           │
│  • Used by: Coordinator for context and learning                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    Authentication Flow                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  1. Agent retrieves OAuth credentials from Secrets Manager   │  │
│  │  2. Agent POSTs to Cognito token endpoint with Basic auth    │  │
│  │  3. Cognito returns short-lived JWT access token             │  │
│  │  4. Agent uses token in Authorization: Bearer header         │  │
│  │  5. Gateway validates JWT against Cognito OIDC discovery     │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Streamlit Web Application

**Location**: `web_app/app.py`

**Purpose**: User interface for interacting with the agent system

**Features**:
- Chat interface with conversation history
- Session management (33+ character session IDs for memory continuity)
- Comparison mode (Agent Swarm vs Direct Claude)
- Telemetry visualization (timeline, agent conversations, tool calls)
- Memory management (view, clear events, clear records)
- Knowledge base document upload interface

**Key Functions**:
- `invoke_agent()`: Calls AgentCore Runtime via boto3
- `invoke_claude_direct()`: Direct Bedrock API call for comparison
- Uses `bedrock-agentcore` client with 15-minute timeout

### 2. AgentCore Runtime

**Location**: `agent/` (deployed as Docker container)

**Container**: ARM64 architecture, built by CDK during deployment

**Entry Point**: `advcomp_swarm.py` - `agent_invocation()` function

**Components**:

#### Coordinator Agent
- **Model**: Claude Sonnet 4.5 (configurable per agent)
- **Tools**: 
  - Memory tools (search, save, delete)
  - `advcomp_swarm()` tool for expert consultation
- **Responsibilities**:
  1. Check memory for relevant past knowledge
  2. Analyze query to determine if experts needed
  3. Select 2-3 relevant experts
  4. Call `advcomp_swarm()` tool with expert list
  5. Save learnings to memory

#### Expert Swarm (Dynamic)
- **Created on-demand** by `advcomp_swarm()` tool
- **Experts**: hpc, quantum, genai, visual, spatial, iot, partners
- **Each expert has**:
  - Domain-specific system prompt
  - MCP tools for knowledge base access
  - Handoff instructions for collaboration
- **Swarm Configuration**:
  - Max handoffs: 20
  - Max iterations: 20
  - Execution timeout: 30 minutes
  - Node timeout: 10 minutes

**Authentication**:
- Retrieves OAuth credentials from Secrets Manager
- Gets JWT token via client_credentials flow
- Passes token to MCP client for Gateway access

**Memory Integration**:
- `SwarmLearningMemoryHook`: Loads recent conversation context on init
- Saves user/assistant pairs after each interaction
- Includes swarm execution context (which experts were used)

### 3. AgentCore Gateway

**Type**: MCP (Model Context Protocol) Gateway

**Authentication**: CUSTOM_JWT with Cognito OAuth

**Configuration**:
- Authorizer: Cognito OIDC discovery URL
- Allowed clients: OAuth app client ID
- Protocol: MCP over HTTP

**Tool Definition**:
```json
{
  "name": "query_knowledge_base",
  "description": "Query domain-specific knowledge bases for AWS documentation",
  "input_schema": {
    "type": "object",
    "properties": {
      "domain": {
        "type": "string",
        "description": "Domain to query (hpc, quantum, genai, visual, spatial, iot, partners)"
      },
      "query": {
        "type": "string",
        "description": "Query text"
      }
    },
    "required": ["domain", "query"]
  }
}
```

**Target**: Lambda function with IAM role credentials

### 4. Knowledge Base Lambda

**Location**: `cdk.out/asset.*/knowledge_base_lambda.py` (deployed from CDK)

**Runtime**: Python 3.12

**Environment Variables**:
- `{DOMAIN}_KNOWLEDGE_BASE_ID`: KB ID for each domain (7 total)

**Functionality**:
1. Receives `domain` and `query` from Gateway
2. Maps domain to knowledge base ID
3. Calls `bedrock-agent-runtime.retrieve_and_generate()`
4. Returns formatted response with 5 vector search results

**API Used**: `RetrieveAndGenerate` (not `Retrieve`)
- Automatically formats results into natural language
- Uses Claude Sonnet 4.5 for generation
- Returns synthesized answer from KB chunks

**Fallback**: Returns mock data if KB unavailable

### 5. Bedrock Knowledge Bases

**Count**: 7 domain-specific KBs

**Domains**:
- HPC: ParallelCluster, AWS PCS, EFA, FSx Lustre
- Quantum: Amazon Braket, quantum algorithms
- GenAI: Bedrock, AgentCore, SageMaker, RAG
- Visual: Rekognition, GPU instances, visualization
- Spatial: Location Service, SDMA, digital twins
- IoT: IoT Core, SiteWise, Greengrass, Kinesis Video
- Partners: APN, ISV solutions, Marketplace

**Storage**: S3 buckets (one per domain)

**Embedding**: Titan Embed Text v1

**Chunking**: FIXED_SIZE strategy

**Data Sources**: S3DataSource with automatic sync

### 6. AgentCore Memory

**Type**: Semantic memory with 90-day retention

**Strategy**: `using_built_in_semantic()`

**Namespace Pattern**: `advcomp/{actor_id}/knowledge`

**Storage**:
- **Events**: Raw conversation data (user/assistant messages)
- **Records**: Processed semantic memories (searchable)

**Actor ID**: `coordinator-persistent` (shared across sessions)

**Session ID**: Unique per web session (33+ characters)

**Memory Tools**:
- `search_memory`: Query past conversations
- `save_memory`: Store new knowledge
- `delete_memory`: Remove specific memories

**Hook**: `SwarmLearningMemoryHook`
- Loads recent context on agent init
- Saves conversations after invocation
- Includes swarm metadata (which experts were consulted)

### 7. Cognito Authentication

**Components**:
- **User Pool**: Manages OAuth clients
- **Resource Server**: `gateway-api` with `invoke` scope
- **App Client**: OAuth client_credentials flow
- **Domain**: Cognito hosted domain for token endpoint

**OAuth Flow**:
1. Agent encodes `client_id:client_secret` as Base64
2. POSTs to token endpoint with `Authorization: Basic {base64}`
3. Request body: `grant_type=client_credentials&scope=gateway-api/invoke`
4. Receives short-lived JWT access token
5. Uses token in Gateway requests: `Authorization: Bearer {token}`

**Token Lifetime**: Managed by Cognito (typically 1 hour)

**Storage**: OAuth credentials in Secrets Manager

## Data Flow

### Query Processing Flow

1. **User submits query** via Streamlit web app
2. **Web app calls** `bedrock-agentcore.invoke_agent_runtime()`
   - Payload: `{"prompt": "user query"}`
   - Session ID: Unique per web session
   - Qualifier: "DEFAULT" endpoint
3. **AgentCore Runtime** invokes `agent_invocation()` handler
4. **Coordinator agent** receives query
   - Checks memory for relevant past knowledge
   - Decides if experts needed (AWS service questions always need experts)
5. **If experts needed**, coordinator calls `advcomp_swarm()` tool
   - Selects 2-3 relevant experts
   - Tool creates expert agents dynamically
6. **Expert swarm executes**:
   - Each expert gets MCP tools for KB access
   - Experts collaborate via handoffs
   - Each expert can call `query_knowledge_base(domain, query)`
7. **Knowledge base queries**:
   - Expert → MCP Gateway (with JWT token)
   - Gateway → Lambda (with IAM credentials)
   - Lambda → Bedrock KB (RetrieveAndGenerate API)
   - Response flows back through chain
8. **Swarm completes**, returns synthesized response
9. **Coordinator** receives swarm result
10. **Memory hook** saves conversation + swarm metadata
11. **Response returned** to web app with:
    - Final answer
    - Agent sequence
    - Individual expert responses
    - Tool calls
    - Telemetry data

### Authentication Flow

1. **Agent startup**: Reads `COGNITO_SECRET_ARN` from environment
2. **Retrieve credentials**: Calls Secrets Manager to get OAuth client ID/secret
3. **Get token**: POSTs to Cognito token endpoint
   - Header: `Authorization: Basic {base64(client_id:client_secret)}`
   - Body: `grant_type=client_credentials&scope=gateway-api/invoke`
4. **Receive JWT**: Cognito returns access token
5. **Create MCP client**: Passes token in Authorization header
6. **Gateway validates**: Checks JWT against Cognito OIDC discovery
7. **Token refresh**: Agent gets new token for each swarm execution

### Memory Flow

1. **Agent init**: `SwarmLearningMemoryHook.on_agent_initialized()`
   - Lists recent events from current session
   - Extracts user/assistant conversation pairs
   - Adds context to agent system prompt
2. **Query processing**: Agent uses memory tools to search past knowledge
3. **After invocation**: `SwarmLearningMemoryHook.save_memories()`
   - Extracts last user/assistant message pair
   - Adds swarm execution context (which experts were used)
   - Creates event via `bedrock-agentcore.create_event()`
4. **Background processing**: AgentCore processes events into semantic records
5. **Future queries**: Agent can search processed records via memory tools

## Infrastructure as Code

All infrastructure is defined in CDK: `advcomp_agentic_strandscore_demo_stack.py`

### CDK Stack Components

**IAM Roles** (scoped permissions, no AWS managed policies):
- Agent role: `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`
- Lambda role: `bedrock:Retrieve`, `bedrock:RetrieveAndGenerate`
- Gateway role: `lambda:InvokeFunction` (scoped to KB Lambda)
- MCP role: Placeholder for future MCP server needs

**ECR**:
- Repository: `advcomp-agent`
- Image: Built by CDK from `agent/` directory
- Architecture: ARM64
- Deployment: `cdk-ecr-deployment` construct

**AgentCore Resources**:
- Runtime: `agentcore_alpha.Runtime` (L2 construct)
- Memory: `agentcore_alpha.Memory` with semantic strategy
- Gateway: `agentcore.CfnGateway` (L1 construct)
- Gateway Target: `agentcore.CfnGatewayTarget` with Lambda backend

**Cognito**:
- User Pool: OAuth provider
- Resource Server: `gateway-api` with `invoke` scope
- App Client: client_credentials flow only
- Domain: For token endpoint
- Secret: OAuth credentials in Secrets Manager

**Knowledge Bases**:
- 7 VectorKnowledgeBases (generative-ai-cdk-constructs)
- 7 S3 buckets for documents
- 7 S3DataSources with FIXED_SIZE chunking
- Titan Embed Text v1 for embeddings

**Lambda**:
- Function: Knowledge base query handler
- Runtime: Python 3.12
- Environment: KB IDs for all 7 domains
- Permissions: Read from S3 buckets, query KBs

**Outputs**:
- Gateway URL, ID
- Runtime ARN, endpoint names
- Memory ID
- KB IDs for all domains
- Bucket names
- ECR image URI

### Deployment

```bash
cdk deploy --require-approval never
```

**What happens**:
1. CDK builds Docker image from `agent/` directory
2. Pushes image to ECR
3. Creates all IAM roles with scoped permissions
4. Creates Cognito resources for OAuth
5. Creates AgentCore Gateway with JWT auth
6. Creates Lambda function with KB IDs
7. Creates 7 Knowledge Bases with S3 data sources
8. Creates AgentCore Memory with semantic strategy
9. Creates AgentCore Runtime with DEFAULT endpoint
10. Outputs all resource IDs to `cdk-outputs.json`

**Time**: ~5-10 minutes

## Security

### Authentication & Authorization

**Gateway Access**:
- OAuth 2.0 client_credentials flow
- Short-lived JWT tokens (1 hour)
- Cognito validates tokens via OIDC discovery
- No user passwords or long-lived credentials

**Lambda Invocation**:
- Gateway uses IAM role credentials
- Lambda execution role has scoped KB permissions
- No cross-account access

**Agent Execution**:
- Runtime uses IAM role for Bedrock API calls
- Scoped to specific model IDs
- No overly-permissive managed policies

### IAM Permissions

**Agent Role**:
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": "arn:aws:bedrock:*::foundation-model/*"
}
```

**Lambda Role**:
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:Retrieve",
    "bedrock:RetrieveAndGenerate"
  ],
  "Resource": "arn:aws:bedrock:*:*:knowledge-base/*"
}
```

**Gateway Role**:
```json
{
  "Effect": "Allow",
  "Action": "lambda:InvokeFunction",
  "Resource": "{lambda_function_arn}"
}
```

### Data Protection

**In Transit**:
- HTTPS for all API calls
- TLS for Bedrock API
- Encrypted S3 transfer

**At Rest**:
- S3 buckets with default encryption
- Secrets Manager encryption for OAuth credentials
- CloudWatch Logs encryption

**Memory Data**:
- Stored in AgentCore Memory service
- 90-day retention policy
- Scoped to actor/session IDs

## Performance

### Execution Times

**Simple queries** (memory-based): 2-5 seconds
**Single expert**: 15-30 seconds
**Multi-expert** (2-3 experts): 25-60 seconds
**Complex queries** (multiple KB calls): up to 200 seconds

### Timeouts

- **Request timeout**: 15 minutes (AgentCore limit)
- **Execution timeout**: 30 minutes (swarm configuration)
- **Node timeout**: 10 minutes (per expert)
- **boto3 read timeout**: 15 minutes (web app client)

### Limits

- **Max handoffs**: 20 per swarm
- **Max iterations**: 20 per swarm
- **Max experts**: 7 (all domains)
- **Recommended experts per query**: 2-3
- **KB results per query**: 5 (vector search)

### Optimization

**Memory-first approach**:
- Coordinator checks memory before calling experts
- Reduces expert invocations for repeated questions
- Faster responses for known topics

**Parallel expert execution**:
- Strands Swarm handles concurrent expert calls
- Handoffs enable sequential collaboration when needed

**KB caching**:
- Lambda warm starts reduce latency
- Bedrock KB results cached by service

## Monitoring & Observability

### CloudWatch Logs

**Agent Runtime**:
- Log group: `/aws/bedrock-agentcore/runtimes/{runtime_name}-DEFAULT`
- Contains: Agent initialization, tool calls, errors
- Retention: Configurable (default 7 days)

**Lambda Function**:
- Log group: `/aws/lambda/{function_name}`
- Contains: KB queries, API calls, errors

### Telemetry

**Captured by agent**:
- Query received timestamp
- Agent response timestamps
- Tool calls (name, input, result preview)
- Execution time per stage
- Total execution time

**Displayed in web app**:
- Collaboration timeline
- Individual agent conversations
- Tool call details
- Time breakdown by stage

### Structured Data

**Stored in `/tmp/swarm_structured_data.json`**:
```json
{
  "individual_responses": {"agent_id": "response_text"},
  "agent_sequence": ["coordinator", "hpc_expert", "genai_expert"],
  "execution_time_ms": 45000,
  "status": "COMPLETED",
  "tool_calls": [
    {
      "agent": "hpc_expert",
      "tool_name": "query_knowledge_base",
      "input": {"domain": "hpc", "query": "AWS PCS"},
      "tool_use_id": "...",
      "status": "success",
      "result_preview": "AWS PCS is..."
    }
  ]
}
```

## Extensibility

### Adding New Experts

1. Add system prompt to `agent/domain_prompts.py`
2. Add expert config to `EXPERT_CONFIGS` in `advcomp_swarm.py`
3. Update coordinator prompt with new expert description
4. Create new knowledge base in CDK stack
5. Deploy with `cdk deploy`

### Adding New Tools

**For coordinator**:
- Add tool function with `@tool` decorator
- Add to `coordinator_tools` list in `create_coordinator_agent()`

**For experts**:
- Add tool to MCP Gateway definition in CDK
- Update Lambda handler to support new tool
- Experts automatically get all MCP tools

### Custom Memory Strategies

Replace `using_built_in_semantic()` with:
- `using_built_in_event()`: Event-based memory
- Custom strategy: Implement `MemoryStrategy` interface

### Model Configuration

Edit `agent/agent_config.py`:
```python
AGENT_MODELS = {
    "coordinator": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "hpc_expert": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # ...
}
```

## Limitations

1. **Response time**: Complex queries can take up to 200 seconds
2. **Expert selection**: Coordinator must choose experts upfront (no dynamic addition mid-swarm)
3. **Knowledge base updates**: Requires manual document upload and sync
4. **Memory processing**: Events processed asynchronously (slight delay before searchable)
5. **Region support**: us-east-1, us-west-2 only (AgentCore availability)
6. **Docker required**: CDK builds agent container during deployment
7. **Token refresh**: Agent gets new token for each swarm (no persistent connection)

## Future Enhancements

1. **Streaming responses**: Enable real-time agent output
2. **Dynamic expert addition**: Allow experts to request additional experts mid-swarm
3. **Automatic KB sync**: Trigger ingestion on S3 upload
4. **Multi-region**: Deploy to additional regions as AgentCore expands
5. **Custom embeddings**: Use domain-specific embedding models
6. **Agent versioning**: Support multiple agent versions with A/B testing
7. **Cost tracking**: Add detailed cost breakdown per query
8. **Caching layer**: Cache common KB queries for faster responses
