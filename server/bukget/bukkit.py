import httplib
import json

class BukkitDB(object):
  host = 'plugins.bukkit.org'
  
  def _post(self, url, payload):
    headers = {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Content-Length': len(payload),
      'X-Requested-With': 'XMLHttpRequest',
    }
    
    http = httplib.HTTPConnection(self.host)
    http.request('POST', url, body=payload, headers=headers)
    resp = http.getresponse()
    return resp.read()
  
  def get_data(self):
    query_data = {
     'j': 685763,
     'title': '',
     'tag': 'all',
     'author': '',
     'inc_submissions': 'false',
     'pageno': 1
    }
    form_data = '='
    db = self._post('/data.php?%s' % urllib.urlencode(query_data), form_data)
    return json.loads(db)