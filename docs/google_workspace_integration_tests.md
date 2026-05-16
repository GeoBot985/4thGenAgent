# Google Workspace Integration Tests

These tests are optional and only run when Google OAuth credentials are configured locally.

## Environment

```text
RUN_GOOGLE_WORKSPACE_INTEGRATION=1
GOOGLE_WORKSPACE_TEST_SPREADSHEET_ID=<spreadsheet-id>
GOOGLE_WORKSPACE_TEST_RANGE=Sheet1!A1:B5
```

## What they cover

- `google/auth_status`
- `gmail/list_unread`
- `calendar/list_upcoming`
- `sheets/read_range`

## Safety

The integration tests are read-only. They do not send mail, write sheets, or mutate calendar state.
