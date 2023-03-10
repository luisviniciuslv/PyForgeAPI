from http.server import BaseHTTPRequestHandler
from http.cookies import SimpleCookie

from PyForgeAPI.constants.content_type import CONTENT_TYPES

from PyForgeAPI.exceptions.file import FileException
from PyForgeAPI.exceptions.response import ResponseException

import mimetypes
import os
import json
import io

class Response:
  def __init__(self, request: BaseHTTPRequestHandler):
    self._request               = request
    self._status_code           = 200
    self._response              = None
    self._request.response_sent = False
    self._headers               = {}
    self._cookies               = SimpleCookie()

  def status(self, code: int) -> 'Response':
    self._status_code = code
    return self
  
  def json(self, response: dict) -> 'Response':
    self._response = json.dumps(response)
    self.content_type = 'application/json'
    return self
  
  def text(self, response: str) -> 'Response':
    self._response = response
    self.content_type = 'text/plain'
    return self
  
  def cookie(
    self,
    name: str,
    value: str,
    path="/",
    expires=None,
    domain: str = None,
    secure: bool = False,
    httponly: bool = False
  ) -> 'Response':
    self._cookies[name] = value
    self._cookies[name]['path'] = path
    self._cookies[name]['secure'] = secure
    self._cookies[name]['httponly'] = httponly
    if expires is not None:
      self._cookies[name]['expires'] = expires
    if domain is not None:
      self._cookies[name]['domain'] = domain
    return self
    
  def _send_archive(self, path: str = None) -> None:
    self.content_type = self._get_content_type(path)

    try:
      with io.open(path, 'rb') as file:
        self._response = file.read()
    except FileNotFoundError:
      self.send_status(404)
      return
      
    self.send()

  def send_file(self, path: str) -> 'Response':
    try:
      with io.open(path, 'rb') as file:
        file_size = os.path.getsize(path)
        content_type = self._get_content_type(path)
        self._request.send_response(200)
        self._request.send_header('Content-type', content_type)
        self._request.send_header('Content-Disposition', f'attachment; filename="{path.split("/")[-1]}"')
        self._request.send_header('Content-Length', file_size)
        self._request.end_headers()
        self._request.wfile.write(file.read())
        self._request.response_sent = True
    except FileNotFoundError:
      raise FileException(f'File not found: Path "{path}"')

  def render_page(self, path: str) -> 'Response':
    if not path.endswith('.html'):
      raise FileException('The path must lead to an HTML file')

    if self._request.static_path:
      path = f"{self._request.static_path}/{path}"

    with io.open(f"{path}", 'r') as file:
      self._response = file.read()
    self.content_type = 'text/html'
    return self

  def html(self, response: str) -> 'Response':
    self._response = response
    self.content_type = 'text/html'
    return self
  
  def header(self, name: str, value) -> 'Response':
    self._headers[name] = value
    return self
  
  def send_status(self, code: int) -> None:
    if self._request.response_sent:
      raise ResponseException('Response already sent')
    self._request.send_response(code)
    self._request.end_headers()
    self._request.response_sent = True

  def send_cookies(self) -> None:
    if self._request.response_sent:
      raise ResponseException('Response already sent')
    if self._status_code is None:
      raise ResponseException('Status code is not set')
    
    self._request.send_response(self._status_code)

    for cookie in self._cookies.values():
      self._request.send_header("Set-Cookie", cookie.OutputString())
    
    self._request.end_headers()
    self._request.response_sent = True

  def send(self) -> None:
    if self._request.response_sent:
      raise ResponseException('Response already sent')
    if self._status_code is None:
      raise ResponseException('Status code is not set')
    if self._response is None:
      raise ResponseException('Response is not set')

    self._request.send_response(self._status_code)
    self._request.send_header('Content-type', self.content_type)
    for name, value in self._headers.items():
      self._request.send_header(name, value)
    for cookie in self._cookies.values():
      self._request.send_header("Set-Cookie", cookie.OutputString())

    self._request.end_headers()

    try:
      self._request.wfile.write(self._response.encode())
    except AttributeError:
      self._request.wfile.write(self._response)
      
    self._request.response_sent = True

  def _get_content_type(self, path: str) -> str:
    try:
      content_type = CONTENT_TYPES[path.split('/')[-1].split('.')[-1]]
    except:
      content_type = mimetypes.guess_type(path)[0]

    return content_type or 'application/octet-stream'