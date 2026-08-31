from server import build_absolute_gallery_url, extract_gallery_image_urls


def test_build_absolute_gallery_url_handles_relative_paths():
    assert build_absolute_gallery_url("https://nas.example.com/photo/Divik 27 march/", "./a.jpg") == "https://nas.example.com/photo/Divik 27 march/a.jpg"
    assert build_absolute_gallery_url("https://nas.example.com/photo/Divik 27 march", "/photo/Divik 27 march/b.jpg") == "https://nas.example.com/photo/Divik 27 march/b.jpg"


def test_extract_gallery_image_urls_handles_basic_html():
    html = '''
    <html><body>
      <img src="/photo/Divik 27 march/a.jpg">
      <img src="https://cdn.example.com/b.jpg">
      <img src="./c.png">
    </body></html>
    '''
    urls = extract_gallery_image_urls("https://nas.example.com/photo/Divik 27 march", html)
    assert urls == [
        "https://nas.example.com/photo/Divik 27 march/a.jpg",
        "https://cdn.example.com/b.jpg",
        "https://nas.example.com/photo/Divik 27 march/c.png",
    ]
