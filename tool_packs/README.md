# Tool Packs

Tool packs are self-contained external tool bundles that can be discovered and enabled through configuration.

They are intentionally separate from the built-in registry so the core runtime does not need a code edit for every new tool.

Rules:

- keep each pack self-contained;
- declare tool safety explicitly;
- do not auto-enable optional/high-risk packs;
- do not bypass pending-action approval for side-effect tools;
- do not import browser or live integration dependencies from default runtime imports.

See `docs/toolpack_contract.md` and `docs/toolpack_authoring_guide.md` for the contract and authoring workflow.
