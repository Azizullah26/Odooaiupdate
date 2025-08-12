from pathlib import Path
import re

# Path to the uploaded domain.yml
domain_path = Path("C:/Users/Raghad PC/estimation-system/domain.yml")

# Read the original content
lines = domain_path.read_text().splitlines()

updated_lines = []
in_intents = False
intents = set()
updated_intents = False
in_slots = False
current_slot = None
slot_has_mappings = set()
in_responses = False
got_utter_goodbye = False

for i, line in enumerate(lines):
    stripped = line.lstrip()
    indent = len(line) - len(stripped)
    
    # Detect intents block
    if stripped.startswith("intents:"):
        in_intents = True
        updated_lines.append(line)
        continue
    if in_intents:
        # End of intents block when next top-level key appears
        if indent == 0 and not stripped.startswith("-"):
            # Insert missing intents if not yet done
            if "goodbye" not in intents:
                updated_lines.append("  - goodbye")
            if "nlu_fallback" not in intents:
                updated_lines.append("  - nlu_fallback")
            in_intents = False
        else:
            # Collect existing intents
            match = re.match(r"-\s*(\w+)", stripped)
            if match:
                intents.add(match.group(1))
        updated_lines.append(line)
        continue
    
    # Detect slots block
    if stripped.startswith("slots:"):
        in_slots = True
        updated_lines.append(line)
        continue
    if in_slots:
        # Slot definitions start with two spaces indent and slot name
        if indent == 2 and stripped.endswith(":"):
            current_slot = stripped[:-1]
            updated_lines.append(line)
            continue
        # Check for mappings under current slot
        if current_slot:
            if stripped.startswith("mappings:"):
                slot_has_mappings.add(current_slot)
            # If next slot or end and no mappings added, insert mappings
            # Detect end of current slot when indent <=2 and previous was slot
            next_indent = indent
            if stripped.endswith(":") and indent == 2 and stripped[:-1] != current_slot:
                if current_slot not in slot_has_mappings:
                    updated_lines.append("    mappings:")
                    updated_lines.append("      - type: from_entity")
                    updated_lines.append(f"        entity: {current_slot}")
                    slot_has_mappings.add(current_slot)
                current_slot = stripped[:-1]
                updated_lines.append(line)
                continue
        # End of slots block at top-level
        if indent == 0 and not stripped.startswith("-") and not stripped.startswith("slots:"):
            if current_slot and current_slot not in slot_has_mappings:
                updated_lines.append("    mappings:")
                updated_lines.append("      - type: from_entity")
                updated_lines.append(f"        entity: {current_slot}")
            in_slots = False
        updated_lines.append(line)
        continue
    
    # Detect responses block
    if stripped.startswith("responses:"):
        in_responses = True
        updated_lines.append(line)
        continue
    if in_responses:
        # Check for utter_goodbye
        if stripped.startswith("utter_goodbye:"):
            got_utter_goodbye = True
        # End responses when next top-level starts
        if indent == 0 and stripped and not stripped.startswith("-") and not stripped.startswith("utter_"):
            if not got_utter_goodbye:
                updated_lines.append("  utter_goodbye:")
                updated_lines.append("    - text: \"Goodbye! Have a great day!\"")
                got_utter_goodbye = True
            in_responses = False
        updated_lines.append(line)
        continue
    
    # Collect default
    updated_lines.append(line)

# Write the updated content back
domain_path.write_text("\n".join(updated_lines))

print("domain.yml has been updated with missing intents, slot mappings, and utter_goodbye response.")
