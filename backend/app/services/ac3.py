"""Arc consistency for catalog domains; absence is allowed for GPU and cooler."""
from collections import deque
from app.db.models import Category, CpuSpec
from app.services.compatibility import SelectedPart, check_pair


def supported(left_category, left, right_category, right):
    if left is None or right is None:
        absent, other = (left_category, right) if left is None else (right_category, left)
        if other is not None and isinstance(other.spec, CpuSpec):
            if absent == Category.GPU:
                return other.spec.integrated_graphics
            if absent == Category.COOLER:
                return other.spec.includes_cooler
        return True
    _, issues, _ = check_pair(left, right)
    return not any(issue.severity == "error" for issue in issues)


def filter_domains(domains):
    """Return copied domains after propagation; never mutate caller selections.

    Unknown specifications retain support. Nonempty domains do not prove that a
    complete solution exists; total power must be checked on the final build.
    """
    remaining = {category: list(values) for category, values in domains.items()}
    queue = deque((a, b) for a in remaining for b in remaining if a != b)
    queued = set(queue)
    cache = {}
    def compatible(a, x, b, y):
        key = (a, None if x is None else x.component.id,
               b, None if y is None else y.component.id)
        if key not in cache:
            cache[key] = supported(a, x, b, y)
        return cache[key]

    while queue:
        a, b = queue.popleft()
        queued.remove((a, b))
        revised = [x for x in remaining[a]
                   if any(compatible(a, x, b, y) for y in remaining[b])]
        if len(revised) != len(remaining[a]):
            remaining[a] = revised
            for neighbor in remaining:
                arc = (neighbor, a)
                if neighbor != a and neighbor != b and arc not in queued:
                    queue.append(arc)
                    queued.add(arc)
    return remaining


def spec_signature(part):
    """Every spec value of a part (None: no specs). Parts with equal signatures pass and fail
    exactly the same rules, whatever they are paired with."""
    if part is None:
        return None
    spec = part.spec
    if spec is None:
        return (part.component.category, "no specs")
    return (part.component.category,) + tuple(
        (c.name, repr(getattr(spec, c.name))) for c in spec.__table__.columns if c.name != "component_id")


def filter_catalog(domains):
    """filter_domains on one representative per spec signature, expanded back to all parts.

    Exact, because support depends only on spec values; it keeps AC-3 fast on a catalog
    with hundreds of parts per category."""
    groups = {}
    representatives = {}
    for category, values in domains.items():
        reps = []
        for part in values:
            key = (category, spec_signature(part))
            if key not in groups:
                groups[key] = []
                reps.append(part)
            groups[key].append(part)
        representatives[category] = reps
    filtered = filter_domains(representatives)
    return {category: [part for rep in values for part in groups[(category, spec_signature(rep))]]
            for category, values in filtered.items()}
