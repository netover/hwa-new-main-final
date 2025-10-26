
def test_tws_client_verify_disabled(mocker):
    ac = mocker.patch("resync.services.http_client_factory.AsyncClient")
    from resync.services.http_client_factory import create_tws_http_client
    create_tws_http_client()
    kwargs = ac.call_args.kwargs
    assert kwargs['verify'] is False