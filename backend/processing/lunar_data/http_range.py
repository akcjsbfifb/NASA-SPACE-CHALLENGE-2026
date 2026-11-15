"""HTTP Range acotado para lectores seek/read; nunca acepta respuesta completa."""

import hashlib
import io
import re
from urllib.request import Request, urlopen


class TransferBudget:
    def __init__(self, limit=16 * 1024 * 1024):
        self.limit = limit
        self.received = 0
        self.requests = []


class RangeSource:
    block_size = 65536

    def __init__(self, url, budget=None):
        if not url.startswith("https://"):
            raise ValueError("Se requiere HTTPS")
        self.url = url
        self.name = url.rsplit("/", 1)[-1]
        self.budget = budget or TransferBudget()
        self.cache = {}
        self.size = None
        self.identity = None
        self._block(0)

    def _block(self, index):
        if index in self.cache:
            return self.cache[index]
        start = index * self.block_size
        end = start + self.block_size - 1
        if self.size is not None:
            end = min(end, self.size - 1)
        length = end - start + 1
        if length <= 0:
            return b""
        if self.budget.received + length > self.budget.limit:
            raise OSError("Presupuesto HTTP agotado; no se descarga el archivo completo")
        headers = {"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"}
        if self.identity and self.identity[0]:
            headers["If-Match"] = self.identity[0]
        with urlopen(Request(self.url, headers=headers), timeout=30) as response:
            if response.status != 206:
                raise OSError("El servidor ignoró Range; se aborta sin leer el cuerpo")
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if not match or int(match[1]) != start or int(match[2]) != end:
                raise OSError("Content-Range no coincide con el rango solicitado")
            identity = (response.headers.get("ETag"), response.headers.get("Last-Modified"), int(match[3]))
            if self.identity and identity != self.identity:
                raise OSError("El archivo remoto cambió durante la lectura")
            self.identity = identity
            self.size = int(match[3])
            if int(response.headers.get("Content-Length", -1)) != length:
                raise OSError("Longitud HTTP inesperada")
            data = response.read(length)
            self.budget.received += len(data)
            if len(data) != length:
                raise OSError("Respuesta HTTP incompleta")
        self.budget.requests.append({"url": self.url, "start": start, "stop": end,
                                     "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.cache[index] = data
        return data

    def open(self, path=None, mode="rb"):
        if path is not None and str(path).replace("\\", "/").rsplit("/", 1)[-1] != self.name:
            raise FileNotFoundError(path)
        if mode not in ("r", "rb"):
            raise ValueError("Sólo lectura")
        return RangeReader(self)

    def manifest(self):
        return {"url": self.url, "size_bytes": self.size, "etag": self.identity[0],
                "last_modified": self.identity[1], "checksum_scope": "retrieved_ranges_only",
                "ranges": [item for item in self.budget.requests if item["url"] == self.url]}


class RangeReader(io.RawIOBase):
    def __init__(self, source):
        super().__init__()
        self.source = source
        self.position = 0
        self.name = source.name

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=0):
        self._checkClosed()
        position = offset + (self.position if whence == 1 else self.source.size if whence == 2 else 0)
        if whence not in (0, 1, 2) or position < 0:
            raise ValueError("seek inválido")
        self.position = position
        return position

    def read(self, size=-1):
        self._checkClosed()
        remaining = max(0, self.source.size - self.position)
        size = remaining if size < 0 else min(size, remaining)
        if size > self.source.budget.limit:
            raise OSError("Lectura masiva bloqueada")
        chunks = []
        while size:
            index, offset = divmod(self.position, self.source.block_size)
            data = self.source._block(index)[offset:offset + size]
            chunks.append(data)
            self.position += len(data)
            size -= len(data)
        return b"".join(chunks)

    def readinto(self, target):
        data = self.read(len(target))
        target[:len(data)] = data
        return len(data)
