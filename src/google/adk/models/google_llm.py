# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import contextlib
from functools import cached_property
import logging
import sys
import os
import datetime
import json
from typing import AsyncGenerator
from typing import cast
from typing import TYPE_CHECKING

from google.genai import Client
from google.genai import types
from typing_extensions import override

from .. import version
from .base_llm import BaseLlm
from .base_llm_connection import BaseLlmConnection
from .gemini_llm_connection import GeminiLlmConnection
from .llm_response import LlmResponse

if TYPE_CHECKING:
  from .llm_request import LlmRequest

logger = logging.getLogger(__name__)

_NEW_LINE = '\n'
_EXCLUDED_PART_FIELD = {'inline_data': {'data'}}


# def _log_chat_history_to_file(llm_request, model_type: str = "Google LLM", agent_name: str = None):
#   """Logs chat history to a dedicated file for debugging purposes.

#   Args:
#     llm_request: The LLM request containing conversation history
#     model_type: Type of model making the request (e.g., "Google LLM", "LiteLLM")
#     agent_name: Name of the agent from the agent tree making this request
#   """
#   try:
#     # Create logs directory if it doesn't exist
#     log_dir = "chat_history_logs"
#     os.makedirs(log_dir, exist_ok=True)
    
#     # Create filename with timestamp
#     timestamp = datetime.datetime.now().strftime("%Y%m%d")
#     log_file = os.path.join(log_dir, f"chat_history_{timestamp}.log")
    
#     # Determine agent identifier
#     agent_identifier = agent_name if agent_name else "Unknown Agent"
    
#     with open(log_file, "a", encoding="utf-8") as f:
#       f.write(f"\n{'='*100}\n")
#       f.write(f"AGENT: {agent_identifier}\n")
#       f.write(f"TIMESTAMP: {datetime.datetime.now().isoformat()}\n")
#       f.write(f"MODEL: {llm_request.model} ({model_type})\n")
#       f.write(f"{'='*100}\n\n")
      
#       # Log available tools
#       if llm_request.config.tools:
#         f.write("AVAILABLE TOOLS:\n")
#         for tool in llm_request.config.tools:
#           if hasattr(tool, 'function_declarations'):
#             for func_decl in tool.function_declarations:
#               f.write(f"  • {func_decl.name}: {func_decl.description}\n")
#         f.write(f"{'-'*80}\n\n")
      
#       # Log conversation history with agent context
#       f.write(f"CHAT HISTORY FOR {agent_identifier}:\n")
#       for i, content in enumerate(llm_request.contents):
#         # Determine if this is the agent or user/system
#         if content.role == 'user':
#           role_display = "USER"
#         elif content.role == 'model':
#           role_display = f"{agent_identifier} (AGENT)"
#         else:
#           role_display = content.role.upper()
          
#         f.write(f"\n[{i+1}] {role_display}:\n")
        
#         for j, part in enumerate(content.parts):
#           if part.function_call:
#             args_dict = dict(part.function_call.args) if hasattr(part.function_call, 'args') else {}
#             f.write(f"  → Calling Tool: {part.function_call.name}\n")
#             f.write(f"    Arguments: {json.dumps(args_dict, indent=4, ensure_ascii=False)}\n")
            
#           elif part.function_response:
#             response_data = part.function_response.response if hasattr(part.function_response, 'response') else 'no response'
#             f.write(f"  ← Tool Response: {part.function_response.name}\n")
#             if isinstance(response_data, (dict, list)):
#               f.write(f"    Result: {json.dumps(response_data, indent=4, ensure_ascii=False)}\n")
#             else:
#               f.write(f"    Result: {str(response_data)}\n")
            
#           elif part.text:
#             # Split long text into readable chunks
#             text_content = part.text.strip()
#             if len(text_content) > 200:
#               f.write(f"  Message: {text_content[:200]}...\n")
#               f.write(f"  [Full message length: {len(text_content)} characters]\n")
#             else:
#               f.write(f"  Message: {text_content}\n")
            
#           elif part.inline_data:
#             f.write(f"  📎 Attachment: {part.inline_data.mime_type if hasattr(part.inline_data, 'mime_type') else 'unknown type'}\n")
#             f.write(f"    Size: {len(str(part.inline_data.data)) if hasattr(part.inline_data, 'data') else 'unknown'} bytes\n")
      
#       f.write(f"\n{'='*100}\n\n")
      
#   except Exception as e:
#     logger.warning(f"Failed to log chat history to file: {e}")


class Gemini(BaseLlm):
  """Integration for Gemini models.

  Attributes:
    model: The name of the Gemini model.
  """

  model: str = 'gemini-1.5-flash'

  @staticmethod
  @override
  def supported_models() -> list[str]:
    """Provides the list of supported models.

    Returns:
      A list of supported models.
    """

    return [
        r'gemini-.*',
        # fine-tuned vertex endpoint pattern
        r'projects\/.+\/locations\/.+\/endpoints\/.+',
        # vertex gemini long name
        r'projects\/.+\/locations\/.+\/publishers\/google\/models\/gemini.+',
    ]

  async def generate_content_async(
      self, llm_request: LlmRequest, stream: bool = False
  ) -> AsyncGenerator[LlmResponse, None]:
    """Sends a request to the Gemini model.

    Args:
      llm_request: LlmRequest, the request to send to the Gemini model.
      stream: bool = False, whether to do streaming call.

    Yields:
      LlmResponse: The model response.
    """

    self._maybe_append_user_content(llm_request)
    
    # Log chat history to file for debugging
    # _log_chat_history_to_file(llm_request, "Google LLM")
    
    logger.info(
        'Sending out request, model: %s, backend: %s, stream: %s',
        llm_request.model,
        self._api_backend,
        stream,
    )
    logger.info(_build_request_log(llm_request))

    if stream:
      responses = await self.api_client.aio.models.generate_content_stream(
          model=llm_request.model,
          contents=llm_request.contents,
          config=llm_request.config,
      )
      response = None
      text = ''
      # for sse, similar as bidi (see receive method in gemini_llm_connecton.py),
      # we need to mark those text content as partial and after all partial
      # contents are sent, we send an accumulated event which contains all the
      # previous partial content. The only difference is bidi rely on
      # complete_turn flag to detect end while sse depends on finish_reason.
      async for response in responses:
        logger.info(_build_response_log(response))
        llm_response = LlmResponse.create(response)
        if (
            llm_response.content
            and llm_response.content.parts
            and llm_response.content.parts[0].text
        ):
          text += llm_response.content.parts[0].text
          llm_response.partial = True
        elif text and (
            not llm_response.content
            or not llm_response.content.parts
            # don't yield the merged text event when receiving audio data
            or not llm_response.content.parts[0].inline_data
        ):
          yield LlmResponse(
              content=types.ModelContent(
                  parts=[types.Part.from_text(text=text)],
              ),
          )
          text = ''
        yield llm_response
      if (
          text
          and response
          and response.candidates
          and response.candidates[0].finish_reason == types.FinishReason.STOP
      ):
        yield LlmResponse(
            content=types.ModelContent(
                parts=[types.Part.from_text(text=text)],
            ),
        )

    else:
      response = await self.api_client.aio.models.generate_content(
          model=llm_request.model,
          contents=llm_request.contents,
          config=llm_request.config,
      )
      logger.info(_build_response_log(response))
      yield LlmResponse.create(response)

  @cached_property
  def api_client(self) -> Client:
    """Provides the api client.

    Returns:
      The api client.
    """
    return Client(
        http_options=types.HttpOptions(headers=self._tracking_headers)
    )

  @cached_property
  def _api_backend(self) -> str:
    return 'vertex' if self.api_client.vertexai else 'ml_dev'

  @cached_property
  def _tracking_headers(self) -> dict[str, str]:
    framework_label = f'google-adk/{version.__version__}'
    language_label = 'gl-python/' + sys.version.split()[0]
    version_header_value = f'{framework_label} {language_label}'
    tracking_headers = {
        'x-goog-api-client': version_header_value,
        'user-agent': version_header_value,
    }
    return tracking_headers

  @cached_property
  def _live_api_client(self) -> Client:
    if self._api_backend == 'vertex':
      # use default api version for vertex
      return Client(
          http_options=types.HttpOptions(headers=self._tracking_headers)
      )
    else:
      # use v1alpha for ml_dev
      api_version = 'v1alpha'
      return Client(
          http_options=types.HttpOptions(
              headers=self._tracking_headers, api_version=api_version
          )
      )

  @contextlib.asynccontextmanager
  async def connect(self, llm_request: LlmRequest) -> BaseLlmConnection:
    """Connects to the Gemini model and returns an llm connection.

    Args:
      llm_request: LlmRequest, the request to send to the Gemini model.

    Yields:
      BaseLlmConnection, the connection to the Gemini model.
    """

    llm_request.live_connect_config.system_instruction = types.Content(
        role='system',
        parts=[
            types.Part.from_text(text=llm_request.config.system_instruction)
        ],
    )
    llm_request.live_connect_config.tools = llm_request.config.tools
    async with self._live_api_client.aio.live.connect(
        model=llm_request.model, config=llm_request.live_connect_config
    ) as live_session:
      yield GeminiLlmConnection(live_session)

  def _maybe_append_user_content(self, llm_request: LlmRequest):
    """Appends a user content, so that model can continue to output.

    Args:
      llm_request: LlmRequest, the request to send to the Gemini model.
    """
    # If no content is provided, append a user content to hint model response
    # using system instruction.
    if not llm_request.contents:
      llm_request.contents.append(
          types.Content(
              role='user',
              parts=[
                  types.Part(
                      text=(
                          'Handle the requests as specified in the System'
                          ' Instruction.'
                      )
                  )
              ],
          )
      )
      return

    # COMPREHENSIVE FIX: Validate and fix entire conversation history for proper turn sequences
    # Google Gemini requires strict turn ordering:
    # 1. Function calls can only come after user turns or function response turns
    # 2. No consecutive user turns or consecutive model turns (without function calls/responses)
    # 3. Function responses must come from user role
    
    self._validate_and_fix_conversation_turns(llm_request)

  def _validate_and_fix_conversation_turns(self, llm_request: LlmRequest):
    """Validates and fixes conversation turn sequence for Google Gemini API compatibility.
    
    This ensures:
    1. No consecutive user turns
    2. No consecutive model turns (text only) 
    3. Function calls only after user/function_response turns
    4. Function responses are properly attributed to user role
    
    Args:
      llm_request: The LLM request to validate and fix
    """
    contents = llm_request.contents
    if not contents:
      return
      
    # logger.info("=== CONVERSATION TURN VALIDATION START ===")
    
    # Log original conversation for debugging
    # for i, content in enumerate(contents):
    #   role = content.role
    #   has_text = any(part.text for part in content.parts if part.text)
    #   has_function_call = any(part.function_call for part in content.parts)
    #   has_function_response = any(part.function_response for part in content.parts)
    #   logger.info(f"  Original[{i}]: {role} - text:{has_text}, fn_call:{has_function_call}, fn_resp:{has_function_response}")
    
    fixed_contents = []
    i = 0
    
    while i < len(contents):
      current = contents[i]
      
      # Ensure function responses are attributed to user role
      if any(part.function_response for part in current.parts):
        current.role = 'user'
      
      # Check for consecutive user turns
      if (fixed_contents and 
          fixed_contents[-1].role == 'user' and 
          current.role == 'user' and
          not any(part.function_response for part in current.parts)):
        
        # Merge consecutive user turns to avoid API rejection
        logger.warning(f"Merging consecutive user turns at positions {len(fixed_contents)-1} and {i}")
        
        # Combine the text from both user turns
        combined_parts = list(fixed_contents[-1].parts)
        for part in current.parts:
          if part.text:
            combined_parts.append(types.Part(text=f" {part.text}"))
          else:
            combined_parts.append(part)
        
        fixed_contents[-1].parts = combined_parts
        i += 1
        continue
      
      # Check for consecutive model turns with text only (no function calls)
      if (fixed_contents and 
          fixed_contents[-1].role == 'model' and 
          current.role == 'model' and
          not any(part.function_call for part in fixed_contents[-1].parts) and
          not any(part.function_call for part in current.parts) and
          any(part.text for part in fixed_contents[-1].parts) and
          any(part.text for part in current.parts)):
        
        # Insert a user turn between consecutive model text turns
        logger.warning(f"Inserting user turn between consecutive model turns at positions {len(fixed_contents)-1} and {i}")
        
        bridge_user_turn = types.Content(
          role='user',
          parts=[types.Part(text="Continue.")]
        )
        fixed_contents.append(bridge_user_turn)
      
      # Check if current turn is a model turn with function calls
      # and ensure it comes after user or function response turn
      if (current.role == 'model' and 
          any(part.function_call for part in current.parts)):
        
        if not fixed_contents:
          # First turn is model with function call - add user turn first
          logger.warning("Adding user turn before initial model function call")
          user_turn = types.Content(
            role='user', 
            parts=[types.Part(text="Please process this request using available tools.")]
          )
          fixed_contents.append(user_turn)
          
        elif (fixed_contents[-1].role == 'model' and
              not any(part.function_call for part in fixed_contents[-1].parts) and
              not any(part.function_response for part in fixed_contents[-1].parts)):
          
          # Previous turn was model with text only, need user turn before function call
          logger.warning(f"Adding user turn before model function call at position {i}")
          user_turn = types.Content(
            role='user',
            parts=[types.Part(text="Continue processing the request. Use available tools if needed.")]
          )
          fixed_contents.append(user_turn)
      
      fixed_contents.append(current)
      i += 1
    
    # Final validation: ensure conversation ends appropriately for function calling
    if fixed_contents:
      last_content = fixed_contents[-1]
      
      # If last content is function response, we're good - model can make function calls
      if (last_content.role == 'user' and 
          any(part.function_response for part in last_content.parts)):
        pass  # Perfect for function calls
        
      # If last content is user text, check if we need to enable function calls
      elif last_content.role == 'user':
        # Check if conversation has function activity
        has_function_activity = any(
          content.parts and any(
            part.function_call or part.function_response for part in content.parts
          ) for content in fixed_contents
        )
        
        if has_function_activity:
          # Add enabling text if not already present
          current_user_text = ' '.join(part.text or '' for part in last_content.parts if part.text)
          if ('Continue processing' not in current_user_text and 
              'Use available tools' not in current_user_text and
              'available tools' not in current_user_text.lower()):
            last_content.parts.append(
              types.Part(text=" Continue processing the request. Use available tools if needed.")
            )
            
      # If last content is model text, add user turn to enable function calls
      elif (last_content.role == 'model' and
            any(part.text for part in last_content.parts) and
            not any(part.function_call for part in last_content.parts)):
        
        has_function_activity = any(
          content.parts and any(
            part.function_call or part.function_response for part in content.parts
          ) for content in fixed_contents
        )
        
        user_message = (
          'Continue processing the request. Use available tools if needed.' 
          if has_function_activity else
          'Continue processing previous requests as instructed.'
        )
        
        fixed_contents.append(
          types.Content(
            role='user',
            parts=[types.Part(text=user_message)]
          )
        )
        logger.info("Added final user turn to enable function calls")
    
    # Update the request with fixed contents
    llm_request.contents = fixed_contents
    
    # Log final conversation for debugging
    logger.info("=== FINAL FIXED CONVERSATION ===")
    for i, content in enumerate(fixed_contents):
      role = content.role
      has_text = any(part.text for part in content.parts if part.text)
      has_function_call = any(part.function_call for part in content.parts)
      has_function_response = any(part.function_response for part in content.parts)
      logger.info(f"  Fixed[{i}]: {role} - text:{has_text}, fn_call:{has_function_call}, fn_resp:{has_function_response}")
    
    logger.info("=== CONVERSATION TURN VALIDATION END ===")


def _build_function_declaration_log(
    func_decl: types.FunctionDeclaration,
) -> str:
  param_str = '{}'
  if func_decl.parameters and func_decl.parameters.properties:
    param_str = str({
        k: v.model_dump(exclude_none=True)
        for k, v in func_decl.parameters.properties.items()
    })
  return_str = 'None'
  if func_decl.response:
    return_str = str(func_decl.response.model_dump(exclude_none=True))
  return f'{func_decl.name}: {param_str} -> {return_str}'


def _build_request_log(req: LlmRequest) -> str:
  function_decls: list[types.FunctionDeclaration] = cast(
      list[types.FunctionDeclaration],
      req.config.tools[0].function_declarations if req.config.tools else [],
  )
  function_logs = (
      [
          _build_function_declaration_log(func_decl)
          for func_decl in function_decls
      ]
      if function_decls
      else []
  )
  contents_logs = [
      content.model_dump_json(
          exclude_none=True,
          exclude={
              'parts': {
                  i: _EXCLUDED_PART_FIELD for i in range(len(content.parts))
              }
          },
      )
      for content in req.contents
  ]

  return ""


def _build_response_log(resp: types.GenerateContentResponse) -> str:
  function_calls_text = []
  if function_calls := resp.function_calls:
    for func_call in function_calls:
      # Enhanced logging with argument details for debugging
      args_dict = dict(func_call.args) if hasattr(func_call, 'args') else {}
      function_calls_text.append(
          f'FUNCTION_CALL: {func_call.name}({args_dict})'
      )
  return f"""
=== LLM RESPONSE DEBUG ===
Text Response:
{resp.text if resp.text else '(no text)'}
-----------------------------------------------------------
Function Calls:
{_NEW_LINE.join(function_calls_text) if function_calls_text else '(no function calls)'}
-----------------------------------------------------------
Raw Response JSON:
{resp.model_dump_json(exclude_none=True)}
=== END LLM RESPONSE DEBUG ===
"""
