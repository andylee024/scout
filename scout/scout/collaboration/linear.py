"""Linear adapter for outbound curated-lead collaboration sync."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

DEFAULT_LINEAR_API_URL = "https://api.linear.app/graphql"

ISSUE_CREATE_MUTATION = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue {
      id
      identifier
      url
    }
  }
}
"""

ISSUE_UPDATE_MUTATION = """
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) {
    success
    issue {
      id
      identifier
      url
    }
  }
}
"""

GraphqlRequestFn = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]


class LinearAdapterError(RuntimeError):
    """Raised when the Linear API returns an unexpected or failed response."""


@dataclass(slots=True)
class LinearIssueRef:
    """Minimal issue reference returned from Linear create/update operations."""

    id: str
    identifier: str = ""
    url: str = ""


def _default_graphql_request(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise LinearAdapterError(f"Linear API HTTP error {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise LinearAdapterError(f"Linear API request failed: {exc.reason}") from exc

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LinearAdapterError("Linear API returned invalid JSON.") from exc
    if not isinstance(decoded, dict):
        raise LinearAdapterError("Linear API response must be a JSON object.")
    return decoded


class LinearAdapter:
    """Create/update issues in Linear for curated lead collaboration."""

    def __init__(
        self,
        *,
        api_key: str,
        team_id: str,
        api_url: str = DEFAULT_LINEAR_API_URL,
        request_fn: GraphqlRequestFn | None = None,
    ) -> None:
        self.api_key = api_key
        self.team_id = team_id
        self.api_url = api_url
        self.request_fn = request_fn or _default_graphql_request

    def create_issue(self, *, title: str, description: str) -> LinearIssueRef:
        data = self._execute(
            ISSUE_CREATE_MUTATION,
            {"input": {"teamId": self.team_id, "title": title, "description": description}},
        )
        payload = data.get("issueCreate")
        if not isinstance(payload, dict):
            raise LinearAdapterError("Linear create response missing `issueCreate`.")
        if payload.get("success") is not True:
            raise LinearAdapterError("Linear create response reported failure.")
        issue_payload = payload.get("issue")
        issue = self._parse_issue_ref(issue_payload)
        if issue is None:
            raise LinearAdapterError("Linear create response missing issue payload.")
        return issue

    def update_issue(self, *, issue_id: str, title: str, description: str) -> LinearIssueRef:
        data = self._execute(
            ISSUE_UPDATE_MUTATION,
            {"id": issue_id, "input": {"title": title, "description": description}},
        )
        payload = data.get("issueUpdate")
        if not isinstance(payload, dict):
            raise LinearAdapterError("Linear update response missing `issueUpdate`.")
        if payload.get("success") is not True:
            raise LinearAdapterError("Linear update response reported failure.")

        issue_payload = payload.get("issue")
        issue = self._parse_issue_ref(issue_payload)
        if issue is None:
            return LinearIssueRef(id=issue_id)
        if not issue.id:
            return LinearIssueRef(id=issue_id, identifier=issue.identifier, url=issue.url)
        return issue

    def _execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self.request_fn(
            self.api_url,
            {"query": query, "variables": variables},
            {"Authorization": self.api_key},
        )
        errors = response.get("errors")
        if errors:
            raise LinearAdapterError(f"Linear API returned GraphQL errors: {errors}")
        data = response.get("data")
        if not isinstance(data, dict):
            raise LinearAdapterError("Linear API response missing `data` payload.")
        return data

    @staticmethod
    def _parse_issue_ref(issue_payload: Any) -> LinearIssueRef | None:
        if not isinstance(issue_payload, dict):
            return None
        issue_id = issue_payload.get("id")
        if issue_id is None:
            issue_id = ""
        identifier = issue_payload.get("identifier")
        if identifier is None:
            identifier = ""
        url = issue_payload.get("url")
        if url is None:
            url = ""
        if not isinstance(issue_id, str) or not isinstance(identifier, str) or not isinstance(url, str):
            raise LinearAdapterError("Linear issue payload is invalid.")
        return LinearIssueRef(id=issue_id, identifier=identifier, url=url)
