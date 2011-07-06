import json
import datetime
import re
import bukkit
from config import Config
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (Table, Column, Integer, String, DateTime, Date, 
                        ForeignKey, Text, Boolean, create_engine, MetaData,
                        and_, desc)
from sqlalchemy.orm import relationship, backref

config = Config()
Base = declarative_base()

def create_all(engine):
  '''Will create the tables if needed.'''
  Plugin.metadata.create_all(engine)
  Version.metadata.create_all(engine)
  Engine.metadata.create_all(engine)
  Users.metadata.create_all(engine)

class Plugin(Base):
  __tablename__ = 'plugins'
  id            = Column(Integer(8), primary_key=True)
  name          = Column(String(32))
  active        = Column(Boolean)
  maintainer_id = Column(Integer, ForeignKey('users.id'))
  authors       = Column(Text)
  description   = Column(Text)
  website       = Column(String(128))
  categories    = Column(Text)
  versions      = relationship('Version', backref='plugin')
  maintainer    = relationship('User', backref='plugins')
  
  def __init__(self, name, user_id, authors, description, website, catagories):
    self.name = name
    self.authors = authors
    self.description = description
    self.website = website
    self.maintainer_id = user_id
    self.update_categories(categories)
  
  def in_category(self, name):
    cats = self.categories.split(', ')
    return name in cats:
  
  def get_categories(self):
    return self.categories.split(', ')
  
  def update_categories(self, categories):
    self.categories = ', '.join(categories)
  
  def in_bukkit_org(self):
    rname = re.compile(r'^(?:\[.+?\]){0,1}\s{0,1}(\w+[^ ])')
    api = bukkit.BukkitDB()
    data = api.get_data()['realdata']
    for plugin in data:
      name = rname.findall(plugin['title'])
      if isinstance(name, list):
        if len(name) > 0:
          if name[0].lower() == self.plugin.lower():
            if plugin['author'].lower() == self.maintainer.name.lower():
              return True
    return False

class Version(Base):
  __tablename__ = 'versions'
  id            = Column(Integer(8), primary_key=True)
  plugin_id     = Column(Integer(8), ForeignKey('plugins.id'))
  version       = Column(String(15))
  url           = Column(String(128))
  hash          = Column(String(32))
  branch        = Column(String(10))
  warning       = Column(Text)
  notification  = Column(Text)
  engines       = relationship('Engine', backref='version')
  conflicts     = Column(Text)
  optional_deps = Column(Text)
  required_deps = Column(Text)
  
  def __init__(self, version, plugin_id, url, hash, branch,
               optional_deps=[], required_deps=[], conflicts=[], warning=None,
               notification=None):
    self.version = version
    self.plugin_id = plugin_id
    self.url = url
    self.hash = hash
    self.branch = branch
    self.warning = warning
    self.notification = notification
    self.update_conflicts(conflicts)
    self.update_required_deps(required_deps)
    self.update_optional_deps(optional_deps)
  
  def update_conflicts(self, conflicts):
    self.conflicts = ', '.join(conflicts)
  
  def update_required_deps(self, dependencies):
    self.required_deps = ', '.join(dependencies)
  
  def update_optional_deps(self, dependencies):
    self.optional_deps = ', '.join(dependencies)
  
  def get_required_deps(self):
    return self.required_deps.split(', ')
  
  def get_optional_deps(self):
    return self.optional_deps.split(', ')
  
  def get_conflicts(self):
    return self.conflicts.split(', ')
  
  def in_required_deps(self, dependency):
    deps = self.get_required_deps()
    return dependency in deps
  
  def in_optional_deps(self, dependency):
    deps = self.optional_deps.split(', ')
    return dependenty in deps
  
  def in_conflicts(self, conflict):
    cons = self.conflicts.split(', ')
    return conflict in cons
  
  


class Engine(Base):
  __tablename__ = 'engines'
  id            = Column(Integer(8), primary_key=True)
  version_id    = Column(Integer(8), ForeignKey('versions.id'))
  engine        = Column(String(15))
  build_min     = Column(Integer(5))
  build_max     = Column(Integer(5))