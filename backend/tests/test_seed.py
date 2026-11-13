from app.scripts.seed import demo_certificates


def test_demo_certificates_are_valid_and_unique() -> None:
    certs = demo_certificates()  # constructing them runs full validation
    assert len(certs) == 20
    assert len({c.cert_number for c in certs}) == 20
    assert all(c.cert_number.startswith("NBIT") for c in certs)
