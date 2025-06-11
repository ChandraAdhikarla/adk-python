# Agent Development Kit (ADK)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python Unit Tests](https://github.com/google/adk-python/actions/workflows/python-unit-tests.yml/badge.svg)](https://github.com/google/adk-python/actions/workflows/python-unit-tests.yml)
[![r/agentdevelopmentkit](https://img.shields.io/badge/Reddit-r%2Fagentdevelopmentkit-FF4500?style=flat&logo=reddit&logoColor=white)](https://www.reddit.com/r/agentdevelopmentkit/)

<html>
    <h2 align="center">
      <img src="https://raw.githubusercontent.com/google/adk-python/main/assets/agent-development-kit.png" width="256"/>
    </h2>
    <h3 align="center">
      An open-source, code-first Python toolkit for building, evaluating, and deploying sophisticated AI agents with flexibility and control.
    </h3>
    <h3 align="center">
      Important Links:
      <a href="https://google.github.io/adk-docs/">Docs</a> &
      <a href="https://github.com/google/adk-samples">Samples</a>.
    </h3>
</html>

Agent Development Kit (ADK) is designed for developers seeking fine-grained
control and flexibility when building advanced AI agents that are tightly
integrated with services in Google Cloud. It allows you to define agent
behavior, orchestration, and tool use directly in code, enabling robust
debugging, versioning, and deployment anywhere – from your laptop to the cloud.


---

## ✨ Key Features

- **Rich Tool Ecosystem**: Utilize pre-built tools, custom functions,
  OpenAPI specs, or integrate existing tools to give agents diverse
  capabilities, all for tight integration with the Google ecosystem.

- **Code-First Development**: Define agent logic, tools, and orchestration
  directly in Python for ultimate flexibility, testability, and versioning.

- **Modular Multi-Agent Systems**: Design scalable applications by composing
  multiple specialized agents into flexible hierarchies.

- **Deploy Anywhere**: Easily containerize and deploy agents on Cloud Run or
  scale seamlessly with Vertex AI Agent Engine.


## 🚀 Installation

### Stable Release (Recommended)

You can install the latest stable version of ADK using `pip`:

```bash
pip install google-adk
```

The release cadence is weekly.

This version is recommended for most users as it represents the most recent official release.

### Development Version
Bug fixes and new features are merged into the main branch on GitHub first. If you need access to changes that haven't been included in an official PyPI release yet, you can install directly from the main branch:

```bash
pip install git+https://github.com/google/adk-python.git@main
```

Note: The development version is built directly from the latest code commits. While it includes the newest fixes and features, it may also contain experimental changes or bugs not present in the stable release. Use it primarily for testing upcoming changes or accessing critical fixes before they are officially released.

## 📚 Documentation

Explore the full documentation for detailed guides on building, evaluating, and
deploying agents:

* **[Documentation](https://google.github.io/adk-docs)**

## 🏁 Feature Highlight

### Define a single agent:

```python
from google.adk.agents import Agent
from google.adk.tools import google_search

root_agent = Agent(
    name="search_assistant",
    model="gemini-2.0-flash", # Or your preferred Gemini model
    instruction="You are a helpful assistant. Answer user questions using Google Search when needed.",
    description="An assistant that can search the web.",
    tools=[google_search]
)
```

### Define a multi-agent system:

Define a multi-agent system with coordinator agent, greeter agent, and task execution agent. Then ADK engine and the model will guide the agents works together to accomplish the task.

```python
from google.adk.agents import LlmAgent, BaseAgent

# Define individual agents
greeter = LlmAgent(name="greeter", model="gemini-2.0-flash", ...)
task_executor = LlmAgent(name="task_executor", model="gemini-2.0-flash", ...)

# Create parent agent and assign children via sub_agents
coordinator = LlmAgent(
    name="Coordinator",
    model="gemini-2.0-flash",
    description="I coordinate greetings and tasks.",
    sub_agents=[ # Assign sub_agents here
        greeter,
        task_executor
    ]
)
```

### Development UI

A built-in development UI to help you test, evaluate, debug, and showcase your agent(s).

<img src="https://raw.githubusercontent.com/google/adk-python/main/assets/adk-web-dev-ui-function-call.png"/>

###  Evaluate Agents

```bash
adk eval \
    samples_for_testing/hello_world \
    samples_for_testing/hello_world/hello_world_eval_set_001.evalset.json
```

## 🤖 A2A and ADK integration

For remote agent-to-agent communication, ADK integrates with the
[A2A protocol](https://github.com/google/A2A/).
See this [example](https://github.com/google/A2A/tree/main/samples/python/agents/google_adk)
for how they can work together.

## 🤝 Contributing

We welcome contributions from the community! Whether it's bug reports, feature requests, documentation improvements, or code contributions, please see our 
- [General contribution guideline and flow](https://google.github.io/adk-docs/contributing-guide/#questions).
- Then if you want to contribute code, please read [Code Contributing Guidelines](./CONTRIBUTING.md) to get started.

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## Preview

This feature is subject to the "Pre-GA Offerings Terms" in the General Service Terms section of the [Service Specific Terms](https://cloud.google.com/terms/service-terms#1). Pre-GA features are available "as is" and might have limited support. For more information, see the [launch stage descriptions](https://cloud.google.com/products?hl=en#product-launch-stages).

---

# ADK FastAPI Server

This FastAPI server provides an HTTP interface to Google's Agent Development Kit (ADK). It allows you to:

1. Register agent definitions
2. Create and manage sessions
3. Run agents and retrieve results
4. Manage artifacts and other ADK features

## Installation

```bash
pip install -r requirements.txt
```

## Running the Server

```bash
python api_server.py
```

The server will be accessible at: http://localhost:8000

API documentation is available at: http://localhost:8000/docs

## API Endpoints

### Agent Management

- **POST /agents** - Register an agent definition
- **GET /agents** - List all registered agents

### Session Management

- **POST /sessions** - Create a new session
- **GET /sessions** - List all sessions for a user
- **GET /sessions/{session_id}** - Get session details
- **DELETE /sessions/{session_id}** - Delete a session

### Agent Execution

- **POST /run** - Run an agent and get results (streaming or non-streaming)

### Events and Artifacts

- **GET /sessions/{session_id}/events** - List all events in a session
- **GET /sessions/{session_id}/artifacts** - List all artifacts in a session
- **GET /sessions/{session_id}/artifacts/{artifact_name}** - Get an artifact
- **DELETE /sessions/{session_id}/artifacts/{artifact_name}** - Delete an artifact

## Example Usage

### Register an Agent

```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_agent",
    "model": "gemini-1.5-pro",
    "description": "A helpful assistant",
    "instruction": "You are an AI assistant that helps with various tasks.",
    "tools": [
      {
        "function_name": "search_web",
        "description": "Search the web for information",
        "parameters": {
          "query": {
            "type": "string",
            "description": "The search query",
            "required": true
          }
        }
      }
    ],
    "sub_agents": []
  }'
```

### Create a Session

```bash
curl -X POST "http://localhost:8000/sessions?app_name=my_app&user_id=user123"
```

### Run an Agent

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "app_name": "my_app",
    "user_id": "user123",
    "session_id": "session123",
    "message": {
      "role": "user",
      "parts": [{"text": "Hello, can you help me?"}]
    },
    "streaming": false
  }'
```

## Integration with Your Golang Service

Your Golang service can interact with this API by:

1. Fetching agent definitions from your database
2. POSTing them to the `/agents` endpoint
3. Creating sessions via the `/sessions` endpoint
4. Running agents via the `/run` endpoint

All sessions, artifacts, and events will be managed by this server using ADK's built-in services.
