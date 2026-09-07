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

DEMO_VIDEO_ACTIVITY_PROMPT = """Analyze these demo video observations and extract TASK-LEVEL ACTIONS.

CRITICAL: This is for SOP generation. Focus on WHAT NEEDS TO BE ACCOMPLISHED, NOT how the demonstrator moved.

VISUAL OBSERVATIONS:
{visual_evidence}

SPEECH TRANSCRIPT:
{transcript}

OCR TEXT:
{ocr_text}

Extract task-level object manipulation steps. Ignore human hand/body movements unless they are genuinely task-essential.

EXTRACTION RULES:
1. Identify objects and their properties (color, type, identity)
2. Extract meaningful object relationships (on top of, beside, inside, etc.)
3. Track assembly sequence and order
4. Note required object orientation ONLY if task depends on it
5. Describe resulting object state after each action
6. Ignore hand movements, wrist rotation, finger movement, arm movement, trajectories, grip styles, approach angles, body movements
7. One meaningful task action = One activity
8. Target 3-8 task steps (not dozens of micro-steps)

IGNORE (do NOT extract as activities):
- Hand trajectory, approach direction, approach angle
- Wrist rotation, hand rotation, finger movements
- Grasping style, grip position, exact finger placement
- Arm movements, body movements, posture
- Temporary pauses, hesitations, corrective movements
- Hand moving away after placement
- Temporary occlusion or hand in the way
- Exact movement timing or speed
- Demonstrator-specific variations

EXTRACT (as meaningful task actions):
- Object identity, color, type
- Object placement and positioning
- Object relationships (stacking, assembly, arrangement)
- Object orientation (ONLY if required for task)
- Assembly sequence and order
- Resulting object state
- Task completion conditions

Return ONLY a JSON object:

{{
  "activities": [
    {{
      "start_time": 0.0,
      "end_time": 5.0,
      "activity": "task action focusing on object state (e.g., 'Place the red LEGO block on top of the blue LEGO block')",
      "visual_evidence": ["objects and their final state"],
      "speech": "relevant transcript or empty string",
      "ocr": ["any text visible"],
      "tools": [],
      "materials": ["objects involved (with color/type if identifiable)"],
      "confidence": 0.9
    }}
  ]
}}

GOOD Examples:
✓ "Place the blue LEGO block"
✓ "Place the red LEGO block on top of the blue LEGO block"
✓ "Place the yellow LEGO block on top of the red LEGO block"
✓ "Rotate the LEGO piece 90 degrees and place it in the slot"

BAD Examples (do NOT extract these):
✗ "Move hand toward red block"
✗ "Rotate wrist 20 degrees"
✗ "Grip using fingers"
✗ "Move hand from left to right"
✗ "Lift hand upward"
✗ "Approach block from the right"
"""

DEMO_VIDEO_SOP_PROMPT = """Create a TASK-CENTRIC SOP from this timeline.

{timeline_json}

CRITICAL PRINCIPLE:
Describe WHAT needs to be accomplished, NOT HOW the demonstrator moved while accomplishing it.

The SOP must be:
- Task-centric (focused on object states and relationships)
- Concise (one meaningful action = one step)
- Monitorable (verifiable from real-time video)
- Robust (works regardless of how a user moves their hands)
- Object-centric (focus on objects, colors, placement, relationships)

FILTER OUT (ignore these activities):
- Hand movements, wrist rotation, finger movements
- Arm movements, body movements, posture
- Approach directions, trajectories, grip styles
- Exact hand positions, timing, speed
- Demonstrator-specific movement variations
- Temporary movements or corrective actions

PRESERVE (include these):
- Object identity, color, type
- Object placement and positioning
- Assembly sequence and order
- Object relationships (on top of, beside, inside, etc.)
- Required object orientation (if task-essential)
- Clear completion conditions

Format:
{{
  "title": "Simple, descriptive title",
  "purpose": "What will you accomplish? (one sentence, object-centric)",
  "scope": "What objects will you need?",
  "required_materials": ["list of objects with colors/types"],
  "steps": [
    {{
      "step_number": 1,
      "title": "Simple action title (object-centric)",
      "description": "Clear description of object state or placement (e.g., 'Place the red LEGO block on top of the blue LEGO block')",
      "materials": ["specific objects involved with their properties"],
      "quality_check": "How to verify this step is correct (focus on object state, not hand position)"
    }}
  ],
  "estimated_duration": "time to complete"
}}

GOOD SOP Example (3-block stack):
Step 1:
Title: "Place the blue LEGO block"
Description: "Place the blue LEGO block on the workspace."
Quality Check: "Blue LEGO block is on the workspace."

Step 2:
Title: "Stack the red LEGO block"
Description: "Place the red LEGO block on top of the blue LEGO block."
Quality Check: "Red LEGO block is stable on top of blue LEGO block."

Step 3:
Title: "Complete the stack"
Description: "Place the yellow LEGO block on top of the red LEGO block."
Quality Check: "Yellow LEGO block is stable on top of red LEGO block. Stack is complete."

BAD SOP Example (do NOT generate):
Step 1: Move hand toward blue block
Step 2: Rotate wrist clockwise
Step 3: Grip using fingers
Step 4: Lift hand upward
... (etc - this is wrong)

Rules:
1. Each step represents a meaningful task outcome
2. Avoid micro-steps (pick up, move, lower, release should be one step)
3. Use simple, clear language
4. Focus on object states and relationships
5. Do NOT include human motion details
6. Quality checks should verify object state, not hand position
7. Target 3-8 steps for typical demo (not dozens)

Remember: The SOP will be monitored by a real-time vision system that evaluates OBJECT STATE, not hand movement matching.
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

# =============================================================================
# REAL-TIME COMPLIANCE MONITORING PROMPTS (for SOP monitoring)
# =============================================================================

# For DEMO_VIDEO - Object/Task-centric compliance check (LEGO, simple assembly, etc.)
DEMO_VIDEO_COMPLIANCE_SYSTEM_PROMPT = (
    "You are a task compliance evaluator for simple object assembly procedures. "
    "Your ONLY role is to verify that the REQUIRED OBJECTS are in the correct state. "
    "Do NOT evaluate human movement, hand position, wrist rotation, grip style, or body position. "
    "Focus EXCLUSIVELY on: "
    "- Required object identity and presence "
    "- Required object colors and properties "
    "- Required object positions and spatial relationships "
    "- Required object orientation (when specified) "
    "Ignore all human hand/body movements, temporary occlusions, approach angles, trajectories, and grip variations. "
    "The task is complete ONLY when the required object state is achieved."
)

DEMO_VIDEO_COMPLIANCE_PROMPT_TEMPLATE = """TASK COMPLIANCE CHECK
=====================

Current SOP Step: {step_title}
Instructions: {step_description}
Required Objects: {required_objects}

Your task: Verify that the REQUIRED OBJECTS are in the correct state to complete this step.

CRITICAL - DO NOT EVALUATE:
- Human hand position, movements, or rotation
- Wrist rotation, finger movements, or grip style
- Arm movements or body movements
- Hand approach direction or trajectory
- Speed or timing of movements
- Temporary hand occlusion
- How the demonstrator is holding or manipulating
- Natural movement variations between users

CRITICAL - DO EVALUATE (object state only):
- Are ALL required objects visible in the frame?
- Are objects the CORRECT color/type? (exact match to requirement)
- Are objects in the CORRECT POSITION relative to each other?
- Are objects in the CORRECT SPATIAL RELATIONSHIP? (e.g., "red on top of blue")
- Is object ORIENTATION correct? (ONLY if step requires specific orientation)
- Are objects STABLE and in final position?
- Are there any WRONG objects present?
- Is the FINAL TASK STATE achieved as described in the SOP?

DECISION LOGIC:
- If ALL required objects are present AND in correct state AND correctly positioned: task_compliant = TRUE
- If ANY required object is missing OR wrong color OR wrong position OR wrong orientation: task_compliant = FALSE
- Ignore HOW the user got there; evaluate WHAT the result is

Return ONLY valid JSON:
{{
  "required_objects_present": boolean,  # ALL required objects visible and identifiable
  "object_colors_correct": boolean,     # ALL objects match required colors exactly
  "object_positioning_correct": boolean, # ALL objects in correct positions/relationships
  "object_orientation_correct": boolean, # Objects oriented correctly (if orientation was required)
  "task_compliant": boolean,             # Overall: Does the final state match the SOP requirement?
  "compliance_explanation": "brief explanation focusing ONLY on final object state, not hand movements",
  "ignored_hand_movements": boolean,     # Always true for DEMO_VIDEO
  "confidence": 0.0-1.0                  # How confident are you in this assessment?
}}

EXAMPLES:
=========

Example 1 (Compliant):
SOP: "Place the red LEGO block on top of the blue LEGO block"
Frame shows: Red block clearly on top of blue block, stable position
Response: task_compliant = TRUE, object_positioning_correct = TRUE
(Ignore: User's hand is still visible, wrist bent at unusual angle, different approach than demo)

Example 2 (Non-Compliant):
SOP: "Place the red LEGO block on top of the blue LEGO block"
Frame shows: Red block beside (not on top of) blue block
Response: task_compliant = FALSE, object_positioning_correct = FALSE
(Correct: Caught the wrong positioning regardless of hand motion)

Example 3 (Compliant - Different Technique):
SOP: "Place the red LEGO block on top of the blue LEGO block"
Frame shows: Red block on top of blue block, but user used different hand approach
Response: task_compliant = TRUE, object_positioning_correct = TRUE
(Correct: Evaluated object state, not hand technique)
"""

# For MACHINE_VIDEO - Equipment/Process-centric compliance check
MACHINE_VIDEO_COMPLIANCE_SYSTEM_PROMPT = (
    "You are a process compliance auditor for industrial operations. "
    "Your ONLY role is to verify that the EQUIPMENT and PROCESS are in the correct operational state. "
    "Do NOT evaluate operator movements, body position, or technique. "
    "Focus EXCLUSIVELY on: "
    "- Equipment presence and activation status "
    "- Operational parameters and readings "
    "- Material flow, positioning, and state "
    "- Process phase completion "
    "- Safety system status "
    "Ignore all operator body movements, technique variations, and hand/body positions. "
    "The step is complete ONLY when the required equipment state and process state are achieved."
)

MACHINE_VIDEO_COMPLIANCE_PROMPT_TEMPLATE = """PROCESS COMPLIANCE CHECK
========================

Current SOP Step: {step_title}
Instructions: {step_description}
Required Equipment: {required_tools}

Your task: Verify that the EQUIPMENT and PROCESS are in the correct state to complete this step.

CRITICAL - DO NOT EVALUATE:
- Operator body position or movements
- Operator hand movements or technique
- Operator posture or positioning
- How the operator is performing the action
- Operator movement speed or timing
- Natural variation in operator technique

CRITICAL - DO EVALUATE (process state only):
- Is ALL required equipment visible and identifiable?
- Is equipment in the CORRECT OPERATIONAL STATE? (off/on/active/idle as required)
- Are OPERATIONAL PARAMETERS correct? (temperature, pressure, speed, flow rate, etc.)
- Is MATERIAL in the correct state? (positioned, flowing, ready, etc.)
- Are SAFETY SYSTEMS active and functioning? (guards, interlocks, indicators)
- Is the PROCESS PHASE correct? (setup, active, standby, etc.)
- Are there any UNEXPECTED STATES or ERRORS visible?
- Is the FINAL PROCESS STATE achieved as described in the SOP?

DECISION LOGIC:
- If ALL required equipment is present AND in correct state AND parameters are correct: process_compliant = TRUE
- If ANY required equipment is missing OR wrong state OR parameters incorrect: process_compliant = FALSE
- Ignore HOW the operator got there; evaluate WHAT the equipment/process state is

Return ONLY valid JSON:
{{
  "equipment_present": boolean,        # ALL required equipment visible and identifiable
  "equipment_active": boolean,         # Equipment in correct operational state (on/off/active)
  "parameters_correct": boolean,       # Parameters/readings within acceptable range if visible
  "material_state_correct": boolean,   # Material in correct position/flow/state
  "process_compliant": boolean,        # Overall: Is the process in the correct state?
  "compliance_explanation": "brief explanation focusing ONLY on equipment/process state, not operator movements",
  "confidence": 0.0-1.0               # How confident are you in this assessment?
}}

EXAMPLES:
=========

Example 1 (Compliant):
SOP: "Start the injection pump and monitor pressure at 150 bar"
Frame shows: Pump indicator shows ACTIVE, pressure gauge reads 150 bar
Response: process_compliant = TRUE, equipment_active = TRUE, parameters_correct = TRUE
(Ignore: Operator's hand position, grip, technique variation)

Example 2 (Non-Compliant):
SOP: "Start the injection pump and monitor pressure at 150 bar"
Frame shows: Pump indicator shows IDLE, pressure gauge reads 95 bar
Response: process_compliant = FALSE, equipment_active = FALSE
(Correct: Caught the wrong equipment state regardless of operator positioning)

Example 3 (Compliant - Different Technique):
SOP: "Load material and position for processing"
Frame shows: Material loaded and correctly positioned, even though operator used different placement method
Response: process_compliant = TRUE, material_state_correct = TRUE
(Correct: Evaluated material state, not operator technique)
"""
