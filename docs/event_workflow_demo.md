# Event Workflow Demo

## Purpose
Shows event-driven TaskFrame execution using a demo customer message.

## Command
python scripts/run_event_demo.py

## Expected Result
Workflow ends at WAITING_FOR_EXECUTE with one pending send_customer_message action.

## What This Proves
- External event intake works.
- Event-to-manifest routing works.
- Event payload maps into TaskFrame inputs.
- Manifest execution works.
- Demo business lookup works.
- Draft reply generation works.
- Side effects are gated as pending actions.

## What This Does Not Do
- It does not send real messages.
- It does not use Gmail or WhatsApp.
- It does not use a real database.
- It does not use an LLM.
- It does not run a listener or webhook.
