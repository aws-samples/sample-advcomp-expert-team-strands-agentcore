"""
Telemetry visualization component for the Streamlit app
"""

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

def display_telemetry(telemetry_events):
    """Display telemetry events in the Streamlit app"""
    if not telemetry_events:
        st.info("No telemetry data available")
        return
    
    # Show expert responses prominently
    expert_responses = []
    for event in telemetry_events:
        if event["type"] == "agent_response":
            agent = event["data"].get("agent", "unknown")
            response = event["data"].get("response", "")
            elapsed = event.get("elapsed", 0)
            
            # Extract text from response if it's in a complex format
            if isinstance(response, dict) and "content" in response:
                text = ""
                for item in response["content"]:
                    if isinstance(item, dict) and "text" in item:
                        text += item["text"]
                response = text
            
            expert_responses.append({
                "agent": agent,
                "response": response,
                "elapsed": elapsed
            })
    
    # Show tool calls if available
    tool_calls = []
    for event in telemetry_events:
        if event["type"] == "tool_calls":
            tool_calls.extend(event["data"].get("calls", []))
    
    if tool_calls:
        st.subheader("🔧 Knowledge Base Queries")
        for i, call in enumerate(tool_calls):
            agent_name = call.get('agent', 'unknown').replace('_', ' ').title()
            query = call.get('input', {}).get('query', 'N/A')
            description = call.get('input', {}).get('description', 'Knowledge Base')
            
            with st.expander(f"📚 {agent_name} → {description}", expanded=False):
                st.markdown(f"**Description:** {description}")
                st.markdown("")
                
                st.markdown(f"**🔍 Query Sent:**")
                st.info(query)
                
                st.markdown(f"**📥 Retrieval Response:**")
                response_text = call.get('result_preview', 'No response')
                
                # Parse the response - it could be a JSON string or already parsed
                try:
                    import json
                    if isinstance(response_text, str):
                        response_data = json.loads(response_text)
                    else:
                        response_data = response_text
                    
                    # Extract content field if it exists
                    if isinstance(response_data, dict) and 'content' in response_data:
                        content = response_data['content']
                    else:
                        content = str(response_data)
                except (json.JSONDecodeError, TypeError):
                    # If parsing fails, use the raw text
                    content = response_text
                
                st.success(content)
    
    if expert_responses:
        st.subheader("🤖 Expert Responses")
        for expert in expert_responses:
            agent_name = expert["agent"].replace('_', ' ').title()
            with st.expander(f"💬 {agent_name} ({expert['elapsed']:.1f}s)", expanded=False):
                st.markdown(expert["response"])
    else:
        st.info("No expert responses captured in telemetry")
    
    with st.expander("View all telemetry events"):
        for event in telemetry_events:
            st.json(event)