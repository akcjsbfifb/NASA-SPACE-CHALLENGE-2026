import io
import pytest
from lunar_data.http_range import RangeSource,TransferBudget


@pytest.fixture
def server(monkeypatch):
    content=bytes(range(256))*1024
    events=[]
    class Response(io.BytesIO):
        status=206
        def __init__(self,start,end):
            super().__init__(content[start:end+1])
            self.headers={"Content-Range":f"bytes {start}-{end}/{len(content)}",
                          "Content-Length":str(end-start+1),"ETag":"fixed","Last-Modified":"fixed"}
        def read(self,*args):events.append("body_read");return super().read(*args)
    def request(req,timeout):
        start,end=map(int,req.get_header("Range").split("=")[1].split("-"))
        result=Response(start,end)
        events.append(result)
        return result
    monkeypatch.setattr("lunar_data.http_range.urlopen",request)
    return content,events


def test_seek_and_read_and_cache_with_hard_budget(server):
    content,events=server
    budget=TransferBudget(2*65536)
    source=RangeSource("https://example.org/raster.tif",budget)
    with source.open() as stream:
        assert stream.read(4)==content[:4]
        stream.seek(65534)
        assert stream.read(5)==content[65534:65539]
        assert budget.received==131072
        stream.seek(0); assert stream.read(4)==content[:4]
        stream.seek(3*65536)
        with pytest.raises(OSError,match="Presupuesto"):stream.read(1)
        stream.seek(0)
        with pytest.raises(OSError,match="masiva"):stream.read()
    assert len(source.manifest()["ranges"])==2


def test_full_response_is_rejected_without_read(monkeypatch):
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):raise AssertionError("No debe leer el archivo completo")
    monkeypatch.setattr("lunar_data.http_range.urlopen",lambda *args,**kwargs:Response())
    with pytest.raises(OSError,match="ignoró Range"):RangeSource("https://example.org/a.tif")


@pytest.mark.parametrize("field,value", [("Content-Range","bytes 1-65536/262144"),
    ("Content-Length","1000000000")])
def test_invalid_headers_abort_before_body(server,monkeypatch,field,value):
    import lunar_data.http_range as module
    original=module.urlopen
    def altered(*args,**kwargs):
        response=original(*args,**kwargs);response.headers[field]=value;return response
    monkeypatch.setattr(module,"urlopen",altered)
    with pytest.raises(OSError):RangeSource("https://example.org/a.tif")
    assert "body_read" not in server[1]
