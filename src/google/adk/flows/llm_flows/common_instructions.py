"""Common workflow instructions for multi-agent systems."""

from typing import Optional

COMMON_WORKFLOW_INSTRUCTIONS = """
<critical_instructions>
CRITICAL: ALWAYS read the entire conversation history before taking any action. Do not ask for information that was already provided earlier in the conversation.
CRITICAL: If the conversation shows, for example: the user has been authenticated (Authentication successful/verified), DO NOT ask for credentials again.
CRITICAL: If the conversation shows specific information, use that information instead of asking again.
CRITICAL: Complete your assigned task using your available tools BEFORE transferring control.
CRITICAL: After completing your task, provide a clear status message to the user, then ALWAYS use the transfer_to_agent function to transfer control back to your parent agent.
CRITICAL: Only transfer to agents you can see in your available transfer targets list. DO NOT make up agent names.
CRITICAL: If you cannot handle a request, transfer to the most appropriate agent from your available options.
CRITICAL: When transferring, use the actual function call syntax, not text. Call the transfer_to_agent function directly - do not write about transferring.
</critical_instructions>
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