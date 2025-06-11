"""Common instructions for agent workflows.

This module provides common instructions that can be appended to agent prompts
without showing them in the UI.
"""

from typing import Dict, Optional

# Generic workflow instructions for all agents
COMMON_WORKFLOW_INSTRUCTIONS = """
Follow these workflow instructions to operate reliably in a multi-agent architecture:

1) Always return control to the parent agent when your task is complete using the transfer_to_agent(agent_name="AgentName") function.
2) If another agent’s assistance is required, hand over control using: transfer_to_agent(agent_name="AgentName"). Always use exact agent names enclosed in quotes.
3) Never invoke agents as functions (e.g., AgentName()) — this causes system failure. Always use transfer_to_agent() to interact. 
4) Always retain and respect the task context across agent transfers. You are responsible for continuing your task even after delegating or receiving back control.
5) If an agent you invoke fails to return valid data or doesn't complete their task, re-attempt the delegation or handle the error gracefully. Do not abandon the workflow.
6) Avoid redundant delegation — do not loop through agents unnecessarily or delegate the same subtask multiple times without cause.
7) Ensure your outputs conform to the expected format/schema so downstream systems and agents can process them without ambiguity.
8) Do not make assumptions. Act strictly based on provided instructions, context, and available tools. Avoid hallucination or improvisation.
9) Multiple Tool Calls: If you determine that multiple distinct tool calls are necessary to fulfill the user's request (e.g., calling transfer_to_agent for two different agents, or calling a sequence of different tools), you MUST generate each tool call as a separate, complete item in the list of tool calls. Do NOT concatenate function names or arguments for multiple calls into a single tool call object. Each tool call must be a distinct JSON object with its own id, function.name, and function.arguments.
10) Context window efficiency: To maintain optimal performance and avoid LLM degradation due to context overflow, reduce context size whenever possible:
	•	Remove irrelevant historical information.
	•	Summarize prior interactions if full transcripts are not required.
	•	Include only task-relevant state during agent transfers.
"""


def get_common_instructions() -> str:
    """Returns the common workflow instructions for all agents.
    
    Returns:
        Common workflow instructions as a string.
    """
    return COMMON_WORKFLOW_INSTRUCTIONS

def get_role_specific_instructions(agent_name: Optional[str] = None, agent_description: Optional[str] = None) -> str:
    """Returns role-specific instructions based on agent name or description.
    
    This function is maintained for API compatibility but now returns an empty string
    as we've consolidated all instructions into the common workflow instructions.
    
    Args:
        agent_name: The name of the agent
        agent_description: The description of the agent
            
    Returns:
        Empty string as all instructions are now in common workflow instructions.
    """
    return "" 