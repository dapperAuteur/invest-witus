"""What a PostHog page view may say about the page (2026-11-04, decision 176).

The only thing sent is the page's path, and not the path in the address bar: the route it matched,
with every part the route captures replaced by the part's name. `/accounts/12/watch/SPY/` becomes
`/accounts/:id/watch/:symbol/`, so no account id, symbol, month or entry number leaves the site,
and no query string or fragment either. Taking the route rather than cleaning the path with a
pattern means a route added later is covered without anyone remembering to add a rule.
"""

from django.http import HttpRequest

# A request no route matched (a 404 page): its path could hold anything, so none of it is sent.
NOT_FOUND = "/:not-found/"


def _part_name(name: str) -> str:
    """`pk` reads as `id`, and `item_pk` as `item_id`: what a reader of the dashboard expects."""
    if name == "pk":
        return "id"
    if name.endswith("_pk"):
        return name[: -len("pk")] + "id"
    return name


def _skip_group(route: str, start: int) -> int:
    """The index just past the regular-expression group that opens at `start`, nested groups,
    character classes and escapes included."""
    depth = 0
    index = start
    in_class = False
    while index < len(route):
        char = route[index]
        if char == "\\":
            index += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return index


def route_template(route: str) -> str:
    """A Django route as a path with named parts: `accounts/<int:pk>/watch/<str:symbol>/` gives
    `/accounts/:id/watch/:symbol/`, and a regular-expression route such as
    `accounts/<int:pk>/method/review/(?P<month>\\d{4}-\\d{2})/$` gives
    `/accounts/:id/method/review/:month/`. A group without a name becomes `:part`."""
    out: list[str] = []
    index = 0
    while index < len(route):
        char = route[index]
        if route.startswith("(?P<", index):
            end = route.index(">", index)
            out.append(":" + _part_name(route[index + 4 : end]))
            index = _skip_group(route, index)
        elif char == "(":
            out.append(":part")
            index = _skip_group(route, index)
        elif char == "<":
            end = route.index(">", index)
            out.append(":" + _part_name(route[index + 1 : end].split(":")[-1]))
            index = end + 1
        elif char in "^$":
            index += 1
        elif char == "\\" and index + 1 < len(route):
            out.append(route[index + 1])
            index += 2
        else:
            out.append(char)
            index += 1
    return "/" + "".join(out).lstrip("/")


def page_path(request: HttpRequest) -> str:
    """The path a page view reports for this request: its route's template, or NOT_FOUND."""
    match = request.resolver_match
    if match is None:
        return NOT_FOUND
    return route_template(match.route)
