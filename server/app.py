import sys
import os
import getopt
import urllib2
import json
import re
import hashlib
import datetime
import logging
import re
from ConfigParser import ConfigParser
from xenforo import XenForo
from logging.handlers import SysLogHandler
from BeautifulSoup import BeautifulSoup    as bsoup
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (Table, Column, Integer, String, DateTime, Date, 
                        ForeignKey, Text, Boolean, create_engine, MetaData, 
                        and_)
from sqlalchemy.orm import relationship, backref, sessionmaker
from bottle import (route, run, debug, template, request, default_app, 
                    redirect, static_file)

#### CONFIGURATION AND PRE-PROCESSING
# The script has to run from the location on disk that it lives.
os.chdir(os.path.dirname(__file__))

# Next we need to load the configuration file into memory.
config = ConfigParser()
config.read('config.ini')

# This is a list of the IP addresses allowed to run the repo generation.
allowed_hosts = config.get('Settings','allowed_hosts').split(',')

# Now we setup the logging
LOG_FORMAT = logging.Formatter('%(name)s: %(levelname)s %(message)s')
#LOG_FILE = logging.FileHandler(config.get('Settings', 'log_file'))
#LOG_FILE.setFormatter(LOG_FORMAT)
SYSLOG = SysLogHandler(address='/dev/log')
SYSLOG.setFormatter(LOG_FORMAT)
log = logging.getLogger('bukget')
log.setLevel(logging.INFO)
log.addHandler(SYSLOG)

# Now we can attach to the database.
engine = create_engine(config.get('Settings', 'db_string'))
Session = sessionmaker(bind=engine)

# Here we declare Base, as it will be used to declaritively define the 
# database with SQLAlchemy.
Base = declarative_base()
#### END CONFIGURATION AND PRE-PROCESSING

## These are still in dev and are not used for now...
# class Plugin(Base):
#   '''
#   Base class to define plugins.
#   '''
#   __tablename__ = 'plugin'
#   id            = Column(Integer(8), primary_key=True)
#   name          = Column(String(32))
#   description   = Column(Text)
#   website       = Column(String(128))
#   authors       = relationship('AuthorRT',  backref='plugins')
#   categories    = relationship('CatRT',     backref='plugins')
#   version       = relationship('Version',   backref='plugin')
# Plugin.metadata.create_all(engine)
# 
# class Version(Base):
#   '''
#   Base class for a plugin version.
#   '''
#   __tablename__ = 'version'
#   id            = Column(Integer(8), primary_key=True)
#   plugin_id     = Column(String(32), ForeignKey('plugins.id'))
#   version       = Column(String(10))
#   checksum      = Column(String(32))
#   branch        = Column(String(10))
#   bukkit_min    = Column(Integer(6))
#   bukkit_max    = Column(Integer(6))
#   dependencies  = relationship('Dependency', backref='dependents')
#   conflictions  = relationship('Conflict', backref='conflictors')
# Version.metadata.create_all(engine)
# 
# 
# class Category(Base):
#   __tablename__ = 'category'
#   id            = Column(Integer(8), primary_key=True)
#   name          = Column(String(16))
#   plugins       = relationship('CatRT', backref='categories')
# Category.metadata.create_all(engine)
# 
# class User(Base):
#   '''
#   Base class for users.
#   '''
#   __tablename__ = 'user'
#   id            = Column(Integer(8), primary_key=True)
#   name          = Column(String(32))
#   key           = Column(String(32))
#   email         = Column(String(64))
#   plugins       = relationship('AuthorRT', backref='authors')
# User.metadata.create_all(engine)
# 
# class AuthorRT(Base):
#   '''
#   Relational table for Authors.
#   '''
#   __tablename__ = 'author_rt'
#   user_id       = Column(Integer(8), ForeignKey('user.id'), primary_key=True)
#   plugin_id     = Column(Integer(8), ForeignKey('plugin.id'), primary_key=True)
# AuthorRT.metadata.create_all(engine)
# 
# class CatRT(Base):
#   '''
#   Relational Table for Categories.
#   '''
#   __tablename__ = 'cat_rt'
#   category_id   = Column(Integer(8), ForeignKey('category.id'), primary_key=True)
#   plugin_id     = Column(Integer(8), ForeignKey('plugin.id'), primary_key=True)
# CatRT.metadata.create_all(engine)
# 
# class Dependency(Base):
#   '''
#   Dependency class to link dependencies back to other plugins.
#   '''
#   __tablename__ = 'dependency'
#   id            = Column(Integer(8), primary_key=True)
#   plugin_id     = Column(Integer(8), ForeignKey('plugin.id'), primary_key=True)
#   dependent_id  = Column(Integer(8), ForeignKey('version.id'), primary_key=True)
#   restrictions  = Column(Text)
#   hard          = Column(Boolean)
# Dependency.metadata.create_all(engine)
# 
# class Conflict(Base):
#   '''
#   Conflict class to link conflicting plugins together.
#   '''
#   __tablename__ = 'conflict'
#   id            = Column(Integer(8), primary_key=True)
#   plugin_id     = Column(Integer(8), ForeignKey('plugin.id'), primary_key=True)
#   conflictor_id = Column(Integer(8), ForeignKey('version.id'), primary_key=True)
#   restrictions  = Column(Text)
# Conflict.metadata.create_all(engine)

class NewsArticle(Base):
  '''
  News article class for the site.
  '''
  __tablename__ = 'news'
  id    = Column(Integer(8), primary_key=True)
  title = Column(String(128))
  date  = Column(DateTime)
  data  = Column(Text)
NewsArticle.metadata.create_all(engine)

class Repository(Base):
  __tablename__ = 'repository'
  id          = Column(Integer(6), primary_key=True)
  maintainer  = Column(String(32))
  email       = Column(String(128))
  url         = Column(Text)
  plugin      = Column(String(32))
  cache       = Column(Text)
  activated   = Column(Boolean)
  hash        = Column(String(32))
  created     = Column(DateTime)
  
  def __init__(self, plugin, maintainer, email, url):
    self.plugin     = plugin
    self.maintainer = maintainer
    self.email      = email
    self.url        = url
    self.created    = datetime.datetime.now()
  
  def _valid(self, d):
    '''
    This function will check to see if the dictionary that we were given is
    valid and usable to import all the information we need.
    '''
    # before we start its worth noting that we will be stepping through all
    # of the definitions that should exist within the json dictionary.  If
    # there are any missing items or malformed items, we should be returning
    # false.  If everything does check out, then True should be returned.
    if 'name' not in d: return False
    if not isinstance(d['name'], unicode): return False
    if 'authors' not in d: return False
    if not isinstance(d['authors'], list): return False
    if 'maintainer' not in d: return False
    if not isinstance(d['maintainer'], unicode): return False
    if 'description' not in d: return False
    if not isinstance(d['description'], unicode): return False
    if 'website' not in d: return False
    if not isinstance(d['website'], unicode): return False
    if 'categories' not in d: return False
    if not isinstance(d['categories'], list): return False
    if 'versions' not in d: return False
    if not isinstance(d['versions'], list): return False
    for v in d['versions']:
      if 'version' not in v: return False
      if not isinstance(v['version'], unicode): return False
      if 'required_dependencies' not in v: return False
      if not isinstance(v['required_dependencies'], list): return False
      if 'optional_dependencies' not in v: return False
      if not isinstance(v['optional_dependencies'], list): return False
      if 'conflicts' not in v: return False
      if not isinstance(v['conflicts'], list): return False
      if 'location' not in v: return False
      if not isinstance(v['location'], unicode): return False
      if 'checksum' not in v: return False
      if not isinstance(v['checksum'], unicode): return False
      if 'branch' not in v: return False
      if not isinstance(v['branch'], unicode): return False
      if v['branch'] not in ['stable','test','dev']: return False
      if 'bukkit_min' not in v: return False
      if not isinstance(v['bukkit_min'], int): return False
      if 'bukkit_max' not in v: return False
      if not isinstance(v['bukkit_max'], int): return False
      if not v['bukkit_min'] <= v['bukkit_max']: return False
    
    # If we made it all the way here, then it looks to be a valid dictionary!
    return True
  
  def update(self):
    '''
    Updates the json dictionary cache stored in the database.
    '''
    try:
      newd = urllib2.urlopen(self.url).read()
      d = json.loads(newd)
    except:
      log.error('Could not read from %s\'s package.json' % self.plugin)
      return False
    if not self._valid(d):
      log.error('%s\'s remote package.json does not appear to be valid.' % self.plugin)
      return False
    
    # New we are going to compare the newly downloaded data to the one we have
    # in the cache.  if the 2 don't match, then we will update the cache with
    # the newer information.
    cur = hashlib.md5()
    cur.update(str(self.cache))
    new = hashlib.md5()
    new.update(newd)
    if new.hexdigest() != cur.hexdigest():
      self.cache = newd
      log.info('Updated %s\'s local package.json' % self.plugin)
      return True
    else:
      return False
  
  def activate(self):
    '''
    Activates the repository so that it can be used by the bukget clients.
    '''
    rname = re.compile(r'^(?:\[.+?\]){0,1}\s{0,1}(\w+[^ ])')
    check_ok = False
    
    # First we need to pull the json database from bukkit and parse it into
    # a native dictionary.  If this fails then throw an error and log the
    # problem.
    try:
      bukkit = urllib2.urlopen('http://plugins.bukkit.org/data.php').read()
      bktdata = json.loads(bukkit)
    except:
      log.error('Could not contact Bukkit\'s plugin dictionary.')
      return False
    for plugin in bktdata:
      name = rname.findall(plugin['title'])
      if isinstance(name, list):
        if name[0].lower() == self.plugin.lower():
          if plugin['author'].lower() == self.maintainer.lower():
            log.info('Found entry')
            check_ok = True
    log.info('check_ok is %s' % check_ok)
    if check_ok:
      forum = XenForo(config.get('Forum', 'username'), 
                      config.get('Forum', 'password'),
                      config.get('Forum', 'hostname'))
      if forum.login():
        md5 = hashlib.md5()
        md5.update(self.plugin + datetime.datetime.now().ctime())
        self.hash = md5.hexdigest()
        forum.private_message(self.maintainer,
                              'BukGet Plugin Repo Activation',
                              template('bukkit_activation', 
                                       user=self.maintainer,
                                       plugin=self.plugin, 
                                       hash=self.hash), 
                              locked=True)
      return True
    return False
Repository.metadata.create_all(engine)
    


@route('/')
@route('/index.html')
def home_page():
  s = Session()
  news = s.query(NewsArticle).all()
  return template('home_page', news=news)

@route('/add', method='GET')
@route('/add', method='POST')
def add_repo():
  errors = []
  notes = []
  s = Session()
  
  if request.GET.get('hash','').strip():
    # If re received an activation field, then we will need to parse it out
    # and compare it to what we have on file.
    act = request.GET.get('hash','').strip()
    name = request.GET.get('plugin','').strip()
    try:
      repo = s.query(Repository).filter_by(plugin=name).one()
    except:
      errors.append('Activation Failed.  Could not find repository record.')
    else:
      if repo.hash == act:
        repo.activated = True
        s.merge(repo)
        s.commit()
        notes.append('Activation Successful!')
        log.info('%s is now  active and will be cached next generation cycle.' % name)
      else:
        errors.append('Activation Failed.  Activation Hash did not match.')
    
  elif request.POST.get('add','').strip():
    # If the data was posted to the page, then we need to parse out the
    # relevent data, try to match the maintainer to the one that si on the
    # bukkit forums, and lastly send an activation request.
    user = request.POST.get('user','').strip()
    url = request.POST.get('url','').strip()
    email = request.POST.get('email','').strip()
    name = request.POST.get('plugin','').strip()
    
    # Now we need to validate all the data we have to make sure it's ok before
    # continue.  First we will define the regexes that we will use to
    # validate the fields then check to make sure that they get exactly 1
    # response back from each of them.  If we don't, then we need to tell
    # the user what failed and allow them to fix their input.
    remail = re.compile(r'^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,4}$')
    rurl = re.compile(r'^(?:http|https|ftp)\://[a-zA-Z0-9\-\./\?\=\;\%]+')
    ruser = re.compile(r'^[A-Za-z0-9\_\.]+$')
    rname = re.compile(r'^[A-Za-z0-9\_]+$')
    
    if len(remail.findall(email)) <> 1:
      errors.append('Not a Valid Email Address.')
    if len(rurl.findall(url)) <> 1:
      errors.append('Not a Valid URL.')
    if len(ruser.findall(user)) <> 1:
      errors.append('Not a Valid Username')
    if len(rname.findall(name)) <> 1:
      errors.append('Not a Valid Plugin Name')
    if len(s.query(Repository).filter_by(plugin=name).all()) > 0:
      errors.append('Plugin Name Already Exists.')
    
    if len(errors) == 0:
      # If there are no errors, then we will try to activate the repository
      # that was defined.
      new_repo = Repository(name, user, email, url)
      if new_repo.activate():
        notes.append('Please check your Bukkit.org account for ' +\
                     'activation message.  If you havent received one, ' +\
                     'please contact us.')
        s.add(new_repo)
        s.commit()
      else:
        errors.append('We were unable to send your Bukkit.org account the ' +\
                      'activation message.  If this issue continues please '+\
                      'notify us of the issue.')
  s.close()
  return template('add_repository', notes=notes, errors=errors)

@route('/log')
def display_logs():
  logfile = open(config.get('Settings', 'log_file'), 'r')
  logdata = logfile.read()
  logfile.close()
  return template('display_logs', logdata=logdata)

@route('/code')
def github_redirect():
  redirect('https://github.com/SteveMcGrath/bukget')

@route('/repo.json')
def get_repo_file():
  return static_file('repo.json', config.get('Settings','static_files'))

@route('/help')
def help_page():
  return template('help_page')

@route('/generate')
def generate_repository():
  '''
  Generates the master repository file.
  '''
  if request.environ.get('REMOTE_ADDR') in allowed_hosts:
    s = Session()
    rdict = []
    repos = s.query(Repository).filter_by(activated=True).all()
    for repo in repos:
      if repo.update():
        s.merge(repo)
        s.commit()
      if repo.cache is not None:
        rdict.append(json.loads(repo.cache))
    rfile = open(os.path.join(\
                 config.get('Settings', 'static_files'),'repo.json'), 'w')
    rfile.write(json.dumps(rdict))
    rfile.close()
    return '{"plugins": %s}' % len(repos)
  return '{"error": "Not an allowed address"}'

# And here we set everything up for Apache to understand what to do with this
# mess of code ;)
debug(True)
application = default_app()