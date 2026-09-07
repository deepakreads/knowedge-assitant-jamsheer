"""
Optimized, concise prompts for vision-based SOP generation.

Use these prompts instead of the verbose defaults for tighter, more actionable SOPs.
Each prompt is designed to produce concise output while maintaining clarity.
"""

# ============================================================================
# TIER 1: VISION FRAME ANALYSIS PROMPTS (vision_service.py)
# ============================================================================

VISION_SYSTEM_PROMPT_CONCISE = (
    "You are a manufacturing process analyst. Describe only observable actions, "
    "tools, and critical details. Be concise. Omit explanations."
)

VISION_USER_PROMPT_CONCISE = """Analyze this manufacturing frame. Answer ONLY these 3 questions:

1. WHAT ACTION: Single sentence. What is happening right now?
   Examples: "Operator positions part in fixture" or "Mold closes" or "Blade trims material"

2. TOOLS VISIBLE: Comma-separated list only.
   Examples: "wrench, clamp, height gauge" or "none"

3. KEY DETAILS: One sentence max. Any critical info?
   Examples: "Part aligned to centerline" or "Blade height 2mm" or "Pressure: 50 PSI" or "none"

Return ONLY this format (no JSON, no extra text):
ACTION: [single sentence]
TOOLS: [comma-separated or "none"]
DETAILS: [one sentence or "none"]"""

# ============================================================================
# TIER 2: ACTIVITY TIMELINE PROMPTS (activity_service.py)
# ============================================================================

ACTIVITY_TIMELINE_SYSTEM_PROMPT_CONCISE = (
    "You are a manufacturing procedure analyst. Create concise activity steps. "
    "Use action verbs. One step = one action. Avoid repetition."
)

ACTIVITY_TIMELINE_USER_PROMPT_CONCISE = """Create a concise activity timeline from these observations.

Rules:
1. ONE step per major action ONLY - skip trivial movements
2. Combine related actions (e.g., "position and secure" not separate steps)
3. Use action verbs: Position, Insert, Tighten, Verify, Apply, Remove, Trim, Stack, etc.
4. Each step under 10 words
5. Skip "operator moves", "operator reaches" if action is included (e.g., "Tighten bolts")
6. Include critical specs/dimensions if visible

Observations:
{observations}

Output EXACTLY in this format (plain text, no numbering):
Position part in fixture
Tighten bolts to 25 Nm
Verify dimension within tolerance
Trim excess material
Stack on pallet

Do NOT include:
- "Operator" or "User"
- Explanations (just actions)
- Repetitive steps
- Multiple sentences per step"""

# ============================================================================
# TIER 3: SOP GENERATION PROMPTS (sop_service.py)
# ============================================================================

SOP_SYSTEM_PROMPT_CONCISE = (
    "You are an industrial technical writer. Create concise SOPs. "
    "Omit explanations. Use action verbs. Each description is one sentence max."
)

SOP_PROMPT_TEMPLATE_CONCISE = """Create a manufacturing SOP from this timeline.

Concise SOP Rules:
- Title: Short, specific. Max 6 words. (e.g., "Injection Mold Setup" not "Complete Process of Setting Up Equipment")
- Purpose: 1-2 sentences max. Benefit/goal only.
- Scope: 1 sentence. Equipment and context only.
- Safety: 2-3 bullets. ONLY critical hazards. No explanations.
- Each step title: Verb + object. Max 8 words.
  GOOD: "Position part in fixture" (4 words)
  BAD: "The positioning of the component within the fixture assembly" (9 words)
- Each description: ONE sentence ONLY. Include: action, method, critical spec.
  GOOD: "Insert part with flat side facing left, apply 50 PSI."
  BAD: "The part should be positioned in such a way that ensures proper alignment.
         This should be done carefully to avoid damage."
- Tools: List only tools used in THIS step
- Materials: List only materials used in THIS step
- Quality Check: One sentence. What to verify?
- Safety Notes: One sentence. Critical hazard ONLY.

Timeline:
{timeline_json}

Return JSON object with this structure (keep descriptions SHORT):
{{
  "title": "short specific title",
  "purpose": "goal and benefit only",
  "scope": "equipment and context",
  "required_tools": ["list of tools"],
  "required_materials": ["list of materials"],
  "safety": ["critical hazard 1", "critical hazard 2"],
  "steps": [
    {{
      "step_number": 1,
      "title": "verb + object max 8 words",
      "description": "one sentence action method spec",
      "tools": ["tools used in this step"],
      "materials": ["materials used in this step"],
      "safety_notes": ["critical hazard if any"],
      "quality_check": "what to verify in one sentence"
    }}
  ],
  "quality_checks": ["final verification checks"],
  "estimated_duration": "calculated duration"
}}

Keep total characters per description UNDER 100. Omit: why, detailed explanations,
unnecessary context, operator names, or multiple sentences."""

# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
TO USE THESE PROMPTS:

1. In vision_service.py:
   Replace:
     VISION_SYSTEM_PROMPT = ...
     VISION_USER_PROMPT = ...

   With:
     VISION_SYSTEM_PROMPT = VISION_SYSTEM_PROMPT_CONCISE
     VISION_USER_PROMPT = VISION_USER_PROMPT_CONCISE

2. In activity_service.py:
   In build_activity_timeline(), use:
     ACTIVITY_TIMELINE_SYSTEM_PROMPT_CONCISE
     ACTIVITY_TIMELINE_USER_PROMPT_CONCISE

3. In sop_service.py:
   Replace:
     SOP_PROMPT_TEMPLATE = ...

   With:
     SOP_PROMPT_TEMPLATE = SOP_PROMPT_TEMPLATE_CONCISE

EXPECTED RESULTS:
- 40-60% reduction in text per step
- 10-15 tokens per step instead of 30-40
- More scannable for operators
- Faster reading time
- Focus on action, not explanation
"""

# ============================================================================
# COMPARISON: VERBOSE vs CONCISE OUTPUT
# ============================================================================

VERBOSE_EXAMPLE = """
Step 1: Position Assembly Component in Fixture
Description: The operator positions the metal component in the assembly fixture
by carefully aligning it with the guide pins on the fixture. The component should be
fully seated against the reference surface at the back of the fixture. Once positioned,
the operator may need to make minor adjustments to ensure that the component is correctly
aligned within the tolerance limits of plus or minus 0.5 millimeters. The operator should
ensure that the component is not forcing into the fixture, as this may indicate improper alignment.

Tools: ["precision wrench", "alignment guide", "measuring tape", "caliper"]
Materials: ["assembly cleaner", "lubricant"]
Safety Notes: ["Ensure hands are clear of pinch points at all times",
              "Wear safety glasses during assembly operations",
              "Remove any jewelry that might catch in the fixture"]
Quality Check: "Verify that the component is seated against the reference surface and
               that the alignment is within plus or minus 0.5 millimeters of the centerline"
"""

CONCISE_EXAMPLE = """
Step 1: Position Component in Fixture
Description: Insert component with reference edge against back stop, align within ±0.5mm.

Tools: ["alignment guide", "caliper"]
Materials: []
Safety Notes: "Keep hands clear of pinch points."
Quality Check: "Verify alignment within ±0.5mm of centerline."
"""

# ============================================================================
# QUICK REFERENCE: PREFERRED VERBS FOR CONCISE STEPS
# ============================================================================

CONCISE_VERBS = [
    # Assembly
    "Position", "Insert", "Align", "Attach", "Secure", "Join", "Engage", "Connect",

    # Fastening
    "Tighten", "Loosen", "Torque", "Crimp", "Rivet", "Bolt", "Screw", "Clamp",

    # Trimming/Cutting
    "Trim", "Cut", "Shear", "Slice", "Remove", "Grind", "Sand", "Polish",

    # Verification
    "Verify", "Check", "Inspect", "Measure", "Test", "Confirm", "Validate", "Gauge",

    # Application
    "Apply", "Coat", "Spray", "Lubricate", "Clean", "Wash", "Wipe", "Dry",

    # Movement
    "Load", "Unload", "Transfer", "Stack", "Arrange", "Place", "Set", "Mount",

    # Adjustment
    "Adjust", "Set", "Calibrate", "Fine-tune", "Regulate", "Configure", "Balance",

    # Operation
    "Start", "Stop", "Activate", "Engage", "Run", "Begin", "Complete", "Finish",
]

# ============================================================================
# ANTI-PATTERNS: AVOID THESE IN CONCISE PROMPTS
# ============================================================================

ANTI_PATTERNS = {
    "verbose_description": "The operator then proceeds to carefully position the assembly component",
    "concise_description": "Position component in fixture.",

    "verbose_title": "Careful Positioning of the Assembly Component Within the Precision Fixture",
    "concise_title": "Position Component in Fixture",

    "verbose_safety": "It is important to ensure that hands and fingers are kept clear of any pinch points that may exist in the fixture assembly during this operation",
    "concise_safety": "Keep hands clear of pinch points.",

    "verbose_quality": "The operator should verify that the assembly component is properly seated against the reference surface and that the alignment is within the specified tolerance range",
    "concise_quality": "Verify alignment within ±0.5mm.",

    "verbose_tools": "precision wrench, stainless steel measuring tape, precision alignment guide, vernier caliper",
    "concise_tools": "alignment guide, caliper",
}

# ============================================================================
# TOKEN EFFICIENCY COMPARISON
# ============================================================================

TOKEN_COMPARISON = """
For a 10-step procedure:

VERBOSE VERSION:
- ~50 tokens per step description
- ~10 steps × 50 = 500 tokens for descriptions
- Total SOP: ~800-1000 tokens

CONCISE VERSION:
- ~15 tokens per step description
- ~10 steps × 15 = 150 tokens for descriptions
- Total SOP: ~300-400 tokens

SAVINGS: 60-70% reduction in tokens
BENEFIT: Lower API costs, faster processing, better for operators
"""
