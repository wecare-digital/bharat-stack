"""Runtime shim for the CDK-packaged SEO tools Lambda."""
import sys

sys.path.insert(0, '/var/task/shared')
sys.path.insert(0, '/var/task/operations/seo-tools')

from handler import handler  # noqa: E402,F401
