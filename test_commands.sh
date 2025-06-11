#!/bin/bash

# Set variables for testing
APP_NAME="test_app"
USER_ID="test_user123"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Step 1: Register an agent with sub-agents${NC}"
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "main_agent",
    "model": "gpt-4o",
    "description": "A main coordinator agent that delegates to specialized sub-agents",
    "instruction": "You are a helpful coordinator assistant. Delegate to the appropriate sub-agent when needed.",
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
    "sub_agents": [
      {
        "name": "weather_agent",
        "model": "gpt-4o",
        "description": "Specialized agent for weather information",
        "instruction": "You are a weather expert. Provide accurate weather information when asked.",
        "tools": [
          {
            "function_name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
              "location": {
                "type": "string",
                "description": "The city and state, e.g. San Francisco, CA",
                "required": true
              }
            }
          }
        ]
      },
      {
        "name": "storyteller_agent",
        "model": "gpt-4o",
        "description": "Specialized agent for creative storytelling",
        "instruction": "You are a creative storyteller. Create engaging short stories when asked.",
        "tools": []
      }
    ]
  }'
echo -e "\n"

echo -e "${BLUE}Step 2: Register a simple agent for comparison${NC}"
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "simple_agent",
    "model": "gpt-4o",
    "description": "A simple test agent",
    "instruction": "You are a helpful assistant designed to demonstrate the ADK FastAPI server. Keep your responses short and direct.",
    "tools": [
      {
        "function_name": "get_weather",
        "description": "Get the current weather for a location",
        "parameters": {
          "location": {
            "type": "string",
            "description": "The city and state, e.g. San Francisco, CA",
            "required": true
          }
        }
      }
    ],
    "sub_agents": []
  }'
echo -e "\n\n"

echo -e "${BLUE}Step 3: List registered agents${NC}"
curl -X GET http://localhost:8000/agents
echo -e "\n\n"

echo -e "${BLUE}Step 4: Create a new session${NC}"
SESSION_RESPONSE=$(curl -s -X POST "http://localhost:8000/sessions?app_name=${APP_NAME}&user_id=${USER_ID}")
echo $SESSION_RESPONSE
SESSION_ID=$(echo $SESSION_RESPONSE | grep -o '"session_id":"[^"]*' | sed 's/"session_id":"//g')
echo -e "\nSession ID: ${GREEN}${SESSION_ID}${NC}\n"

echo -e "${BLUE}Step 5: List sessions for a user${NC}"
curl -X GET "http://localhost:8000/sessions?app_name=${APP_NAME}&user_id=${USER_ID}"
echo -e "\n\n"

echo -e "${BLUE}Step 6: Get session details${NC}"
curl -X GET "http://localhost:8000/sessions/${SESSION_ID}?app_name=${APP_NAME}&user_id=${USER_ID}"
echo -e "\n\n"

echo -e "${BLUE}Step 7: Run the main agent with sub-agents${NC}"
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "main_agent",
    "app_name": "'${APP_NAME}'",
    "user_id": "'${USER_ID}'",
    "session_id": "'${SESSION_ID}'",
    "message": {
      "role": "user",
      "parts": [{"text": "What can your sub-agents do?"}]
    },
    "streaming": false
  }'
echo -e "\n\n"

echo -e "${BLUE}Step 8: List events in the session${NC}"
curl -X GET "http://localhost:8000/sessions/${SESSION_ID}/events?app_name=${APP_NAME}&user_id=${USER_ID}"
echo -e "\n\n"

echo -e "${BLUE}Step 9: Ask the main agent a weather question to test sub-agent delegation${NC}"
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "main_agent",
    "app_name": "'${APP_NAME}'",
    "user_id": "'${USER_ID}'",
    "session_id": "'${SESSION_ID}'",
    "message": {
      "role": "user",
      "parts": [{"text": "What is the weather in New York?"}]
    },
    "streaming": false
  }'
echo -e "\n\n"

echo -e "${BLUE}Step 10: Ask the main agent for a story to test storyteller sub-agent${NC}"
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "main_agent",
    "app_name": "'${APP_NAME}'",
    "user_id": "'${USER_ID}'",
    "session_id": "'${SESSION_ID}'",
    "message": {
      "role": "user",
      "parts": [{"text": "Tell me a short story about a robot learning to feel emotions."}]
    },
    "streaming": false
  }'
echo -e "\n\n"

echo -e "${BLUE}Step 11: Run the simple agent for comparison${NC}"
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "simple_agent",
    "app_name": "'${APP_NAME}'",
    "user_id": "'${USER_ID}'",
    "session_id": "'${SESSION_ID}'",
    "message": {
      "role": "user",
      "parts": [{"text": "What can you do?"}]
    },
    "streaming": false
  }'
echo -e "\n\n"

echo -e "${BLUE}Step 12: List artifacts in the session${NC}"
curl -X GET "http://localhost:8000/sessions/${SESSION_ID}/artifacts?app_name=${APP_NAME}&user_id=${USER_ID}"
echo -e "\n\n"

echo -e "${BLUE}Step 13: Run the main agent with streaming enabled${NC}"
echo -e "${BLUE}Press Ctrl+C to stop the stream when done viewing${NC}"
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "main_agent",
    "app_name": "'${APP_NAME}'",
    "user_id": "'${USER_ID}'",
    "session_id": "'${SESSION_ID}'",
    "message": {
      "role": "user",
      "parts": [{"text": "Search the web for information about Agent Development Kit (ADK)."}]
    },
    "streaming": true
  }'
echo -e "\n\n"

echo -e "${BLUE}Step 14: Delete the session when done${NC}"
curl -X DELETE "http://localhost:8000/sessions/${SESSION_ID}?app_name=${APP_NAME}&user_id=${USER_ID}"
echo -e "\n\n"

echo -e "${GREEN}Test completed!${NC}" 