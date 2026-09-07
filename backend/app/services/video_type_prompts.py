"""
Video Type-Specific Prompts

Different prompt templates for:
1. DEMO_VIDEO - Simple hand movements and object manipulations
2. MACHINE_INSTRUCTIONS - Industrial machine operations
"""

# =============================================================================
# DEMO VIDEO PROMPTS (Hand movements with simple objects)
# =============================================================================

DEMO_VIDEO_SYSTEM_PROMPT = (
    "You are an educational procedure analyst. Describe hand movements and object "
    "manipulations in simple, clear steps. Focus on what the demonstrator is doing "
    "with their hands and how objects are being positioned or moved."
)

DEMO_VIDEO_ACTIVITY_PROMPT = """Analyze these demo video observations.

VISUAL OBSERVATIONS:
{visual_evidence}

SPEECH TRANSCRIPT:
{transcript}

OCR TEXT:
{ocr_text}

Create clear, simple steps showing the hand movements and object manipulations.

Rules:
1. Focus on  actions (pick up, place, stack, rotate, etc.)
2. Describe object positions and movements clearly
3. Include orientation details (e.g., "flat side facing up")
4. Simple language - easy to follow
5. One action per step
6. Target 4-8 distinct steps

Return ONLY a JSON object:

{{
  "activities": [
    {{
      "start_time": 0.0,
      "end_time": 5.0,
      "activity": "hand action with object (e.g., 'Pick up red block and place on table')",
      "visual_evidence": ["what is visible"],
      "speech": "relevant transcript or empty string",
      "ocr": ["any text visible"],
      "tools": [],
      "materials": ["objects being manipulated"],
      "confidence": 0.9
    }}
  ]
}}

Examples:
✓ "Pick up blue cube and stack on red cube"
✓ "Rotate green block 90 degrees clockwise"
✓ "Place pen on top of book"
"""

DEMO_VIDEO_SOP_PROMPT = """Create a simple procedural guide from this timeline.

{timeline_json}

Create a clear, step-by-step guide that anyone can follow.

Format:
{{
  "title": "Simple, descriptive title",
  "purpose": "What will you accomplish? (one sentence)",
  "scope": "What objects will you need?",
  "required_materials": ["list of objects needed"],
  "steps": [
    {{
      "step_number": 1,
      "title": "Simple action title",
      "description": "Clear description of object position",
      "materials": ["objects involved"],
      "quality_check": "How to verify this step is correct"
    }}
  ],
  "estimated_duration": "time to complete"
}}

Use simple language. Each step should be easy to understand.
Focus on: picking up, placing, stacking, rotating, arranging objects.8.
Ignnore hand movements but focus on the objects
"""

# =============================================================================
# MACHINE INSTRUCTION PROMPTS (Industrial operations)
# =============================================================================

MACHINE_VIDEO_SYSTEM_PROMPT = (
    "You are an industrial technical writer. Convert chronological timeline activities "
    "into precise operational instructions for industrial machines. Focus on exact "
    "procedures, safety, and quality specifications."
)

MACHINE_VIDEO_ACTIVITY_PROMPT = """Analyze these machine operation observations.

VISUAL OBSERVATIONS:
{visual_evidence}

SPEECH TRANSCRIPT:
{transcript}

OCR TEXT:
{ocr_text}

Create a timeline of distinct operational phases.

Rules:
1. One action per distinct operation
2. Include tool and equipment usage
3. Note parameter changes (temperature, pressure, speed, etc.)
4. Include quality checkpoints
5. Merge repetitive observations
6. Target 6-12 main operational phases
7. Consolidate adjacent duplicate observations into logical sequences


Return ONLY a JSON object:

{{
  "activities": [
    {{
      "start_time": 0.0,
      "end_time": 15.0,
      "activity": "specific machine operation",
      "visual_evidence": ["observable indicators"],
      "speech": "relevant transcript or empty string",
      "ocr": ["any text visible"],
      "tools": ["equipment used"],
      "materials": ["parts, materials, resins"],
      "confidence": 0.95
    }}
  ]
}}

Examples:
✓ "Load part into mold cavity"
✓ "Set injection pressure to 150 bar"
✓ "Monitor mold temperature at 85°C"
✓ "Inject molten polymer into mold"
"""

MACHINE_VIDEO_SOP_PROMPT = """Create a manufacturing SOP from this timeline.

{timeline_json}

Draft a complete, detailed manufacturing procedure.

Format:
{{
  "title": "precise technical procedure title",
  "purpose": "2-3 detailed sentences explaining the operational goal",
  "scope": "2-3 sentences specifying machine types and operational context",
  "required_tools": ["list of equipment and instruments"],
  "required_materials": ["resins, parts, components"],
  "safety": ["safety precautions and PPE requirements"],
  "steps": [
    {{
      "step_number": 1,
      "title": "imperative step naming precise action and component",
      "description": "3-4 detailed sentences explaining how to execute",
      "tools": ["equipment used in this step"],
      "materials": ["materials used in this step"],
      "safety_notes": ["step-specific safety cautions"],
      "quality_check": "specific verification criteria"
    }}
  ],
  "quality_checks": ["overall quality control checks"],
  "estimated_duration": "calculated duration"
}}

Expand visual evidence into detailed technical instructions.
Include exact parameters, tolerances, and verification procedures.
"""

# =============================================================================
# VISION ANALYSIS PROMPTS (for frame-by-frame analysis)
# =============================================================================

# For DEMO_VIDEO - Focus on hands and simple objects
DEMO_VIDEO_VISION_SYSTEM_PROMPT = (
    "You are a procedure analyst. Describe object manipulations. "
    "Be precise about positions, orientations, and actions."
)

DEMO_VIDEO_VISION_USER_PROMPT = """Analyze this frame from a demonstration video.

Focus on:
1. Object positions and orientations
2. Actions being performed
3. order of the objects

Return as JSON:
{
  "actions": ["object action"],
  "objects": ["objects visible"],
  "positioning": "relative positions (e.g., 'on top of', 'beside', 'inside'))",
  "orientation": "how objects are oriented",
  "confidence": 0.9
}"""

# For MACHINE_VIDEO - Focus on equipment and operations
MACHINE_VIDEO_VISION_SYSTEM_PROMPT = (
    "You are an industrial process analyst. Describe machine operations, equipment states, "
    "and parameter values. Be precise about measurements and indicators."
)

MACHINE_VIDEO_VISION_USER_PROMPT = """Analyze this frame from a machine operation video.

Focus on:
1. Machine equipment and components visible
2. Current operational parameters (if readable)
3. Material flow or mechanical actions
4. Safety indicators

Return as JSON:
{
  "actions": ["machine operation observed"],
  "equipment": ["machines, tools, fixtures visible"],
  "parameters": ["temperature", "pressure", "speed" values if visible],
  "materials": ["materials being processed"],
  "indicators": ["warning lights, status indicators"],
  "confidence": 0.95
}"""
