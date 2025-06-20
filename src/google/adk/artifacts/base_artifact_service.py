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


from abc import ABC
from abc import abstractmethod
from typing import Optional
from datetime import datetime

from google.genai import types


class BaseArtifactService(ABC):
  """Abstract base class for artifact services."""

  @abstractmethod
  def save_artifact(
      self,
      *,
      org_id: str,
      team_id: str,
      session_id: str,
      filename: str,
      artifact_id: str,
      timestamp: datetime,
      file_type: str,
      file_size: int,
      agent_id: str,
      agent_name: str
  ) -> None:
    """Saves an artifact to the artifact service storage.

    The artifact is a file identified by the organization ID, team ID, session ID,
    and filename.

    Args:
      org_id: The organization ID.
      team_id: The team ID.
      session_id: The session ID.
      filename: The filename of the artifact.
      artifact_id: The unique ID for this artifact instance.
      timestamp: The timestamp of the artifact creation or saving.
      file_type: The type of the file (e.g., 'image/png', 'text/plain').
      file_size: The size of the file.
      agent_id: The ID of the agent.
      agent_name: The name of the agent.
    Returns:
      None.
    """


  @abstractmethod
  def delete_artifact(
      self, *, org_id: str, team_id: str, session_id: str, filename: str
  ) -> None:
    """Deletes an artifact.

    Args:
        app_name: The name of the application.
        user_id: The ID of the user.
        session_id: The ID of the session.
        filename: The name of the artifact file.
    """
    pass

