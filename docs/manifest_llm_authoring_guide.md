# Frontier LLM Authoring Guide

## Purpose

This guide is written so a frontier LLM can generate or revise manifests without inventing unsupported runtime behavior.

## When generating a manifest

1. Do not invent tools.
2. Use only commands listed in the command reference or existing tool registry.
3. Every required input must appear in `inputs`.
4. Every produced value must have an output alias.
5. Later steps must reference prior outputs through `$outputs`.
6. Add validations for required business facts.
7. Add completion rules that match the intended final state.
8. Side effects must be staged and approval-gated.
9. Failed validation must stop safely.
10. Do not rely on chat history. The TaskFrame outputs are the data pipe.

## Required output format for LLM-generated manifest

Return only:

1. Manifest JSON
2. Test input JSON
3. Expected outcome summary
4. Workbench test checklist

## LLM build procedure

1. Identify task type.
2. Identify trigger.
3. Define required inputs.
4. Select allowed tools or LLM micro-actions.
5. Build step sequence.
6. Add validations.
7. Add completion rules.
8. Check side-effect policy.
9. Produce test input JSON.
10. Predict expected Workbench result.

## LLM self-check checklist

- Is every command valid?
- Does every output alias exist before it is referenced?
- Are required inputs complete?
- Does every side effect require approval?
- Can failed lookup or validation stop safely?
- Does completion require the right output or pending action?
- Can this run in dry-run mode?
- Is the manifest specific enough for the runtime and not relying on model judgment?
