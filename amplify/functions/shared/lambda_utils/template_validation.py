"""
Decomposed WhatsApp message-template validation service.

Single source of truth for template structure validation. Each component
type has its own validator so callers (create + a dedicated /validate route)
share identical rules. Returns structured results:

    { 'ok': bool, 'errors': [str], 'warnings': [str] }

Rules follow Meta's Cloud API template reference. Soft issues (e.g. 4+
buttons may truncate on desktop) are returned as warnings, not errors.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from .whatsapp_types import (
    TEMPLATE_CATEGORIES,
    HEADER_FORMATS,
    BUTTON_TYPES,
    HEADER_TEXT_MAX,
    BODY_TEXT_MAX,
    FOOTER_TEXT_MAX,
    BUTTON_TEXT_MAX,
    COPY_CODE_EXAMPLE_MAX,
    PHONE_NUMBER_MAX,
    URL_MAX,
    FLOW_NAME_MAX,
)
from .template_ttl import validate_ttl

_PLACEHOLDER_RE = re.compile(r'\{\{\s*([A-Za-z0-9_]+)\s*\}\}')
# Markdown-ish characters that need escaping in template text headers/bodies.
_MARKDOWN_CHARS = set('*_~`')


def detect_parameter_format(text: str) -> str:
    """Return 'POSITIONAL', 'NAMED', 'MIXED', or 'NONE' for a text string."""
    if not text:
        return 'NONE'
    tokens = _PLACEHOLDER_RE.findall(text)
    if not tokens:
        return 'NONE'
    has_positional = any(tok.isdigit() for tok in tokens)
    has_named = any(not tok.isdigit() for tok in tokens)
    if has_positional and has_named:
        return 'MIXED'
    return 'POSITIONAL' if has_positional else 'NAMED'


def _placeholders(text: str) -> List[str]:
    return _PLACEHOLDER_RE.findall(text or '')


def validate_root(template_def: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Validate name, language, category, TTL. Returns (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []

    name = (template_def.get('name') or '').strip()
    if not name:
        errors.append('Template name is required')
    elif not re.fullmatch(r'[a-z0-9_]+', name):
        errors.append('Template name must be lowercase letters, numbers, and underscores only')

    if not template_def.get('language'):
        errors.append('Template language is required')

    category = (template_def.get('category') or '').upper()
    if not category:
        errors.append('Template category is required')
    elif category not in TEMPLATE_CATEGORIES:
        errors.append(f'Invalid category: {category}. Must be one of {", ".join(TEMPLATE_CATEGORIES)}')

    ttl = template_def.get('message_send_ttl_seconds')
    if ttl is not None and category in TEMPLATE_CATEGORIES:
        ttl_res = validate_ttl(category, ttl)
        if not ttl_res['ok']:
            errors.append(ttl_res['error'])
        warnings.extend(ttl_res.get('warnings', []))

    return errors, warnings


def _check_markdown(text: str, where: str) -> List[str]:
    if text and any(c in _MARKDOWN_CHARS for c in text):
        return [f'{where} contains markdown characters (* _ ~ `); they may render unexpectedly.']
    return []


def validate_header(comp: Dict[str, Any], category: str) -> Tuple[List[str], List[str]]:
    """Validate a HEADER component. Returns (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []
    fmt = (comp.get('format') or '').upper()
    cat = (category or '').upper()

    if fmt and fmt not in HEADER_FORMATS:
        errors.append(f'Invalid header format: {fmt}. Must be one of {", ".join(HEADER_FORMATS)}')
        return errors, warnings

    if fmt == 'TEXT':
        text = comp.get('text', '')
        if len(text) > HEADER_TEXT_MAX:
            errors.append(f'TEXT header must be <= {HEADER_TEXT_MAX} characters')
        placeholders = _placeholders(text)
        if len(placeholders) > 1:
            errors.append('TEXT header may contain at most 1 parameter')
        if placeholders:
            example = (comp.get('example') or {}).get('header_text')
            if not example:
                errors.append('TEXT header with a parameter requires an example (example.header_text)')
        warnings.extend(_check_markdown(text, 'TEXT header'))
    elif fmt == 'LOCATION':
        if cat == 'AUTHENTICATION':
            errors.append('LOCATION header is only allowed for UTILITY or MARKETING templates')
    elif fmt in ('IMAGE', 'VIDEO', 'GIF', 'DOCUMENT'):
        example = comp.get('example') or {}
        if not example.get('header_handle') and not example.get('header_url'):
            warnings.append(
                f'{fmt} header usually requires a header_handle (from media upload) in example.'
            )

    return errors, warnings


def validate_body(comp: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Validate the BODY component. Returns (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []
    text = comp.get('text', '')
    if not text:
        errors.append('BODY text is required')
    if len(text) > BODY_TEXT_MAX:
        errors.append(f'BODY text must be <= {BODY_TEXT_MAX} characters')
    errors.extend(validate_examples(comp, 'BODY'))
    warnings.extend(_check_markdown(text, 'BODY'))
    return errors, warnings


def validate_footer(comp: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Validate a FOOTER component. Returns (errors, warnings)."""
    errors: List[str] = []
    text = comp.get('text', '')
    if len(text) > FOOTER_TEXT_MAX:
        errors.append(f'FOOTER text must be <= {FOOTER_TEXT_MAX} characters')
    if _placeholders(text):
        errors.append('FOOTER must not contain variables')
    return errors, []


def validate_examples(comp: Dict[str, Any], where: str) -> List[str]:
    """Validate that placeholders have matching examples and a consistent format."""
    errors: List[str] = []
    text = comp.get('text', '')
    placeholders = _placeholders(text)
    if not placeholders:
        return errors

    fmt = detect_parameter_format(text)
    if fmt == 'MIXED':
        errors.append(f'{where} mixes positional ({{1}}) and named ({{name}}) parameters; use one style')
        return errors

    if fmt == 'POSITIONAL':
        nums = sorted(int(p) for p in placeholders)
        expected = list(range(1, len(set(nums)) + 1))
        if sorted(set(nums)) != expected:
            errors.append(f'{where} positional parameters must be sequential starting at {{1}}')

    example = comp.get('example') or {}
    # Meta example keys differ by component; accept the common ones.
    example_values = (
        example.get('body_text')
        or example.get('body_text_named_params')
        or example.get('header_text')
        or example.get('header_text_named_params')
    )
    if not example_values:
        errors.append(f'{where} has parameters but no example values were provided')
        return errors

    # For positional body_text Meta expects a list-of-lists; count the inner row.
    if fmt == 'POSITIONAL' and isinstance(example_values, list) and example_values:
        row = example_values[0] if isinstance(example_values[0], list) else example_values
        if len([v for v in row if v is not None]) < len(set(placeholders)):
            errors.append(f'{where} example does not provide a value for every parameter')
    return errors


def validate_flow_button(button: Dict[str, Any]) -> List[str]:
    """Validate a FLOW-type button. Returns errors."""
    errors: List[str] = []
    text = button.get('text', '')
    if not text:
        errors.append('FLOW button requires text')
    if len(text) > BUTTON_TEXT_MAX:
        errors.append(f'FLOW button text must be <= {BUTTON_TEXT_MAX} characters')
    # Must reference a flow by id, name, or inline json
    if not (button.get('flow_id') or button.get('flow_name') or button.get('flow_json')):
        errors.append('FLOW button requires one of flow_id, flow_name, or flow_json')
    if button.get('flow_name') and len(button['flow_name']) > FLOW_NAME_MAX:
        errors.append(f'flow_name must be <= {FLOW_NAME_MAX} characters')
    action = (button.get('flow_action') or '').lower()
    if action and action not in ('navigate', 'data_exchange'):
        errors.append("flow_action must be 'navigate' or 'data_exchange'")
    if action == 'navigate' and not button.get('navigate_screen'):
        errors.append("FLOW button with flow_action 'navigate' requires navigate_screen")
    return errors


def validate_button_grouping(buttons: List[Dict[str, Any]]) -> Optional[str]:
    """Quick replies must be contiguous (a single group). Returns error or None."""
    types = [(b.get('type') or '').upper() for b in buttons]
    qr = [i for i, t in enumerate(types) if t == 'QUICK_REPLY']
    if qr and (max(qr) - min(qr) + 1) != len(qr):
        return 'Quick reply buttons must be grouped together (contiguous), not interleaved with other button types'
    return None


def validate_buttons(buttons: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """Validate a BUTTONS component. Returns (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []
    if not buttons:
        return errors, warnings
    if len(buttons) > 10:
        errors.append('A template may have at most 10 buttons')
    if len(buttons) >= 4:
        warnings.append('4 or more buttons may not display fully on WhatsApp desktop')

    counts: Dict[str, int] = {}
    for b in buttons:
        t = (b.get('type') or '').upper()
        if t and t not in BUTTON_TYPES:
            errors.append(f'Unknown button type: {t}')
            continue
        counts[t] = counts.get(t, 0) + 1
        if t == 'FLOW':
            errors.extend(validate_flow_button(b))
            continue
        if t in ('QUICK_REPLY', 'URL', 'PHONE_NUMBER', 'VOICE_CALL') and len(b.get('text', '')) > BUTTON_TEXT_MAX:
            errors.append(f'{t} button text must be <= {BUTTON_TEXT_MAX} characters')
        if t == 'COPY_CODE' and len(str(b.get('example', ''))) > COPY_CODE_EXAMPLE_MAX:
            errors.append(f'COPY_CODE example must be <= {COPY_CODE_EXAMPLE_MAX} characters')
        if t == 'PHONE_NUMBER' and len(str(b.get('phone_number', ''))) > PHONE_NUMBER_MAX:
            errors.append(f'PHONE_NUMBER must be <= {PHONE_NUMBER_MAX} characters')
        if t == 'URL' and len(str(b.get('url', ''))) > URL_MAX:
            errors.append(f'URL must be <= {URL_MAX} characters')

    if counts.get('COPY_CODE', 0) > 1:
        errors.append('At most 1 COPY_CODE button allowed')
    if counts.get('PHONE_NUMBER', 0) > 1:
        errors.append('At most 1 PHONE_NUMBER button allowed')
    if counts.get('URL', 0) > 2:
        errors.append('At most 2 URL buttons allowed')
    if counts.get('QUICK_REPLY', 0) > 10:
        errors.append('At most 10 QUICK_REPLY buttons allowed')

    grouping = validate_button_grouping(buttons)
    if grouping:
        errors.append(grouping)
    return errors, warnings


def validate_components(components: List[Dict[str, Any]], category: str) -> Tuple[List[str], List[str]]:
    """Validate all components. Returns (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []
    has_body = False
    for comp in components or []:
        ctype = (comp.get('type') or '').upper()
        if ctype == 'HEADER':
            e, w = validate_header(comp, category)
        elif ctype == 'BODY':
            has_body = True
            e, w = validate_body(comp)
        elif ctype == 'FOOTER':
            e, w = validate_footer(comp)
        elif ctype == 'BUTTONS':
            e, w = validate_buttons(comp.get('buttons', []))
        elif ctype == 'CAROUSEL':
            e, w = [], []
            for card in comp.get('cards', []):
                ce, cw = validate_components(card.get('components', []), category)
                e.extend(ce)
                w.extend(cw)
        else:
            e, w = ([f'Unknown component type: {ctype}'] if ctype else ['Component missing type']), []
        errors.extend(e)
        warnings.extend(w)
    if not has_body:
        errors.append('Template must include a BODY component')
    return errors, warnings


def build_human_warnings(template_def: Dict[str, Any]) -> List[str]:
    """Collect non-blocking, human-friendly warnings for the whole template."""
    _, warnings = validate_template_parts(template_def)
    return warnings


def validate_template_parts(template_def: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Run root + component validation. Returns (errors, warnings)."""
    errors, warnings = validate_root(template_def)
    e, w = validate_components(template_def.get('components', []), template_def.get('category', ''))
    errors.extend(e)
    warnings.extend(w)
    return errors, warnings


def validate_template(template_def: Dict[str, Any]) -> Dict[str, Any]:
    """Full validation. Returns { ok, errors, warnings }."""
    if not template_def:
        return {'ok': False, 'errors': ['templateDefinition required'], 'warnings': []}
    errors, warnings = validate_template_parts(template_def)
    return {'ok': len(errors) == 0, 'errors': errors, 'warnings': warnings}


def first_error(template_def: Dict[str, Any]) -> Optional[str]:
    """Backwards-compatible: return the first error string or None."""
    res = validate_template(template_def)
    return res['errors'][0] if res['errors'] else None
