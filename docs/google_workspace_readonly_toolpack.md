# Google Workspace Read-Only Tool Pack

## Purpose

The Google Workspace tool pack provides optional, read-only Gmail, Calendar, and Sheets tools.
It is designed to be discoverable and inspectable without requiring Google credentials in a clean clone.

## Safety model

- no send, create, update, delete, move, archive, or write operations;
- no raw OAuth tokens in logs, reports, TaskFrames, or health output;
- live reads require explicit configuration and credentials;
- the live probe is manual and never runs during default validation;
- default demo paths remain unchanged.

## Health modes

The pack supports local readiness checks without live API calls by default.
Live verification is optional and only runs when explicitly requested.
Credentials are optional for clean-clone validation, but required for live reads.

## Example tools

- `google/auth_status`
- `gmail/list_unread`
- `gmail/search`
- `gmail/read_metadata`
- `calendar/search`
- `calendar/list_upcoming`
- `sheets/read_range`
