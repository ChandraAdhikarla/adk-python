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


import base64
import json
import logging
from typing import Any
from typing import AsyncGenerator
from typing import cast
from typing import Dict
from typing import Generator
from typing import Iterable
from typing import Literal
from typing import Optional
from typing import Tuple
from typing import Union

from google.genai import types
from litellm import acompletion
from litellm import ChatCompletionAssistantMessage
from litellm import ChatCompletionDeveloperMessage
from litellm import ChatCompletionImageUrlObject
from litellm import ChatCompletionMessageToolCall
from litellm import ChatCompletionTextObject
from litellm import ChatCompletionToolMessage
from litellm import ChatCompletionUserMessage
from litellm import ChatCompletionVideoUrlObject
from litellm import completion
from litellm import CustomStreamWrapper
from litellm import Function
from litellm import Message
from litellm import ModelResponse
from litellm import OpenAIMessageContent
from pydantic import BaseModel
from pydantic import Field
from typing_extensions import override

from .base_llm import BaseLlm
from .llm_request import LlmRequest
from .llm_response import LlmResponse

logger = logging.getLogger(__name__)

_NEW_LINE = "\n"
_EXCLUDED_PART_FIELD = {"inline_data": {"data"}}


class FunctionChunk(BaseModel):
  id: Optional[str]
  name: Optional[str]
  args: Optional[str]


class TextChunk(BaseModel):
  text: str


class LiteLLMClient:
  """Provides acompletion method (for better testability)."""

  async def acompletion(
      self, model, messages, tools, **kwargs
  ) -> Union[ModelResponse, CustomStreamWrapper]:
    """Asynchronously calls acompletion.

    Args:
      model: The model name.
      messages: The messages to send to the model.
      tools: The tools to use for the model.
      **kwargs: Additional arguments to pass to acompletion.

    Returns:
      The model response as a message.
    """

    return await acompletion(
        model=model,
        messages=messages,
        tools=tools,
        **kwargs,
    )

  def completion(
      self, model, messages, tools, stream=False, **kwargs
  ) -> Union[ModelResponse, CustomStreamWrapper]:
    """Synchronously calls completion. This is used for streaming only.

    Args:
      model: The model to use.
      messages: The messages to send.
      tools: The tools to use for the model.
      stream: Whether to stream the response.
      **kwargs: Additional arguments to pass to completion.

    Returns:
      The response from the model.
    """

    return completion(
        model=model,
        messages=messages,
        tools=tools,
        stream=stream,
        **kwargs,
    )


def _safe_json_serialize(obj) -> str:
  """Convert any Python object to a JSON-serializable type or string.

  Args:
    obj: The object to serialize.

  Returns:
    The JSON-serialized object string or string.
  """

  try:
    # Try direct JSON serialization first
    return json.dumps(obj)
  except (TypeError, OverflowError):
    return str(obj)


def _content_to_message_param(
    content: types.Content,
) -> Union[Message, list[Message]]:
  """Converts a types.Content to a litellm Message or list of Messages.

  Handles multipart function responses by returning a list of
  ChatCompletionToolMessage objects if multiple function_response parts exist.

  Args:
    content: The content to convert.

  Returns:
    A litellm Message, a list of litellm Messages.
  """

  tool_messages = []
  for part in content.parts:
    if part.function_response:
      tool_messages.append(
          ChatCompletionToolMessage(
              role="tool",
              tool_call_id=part.function_response.id,
              content=_safe_json_serialize(part.function_response.response),
          )
      )
  if tool_messages:
    return tool_messages if len(tool_messages) > 1 else tool_messages[0]

  # Handle user or assistant messages
  role = _to_litellm_role(content.role)
  message_content = _get_content(content.parts) or None

  if role == "user":
    return ChatCompletionUserMessage(role="user", content=message_content)
  else:  # assistant/model
    tool_calls = []
    content_present = False
    for part in content.parts:
        if part.function_call:
            tool_calls.append(
                ChatCompletionMessageToolCall(
                    type="function",
                    id=part.function_call.id,
                    function=Function(
                        name=part.function_call.name,
                        arguments=part.function_call.args,
                    ),
                )
            )
        elif part.text or part.inline_data:
            content_present = True

    final_content = message_content if content_present else None

    return ChatCompletionAssistantMessage(
        role=role,
        content=final_content,
        tool_calls=tool_calls or None,
    )


def _get_content(
    parts: Iterable[types.Part],
) -> Union[OpenAIMessageContent, str]:
  """Converts a list of parts to litellm content.

  Args:
    parts: The parts to convert.

  Returns:
    The litellm content.
  """

  content_objects = []
  for part in parts:
    if part.text:
      if len(parts) == 1:
        return part.text
      content_objects.append(
          ChatCompletionTextObject(
              type="text",
              text=part.text,
          )
      )
    elif (
        part.inline_data
        and part.inline_data.data
        and part.inline_data.mime_type
    ):
      base64_string = base64.b64encode(part.inline_data.data).decode("utf-8")
      data_uri = f"data:{part.inline_data.mime_type};base64,{base64_string}"

      if part.inline_data.mime_type.startswith("image"):
        content_objects.append(
            ChatCompletionImageUrlObject(
                type="image_url",
                image_url=data_uri,
            )
        )
      elif part.inline_data.mime_type.startswith("video"):
        content_objects.append(
            ChatCompletionVideoUrlObject(
                type="video_url",
                video_url=data_uri,
            )
        )
      else:
        raise ValueError("LiteLlm(BaseLlm) does not support this content part.")

  return content_objects


def _to_litellm_role(role: Optional[str]) -> Literal["user", "assistant"]:
  """Converts a types.Content role to a litellm role.

  Args:
    role: The types.Content role.

  Returns:
    The litellm role.
  """

  if role in ["model", "assistant"]:
    return "assistant"
  return "user"


TYPE_LABELS = {
    "STRING": "string",
    "NUMBER": "number",
    "BOOLEAN": "boolean",
    "OBJECT": "object",
    "ARRAY": "array",
    "INTEGER": "integer",
}


def _schema_to_dict(schema: types.Schema) -> dict:
  """Recursively converts a types.Schema to a dictionary.

  Args:
    schema: The schema to convert.

  Returns:
    The dictionary representation of the schema.
  """

  schema_dict = schema.model_dump(exclude_none=True)
  if "type" in schema_dict:
    schema_dict["type"] = schema_dict["type"].lower()
  if "items" in schema_dict:
    if isinstance(schema_dict["items"], dict):
      schema_dict["items"] = _schema_to_dict(
          types.Schema.model_validate(schema_dict["items"])
      )
    elif isinstance(schema_dict["items"]["type"], types.Type):
      schema_dict["items"]["type"] = TYPE_LABELS[
          schema_dict["items"]["type"].value
      ]
  if "properties" in schema_dict:
    properties = {}
    for key, value in schema_dict["properties"].items():
      if isinstance(value, types.Schema):
        properties[key] = _schema_to_dict(value)
      else:
        properties[key] = value
        if "type" in properties[key]:
          properties[key]["type"] = properties[key]["type"].lower()
    schema_dict["properties"] = properties
  return schema_dict


def _function_declaration_to_tool_param(
    function_declaration: types.FunctionDeclaration,
) -> dict:
  """Converts a types.FunctionDeclaration to a openapi spec dictionary.

  Args:
    function_declaration: The function declaration to convert.

  Returns:
    The openapi spec dictionary representation of the function declaration.
  """

  assert function_declaration.name

  properties = {}
  if (
      function_declaration.parameters
      and function_declaration.parameters.properties
  ):
    for key, value in function_declaration.parameters.properties.items():
      properties[key] = _schema_to_dict(value)

  return {
      "type": "function",
      "function": {
          "name": function_declaration.name,
          "description": function_declaration.description or "",
          "parameters": {
              "type": "object",
              "properties": properties,
          },
      },
  }


def _model_response_to_chunk(
    response: ModelResponse,
) -> Generator[
    Tuple[Optional[Union[TextChunk, FunctionChunk]], Optional[str]], None, None
]:
  """Converts a litellm message to text or function chunk.

  Args:
    response: The response from the model.

  Yields:
    A tuple of text or function chunk and finish reason.
  """

  message = None
  if response.get("choices", None):
    message = response["choices"][0].get("message", None)
    finish_reason = response["choices"][0].get("finish_reason", None)
    # check streaming delta
    if message is None and response["choices"][0].get("delta", None):
      message = response["choices"][0]["delta"]

    if message.get("content", None):
      yield TextChunk(text=message.get("content")), finish_reason

    if message.get("tool_calls", None):
      for tool_call in message.get("tool_calls"):
        # aggregate tool_call
        if tool_call.type == "function":
          yield FunctionChunk(
              id=tool_call.id,
              name=tool_call.function.name,
              args=tool_call.function.arguments,
          ), finish_reason

    if finish_reason and not (
        message.get("content", None) or message.get("tool_calls", None)
    ):
      yield None, finish_reason

  if not message:
    yield None, None


def _model_response_to_generate_content_response(
    response: ModelResponse, declared_tool_names: Optional[list[str]] = None
) -> LlmResponse:
  """Converts a litellm response to LlmResponse.

  Args:
    response: The model response.
    declared_tool_names: A list of declared tool names for the current LLM call.

  Returns:
    The LlmResponse.
  """

  message = None
  if response.get("choices", None):
    message = response["choices"][0].get("message", None)

  if not message:
    raise ValueError("No message in response")
  return _message_to_generate_content_response(
      message, declared_tool_names=declared_tool_names
  )


def _deduce_function_names_from_concatenation(
    mangled_name: str,
    arg_count: int,
    known_tool_names: Optional[list[str]],
) -> list[str]:
  """Attempts to deduce individual function names from a concatenated string.

  Args:
    mangled_name: The concatenated string of function names.
    arg_count: The expected number of function names (should match arg sets).
    known_tool_names: A list of valid tool names.

  Returns:
    A list of deduced function names. If deduction fails or is partial,
    it returns a list of [mangled_name] * arg_count.
  """
  if not known_tool_names or not mangled_name:
    return [mangled_name] * arg_count

  deduced_names = []
  remaining_mangled_name = mangled_name
  # Sort known_tool_names by length descending to match longest possible names first
  sorted_known_tool_names = sorted(known_tool_names, key=len, reverse=True)

  for i in range(arg_count):
    found_match_for_segment = False
    for tool_name in sorted_known_tool_names:
      if remaining_mangled_name.startswith(tool_name):
        # Check if this is the last segment and if it consumes the rest of the string,
        # or if there are more segments to find.
        if i == arg_count - 1: # Last segment
          if remaining_mangled_name == tool_name: # Exact match for the remainder
            deduced_names.append(tool_name)
            remaining_mangled_name = ""
            found_match_for_segment = True
            break
          # else: it starts with tool_name but there's more, not a clean match for last segment
        else: # Not the last segment
          deduced_names.append(tool_name)
          remaining_mangled_name = remaining_mangled_name[len(tool_name) :]
          found_match_for_segment = True
          break # Move to the next segment of the mangled name
    
    if not found_match_for_segment:
      # If any segment cannot be matched, the overall deduction is considered failed.
      logger.warning(
          f"Failed to deduce function name for segment {i+1} from '{mangled_name}'. "
          f"Remaining part: '{remaining_mangled_name}'. Deduced so far: {deduced_names}."
      )
      return [mangled_name] * arg_count # Fallback to original mangled name for all parts

  # Final check: all segments deduced and the entire mangled string is consumed.
  if len(deduced_names) == arg_count and not remaining_mangled_name.strip():
    logger.info(f"Successfully deduced function names: {deduced_names} from '{mangled_name}'.")
    return deduced_names
  else:
    logger.warning(
        f"Could not fully segment mangled name '{mangled_name}' into {arg_count} known tool names. "
        f"Deduced: {deduced_names}. Remainder: '{remaining_mangled_name}'."
    )
    return [mangled_name] * arg_count


def _try_parse_concatenated_json(json_str: str) -> list[Any]:
  """Attempts to parse a string that might contain one or more JSON objects concatenated.

  Args:
    json_str: The string to parse.

  Returns:
    A list of parsed JSON objects. Returns an empty list if parsing fails early
    or a list with one item if it's a single valid JSON.
  """
  results = []
  decoder = json.JSONDecoder()
  idx = 0
  s = json_str.strip() # Remove leading/trailing whitespace from the whole string

  while idx < len(s):
    try:
      # Skip any leading whitespace for the current object
      current_char_idx = idx
      while current_char_idx < len(s) and s[current_char_idx].isspace():
        current_char_idx +=1
      if current_char_idx == len(s): # Only whitespace remaining
          break

      obj, end_idx = decoder.raw_decode(s, current_char_idx)
      results.append(obj)
      idx = end_idx
    except json.JSONDecodeError:
      # If we've already parsed at least one object, and the rest is invalid,
      # return what we have. Otherwise, this indicates the string itself is not
      # starting with a valid JSON or is malformed in a way we can't split.
      if not results:
          # This means the very first attempt to decode failed.
          # Re-raise to be caught by the caller's original try-except.
          raise
      # If there was an error after parsing at least one object,
      # it means the remaining part is not valid JSON. Stop and return current results.
      logger.warning(
          f"Partial success in parsing concatenated JSON. Parsed {len(results)} objects. "
          f"Remaining unparsable content: >>>{s[idx:]}<<<"
      )
      break
  return results


def _message_to_generate_content_response(
    message: Message,
    is_partial: bool = False,
    declared_tool_names: Optional[list[str]] = None,
) -> LlmResponse:
  """Converts a litellm message to LlmResponse.

  Args:
    message: The message to convert.
    is_partial: Whether the message is partial.
    declared_tool_names: A list of declared tool names for the current LLM call.

  Returns:
    The LlmResponse.
  """

  parts = []
  if message.get("content", None):
    parts.append(types.Part.from_text(text=message.get("content")))

  if message.get("tool_calls", None):
    for tool_call in message.get("tool_calls"):
      if tool_call.type == "function":
        original_function_name = tool_call.function.name
        arguments_str = tool_call.function.arguments or "{}"
        tool_call_id_str = tool_call.id
        
        parsed_arg_list = []
        try:
          # Attempt to parse as one or more concatenated JSON objects
          parsed_arg_list = _try_parse_concatenated_json(arguments_str)
          if not parsed_arg_list and arguments_str != "{}": # If empty list and not empty string, means it failed initial parse
              # This case should be caught by the JSONDecodeError in _try_parse_concatenated_json
              # and re-raised if arguments_str was not parseable at all.
              # If arguments_str was "{}", parsed_arg_list would be [{}] by json.loads or empty by our parser (if {} is invalid alone)
              # Let's ensure that an empty arguments_str ("{}") results in a single empty dict.
              if arguments_str == "{}":
                  parsed_arg_list = [{}] # Treat "{}" as a single empty JSON object
              else: # Should have been a JSONDecodeError from _try_parse_concatenated_json
                  raise json.JSONDecodeError("Failed to parse arguments", arguments_str, 0)


        except json.JSONDecodeError as e:
          logger.error(
              "Failed to decode JSON from tool_call.function.arguments. "
              f"Content was: >>>{arguments_str}<<<"
          )
          logger.error(
              f"Error for tool_call_id='{tool_call_id_str}', function_name='{original_function_name}'. Exception: {e}"
          )
          raise # Re-raise the original error if parsing completely fails

        if not parsed_arg_list: # e.g. arguments_str was empty or "{}" which resolved to [{}] and then maybe not.
             # This case handles if arguments_str was truly empty or just "{}".
             # An empty string for arguments is not valid JSON. "{}" is.
            if arguments_str.strip() == "": # Truly empty, not even "{}"
                logger.warning(f"Empty arguments string for tool_call_id='{tool_call_id_str}', function_name='{original_function_name}'. Using empty dict.")
                parsed_arg_list = [{}] 
            elif arguments_str.strip() == "{}":
                 parsed_arg_list = [{}]


        if len(parsed_arg_list) == 1:
          # Standard case: one function call, one set of arguments
          part = types.Part.from_function_call(
              name=original_function_name,
              args=parsed_arg_list[0],
          )
          part.function_call.id = tool_call_id_str
          parts.append(part)
        elif len(parsed_arg_list) > 1:
          logger.warning(
              f"Detected {len(parsed_arg_list)} argument sets in a single tool call "
              f"(id='{tool_call_id_str}', name='{original_function_name}'). "
              "Splitting into multiple tool calls."
          )
          
          # Attempt to deduce function names using the new logic
          function_names_to_use = _deduce_function_names_from_concatenation(
              original_function_name, len(parsed_arg_list), declared_tool_names
          )

          for i, arg_set in enumerate(parsed_arg_list):
            part = types.Part.from_function_call(
                name=function_names_to_use[i], # Use deduced or original name
                args=arg_set,
            )
            part.function_call.id = f"{tool_call_id_str}_{i+1}"
            parts.append(part)
        # If parsed_arg_list is empty (e.g. from "{}"), and it was not an error condition.
        # This case should be handled by the initial check for arguments_str == "{}" becoming [{}]
        # or an empty string becoming [{}] with a warning.
        # If it's still empty here, it implies an unhandled edge case or non-JSON "{}" (which is unlikely).
        elif not parsed_arg_list and arguments_str.strip() == "{}": #Specifically for "{}" that became empty list
             part = types.Part.from_function_call(
                name=original_function_name,
                args={},)
             part.function_call.id = tool_call_id_str
             parts.append(part)


  return LlmResponse(
      content=types.Content(role="model", parts=parts), partial=is_partial
  )


def _get_completion_inputs(
    llm_request: LlmRequest,
) -> tuple[Iterable[Message], Iterable[dict]]:
  """Converts an LlmRequest to litellm inputs.

  Args:
    llm_request: The LlmRequest to convert.

  Returns:
    The litellm inputs (message list and tool dictionary).
  """
  messages = []
  for content in llm_request.contents or []:
    message_param_or_list = _content_to_message_param(content)
    if isinstance(message_param_or_list, list):
        messages.extend(message_param_or_list)
    elif message_param_or_list: # Ensure it's not None before appending
        messages.append(message_param_or_list)

  if llm_request.config.system_instruction:
    messages.insert(
        0,
        ChatCompletionDeveloperMessage(
            role="developer",
            content=llm_request.config.system_instruction,
        ),
    )

  tools = None
  if (
      llm_request.config
      and llm_request.config.tools
      and llm_request.config.tools[0].function_declarations
  ):
    tools = [
        _function_declaration_to_tool_param(tool)
        for tool in llm_request.config.tools[0].function_declarations
    ]
  return messages, tools


def _build_function_declaration_log(
    func_decl: types.FunctionDeclaration,
) -> str:
  """Builds a function declaration log.

  Args:
    func_decl: The function declaration to convert.

  Returns:
    The function declaration log.
  """

  param_str = "{}"
  if func_decl.parameters and func_decl.parameters.properties:
    param_str = str({
        k: v.model_dump(exclude_none=True)
        for k, v in func_decl.parameters.properties.items()
    })
  return_str = "None"
  if func_decl.response:
    return_str = str(func_decl.response.model_dump(exclude_none=True))
  return f"{func_decl.name}: {param_str} -> {return_str}"


def _build_request_log(req: LlmRequest) -> str:
  """Builds a request log.

  Args:
    req: The request to convert.

  Returns:
    The request log.
  """

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
              "parts": {
                  i: _EXCLUDED_PART_FIELD for i in range(len(content.parts))
              }
          },
      )
      for content in req.contents
  ]

  return ""


class LiteLlm(BaseLlm):
  """Wrapper around litellm.

  This wrapper can be used with any of the models supported by litellm. The
  environment variable(s) needed for authenticating with the model endpoint must
  be set prior to instantiating this class.

  Example usage:
  ```
  os.environ["VERTEXAI_PROJECT"] = "your-gcp-project-id"
  os.environ["VERTEXAI_LOCATION"] = "your-gcp-location"

  agent = Agent(
      model=LiteLlm(model="vertex_ai/claude-3-7-sonnet@20250219"),
      ...
  )
  ```

  Attributes:
    model: The name of the LiteLlm model.
    llm_client: The LLM client to use for the model.
    model_config: The model config.
  """

  llm_client: LiteLLMClient = Field(default_factory=LiteLLMClient)
  """The LLM client to use for the model."""

  _additional_args: Dict[str, Any] = None

  def __init__(self, model: str, **kwargs):
    """Initializes the LiteLlm class.

    Args:
      model: The name of the LiteLlm model.
      **kwargs: Additional arguments to pass to the litellm completion api.
    """
    super().__init__(model=model, **kwargs)
    self._additional_args = kwargs
    # preventing generation call with llm_client
    # and overriding messages, tools and stream which are managed internally
    self._additional_args.pop("llm_client", None)
    self._additional_args.pop("messages", None)
    self._additional_args.pop("tools", None)
    # public api called from runner determines to stream or not
    self._additional_args.pop("stream", None)
    
    # Add a default timeout if not specified
    if "timeout" not in self._additional_args:
        self._additional_args["timeout"] = 300  # 5 minutes

  async def generate_content_async(
      self, llm_request: LlmRequest, stream: bool = False
  ) -> AsyncGenerator[LlmResponse, None]:
    """Generates content asynchronously.

    Args:
      llm_request: LlmRequest, the request to send to the LiteLlm model.
      stream: bool = False, whether to do streaming call.

    Yields:
      LlmResponse: The model response.
    """

    logger.info(_build_request_log(llm_request))

    messages, tools = _get_completion_inputs(llm_request)
    
    tool_declarations = (
        llm_request.config.tools[0].function_declarations
        if llm_request.config.tools
        and llm_request.config.tools[0].function_declarations
        else []
    )
    current_tool_names = [
        tool.name for tool in tool_declarations if tool.name
    ]


    completion_args = {
        "model": self.model,
        "messages": messages,
        "tools": tools,
    }
    completion_args.update(self._additional_args)

    if stream:
      text = ""
      function_name = ""
      function_args = ""
      function_id = None
      completion_args["stream"] = True
      for part in self.llm_client.completion(**completion_args):
        for chunk, finish_reason in _model_response_to_chunk(part):
          if isinstance(chunk, FunctionChunk):
            if chunk.name:
              function_name += chunk.name
            if chunk.args:
              function_args += chunk.args
            function_id = chunk.id or function_id
          elif isinstance(chunk, TextChunk):
            text += chunk.text
            yield _message_to_generate_content_response(
                ChatCompletionAssistantMessage(
                    role="assistant",
                    content=chunk.text,
                ),
                is_partial=True,
                declared_tool_names=current_tool_names,
            )
          if finish_reason == "tool_calls" and function_id:
            yield _message_to_generate_content_response(
                ChatCompletionAssistantMessage(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ChatCompletionMessageToolCall(
                            type="function",
                            id=function_id,
                            function=Function(
                                name=function_name,
                                arguments=function_args,
                            ),
                        )
                    ],
                ),
                declared_tool_names=current_tool_names,
            )
            function_name = ""
            function_args = ""
            function_id = None
          elif finish_reason == "stop" and text:
            yield _message_to_generate_content_response(
                ChatCompletionAssistantMessage(role="assistant", content=text),
                declared_tool_names=current_tool_names,
            )
            text = ""

    else:
      response = await self.llm_client.acompletion(**completion_args)
      yield _model_response_to_generate_content_response(
          response, declared_tool_names=current_tool_names
      )

  @staticmethod
  @override
  def supported_models() -> list[str]:
    """Provides the list of supported models.

    LiteLlm supports all models supported by litellm. We do not keep track of
    these models here. So we return an empty list.

    Returns:
      A list of supported models.
    """

    return []
