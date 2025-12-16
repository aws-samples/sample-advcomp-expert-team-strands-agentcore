"""
Advanced Computing Team Collaboration Swarm - Web UI

A Streamlit web application for interacting with the Advanced Computing Team
Collaboration Swarm.
"""

import os
import json
import boto3
import uuid
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set default agent ARN from environment variable
if "AGENT_ARN" not in os.environ:
    os.environ["AGENT_ARN"] = ""  # Will be set by deployment or .env file

# Set page configuration
st.set_page_config(
    page_title="Advanced Computing Team Collaboration Swarm",
    page_icon="🧠",
    layout="wide"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    # Generate a unique session ID with at least 33 characters (AWS requirement)
    import uuid
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4())
    st.session_state.session_id = f"session-{timestamp}-{unique_id}"
    print(f"Generated session ID: {st.session_state.session_id} (length: {len(st.session_state.session_id)})")
    
    # Ensure session ID is at least 33 characters
    if len(st.session_state.session_id) < 33:
        st.session_state.session_id = st.session_state.session_id + "x" * (33 - len(st.session_state.session_id))

# Function to invoke Claude directly (baseline)
def invoke_claude_direct(prompt):
    """
    Invoke Claude directly without agents for comparison
    
    Args:
        prompt (str): The user's query
        
    Returns:
        dict: Claude's response
    """
    import time
    try:
        start_time = time.time()
        
        region = os.environ.get("AWS_REGION", "us-east-1")
        model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"  # Force Claude 4.5
        
        bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
        
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}]
        )
        
        response_text = response['output']['message']['content'][0]['text']
        
        execution_time = time.time() - start_time
        
        return {
            "response": response_text,
            "status": "COMPLETED",
            "model": model_id,
            "execution_time": execution_time
        }
    except Exception as e:
        execution_time = time.time() - start_time if 'start_time' in locals() else 0
        return {
            "response": f"Error calling Claude directly: {str(e)}",
            "status": "ERROR",
            "model": model_id,
            "execution_time": execution_time
        }

# Function to invoke the agent
def invoke_agent(prompt):
    """
    Invoke the Advanced Computing Team Collaboration Swarm agent
    
    Args:
        prompt (str): The user's query
        
    Returns:
        dict: The agent's response
    """
    try:
        # Get the agent ARN from environment variable
        agent_arn = os.environ.get("AGENT_ARN")
        
        # If agent ARN is not set or contains the placeholder value, use local testing mode
        if not agent_arn or "123456789012" in agent_arn:
            st.warning("⚠️ Agent ARN not properly configured. Using local testing mode.")
            return {
                "response": f"This is a simulated response to: {prompt}\n\nTo get real responses, set the AGENT_ARN environment variable to your actual agent ARN.",
                "agent_sequence": ["coordinator", "hpc_expert", "quantum_expert", "genai_expert", "coordinator"],
                "status": "COMPLETED",
                "execution_time_ms": 5000
            }
        
        # Get the region from the ARN or use the default region
        if ':' in agent_arn:
            region = agent_arn.split(':')[3]
        else:
            region = os.environ.get("AWS_REGION", "us-east-1")
            
        # Print diagnostic information
        print(f"Using agent ARN: {agent_arn}")
        print(f"Using region: {region}")
        print(f"Session ID: {st.session_state.session_id}")
        
        # Initialize the Bedrock AgentCore client with timeout matching AgentCore limits
        from botocore.config import Config
        config = Config(
            read_timeout=900,  # 15 minutes - matches AgentCore request timeout
            connect_timeout=60,
            retries={'max_attempts': 0}  # Disable retries to avoid confusion
        )
        client = boto3.client('bedrock-agentcore', region_name=region, config=config)
        
        payload = json.dumps({"prompt": prompt}).encode()
        
        # Get endpoint name from environment (set by CDK outputs)
        # DEFAULT endpoint is automatically created by AgentCore
        endpoint_name = os.environ.get("AGENT_ENDPOINT_NAME", "DEFAULT")
        
        # Invoke the agent using the endpoint qualifier
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=st.session_state.session_id,
            payload=payload,
            qualifier=endpoint_name
        )
        
        # Parse the response
        response_body = response['response'].read().decode('utf-8')
        
        # Try to parse as JSON if possible
        try:
            parsed_response = json.loads(response_body)
            
            # Handle the exact format: {'role': 'assistant', 'content': [{'text': '...'}]}
            if (isinstance(parsed_response, dict) and 
                'content' in parsed_response and 
                isinstance(parsed_response['content'], list) and 
                len(parsed_response['content']) > 0 and 
                'text' in parsed_response['content'][0]):
                
                # Extract the text content
                text_content = parsed_response['content'][0]['text']
                
                # Try to parse the text as structured JSON (backend embeds structured data here)
                try:
                    structured_data = json.loads(text_content)
                    if isinstance(structured_data, dict) and 'response' in structured_data:
                        # This is the structured response with telemetry!
                        return structured_data
                except json.JSONDecodeError:
                    pass
                
                # If not structured, return as plain text
                return {
                    "response": text_content,
                    "agent_sequence": parsed_response.get("agent_sequence", ["coordinator"]),
                    "domains_involved": parsed_response.get("domains_involved", []),
                    "status": parsed_response.get("status", "COMPLETED"),
                    "execution_time_ms": parsed_response.get("execution_time_ms", 0),
                    "telemetry": parsed_response.get("telemetry", [])
                }
            
            # If it already has a 'response' key, check if it's structured JSON
            if isinstance(parsed_response, dict) and 'response' in parsed_response:
                response_text = parsed_response['response']
                # Try to parse the response as structured JSON
                try:
                    structured_data = json.loads(response_text)
                    if isinstance(structured_data, dict) and 'response' in structured_data:
                        return structured_data
                except json.JSONDecodeError:
                    pass
                return parsed_response
                
            # Otherwise, use the entire parsed response as the response text
            return {
                "response": str(parsed_response),
                "agent_sequence": ["coordinator"],
                "status": "COMPLETED",
                "execution_time_ms": 0
            }
        except json.JSONDecodeError:
            # Try to parse response_body directly as structured JSON
            try:
                structured_data = json.loads(response_body)
                if isinstance(structured_data, dict) and 'response' in structured_data:
                    return structured_data
            except json.JSONDecodeError:
                pass
                
            # If not JSON, return as plain text response
            return {
                "response": response_body,
                "agent_sequence": ["coordinator"],
                "status": "COMPLETED",
                "execution_time_ms": 0
            }
    except Exception as e:
        st.error(f"Error invoking agent: {str(e)}")
        print(f"Detailed error: {e}")
        
        error_str = str(e)
        if "AccessDeniedException" in error_str:
            return {
                "response": f"Error: {error_str}\n\nAccess denied. Please check:\n1. Your AWS credentials have the 'bedrock-agentcore:InvokeAgentRuntime' permission\n2. The agent ARN is correct and you have access to it\n3. You're using the correct AWS region\n\nTo add the required permission, add this policy to your IAM user/role:\n```json\n{{\n  \"Effect\": \"Allow\",\n  \"Action\": \"bedrock-agentcore:InvokeAgentRuntime\",\n  \"Resource\": \"*\"\n}}\n```", 
                "agent_sequence": [], 
                "status": "ERROR"
            }
        elif "ResourceNotFoundException" in error_str:
            return {
                "response": f"Error: {error_str}\n\nThe agent was not found. Please check:\n1. The agent ARN is correct\n2. The agent is deployed and in ACTIVE state\n3. You're using the correct AWS region", 
                "agent_sequence": [], 
                "status": "ERROR"
            }
        else:
            return {
                "response": f"Error: {error_str}\n\nPlease check that:\n1. The AGENT_ARN environment variable is set correctly\n2. Your AWS credentials have permission to invoke the agent\n3. The agent is deployed and in ACTIVE state", 
                "agent_sequence": [], 
                "status": "ERROR"
            }

# Header
st.title("Advanced Computing Team Collaboration Swarm")
st.markdown("""
This demo showcases a multi-agent system that reflects the Advanced Computing team's structure,
with specialized agents for each domain (HPC, Quantum, Applied GenAI, Spatial, Visual, IoT, Partners).
""")

# Navigation link to Knowledge Base Manager
st.markdown("[📚 Knowledge Base Manager](/Knowledge_Base_Manager)")
st.markdown("---")

# Add comparison mode toggle
if "comparison_mode" not in st.session_state:
    st.session_state.comparison_mode = False

comparison_mode = st.toggle("🔬 Comparison Mode: Show Agent vs Direct LLM", value=st.session_state.comparison_mode)
st.session_state.comparison_mode = comparison_mode

if comparison_mode:
    st.info("💡 **Comparison Mode Active**: Each query will be answered by both the Agent Swarm and a direct Claude 4.5 call for side-by-side comparison.")

st.markdown("---")

# Sidebar with agent information
with st.sidebar:
    # Check agent configuration
    agent_arn = os.environ.get("AGENT_ARN")
    
    st.subheader("Agent Status")
    if not agent_arn or "123456789012" in agent_arn:
        st.warning("⚠️ Agent not configured")
    else:
        st.success("✅ Agent configured")
    
        
        # Add button to test the agent with a simple query
        if st.button("📝 Test Agent"):
            with st.spinner("Testing agent..."):
                test_response = invoke_agent("Hello, can you help me?")
                if "error" in test_response.get("status", "").lower():
                    st.error("❌ Agent test failed")
                    st.code(test_response.get("response", "Unknown error"))
                else:
                    st.success("✅ Agent test successful")
        
        st.markdown("---")
        st.subheader("Memory Management")
        
        if st.button("🗑️ Clear Agent Memory (Records Only)", type="secondary"):
            with st.spinner("Clearing processed memory records..."):
                try:
                    # Use the agent to clear its own memory records
                    clear_response = invoke_agent("Please use your memory tool to list all stored memories, then delete each one to clear your memory completely. Confirm when done.")
                    
                    if "error" not in clear_response["response"].lower():
                        st.success("✅ Agent memory records cleared successfully!")
                        st.info("Processed memory records cleared. Raw events remain until processed.")
                    else:
                        st.error(f"Error clearing memory: {clear_response['response']}")
                        
                except Exception as e:
                    st.error(f"Error clearing memory: {str(e)}")
        
        if st.button("🗑️ Clear All Memory (Events + Records)", type="primary"):
            with st.spinner("Clearing all memory data..."):
                try:
                    # Extract region from ARN
                    if ':' in agent_arn:
                        region = agent_arn.split(':')[3]
                    else:
                        region = os.environ.get("AWS_REGION", "us-east-1")
                    
                    data_client = boto3.client('bedrock-agentcore', region_name=region)
                    memory_id = os.environ.get("MEMORY_ID")
                    if not memory_id:
                        st.error("⚠️ MEMORY_ID environment variable not set. Set it from CDK outputs to use memory management features.")
                    else:
                        actor_id = os.environ.get("COORDINATOR_ACTOR_ID", "coordinator-persistent")
                        
                        # Get ALL sessions for this actor using ListSessions API
                        try:
                            sessions_response = data_client.list_sessions(
                                memoryId=memory_id,
                                actorId=actor_id,
                                maxResults=100
                            )
                            session_ids_to_clear = [session['sessionId'] for session in sessions_response.get('sessionSummaries', [])]
                            st.info(f"Found {len(session_ids_to_clear)} sessions to clear: {session_ids_to_clear[:3]}{'...' if len(session_ids_to_clear) > 3 else ''}")
                        except Exception as e:
                            st.warning(f"Could not list sessions: {e}")
                            # Fallback to known sessions
                            session_ids_to_clear = [
                                "advcomp-session-main",
                                st.session_state.session_id
                            ]
                        
                        # Clear events from all found sessions
                        all_events = []
                        for session_id in session_ids_to_clear:
                            try:
                                events = data_client.list_events(
                                    memoryId=memory_id,
                                    actorId=actor_id,
                                    sessionId=session_id,
                                    maxResults=50
                                )
                                all_events.extend(events.get('events', []))
                            except Exception as e:
                                st.warning(f"Could not list events for session {session_id[:8]}...: {e}")
                                pass  # Session doesn't exist or no events
                        
                        # Clear events from known sessions
                        deleted_events = 0
                        sessions_cleared = set()
                        for event in all_events:
                            try:
                                event_session_id = event.get('sessionId')
                                data_client.delete_event(
                                    memoryId=memory_id,
                                    eventId=event['eventId'],
                                    sessionId=event_session_id,
                                    actorId=actor_id
                                )
                                deleted_events += 1
                                sessions_cleared.add(event_session_id)
                            except Exception as e:
                                st.warning(f"Could not delete event {event['eventId']}: {e}")
                        
                        if sessions_cleared:
                            st.info(f"Cleared events from {len(sessions_cleared)} sessions: {list(sessions_cleared)[:3]}{'...' if len(sessions_cleared) > 3 else ''}")
                        else:
                            st.warning(f"No events found in {len(session_ids_to_clear)} sessions. Events may have already been processed into memory records.")
                        
                        # Clear memory records - this is what actually matters
                        namespace = f"advcomp/{actor_id}/knowledge"
                        deleted_records = 0
                        try:
                            # Keep fetching and deleting until no more records
                            while True:
                                records = data_client.list_memory_records(
                                    memoryId=memory_id,
                                    namespace=namespace,
                                    maxResults=100
                                )
                                
                                record_summaries = records.get('memoryRecordSummaries', [])
                                if not record_summaries:
                                    break
                                
                                for record in record_summaries:
                                    try:
                                        data_client.delete_memory_record(
                                            memoryId=memory_id,
                                            memoryRecordId=record['memoryRecordId']
                                        )
                                        deleted_records += 1
                                    except Exception as e:
                                        st.warning(f"Could not delete record {record['memoryRecordId'][:8]}...: {e}")
                            
                            if deleted_records > 0:
                                st.success(f"✅ Cleared {deleted_events} events from {len(sessions_cleared)} sessions and {deleted_records} memory records!")
                            else:
                                st.info(f"✅ Cleared {deleted_events} events from {len(sessions_cleared)} sessions. No memory records found (may still be processing).")
                        except Exception as e:
                            if deleted_events > 0:
                                st.success(f"✅ Cleared {deleted_events} events from {len(sessions_cleared)} sessions!")
                            st.warning(f"Could not clear memory records: {e}")
                        
                        if deleted_records > 0 or deleted_events > 0:
                            st.info(f"Memory cleared! Agent will start fresh. ({deleted_records} records + {deleted_events} events removed)")
                        else:
                            st.info("No memory data found to clear. Agent memory is already empty.")
                    
                except Exception as e:
                    st.error(f"Error clearing all memory: {str(e)}")
        
        # Add a button to view current memories via agent
        if st.button("📋 View Current Memories (via Agent)"):
            with st.spinner("Retrieving stored memories via agent..."):
                try:
                    # Use the agent to list its memories
                    memory_response = invoke_agent("Please use your memory tool to list all currently stored memories and provide a brief summary of what knowledge you have stored.")
                    
                    st.subheader("Current Agent Memories (via Agent)")
                    st.markdown(memory_response["response"])
                        
                except Exception as e:
                    st.error(f"Error retrieving memories: {str(e)}")
        
        # Add a button to check memories directly via API
        if st.button("🔍 Check Memories Directly (via API)"):
            with st.spinner("Checking memories directly via AWS API..."):
                try:
                    # Extract region from ARN
                    if ':' in agent_arn:
                        region = agent_arn.split(':')[3]
                    else:
                        region = os.environ.get("AWS_REGION", "us-east-1")
                    
                    # Check memories using AWS API directly
                    bedrock_client = boto3.client('bedrock-agentcore-control', region_name=region)
                    memories = bedrock_client.list_memories()
                    
                    st.subheader("Direct Memory API Check")
                    st.write(f"Found {len(memories.get('memories', []))} memories:")
                    
                    for memory in memories.get('memories', []):
                        st.write(f"- **Memory ID**: {memory.get('id')}")
                        st.write(f"  - **Status:** {memory.get('status')}")
                        st.write(f"  - **Created:** {memory.get('createdAt')}")
                        
                        # Try to get memory records with namespace
                        try:
                            data_client = boto3.client('bedrock-agentcore', region_name=region)
                            control_client = boto3.client('bedrock-agentcore-control', region_name=region)
                            
                            # Get the actual namespace from semantic memory strategy
                            actor_id = os.environ.get("COORDINATOR_ACTOR_ID", "coordinator-persistent")
                            memory_details = control_client.get_memory(memoryId=memory.get('id'))
                            strategies = memory_details.get('memory', {}).get('strategies', [])
                            if strategies:
                                strategy_id = strategies[0]['strategyId']
                                namespace = f"/strategies/{strategy_id}/actors/{actor_id}"
                            else:
                                namespace = f"advcomp/{actor_id}/knowledge"
                            
                            records = data_client.list_memory_records(
                                memoryId=memory.get('id'),
                                namespace=namespace,
                                maxResults=10
                            )
                            st.write(f"  - **Namespace:** `{namespace}`")
                            
                            # Check events from known sessions
                            try:
                                # Get all sessions for this actor
                                try:
                                    sessions_response = data_client.list_sessions(
                                        memoryId=memory.get('id'),
                                        actorId=actor_id,
                                        maxResults=50
                                    )
                                    session_ids_to_check = [session['sessionId'] for session in sessions_response.get('sessionSummaries', [])]
                                except:
                                    # Fallback to known sessions
                                    session_ids_to_check = [
                                        "advcomp-session-main",
                                        st.session_state.session_id
                                    ]
                                
                                total_events = 0
                                found_sessions = []
                                
                                for session_id in session_ids_to_check:
                                    try:
                                        events = data_client.list_events(
                                            memoryId=memory.get('id'),
                                            actorId=actor_id,
                                            sessionId=session_id,
                                            maxResults=10
                                        )
                                        event_count = len(events.get('events', []))
                                        if event_count > 0:
                                            total_events += event_count
                                            found_sessions.append(f"{session_id}: {event_count}")
                                    except:
                                        pass  # Session doesn't exist
                                
                                st.write(f"  - Events: {total_events} total")
                                if found_sessions:
                                    st.write(f"  - Sessions with events: {found_sessions}")
                                else:
                                    st.write(f"  - No events found in checked sessions")
                            except Exception as e:
                                st.write(f"  - Error getting events: {e}")
                            
                            record_summaries = records.get('memoryRecordSummaries', [])
                            st.write(f"  - **Records: {len(record_summaries)} memories extracted**")
                            
                            if record_summaries:
                                st.write("\n  **Sample Memories:**")
                                for i, record in enumerate(record_summaries[:5], 1):  # Show first 5
                                    try:
                                        record_detail = data_client.get_memory_record(
                                            memoryId=memory.get('id'),
                                            memoryRecordId=record.get('memoryRecordId')
                                        )
                                        content = record_detail.get('memoryRecord', {}).get('content', {})
                                        if 'text' in content:
                                            text = content['text']
                                            st.write(f"  {i}. {text}")
                                        else:
                                            st.write(f"  {i}. [No text content]")
                                    except Exception as e:
                                        st.write(f"  {i}. [Error: {e}]")
                                if len(record_summaries) > 5:
                                    st.write(f"  ... and {len(record_summaries) - 5} more memories")
                            else:
                                st.write("    - No memory records found (still processing events)")
                                
                        except Exception as e:
                            st.write(f"  - Error getting records: {str(e)}")
                            # Try without namespace to see if records exist in other namespaces
                            try:
                                # List all actors to see what namespaces exist
                                actors = data_client.list_actors(memoryId=memory.get('id'))
                                st.write(f"  - Available actors: {len(actors.get('actors', []))}")
                                for actor in actors.get('actors', [])[:3]:  # Show first 3
                                    st.write(f"    - Actor: {actor.get('actorId', 'Unknown')}")
                            except Exception as actor_e:
                                st.write(f"  - Error listing actors: {str(actor_e)}")
                        
                        st.write("---")
                        
                except Exception as e:
                    st.error(f"Error checking memories directly: {str(e)}")
                    st.info("Make sure your AWS credentials have bedrock-agentcore permissions.")
                    
                    # Show debug info
                    st.write("**Debug Info:**")
                    st.write(f"- Region: {region}")
                    actor_id = os.environ.get("COORDINATOR_ACTOR_ID", "coordinator-persistent")
                    st.write(f"- Expected namespace pattern: advcomp/{actor_id}/knowledge")
        
        # Add button to check agent logs specifically
        if st.button("📋 Check Agent Logs"):
            try:
                # Extract region from ARN
                if ':' in agent_arn:
                    region = agent_arn.split(':')[3]
                else:
                    region = os.environ.get("AWS_REGION", "us-east-1")
                
                # Extract runtime name from ARN
                runtime_name = agent_arn.split('/')[-1]
                
                # Get CloudWatch logs - use the correct log group format
                logs_client = boto3.client('logs', region_name=region)
                log_group_name = f"/aws/bedrock-agentcore/runtimes/{runtime_name}-DEFAULT"
                
                st.subheader("Recent Agent Logs")
                st.code(f"Log Group: {log_group_name}")
                
                try:
                    # Get log streams
                    streams = logs_client.describe_log_streams(
                        logGroupName=log_group_name,
                        orderBy='LastEventTime',
                        descending=True,
                        limit=1
                    )
                    
                    if streams.get('logStreams'):
                        # Get most recent log stream
                        stream_name = streams['logStreams'][0]['logStreamName']
                        
                        # Get log events - look for initialization logs
                        events = logs_client.get_log_events(
                            logGroupName=log_group_name,
                            logStreamName=stream_name,
                            limit=50,  # More logs to see initialization
                            startFromHead=False
                        )
                        
                        # Display log events
                        if events.get('events'):
                            log_text = "\n".join([event['message'] for event in events['events']])
                            
                            # Highlight important initialization messages
                            if "Expert agents initialized" in log_text:
                                st.success("✅ Found expert agent initialization in logs")
                            elif "Module loading" in log_text:
                                st.info("ℹ️ Found module loading messages")
                            else:
                                st.warning("⚠️ No clear initialization messages found")
                                
                            st.code(log_text, language="text")
                        else:
                            st.info("No log events found in the most recent stream.")
                    else:
                        st.info("No log streams found for this agent.")
                except Exception as e:
                    st.error(f"Error getting logs: {str(e)}")
                    st.info("Make sure your AWS credentials have CloudWatch Logs permissions.")
            except Exception as e:
                st.error(f"Error checking logs: {str(e)}")
                st.info("Make sure your AWS credentials have CloudWatch Logs permissions.")
        


    
    st.header("Available Experts")
    st.markdown("""
    - **HPC Expert**: High Performance Computing specialist
    - **GenAI Expert**: Applied Generative AI specialist
    - **Quantum Expert**: Quantum Computing specialist
    - **Visual Expert**: Visual Computing specialist
    - **Spatial Expert**: Spatial Computing specialist
    - **IoT Expert**: Internet of Things specialist
    - **Partners Expert**: Advanced Computing Partnerships specialist
    - **Coordinator**: Orchestrates collaboration between experts
    """)
    
    st.header("Example Questions")
    example_questions = [
        "How could we accelerate material simulation workflows with both quantum computing and HPC?",
        "Where could GenAI and Quantum computing jointly accelerate drug discovery?",
        "What's the best approach for visualizing quantum computing results?",
        "How can IoT sensors and spatial computing be combined for smart city applications?",
        "What partner ecosystem would be needed for a hybrid HPC-Quantum solution?"
    ]
    
    for question in example_questions:
        if st.button(question, key=question):
            st.session_state.messages.append({"role": "user", "content": question})



# Helper function to detect handoffs in agent responses
def detect_handoffs(individual_responses, agent_sequence):
    """Detect handoffs between agents based on response content and sequence"""
    handoffs = []
    
    # If we have multiple experts (not just coordinator), there were handoffs
    experts = [a for a in agent_sequence if a != 'coordinator']
    
    if len(experts) > 1:
        # Multiple experts means handoffs occurred
        for i in range(len(experts) - 1):
            handoffs.append({
                'from': experts[i],
                'to': experts[i + 1],
                'index': agent_sequence.index(experts[i])
            })
    
    return handoffs

# Helper function to format agent names
def format_agent_name(agent_id):
    """Convert agent_id to display name"""
    name_map = {
        'coordinator': 'Coordinator',
        'hpc_expert': 'HPC Expert',
        'quantum_expert': 'Quantum Expert',
        'genai_expert': 'GenAI Expert',
        'visual_expert': 'Visual Expert',
        'spatial_expert': 'Spatial Expert',
        'iot_expert': 'IoT Expert',
        'partners_expert': 'Partners Expert'
    }
    return name_map.get(agent_id, agent_id.replace('_', ' ').title())

# Helper function to get agent emoji
def get_agent_emoji(agent_id):
    """Get emoji for agent type"""
    emoji_map = {
        'coordinator': '🎯',
        'hpc_expert': '⚡',
        'quantum_expert': '⚛️',
        'genai_expert': '🤖',
        'visual_expert': '👁️',
        'spatial_expert': '🗺️',
        'iot_expert': '📡',
        'partners_expert': '🤝'
    }
    return emoji_map.get(agent_id, '🔧')

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # Check if this is a comparison mode message
        if message.get("comparison_mode") and message.get("role") == "assistant":
            # Show tabs for comparison
            tab1, tab2 = st.tabs(["💬 Direct Claude 4.5", "🤖 Agent Swarm"])
            
            with tab1:
                st.markdown(message.get("claude_direct_response", "No direct response available"))
                # Show execution time if available
                if message.get("claude_execution_time"):
                    st.info(f"⏱️ **Execution Time: {message['claude_execution_time']:.2f} seconds**")
            
            with tab2:
                st.markdown(message["content"])
                
                # Show all the same details as normal mode
                if message.get("agent_sequence") and len(message.get("agent_sequence", [])) > 1:
                    st.markdown("---")
                    st.markdown("### 🎯 Expert Team Assembled")
                    experts = [agent for agent in message.get("agent_sequence", []) if agent != "coordinator"]
                    if experts:
                        cols = st.columns(len(experts))
                        for idx, expert in enumerate(experts):
                            with cols[idx]:
                                emoji = get_agent_emoji(expert)
                                name = format_agent_name(expert)
                                st.markdown(f"### {emoji}")
                                st.markdown(f"**{name}**")
                        handoffs = detect_handoffs(message.get("individual_responses", {}), message.get("agent_sequence", []))
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Experts", len(experts))
                        with col2:
                            st.metric("Interactions", len(message.get("agent_sequence", [])) - 1)
                        with col3:
                            st.metric("Handoffs", len(handoffs))
                
                total_time = message.get('execution_time_ms', 0) / 1000
                if "telemetry" in message and message["telemetry"]:
                    elapsed_times = [event.get("elapsed", 0) for event in message["telemetry"] if event.get("elapsed", 0) > 0]
                    if elapsed_times:
                        total_time = max(elapsed_times)
                if total_time > 0:
                    st.info(f"⏱️ **Total Execution Time: {total_time:.2f} seconds**")
                
                if "telemetry" in message and message["telemetry"]:
                    with st.expander("⏱️ Time Breakdown", expanded=False):
                        telemetry_events = message["telemetry"]
                        stages = {}
                        query_start = 0
                        for event in telemetry_events:
                            if event.get("type") == "query_received":
                                query_start = event.get("elapsed", 0)
                                stages["Query Processing"] = query_start
                                break
                        agent_times = {}
                        prev_time = query_start
                        for event in telemetry_events:
                            elapsed = event.get("elapsed", 0)
                            event_type = event.get("type", "unknown")
                            if event_type == "agent_response":
                                agent = event.get("data", {}).get("agent", "unknown")
                                stage_name = f"{agent.replace('_', ' ').title()} Response"
                                time_spent = elapsed - prev_time
                                agent_times[stage_name] = time_spent
                                prev_time = elapsed
                        stages.update(agent_times)
                        if total_time > sum(stages.values()):
                            stages["Final Processing"] = total_time - sum(stages.values())
                        if stages:
                            for stage, time_spent in stages.items():
                                if time_spent > 0:
                                    percentage = (time_spent / total_time) * 100 if total_time > 0 else 0
                                    st.write(f"• **{stage}**: {time_spent:.2f}s ({percentage:.1f}%)")
                        else:
                            st.write(f"• **Total Processing**: {total_time:.2f}s")
                
                if message.get("agent_sequence"):
                    tab1, tab2, tab3 = st.tabs(["📈 Collaboration Timeline", "💬 Agent Conversations", "🔍 Technical Details"])
                    with tab1:
                        st.markdown("#### How the experts collaborated:")
                        agent_sequence = message.get("agent_sequence", [])
                        individual_responses = message.get("individual_responses", {})
                        handoffs = detect_handoffs(individual_responses, agent_sequence)
                        for i, agent in enumerate(agent_sequence):
                            emoji = get_agent_emoji(agent)
                            name = format_agent_name(agent)
                            if agent == "coordinator" and i == 0:
                                st.markdown(f"**{i+1}.** {emoji} **{name}** analyzed the query and assembled the expert team")
                            elif agent == "coordinator":
                                st.markdown(f"**{i+1}.** {emoji} **{name}** synthesized the final response")
                            else:
                                st.markdown(f"**{i+1}.** {emoji} **{name}** provided domain expertise")
                            handoff = next((h for h in handoffs if h['index'] == i), None)
                            if handoff:
                                st.markdown(f"   🔄 *Handed off to {format_agent_name(handoff['to'])}*")
                            if i < len(agent_sequence) - 1:
                                st.markdown("   ↓")
                    with tab2:
                        st.markdown("#### Individual expert contributions:")
                        if individual_responses:
                            for agent_id in agent_sequence:
                                if agent_id in individual_responses and agent_id != "coordinator":
                                    emoji = get_agent_emoji(agent_id)
                                    name = format_agent_name(agent_id)
                                    with st.container():
                                        st.markdown(f"### {emoji} {name}")
                                        st.markdown(individual_responses[agent_id])
                                        st.markdown("---")
                        else:
                            st.info("No individual responses captured for this interaction.")
                    with tab3:
                        st.write("**Agent sequence:**", agent_sequence)
                        if "domains_involved" in message:
                            st.write("**Domains involved:**", message.get("domains_involved", []))
                        if handoffs:
                            st.write("**Detected handoffs:**")
                            for handoff in handoffs:
                                st.write(f"  - {format_agent_name(handoff['from'])} → {format_agent_name(handoff['to'])}")
                
                from components.telemetry_view import display_telemetry
                with st.expander("View agent telemetry"):
                    display_telemetry(message.get("telemetry", []))
        else:
            # Display message content - should now always be a string
            st.markdown(message["content"])
        
        # If this is an assistant message, show team selection and collaboration details
        if message.get("role") == "assistant" and message.get("agent_sequence"):
            # 1. TEAM SELECTION DISPLAY (prominent, before other details)
            if len(message.get("agent_sequence", [])) > 1:  # More than just coordinator
                st.markdown("---")
                st.markdown("### 🎯 Expert Team Assembled")
                
                # Get experts (exclude coordinator)
                experts = [agent for agent in message.get("agent_sequence", []) if agent != "coordinator"]
                
                if experts:
                    # Display expert badges
                    cols = st.columns(len(experts))
                    for idx, expert in enumerate(experts):
                        with cols[idx]:
                            emoji = get_agent_emoji(expert)
                            name = format_agent_name(expert)
                            st.markdown(f"### {emoji}")
                            st.markdown(f"**{name}**")
                    
                    # Show collaboration stats
                    handoffs = detect_handoffs(message.get("individual_responses", {}), message.get("agent_sequence", []))
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Experts", len(experts))
                    with col2:
                        st.metric("Interactions", len(message.get("agent_sequence", [])) - 1)
                    with col3:
                        st.metric("Handoffs", len(handoffs))
        
        # If this is an assistant message with timing info, show it
        if message.get("role") == "assistant":
            total_time = message.get('execution_time_ms', 0) / 1000
            if "telemetry" in message and message["telemetry"]:
                elapsed_times = [event.get("elapsed", 0) for event in message["telemetry"] if event.get("elapsed", 0) > 0]
                if elapsed_times:
                    total_time = max(elapsed_times)
            
            if total_time > 0:
                st.info(f"⏱️ **Total Execution Time: {total_time:.2f} seconds**")
            
            # Show time breakdown if telemetry is available
            if "telemetry" in message and message["telemetry"]:
                with st.expander("⏱️ Time Breakdown", expanded=False):
                    telemetry_events = message["telemetry"]
                    
                    # Calculate time spent in different stages
                    stages = {}
                    query_start = 0
                    
                    # Find query start time
                    for event in telemetry_events:
                        if event.get("type") == "query_received":
                            query_start = event.get("elapsed", 0)
                            stages["Query Processing"] = query_start
                            break
                    
                    # Calculate agent response times - show parallel execution properly
                    agent_times = {}
                    prev_time = query_start
                    for event in telemetry_events:
                        elapsed = event.get("elapsed", 0)
                        event_type = event.get("type", "unknown")
                        
                        if event_type == "agent_response":
                            agent = event.get("data", {}).get("agent", "unknown")
                            stage_name = f"{agent.replace('_', ' ').title()} Response"
                            # Calculate time since last event
                            time_spent = elapsed - prev_time
                            agent_times[stage_name] = time_spent
                            prev_time = elapsed

                    # Track actual individual times
                    stages.update(agent_times)

                    
                    # Add remaining time as "Final Processing"
                    if total_time > sum(stages.values()):
                        stages["Final Processing"] = total_time - sum(stages.values())
                    
                    # Display the breakdown
                    if stages:
                        for stage, time_spent in stages.items():
                            if time_spent > 0:
                                percentage = (time_spent / total_time) * 100 if total_time > 0 else 0
                                st.write(f"• **{stage}**: {time_spent:.2f}s ({percentage:.1f}%)")
                    else:
                        st.write(f"• **Total Processing**: {total_time:.2f}s")
            
            # Show agent collaboration details if available
            if message.get("agent_sequence"):
                # Create tabs for different views
                tab1, tab2, tab3 = st.tabs(["📈 Collaboration Timeline", "💬 Agent Conversations", "🔍 Technical Details"])
                
                with tab1:
                    # COLLABORATION TIMELINE
                    st.markdown("#### How the experts collaborated:")
                    
                    agent_sequence = message.get("agent_sequence", [])
                    individual_responses = message.get("individual_responses", {})
                    handoffs = detect_handoffs(individual_responses, agent_sequence)
                    
                    # Display timeline
                    for i, agent in enumerate(agent_sequence):
                        emoji = get_agent_emoji(agent)
                        name = format_agent_name(agent)
                        
                        # Show agent step
                        if agent == "coordinator" and i == 0:
                            st.markdown(f"**{i+1}.** {emoji} **{name}** analyzed the query and assembled the expert team")
                        elif agent == "coordinator":
                            st.markdown(f"**{i+1}.** {emoji} **{name}** synthesized the final response")
                        else:
                            st.markdown(f"**{i+1}.** {emoji} **{name}** provided domain expertise")
                        
                        # Check if there was a handoff to next agent
                        handoff = next((h for h in handoffs if h['index'] == i), None)
                        if handoff:
                            st.markdown(f"   🔄 *Handed off to {format_agent_name(handoff['to'])}*")
                        
                        # Add arrow if not last
                        if i < len(agent_sequence) - 1:
                            st.markdown("   ↓")
                
                with tab2:
                    # AGENT CONVERSATIONS (threaded view)
                    st.markdown("#### Individual expert contributions:")
                    
                    if individual_responses:
                        for agent_id in agent_sequence:
                            if agent_id in individual_responses and agent_id != "coordinator":
                                emoji = get_agent_emoji(agent_id)
                                name = format_agent_name(agent_id)
                                
                                with st.container():
                                    st.markdown(f"### {emoji} {name}")
                                    st.markdown(individual_responses[agent_id])
                                    st.markdown("---")
                    else:
                        st.info("No individual responses captured for this interaction.")
                
                with tab3:
                    # TECHNICAL DETAILS (original view)
                    st.write("**Agent sequence:**", agent_sequence)
                    
                    # Display domains involved if available
                    if "domains_involved" in message:
                        st.write("**Domains involved:**", message.get("domains_involved", []))
                    
                    # Show handoff details
                    if handoffs:
                        st.write("**Detected handoffs:**")
                        for handoff in handoffs:
                            st.write(f"  - {format_agent_name(handoff['from'])} → {format_agent_name(handoff['to'])}")
            
            # Display telemetry data if available
            from components.telemetry_view import display_telemetry
            with st.expander("View agent telemetry"):
                display_telemetry(message.get("telemetry", []))

# Chat input
prompt = st.chat_input("Ask the Advanced Computing Team a question...")

if prompt:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Check if comparison mode is active
    if st.session_state.comparison_mode:
        # Create tabs for comparison
        tab1, tab2 = st.tabs(["💬 Direct Claude 4.5 Call", "🤖 Agent Swarm (with Knowledge Bases)"])
        
        with tab1:
            with st.spinner("Calling Claude 4.5 directly..."):
                claude_response = invoke_claude_direct(prompt)
                st.markdown(claude_response["response"])
                
                # Show execution time
                exec_time = claude_response.get('execution_time', 0)
                if exec_time > 0:
                    st.info(f"⏱️ **Execution Time: {exec_time:.2f} seconds**")
                st.caption(f"Model: {claude_response.get('model', 'Unknown')}")
        
        with tab2:
            with st.spinner("The Advanced Computing Team is collaborating on your question..."):
                response = invoke_agent(prompt)
            
            if response.get("agent_sequence") and len(response.get("agent_sequence", [])) > 1:
                experts = [agent for agent in response.get("agent_sequence", []) if agent != "coordinator"]
                if experts:
                    st.success(f"✅ **Expert Team Assembled:** {', '.join([format_agent_name(e) for e in experts])}")
                    st.markdown("---")
            
            st.markdown(response["response"])
            
            total_time = response.get('execution_time_ms', 0) / 1000
            if "telemetry" in response and response["telemetry"]:
                elapsed_times = [event.get("elapsed", 0) for event in response["telemetry"] if event.get("elapsed", 0) > 0]
                if elapsed_times:
                    total_time = max(elapsed_times)
            
            st.info(f"⏱️ **Total Execution Time: {total_time:.2f} seconds**")
            
            if "telemetry" in response and response["telemetry"]:
                with st.expander("⏱️ Time Breakdown", expanded=False):
                    telemetry_events = response["telemetry"]
                    stages = {}
                    query_start = 0
                    for event in telemetry_events:
                        if event.get("type") == "query_received":
                            query_start = event.get("elapsed", 0)
                            stages["Query Processing"] = query_start
                            break
                    agent_times = {}
                    prev_time = query_start
                    for event in telemetry_events:
                        elapsed = event.get("elapsed", 0)
                        event_type = event.get("type", "unknown")
                        if event_type == "agent_response":
                            agent = event.get("data", {}).get("agent", "unknown")
                            stage_name = f"{agent.replace('_', ' ').title()} Response"
                            time_spent = elapsed - prev_time
                            agent_times[stage_name] = time_spent
                            prev_time = elapsed
                    stages.update(agent_times)
                    if total_time > sum(stages.values()):
                        stages["Final Processing"] = total_time - sum(stages.values())
                    if stages:
                        for stage, time_spent in stages.items():
                            if time_spent > 0:
                                percentage = (time_spent / total_time) * 100 if total_time > 0 else 0
                                st.write(f"• **{stage}**: {time_spent:.2f}s ({percentage:.1f}%)")
                    else:
                        st.write(f"• **Total Processing**: {total_time:.2f}s")
            
            if response.get("agent_sequence") and len(response.get("agent_sequence", [])) > 1:
                experts = [agent for agent in response.get("agent_sequence", []) if agent != "coordinator"]
                handoffs = detect_handoffs(response.get("individual_responses", {}), response.get("agent_sequence", []))
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Experts Consulted", len(experts))
                with col2:
                    st.metric("Total Interactions", len(response.get("agent_sequence", [])) - 1)
                with col3:
                    st.metric("Handoffs Detected", len(handoffs))
                st.markdown("---")
                tab1, tab2, tab3 = st.tabs(["📈 Collaboration Timeline", "💬 Agent Conversations", "🔍 Technical Details"])
                with tab1:
                    st.markdown("#### How the experts collaborated:")
                    agent_sequence = response.get("agent_sequence", [])
                    individual_responses = response.get("individual_responses", {})
                    for i, agent in enumerate(agent_sequence):
                        emoji = get_agent_emoji(agent)
                        name = format_agent_name(agent)
                        if agent == "coordinator" and i == 0:
                            st.markdown(f"**{i+1}.** {emoji} **{name}** analyzed the query and assembled the expert team")
                        elif agent == "coordinator":
                            st.markdown(f"**{i+1}.** {emoji} **{name}** synthesized the final response")
                        else:
                            st.markdown(f"**{i+1}.** {emoji} **{name}** provided domain expertise")
                        handoff = next((h for h in handoffs if h['index'] == i), None)
                        if handoff:
                            st.markdown(f"   🔄 *Handed off to {format_agent_name(handoff['to'])}*")
                        if i < len(agent_sequence) - 1:
                            st.markdown("   ↓")
                with tab2:
                    st.markdown("#### Individual expert contributions:")
                    if individual_responses:
                        for agent_id in agent_sequence:
                            if agent_id in individual_responses and agent_id != "coordinator":
                                emoji = get_agent_emoji(agent_id)
                                name = format_agent_name(agent_id)
                                with st.container():
                                    st.markdown(f"### {emoji} {name}")
                                    st.markdown(individual_responses[agent_id])
                                    st.markdown("---")
                    else:
                        st.info("No individual responses captured for this interaction.")
                with tab3:
                    st.write("**Agent sequence:**", agent_sequence)
                    if "domains_involved" in response:
                        st.write("**Domains involved:**", response.get("domains_involved", []))
                    if handoffs:
                        st.write("**Detected handoffs:**")
                        for handoff in handoffs:
                            st.write(f"  - {format_agent_name(handoff['from'])} → {format_agent_name(handoff['to'])}")
            
            if "telemetry" in response:
                from components.telemetry_view import display_telemetry
                with st.expander("View agent telemetry", expanded=True):
                    display_telemetry(response.get("telemetry", []))
        
        # Store both responses in chat history
        st.session_state.messages.append({
            "role": "assistant",
            "content": response["response"],
            "agent_sequence": response.get("agent_sequence", []),
            "domains_involved": response.get("domains_involved", []),
            "execution_time_ms": response.get("execution_time_ms", 0),
            "individual_responses": response.get("individual_responses", {}),
            "telemetry": response.get("telemetry", []),
            "comparison_mode": True,
            "claude_direct_response": claude_response["response"],
            "claude_execution_time": claude_response.get("execution_time", 0)
        })
    else:
        # Normal mode - just show agent response
        with st.chat_message("assistant"):
            with st.spinner("The Advanced Computing Team is collaborating on your question..."):
                # Invoke the agent (will use local testing mode if ARN not configured)
                response = invoke_agent(prompt)
            
            # Show team selection first if experts were involved
            if response.get("agent_sequence") and len(response.get("agent_sequence", [])) > 1:
                experts = [agent for agent in response.get("agent_sequence", []) if agent != "coordinator"]
                if experts:
                    st.success(f"✅ **Expert Team Assembled:** {', '.join([format_agent_name(e) for e in experts])}")
                    st.markdown("---")
            
            # Display the response - should now always be clean text
            st.markdown(response["response"])
            
            # Show execution time prominently - get from telemetry if available
            total_time = response.get('execution_time_ms', 0) / 1000
            if "telemetry" in response and response["telemetry"]:
                elapsed_times = [event.get("elapsed", 0) for event in response["telemetry"] if event.get("elapsed", 0) > 0]
                if elapsed_times:
                    total_time = max(elapsed_times)
            
            st.info(f"⏱️ **Total Execution Time: {total_time:.2f} seconds**")
            
            # Show time breakdown if telemetry is available
            if "telemetry" in response and response["telemetry"]:
                with st.expander("⏱️ Time Breakdown", expanded=False):
                    telemetry_events = response["telemetry"]
                    
                    # Calculate time spent in different stages
                    stages = {}
                    query_start = 0
                    
                    # Find query start time
                    for event in telemetry_events:
                        if event.get("type") == "query_received":
                            query_start = event.get("elapsed", 0)
                            stages["Query Processing"] = query_start
                            break
                    
                    # Calculate agent response times - show parallel execution properly
                    agent_times = {}
                    prev_time = query_start
                    for event in telemetry_events:
                        elapsed = event.get("elapsed", 0)
                        event_type = event.get("type", "unknown")
                        
                        if event_type == "agent_response":
                            agent = event.get("data", {}).get("agent", "unknown")
                            stage_name = f"{agent.replace('_', ' ').title()} Response"
                            # Calculate time since last event
                            time_spent = elapsed - prev_time
                            agent_times[stage_name] = time_spent
                            prev_time = elapsed

                    # Track actual individual times
                    stages.update(agent_times)

                    
                    # Add remaining time as "Final Processing"
                    if total_time > sum(stages.values()):
                        stages["Final Processing"] = total_time - sum(stages.values())
                    
                    # Display the breakdown
                    if stages:
                        for stage, time_spent in stages.items():
                            if time_spent > 0:
                                percentage = (time_spent / total_time) * 100 if total_time > 0 else 0
                                st.write(f"• **{stage}**: {time_spent:.2f}s ({percentage:.1f}%)")
                    else:
                        st.write(f"• **Total Processing**: {total_time:.2f}s")
            
            # Show enhanced collaboration details
            if response.get("agent_sequence") and len(response.get("agent_sequence", [])) > 1:
                # Show collaboration stats
                experts = [agent for agent in response.get("agent_sequence", []) if agent != "coordinator"]
                handoffs = detect_handoffs(response.get("individual_responses", {}), response.get("agent_sequence", []))
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Experts Consulted", len(experts))
                with col2:
                    st.metric("Total Interactions", len(response.get("agent_sequence", [])) - 1)
                with col3:
                    st.metric("Handoffs Detected", len(handoffs))
                
                st.markdown("---")
                
                # Create tabs for different views
                tab1, tab2, tab3 = st.tabs(["📈 Collaboration Timeline", "💬 Agent Conversations", "🔍 Technical Details"])
                
                with tab1:
                    # COLLABORATION TIMELINE
                    st.markdown("#### How the experts collaborated:")
                    
                    agent_sequence = response.get("agent_sequence", [])
                    individual_responses = response.get("individual_responses", {})
                    
                    # Display timeline
                    for i, agent in enumerate(agent_sequence):
                        emoji = get_agent_emoji(agent)
                        name = format_agent_name(agent)
                        
                        # Show agent step
                        if agent == "coordinator" and i == 0:
                            st.markdown(f"**{i+1}.** {emoji} **{name}** analyzed the query and assembled the expert team")
                        elif agent == "coordinator":
                            st.markdown(f"**{i+1}.** {emoji} **{name}** synthesized the final response")
                        else:
                            st.markdown(f"**{i+1}.** {emoji} **{name}** provided domain expertise")
                        
                        # Check if there was a handoff to next agent
                        handoff = next((h for h in handoffs if h['index'] == i), None)
                        if handoff:
                            st.markdown(f"   🔄 *Handed off to {format_agent_name(handoff['to'])}*")
                        
                        # Add arrow if not last
                        if i < len(agent_sequence) - 1:
                            st.markdown("   ↓")
                
                with tab2:
                    # AGENT CONVERSATIONS (threaded view)
                    st.markdown("#### Individual expert contributions:")
                    
                    if individual_responses:
                        for agent_id in agent_sequence:
                            if agent_id in individual_responses and agent_id != "coordinator":
                                emoji = get_agent_emoji(agent_id)
                                name = format_agent_name(agent_id)
                                
                                with st.container():
                                    st.markdown(f"### {emoji} {name}")
                                    st.markdown(individual_responses[agent_id])
                                    st.markdown("---")
                    else:
                        st.info("No individual responses captured for this interaction.")
                
                with tab3:
                    # TECHNICAL DETAILS (original view)
                    st.write("**Agent sequence:**", agent_sequence)
                    
                    # Display domains involved if available
                    if "domains_involved" in response:
                        st.write("**Domains involved:**", response.get("domains_involved", []))
                    
                    # Show handoff details
                    if handoffs:
                        st.write("**Detected handoffs:**")
                        for handoff in handoffs:
                            st.write(f"  - {format_agent_name(handoff['from'])} → {format_agent_name(handoff['to'])}")
            
            # Display telemetry data if available
            if "telemetry" in response and response["telemetry"]:
                from components.telemetry_view import display_telemetry
                with st.expander("View agent telemetry", expanded=True):
                    display_telemetry(response.get("telemetry", []))
        
        # Add assistant message to chat history with metadata
        st.session_state.messages.append({
            "role": "assistant", 
            "content": response["response"],
            "agent_sequence": response.get("agent_sequence", []),
            "domains_involved": response.get("domains_involved", []),
            "execution_time_ms": response.get("execution_time_ms", 0),
            "individual_responses": response.get("individual_responses", {}),
            "telemetry": response.get("telemetry", []),
            "comparison_mode": False
        })
