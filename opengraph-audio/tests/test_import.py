def test_package_imports():
    import opengraph_audio

    assert callable(opengraph_audio.main)
    assert callable(opengraph_audio.mcp_main)
