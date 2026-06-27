"""Generic Meta Graph cursor pagination helper (standalone of MetaGraphClient.paginate)."""
from typing import Any, Callable, Dict, Iterator, Optional


def paginate(fetch: Callable[[Dict[str, Any]], Dict[str, Any]],
             params: Optional[Dict[str, Any]] = None,
             max_pages: int = 50) -> Iterator[Dict[str, Any]]:
    """Yield each item across cursor-paged Graph responses.

    `fetch` is a callable taking params dict and returning a Graph response
    ({'data': [...], 'paging': {'cursors': {'after': ...}}} or {'error': ...}).
    """
    page_params = dict(params or {})
    for _ in range(max_pages):
        result = fetch(page_params) or {}
        if 'error' in result:
            return
        for item in result.get('data', []) or []:
            yield item
        after = ((result.get('paging') or {}).get('cursors') or {}).get('after')
        if not after or not result.get('data'):
            return
        page_params['after'] = after
