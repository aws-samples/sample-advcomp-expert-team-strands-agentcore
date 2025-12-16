"""
Telemetry system for tracking agent activities with OpenTelemetry integration
"""

import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Any

# Configure logging first
logger = logging.getLogger("telemetry")

# Import OpenTelemetry modules
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    OTEL_AVAILABLE = True
    logger.info("OpenTelemetry modules imported successfully")
except ImportError as e:
    logger.warning(f"OpenTelemetry modules not available: {e}")
    OTEL_AVAILABLE = False

class Telemetry:
    """Telemetry system for tracking agent activities with OpenTelemetry integration"""
    
    def __init__(self):
        self.events = []
        self.start_time = None
        self.session_id = None
        self.current_span = None
        self.tracer = None
        
        # Initialize OpenTelemetry if available
        if OTEL_AVAILABLE and os.environ.get("OTEL_SDK_DISABLED", "false").lower() != "true":
            try:
                # Set up the tracer provider
                resource = Resource.create({
                    ResourceAttributes.SERVICE_NAME: "advcomp_swarm",
                    ResourceAttributes.SERVICE_VERSION: "1.0.0",
                })
                
                provider = TracerProvider(resource=resource)
                trace.set_tracer_provider(provider)
                
                # Get a tracer
                self.tracer = trace.get_tracer("advcomp_swarm.telemetry")
                logger.info("OpenTelemetry tracer initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenTelemetry: {e}")
                self.tracer = None
    
    def start_session(self, session_id):
        """Start a new telemetry session"""
        self.events = []
        self.start_time = time.time()
        self.session_id = session_id
        
        # Start a new trace for this session
        if self.tracer:
            try:
                self.current_span = self.tracer.start_span(
                    f"session.{session_id}",
                    attributes={
                        "session.id": session_id,
                    }
                )
                self.current_span.__enter__()
                logger.info(f"Started OpenTelemetry trace for session {session_id}")
            except Exception as e:
                logger.error(f"Failed to start OpenTelemetry span: {e}")
                self.current_span = None
        
        self.log_event("session_start", {"session_id": session_id})
    
    def end_session(self):
        """End the current telemetry session"""
        if self.current_span:
            try:
                self.current_span.set_attribute("session.duration", time.time() - self.start_time)
                self.current_span.set_attribute("session.event_count", len(self.events))
                self.current_span.__exit__(None, None, None)
                logger.info(f"Ended OpenTelemetry trace for session {self.session_id}")
            except Exception as e:
                logger.error(f"Failed to end OpenTelemetry span: {e}")
            self.current_span = None
    
    def log_event(self, event_type, data=None):
        """Log an event with timestamp and data"""
        timestamp = time.time()
        event = {
            "timestamp": timestamp,
            "time": datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3],
            "elapsed": round(timestamp - self.start_time, 3) if self.start_time else 0,
            "type": event_type,
            "data": data or {}
        }
        self.events.append(event)
        logger.info(f"Telemetry event: {event_type} - {data}")
        
        # Create a span for this event
        if self.tracer:
            try:
                with self.tracer.start_as_current_span(
                    f"event.{event_type}",
                    attributes={
                        "event.type": event_type,
                        "event.timestamp": timestamp,
                        "event.elapsed": event["elapsed"],
                        "session.id": self.session_id or "unknown",
                        **{f"event.data.{k}": str(v) for k, v in (data or {}).items() if v is not None}
                    }
                ):
                    pass  # The span will be automatically closed when exiting this block
            except Exception as e:
                logger.error(f"Failed to create OpenTelemetry span for event: {e}")
        
        return event
    
    def log_agent_thinking(self, agent_name, query):
        """Log when an agent is thinking about a query"""
        return self.log_event("agent_thinking", {
            "agent": agent_name,
            "query": query
        })
    
    def log_agent_response(self, agent_name, response):
        """Log when an agent provides a response"""
        # Truncate response if too long
        if isinstance(response, str) and len(response) > 100:
            response_summary = response[:100] + "..."
        else:
            response_summary = response
            
        return self.log_event("agent_response", {
            "agent": agent_name,
            "response": response_summary
        })
    
    def log_handoff(self, from_agent, to_agent, reason):
        """Log when control is handed off from one agent to another"""
        return self.log_event("handoff", {
            "from": from_agent,
            "to": to_agent,
            "reason": reason
        })
    
    def log_tool_use(self, agent_name, tool_name, inputs):
        """Log when an agent uses a tool"""
        return self.log_event("tool_use", {
            "agent": agent_name,
            "tool": tool_name,
            "inputs": inputs
        })
    
    def log_tool_result(self, agent_name, tool_name, result):
        """Log when a tool returns a result"""
        # Truncate result if too long
        if isinstance(result, str) and len(result) > 100:
            result_summary = result[:100] + "..."
        else:
            result_summary = result
            
        return self.log_event("tool_result", {
            "agent": agent_name,
            "tool": tool_name,
            "result": result_summary
        })
    
    def log_query_analysis(self, domains):
        """Log the results of query analysis"""
        return self.log_event("query_analysis", {
            "domains": domains
        })
    
    def log_swarm_creation(self, domains):
        """Log when a swarm is created with specific domains"""
        return self.log_event("swarm_creation", {
            "domains": domains
        })
    
    def get_events(self):
        """Get all events in the current session"""
        return self.events
    
    def get_summary(self):
        """Get a summary of the current session"""
        if not self.events:
            return {"events": 0, "agents": [], "tools": []}
        
        agents = set()
        tools = set()
        
        for event in self.events:
            if event["type"] == "agent_thinking" or event["type"] == "agent_response":
                agents.add(event["data"].get("agent"))
            elif event["type"] == "tool_use":
                tools.add(event["data"].get("tool"))
        
        return {
            "events": len(self.events),
            "agents": list(agents),
            "tools": list(tools),
            "duration": round(time.time() - self.start_time, 3) if self.start_time else 0
        }

# Create a global telemetry instance
telemetry = Telemetry()