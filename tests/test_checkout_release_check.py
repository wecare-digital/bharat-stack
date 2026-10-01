import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'scripts/checkout_release_check.py'
spec = importlib.util.spec_from_file_location('checkout_release_check', path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

PAGE = '<header><a href="/cart/">Shopping Bag</a></header><main><h1>Cart</h1>{}</main><footer></footer><a href="https://wecare.digital/r/wa">Chat</a>'


def test_checks_actual_customer_links_and_shared_chrome():
    assert gate.check_html('/cart/', PAGE.format('')) == []
    for href in ('/workspace/access/', '/access/', 'https://store.wecare.digital',
                 'https://legalchamp.in'):
        assert gate.check_html('/cart/', PAGE.format(f'<a href="{href}">Visit</a>'))


def test_embedded_staff_route_strings_are_not_navigation():
    assert gate.check_html('/cart/', PAGE.format('<script>{"path":"/workspace/access/"}</script>')) == []


def test_missing_widget_and_footer_fail_release():
    assert gate.check_html('/cart/', '<main><h1>Cart</h1></main>')


def test_covers_all_customer_pages_without_blog_articles():
    assert set(gate.CUSTOMER_PAGES) <= set(gate.paths())
    assert not any(p.startswith('/blog/') and p != '/blog/' for p in gate.paths())
