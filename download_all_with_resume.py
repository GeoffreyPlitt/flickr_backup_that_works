# Note: The Flickr function results are cached (memcache), so if you make changes to your Flickr
#  account, like adding photos or changing sets and stuff, you need to clear memcache.

import sys
import os
import pprint
import code

import flickrapi
import simplejson as json
import requests
import memcache

#-------- CONST
CONSOLE_WIDTH = '200'

CHUNK_SIZE=4096
PREFIX = 'DOWNLOADED/'

#------- INIT

def get_cached_or_ask(prompt, fn):
  if os.path.exists(fn):
    ret = open(fn, 'rt').read()
  else:
    ret = raw_input(prompt+': ')
    f = open(fn, 'wt')
    f.write(ret)
    f.close()
  return ret

api_key = get_cached_or_ask('Your Flickr API Key', '.flickr_api_key')
api_secret = get_cached_or_ask('Your Flickr API Secret', '.flickr_api_secret')

flickr = flickrapi.FlickrAPI(api_key, api_secret, format='json')

#------- AUTH
os.environ['BROWSER']='echo' # disable opening browsers
print 'If an auth link appears below, enter it in a browser.'
print ''
(token, frob) = flickr.get_token_part_one(perms='read')
if not token:
  raw_input("Press ENTER after you authorized this program")
flickr.get_token_part_two((token, frob))

#------- HELPERS
def jsonp_to_obj(the_jsonp):
  the_json = the_jsonp[ the_jsonp.index("(")+1 : the_jsonp.rindex(")") ]
  the_obj = json.loads(the_json)
  return the_obj

def clean_filename(fn):
  ret = fn
  ret = ret.replace(' ','_')  
  ret = ret.replace('/','-slash-')
  return ret

#------- MEMCACHE
import memcache
from urllib import quote_plus

memcache_client = None
def init_memcache_client():
  endpoints = ['localhost:11211']
  mc = memcache.Client(endpoints, debug=0)
  if len(mc.get_stats())<1:
    print endpoints
    raise Exception("ERROR: memcache servers not found.")
  return mc

memcache_client = init_memcache_client()

def _cache_key(func, args, kwargs):
  ret = 'memoize_in_memcache__%s_%s_%s_%s' % (func.__module__, func.__name__, str(args), str(kwargs))
  ret = quote_plus(ret)
  # print 'CACHE KEY: %s' % ret
  return ret

class memoized_in_memcache(object):
   """Cached until caches are cleared
   """
   def __init__(self, func):
      self.func = func
      self.cache = {}
   def __call__(self, *args):
      ck = self.func.__name__ + str(args)
      ck = ck.replace(' ','_') # memcache can't do spaces
      # print 'GP1: %s' % ck
      cached_results = memcache_client.get(ck)
      if cached_results:
        return cached_results
      else:
         value = self.func(*args)
         memcache_client.set(ck, value)
         return value

   def __repr__(self):
      """Return the function's docstring."""
      return self.func.__doc__




#------- API FUNCTIONS

@memoized_in_memcache
def get_all_sets(user_id):
  """Returns a list of (id, name) pairs."""
  def helper():
    page_num = 1
    while True:
      obj = jsonp_to_obj(flickr.photosets_getList(user_id=user_id, page=page_num))
      for x in obj['photosets']['photoset']:
        yield (x['id'], x['title']['_content']) 
      if page_num == obj['photosets']['pages']:
        break
      page_num+=1

  return list(helper())

@memoized_in_memcache
def get_photos_not_in_a_set():
  def helper():
    page_num = 1
    while True:
      obj = jsonp_to_obj(flickr.photos_getNotInSet(page=page_num))
      for x in obj['photos']['photo']:
        yield (x['id'], x['title']) 
      if page_num == obj['photos']['pages']:
        break
      page_num+=1

  return list(helper())

@memoized_in_memcache
def get_photos_in_set(set_id):
  def helper():
    page_num = 1
    while True:
      obj = jsonp_to_obj(flickr.photosets_getPhotos(photoset_id=set_id, page=page_num))
      for x in obj['photoset']['photo']:
        yield (x['id'], x['title']) 
      if page_num == obj['photoset']['pages']:
        break
      page_num+=1

  return list(helper())

@memoized_in_memcache
def get_original_url(photo_id):
  sizes_obj = jsonp_to_obj(flickr.photos_getSizes(photo_id=photo_id))
  rets = [x['source'] for x in sizes_obj['sizes']['size'] if x['label']=='Original']
  return rets[0]

def get_my_user_id():
  return jsonp_to_obj(flickr.urls_getUserProfile())['user']['nsid']

def get_extension_from_url(url):
  _, ext = os.path.splitext(url)
  return ext

def download_url_to_local(url, fn):
  r = requests.get(url)
  if r.status_code != 200:
    raise Exception(r.status_code + ' ' + url)
  # else  
  with open(fn, 'wb') as f:
    i = 0
    for chunk in r.iter_content(CHUNK_SIZE):
      i += 1
      f.write(chunk)
      if i % 10 == 0:
        sys.stdout.write('.')
        sys.stdout.flush()
    f.close()


def walk_all_sets_and_photos():
  """Generator that walks all sets/photos and yields
       (set_id, set_name, photo_id, photo_name, photo_orig_url) tuples.
  """
  # photos not in sets. The set_id will be -1, and the set_name will be "__NO_SET__"
  for (photo_id, photo_name) in get_photos_not_in_a_set():
    photo_orig_url = get_original_url(photo_id)
    ret = (-1, '__NO_SET__', photo_id, photo_name, photo_orig_url)
    yield ret
  # photos in sets
  for (set_id, set_name) in get_all_sets(get_my_user_id()):
    for (photo_id, photo_name) in get_photos_in_set(set_id):
      photo_orig_url = get_original_url(photo_id)
      ret = (set_id, set_name, photo_id, photo_name, photo_orig_url)
      yield ret

def download_all_sets_and_photos_with_resume():
  if not os.path.isdir(PREFIX):
    os.mkdir(PREFIX)

  seen = {}
  last_set_id = None
  for (set_id, set_name, photo_id, photo_name, photo_orig_url) in walk_all_sets_and_photos():
    if last_set_id != set_id: # new set
      clean_set = clean_filename(set_name)
      print 'SET(name="%s", id=%s)' % (clean_set, set_id)
      if not os.path.isdir(PREFIX + clean_set):
        os.mkdir(PREFIX + clean_set)
      duplicate_handling = 0


    ext = get_extension_from_url(photo_orig_url)
    clean_photo = '%s%s' % (clean_filename(photo_name), ext)

    key = set_name + '/' + clean_photo
    if key in seen:
      # DUPLICATE - make new clean_photo
      duplicate_handling += 1
      clean_photo = '%s_DUPLICATE_%s%s' % (clean_filename(photo_name), duplicate_handling, ext)
      key = set_name + '/' + clean_photo
      seen[key] = photo_id
    else:
      seen[key] = photo_id

    photo_path = '%s/%s' % (clean_set, clean_photo)
    photo_exists = os.path.exists(PREFIX + photo_path)
    status = 'Exists' if photo_exists else 'Downloading'
    print '     PHOTO(name="%s", id=%s) %s' %(clean_photo, photo_id, status),
    if not photo_exists:
      download_url_to_local(photo_orig_url, PREFIX + photo_path)
    print ''

    last_set_id = set_id

def report_duplicate_name_problems():
  seen = {}
  for (set_id, set_name, photo_id, photo_name, photo_orig_url) in walk_all_sets_and_photos():
    key = set_name + '/' + photo_name
    if key in seen:
      print 'DUPLICATE(%s / %s): %s' % (photo_id, seen[key], key)
    else:
      seen[key] = photo_id

if __name__=='__main__':
  download_all_sets_and_photos_with_resume()
  #report_duplicate_name_problems()