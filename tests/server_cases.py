"""Expected schemas and call forwarding for every tool, used by test_server."""

# tool name -> (all properties, required properties)
SCHEMAS = {
    "list_configs": (set(), set()),
    "search_issues": (
        {"jql", "config_id", "limit", "next_page_token", "fields"},
        {"jql"},
    ),
    "get_issue": (
        {"issue_key", "config_id", "include_comments", "include_attachments"},
        {"issue_key"},
    ),
    "create_issue": (
        {
            "project_key",
            "summary",
            "issue_type",
            "description",
            "priority",
            "labels",
            "assignee_account_id",
            "config_id",
        },
        {"project_key", "summary"},
    ),
    "update_issue": (
        {
            "issue_key",
            "summary",
            "description",
            "priority",
            "labels",
            "assignee_account_id",
            "fields",
            "config_id",
        },
        {"issue_key"},
    ),
    "delete_issue": ({"issue_key", "delete_subtasks", "config_id"}, {"issue_key"}),
    "get_transitions": ({"issue_key", "config_id"}, {"issue_key"}),
    "transition_issue": (
        {"issue_key", "transition", "comment", "resolution", "fields", "config_id"},
        {"issue_key", "transition"},
    ),
    "add_comment": ({"issue_key", "body", "config_id"}, {"issue_key", "body"}),
    "download_attachment": (
        {"issue_key", "attachment_id", "output_dir", "config_id"},
        {"issue_key", "attachment_id"},
    ),
}

# (tool name, arguments, expected positional args, expected keyword args)
CALLS = [
    ("list_configs", {}, (), {}),
    (
        "search_issues",
        {
            "jql": "project = ONE",
            "config_id": "work",
            "limit": 10,
            "next_page_token": "tok",
            "fields": ["summary"],
        },
        ("project = ONE",),
        {
            "config_id": "work",
            "limit": 10,
            "next_page_token": "tok",
            "fields": ["summary"],
        },
    ),
    (
        "search_issues",
        {"jql": "project = ONE"},
        ("project = ONE",),
        {"config_id": None, "limit": 50, "next_page_token": None, "fields": None},
    ),
    (
        "get_issue",
        {"issue_key": "ONE-123", "config_id": "work", "include_comments": False},
        ("ONE-123",),
        {"config_id": "work", "include_comments": False, "include_attachments": True},
    ),
    (
        "create_issue",
        {
            "project_key": "ONE",
            "summary": "Title",
            "issue_type": "Bug",
            "description": "Body",
            "priority": "High",
            "labels": ["a"],
            "assignee_account_id": "acc",
            "config_id": "work",
        },
        ("ONE", "Title"),
        {
            "issue_type": "Bug",
            "description": "Body",
            "priority": "High",
            "labels": ["a"],
            "assignee_account_id": "acc",
            "config_id": "work",
        },
    ),
    (
        "update_issue",
        {
            "issue_key": "ONE-123",
            "summary": "Title",
            "description": "Body",
            "priority": "High",
            "labels": [],
            "assignee_account_id": "acc",
            "fields": {"duedate": None},
            "config_id": "work",
        },
        ("ONE-123",),
        {
            "summary": "Title",
            "description": "Body",
            "priority": "High",
            "labels": [],
            "assignee_account_id": "acc",
            "fields": {"duedate": None},
            "config_id": "work",
        },
    ),
    (
        "delete_issue",
        {"issue_key": "ONE-123", "delete_subtasks": True, "config_id": "work"},
        ("ONE-123",),
        {"delete_subtasks": True, "config_id": "work"},
    ),
    (
        "delete_issue",
        {"issue_key": "ONE-123"},
        ("ONE-123",),
        {"delete_subtasks": False, "config_id": None},
    ),
    (
        "get_transitions",
        {"issue_key": "ONE-123", "config_id": "work"},
        ("ONE-123",),
        {"config_id": "work"},
    ),
    (
        "transition_issue",
        {
            "issue_key": "ONE-123",
            "transition": "Done",
            "comment": "Completed yesterday",
            "resolution": "Fixed",
            "fields": {"customfield_1": "Done"},
            "config_id": "work",
        },
        ("ONE-123", "Done"),
        {
            "comment": "Completed yesterday",
            "resolution": "Fixed",
            "fields": {"customfield_1": "Done"},
            "config_id": "work",
        },
    ),
    (
        "add_comment",
        {"issue_key": "ONE-123", "body": "Comment", "config_id": "work"},
        ("ONE-123", "Comment"),
        {"config_id": "work"},
    ),
    (
        "download_attachment",
        {
            "issue_key": "ONE-123",
            "attachment_id": "42",
            "output_dir": "out",
            "config_id": "work",
        },
        ("ONE-123", "42"),
        {"output_dir": "out", "config_id": "work"},
    ),
]


READ_ONLY_TOOLS = {"list_configs", "search_issues", "get_issue", "get_transitions"}
DESTRUCTIVE_TOOLS = {"update_issue", "delete_issue"}
