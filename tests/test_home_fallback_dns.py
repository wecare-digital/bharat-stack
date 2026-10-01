import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("home_dns", Path(__file__).parents[1] / "scripts/home_fallback_dns.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_cutover_replaces_only_retired_wix_hosts_and_adds_wildcard():
    service = {"Name": "sip.wecare.digital.", "Type": "A", "TTL": 60, "ResourceRecords": [{"Value": "192.0.2.1"}]}
    wix = [{"Name": name, "Type": "CNAME", "TTL": 300, "ResourceRecords": [{"Value": "pointing.wixdns.net"}]} for name in module.NAMES[1:]]
    result = module.changes("example.cloudfront.net", wix + [service])
    assert len(result) == 5
    assert all(c["ResourceRecordSet"]["Name"] in module.NAMES for c in result)
    assert [c["ResourceRecordSet"] for c in result if c["Action"] == "DELETE"] == wix
    applied = [c["ResourceRecordSet"] for c in result if c["Action"] == "UPSERT"]
    assert module.changes("example.cloudfront.net", applied + [service]) == []
    escaped = [{**r, "Name": r["Name"].replace("*", "\\052")} for r in applied]
    assert module.changes("example.cloudfront.net", escaped + [service]) == []


def test_unexpected_service_or_cname_prevents_cutover():
    for record in [
        {"Name": module.NAMES[1], "Type": "TXT", "ResourceRecords": [{"Value": "service"}]},
        {"Name": module.NAMES[1], "Type": "CNAME", "ResourceRecords": [{"Value": "other.example"}]},
    ]:
        with pytest.raises(ValueError):
            module.changes("example.cloudfront.net", [record])


def test_fallback_infrastructure_reuses_existing_certificate_only():
    import json
    template = json.loads((Path(__file__).parents[1] / 'amplify/infra/home-fallback.json').read_text())
    assert all(r['Type'] != 'AWS::CertificateManager::Certificate' for r in template['Resources'].values())
    config = template['Resources']['Distribution']['Properties']['DistributionConfig']
    assert config['ViewerCertificate']['AcmCertificateArn'].endswith('/f75d0db0-d476-443a-b787-96c4931862d2')
    assert config['Aliases'] == ['*.wecare.digital']
