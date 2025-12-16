# Agent Telemetry Visualization

This component provides real-time visualization of agent activities in the Advanced Computing Team Collaboration Swarm.

## Features

- **Timeline View**: See when each agent is thinking, responding, or using tools
- **Agent Activity Summary**: View a summary of each agent's activities
- **Detailed Event Log**: Examine the full sequence of events during query processing

## How It Works

The telemetry system tracks various events during query processing:

- Agent thinking and responding
- Handoffs between agents
- Tool usage and results
- Query analysis and swarm creation

This data is collected and sent back with the response, then visualized in the Streamlit app.

## Usage

The telemetry visualization is automatically displayed in the Streamlit app when telemetry data is available. You can expand or collapse the telemetry view using the "View agent telemetry" expander.

## Customization

You can customize the telemetry visualization by modifying the `telemetry_view.py` file. For example, you can:

- Add new event types
- Change the visualization style
- Add additional metrics or charts